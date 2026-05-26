from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .db import connect, now_iso, row_to_dict, rows_to_dicts

CHANNEL_TYPES = {"telegram", "webhook", "email"}


def list_channels() -> list[dict[str, Any]]:
    with connect() as conn:
        channels = rows_to_dicts(
            conn.execute(
                """
                SELECT id, name, type, enabled, config_json, last_error,
                       last_sent_at, created_at, updated_at
                FROM notification_channels
                ORDER BY enabled DESC, id DESC
                """
            ).fetchall()
        )
    return [public_channel(channel) for channel in channels]


def create_channel(payload: dict[str, Any]) -> dict[str, Any]:
    data = normalize_channel_payload(payload)
    ts = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notification_channels (
                name, type, enabled, config_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["type"],
                data["enabled"],
                json.dumps(data["config"], ensure_ascii=False),
                ts,
                ts,
            ),
        )
        channel_id = cursor.lastrowid
    return get_channel(channel_id)


def update_channel(channel_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Update an existing notification channel, preserving secrets if needed."""
    with connect() as conn:
        existing = row_to_dict(
            conn.execute(
                "SELECT * FROM notification_channels WHERE id = ?",
                (channel_id,),
            ).fetchone()
        )
    if not existing:
        raise ValueError("Notification channel not found.")

    existing_config = parse_config(existing)
    data = normalize_channel_payload(payload)

    if existing["type"] == data["type"]:
        # Preserve existing secrets if placeholders are used
        if data["type"] == "telegram" and is_secret_placeholder(data["config"].get("bot_token")):
            data["config"]["bot_token"] = existing_config.get("bot_token", "")
        if data["type"] == "webhook" and is_secret_placeholder(data["config"].get("secret")):
            data["config"]["secret"] = existing_config.get("secret", "")

    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            UPDATE notification_channels
            SET name = ?, type = ?, enabled = ?, config_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                data["name"],
                data["type"],
                data["enabled"],
                json.dumps(data["config"], ensure_ascii=False),
                ts,
                channel_id,
            ),
        )
    return get_channel(channel_id)


def delete_channel(channel_id: int) -> None:
    get_channel(channel_id)
    with connect() as conn:
        conn.execute("DELETE FROM notification_channels WHERE id = ?", (channel_id,))


def get_channel(channel_id: int) -> dict[str, Any]:
    with connect() as conn:
        channel = row_to_dict(
            conn.execute(
                """
                SELECT id, name, type, enabled, config_json, last_error,
                       last_sent_at, created_at, updated_at
                FROM notification_channels
                WHERE id = ?
                """,
                (channel_id,),
            ).fetchone()
        )
    if not channel:
        raise ValueError("Notification channel not found.")
    return public_channel(channel)


def send_test_notification(channel_id: int) -> dict[str, Any]:
    """Send a test message to verify the channel configuration."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM notification_channels WHERE id = ?", (channel_id,)).fetchone()
        if not row:
            raise ValueError("Notification channel not found.")
        channel = row_to_dict(row) or {}
        try:
            send_channel_message(
                channel,
                "Veltrix test notification\nThis channel is ready to receive incident updates.",
                {
                    "event": "test",
                    "product": "Veltrix",
                    "channel_id": channel_id,
                    "sent_at": now_iso(),
                },
            )
            mark_channel_success(conn, channel_id)
            return {"ok": True, "channel": public_channel(channel)}
        except Exception as exc:
            mark_channel_error(conn, channel_id, str(exc))
            raise


def dispatch_incident_event(conn: Any, incident_id: int, event_type: str) -> None:
    """Dispatch notifications to all enabled channels for an incident event."""
    if os.getenv("OUTPANEL_DISABLE_NOTIFICATIONS", "") == "1":
        return
    incident = fetch_incident_for_notification(conn, incident_id)
    if not incident:
        return
    channels = rows_to_dicts(conn.execute("SELECT * FROM notification_channels WHERE enabled = 1 ORDER BY id").fetchall())
    for channel in channels:
        existing = conn.execute(
            """
            SELECT id FROM notification_deliveries
            WHERE channel_id = ? AND incident_id = ? AND event_type = ?
            """,
            (channel["id"], incident_id, event_type),
        ).fetchone()
        if existing:
            continue

        ts = now_iso()
        try:
            send_channel_message(channel, format_incident_message(incident, event_type),
                                 build_incident_payload(incident, event_type))
            conn.execute(
                """
                INSERT INTO notification_deliveries (
                    channel_id, incident_id, event_type, status, created_at
                )
                VALUES (?, ?, ?, 'sent', ?)
                """,
                (channel["id"], incident_id, event_type, ts),
            )
            mark_channel_success(conn, channel["id"], ts)
        except Exception as exc:
            error = str(exc)[:500]
            conn.execute(
                """
                INSERT OR IGNORE INTO notification_deliveries (
                    channel_id, incident_id, event_type, status, error, created_at
                )
                VALUES (?, ?, ?, 'failed', ?, ?)
                """,
                (channel["id"], incident_id, event_type, error, ts),
            )
            mark_channel_error(conn, channel["id"], error, ts)


def fetch_incident_for_notification(conn: Any, incident_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT incidents.*, servers.name AS server_name, outbounds.remark AS outbound_remark
        FROM incidents
        LEFT JOIN servers ON servers.id = incidents.server_id
        LEFT JOIN outbounds ON outbounds.id = incidents.outbound_id
        WHERE incidents.id = ?
        """,
        (incident_id,),
    ).fetchone()
    return row_to_dict(row)


def send_channel_message(channel: dict[str, Any], text: str, payload: dict[str, Any]) -> None:
    config = parse_config(channel)
    if channel["type"] == "telegram":
        send_telegram(config, text)
        return
    if channel["type"] == "webhook":
        send_webhook(config, payload)
        return
    if channel["type"] == "email":
        send_email_notification(config, text, payload)
        return
    raise ValueError(f"Unsupported channel type: {channel['type']}")


def send_telegram(config: dict[str, Any], text: str) -> None:
    token = str(config.get("bot_token") or "").strip()
    chat_id = str(config.get("chat_id") or "").strip()
    if not token or not chat_id:
        raise ValueError("Telegram bot_token and chat_id are required.")
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if config.get("message_thread_id"):
        payload["message_thread_id"] = int(config["message_thread_id"])
    http_post_json(f"https://api.telegram.org/bot{token}/sendMessage", payload)


def send_webhook(config: dict[str, Any], payload: dict[str, Any]) -> None:
    url = str(config.get("url") or "").strip()
    if not url:
        raise ValueError("Webhook url is required.")
    headers = {"X-Veltrix-Event": str(payload.get("event") or "")}
    secret = str(config.get("secret") or "").strip()
    if secret:
        headers["X-Veltrix-Secret"] = secret
    http_post_json(url, payload, headers=headers)


def send_email_notification(config: dict[str, Any], text: str, payload: dict[str, Any]) -> None:
    """Send notification via email channel."""
    to = str(config.get("to") or "").strip()
    if not to:
        raise ValueError("Email recipient is required.")
    from .email_notifier import send_email, is_email_configured
    if not is_email_configured():
        raise ValueError("SMTP is not configured. Set OUTPANEL_SMTP_HOST in environment.")
    event = payload.get("event", "notification")
    subject = f"[Veltrix] {event}"
    html = f"""
    <div style="font-family:Tahoma,Arial,sans-serif;padding:20px;max-width:600px;">
        <h2 style="color:#058274;">Veltrix Notification</h2>
        <pre style="background:#f5f5f5;padding:16px;border-radius:8px;white-space:pre-wrap;">{text}</pre>
        <p style="color:#999;font-size:11px;margin-top:16px;">Event: {event} | {now_iso()}</p>
    </div>
    """
    send_email(to, subject, html, body_text=text)


def http_post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Accept": "application/json", "Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
            if response.status >= 400:
                raise ValueError(f"HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise ValueError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Delivery failed: {exc.reason}") from exc


def normalize_channel_payload(payload: dict[str, Any]) -> dict[str, Any]:
    channel_type = str(payload.get("type") or "").strip().lower()
    if channel_type not in CHANNEL_TYPES:
        raise ValueError("Notification channel type must be telegram, webhook, or email.")
    name = str(payload.get("name") or channel_type.title()).strip()
    config = payload.get("config") or {}

    if channel_type == "telegram":
        normalized_config = {
            "bot_token": str(config.get("bot_token") or payload.get("bot_token") or "").strip(),
            "chat_id": str(config.get("chat_id") or payload.get("chat_id") or "").strip(),
            "message_thread_id": str(config.get("message_thread_id") or payload.get("message_thread_id") or "").strip(),
        }
        if not normalized_config["bot_token"] or not normalized_config["chat_id"]:
            raise ValueError("Telegram bot_token and chat_id are required.")
    elif channel_type == "email":
        normalized_config = {
            "to": str(config.get("to") or payload.get("to") or "").strip(),
        }
        if not normalized_config["to"]:
            raise ValueError("Email recipient address is required.")
    else:
        normalized_config = {
            "url": str(config.get("url") or payload.get("url") or "").strip(),
            "secret": str(config.get("secret") or payload.get("secret") or "").strip(),
        }
        if not normalized_config["url"]:
            raise ValueError("Webhook url is required.")

    return {"name": name, "type": channel_type, "enabled": 1 if bool(payload.get("enabled", True)) else 0,
            "config": normalized_config}


def public_channel(channel: dict[str, Any]) -> dict[str, Any]:
    data = dict(channel)
    config = parse_config(channel)
    if data.get("type") == "telegram":
        data["config"] = {"bot_token": redact(config.get("bot_token")),
                          "chat_id": config.get("chat_id") or "",
                          "message_thread_id": config.get("message_thread_id") or ""}
    elif data.get("type") == "webhook":
        data["config"] = {"url": config.get("url") or "", "secret": redact(config.get("secret"))}
    data.pop("config_json", None)
    return data


def parse_config(channel: dict[str, Any]) -> dict[str, Any]:
    raw = channel.get("config_json") or "{}"
    try:
        config = json.loads(raw)
    except json.JSONDecodeError:
        config = {}
    return config if isinstance(config, dict) else {}


def mark_channel_success(conn: Any, channel_id: int, ts: str | None = None) -> None:
    timestamp = ts or now_iso()
    conn.execute("UPDATE notification_channels SET last_sent_at = ?, last_error = NULL, updated_at = ? WHERE id = ?",
                 (timestamp, timestamp, channel_id))


def mark_channel_error(conn: Any, channel_id: int, error: str, ts: str | None = None) -> None:
    timestamp = ts or now_iso()
    conn.execute("UPDATE notification_channels SET last_error = ?, updated_at = ? WHERE id = ?",
                 (error[:500], timestamp, channel_id))


def redact(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 8:
        return "****"
    return text[:4] + "..." + text[-4:]


def is_secret_placeholder(value: Any) -> bool:
    text = str(value or "")
    return text in {"keep-existing-token", "keep-existing-secret", "****"} or "..." in text
