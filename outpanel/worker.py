"""Separated monitoring worker for Veltrix.

Can run as a standalone process or as a background thread within the API server.
Handles: monitoring cycles, auto-disable logic, scheduled reports, and SSE events.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connect, now_iso, row_to_dict, rows_to_dicts
from .monitor import monitor_once, ping_outbound, sync_server
from .sse import emit_monitor_cycle, emit_outbound_status, emit_server_status


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AUTO_DISABLE_THRESHOLD = int(os.getenv("OUTPANEL_AUTO_DISABLE_THRESHOLD", "5"))
AUTO_DISABLE_WINDOW_MINUTES = int(os.getenv("OUTPANEL_AUTO_DISABLE_WINDOW", "30"))
SCHEDULED_REPORT_HOUR = int(os.getenv("OUTPANEL_REPORT_HOUR", "8"))  # UTC hour
SCHEDULED_REPORT_DAY = int(os.getenv("OUTPANEL_REPORT_DAY", "0"))  # 0=Monday


# ---------------------------------------------------------------------------
# Enhanced monitor loop with SSE and auto-disable
# ---------------------------------------------------------------------------

def enhanced_monitor_loop(stop_event: threading.Event, interval: int) -> None:
    """Enhanced background monitoring loop with SSE events and auto-disable."""
    last_report_check = time.monotonic()
    report_check_interval = 3600  # Check every hour

    while not stop_event.is_set():
        start = time.perf_counter()
        servers_checked = 0

        try:
            servers_checked = enhanced_monitor_once()
        except Exception:
            pass

        duration_ms = (time.perf_counter() - start) * 1000

        # Emit SSE event
        if servers_checked > 0:
            emit_monitor_cycle(servers_checked, duration_ms)

        # Check for auto-disable
        try:
            check_auto_disable()
        except Exception:
            pass

        # Check for scheduled reports
        if time.monotonic() - last_report_check > report_check_interval:
            last_report_check = time.monotonic()
            try:
                check_scheduled_reports()
            except Exception:
                pass

        stop_event.wait(interval)


def enhanced_monitor_once() -> int:
    """Run a single monitoring cycle with SSE events. Returns number of servers checked."""
    with connect() as conn:
        servers = rows_to_dicts(
            conn.execute("SELECT * FROM servers WHERE enabled = 1 ORDER BY id").fetchall()
        )

    for server in servers:
        try:
            result = sync_server(server["id"])
            emit_server_status(server["id"], result.get("status", "unknown"), {
                "synced": result.get("synced", 0),
                "name": server["name"],
            })
        except Exception:
            emit_server_status(server["id"], "error", {"name": server["name"]})

        # Ping outbounds
        try:
            with connect() as conn:
                outbounds = rows_to_dicts(conn.execute(
                    "SELECT id FROM outbounds WHERE server_id = ? AND enabled = 1",
                    (server["id"],),
                ).fetchall())

            for outbound in outbounds:
                try:
                    result = ping_outbound(outbound["id"])
                    emit_outbound_status(
                        outbound["id"],
                        server["id"],
                        result.get("status", "unknown"),
                        result.get("latency_ms"),
                    )
                except Exception:
                    pass
        except Exception:
            pass

    return len(servers)


# ---------------------------------------------------------------------------
# Auto-disable outbounds after repeated failures
# ---------------------------------------------------------------------------

def check_auto_disable() -> list[dict[str, Any]]:
    """Check outbounds for repeated failures and auto-disable them.

    If an outbound has N consecutive timeout/error results within the window,
    it gets automatically disabled with a note.
    """
    if AUTO_DISABLE_THRESHOLD <= 0:
        return []

    window_start = (
        datetime.now(timezone.utc) - timedelta(minutes=AUTO_DISABLE_WINDOW_MINUTES)
    ).isoformat(timespec="seconds")

    disabled_outbounds: list[dict[str, Any]] = []

    with connect() as conn:
        # Find outbounds with consecutive failures
        candidates = rows_to_dicts(conn.execute("""
            SELECT outbounds.id, outbounds.remark, outbounds.server_id,
                   servers.name as server_name
            FROM outbounds
            JOIN servers ON servers.id = outbounds.server_id
            WHERE outbounds.enabled = 1
              AND outbounds.last_status IN ('timeout', 'error')
              AND servers.enabled = 1
        """).fetchall())

        for candidate in candidates:
            # Count recent consecutive failures
            recent_checks = rows_to_dicts(conn.execute("""
                SELECT status FROM outbound_checks
                WHERE outbound_id = ? AND created_at > ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (candidate["id"], window_start, AUTO_DISABLE_THRESHOLD)).fetchall())

            if len(recent_checks) < AUTO_DISABLE_THRESHOLD:
                continue

            # Check if ALL recent checks are failures
            all_failed = all(
                check["status"] in ("timeout", "error")
                for check in recent_checks
            )

            if not all_failed:
                continue

            # Auto-disable this outbound
            ts = now_iso()
            conn.execute("""
                UPDATE outbounds
                SET enabled = 0, last_status = 'disabled',
                    last_error = ?, updated_at = ?
                WHERE id = ?
            """, (
                f"Auto-disabled: {AUTO_DISABLE_THRESHOLD} consecutive failures in {AUTO_DISABLE_WINDOW_MINUTES} minutes",
                ts,
                candidate["id"],
            ))

            disabled_outbounds.append({
                "outbound_id": candidate["id"],
                "remark": candidate["remark"],
                "server_name": candidate["server_name"],
                "reason": f"{AUTO_DISABLE_THRESHOLD} consecutive failures",
            })

            # Create an incident for the auto-disable
            conn.execute("""
                INSERT INTO incidents (
                    server_id, outbound_id, kind, severity, title, message,
                    status, first_seen_at, last_seen_at, created_at, updated_at
                )
                VALUES (?, ?, 'outbound.auto_disabled', 'warning', ?, ?, 'open', ?, ?, ?, ?)
            """, (
                candidate["server_id"],
                candidate["id"],
                f"Auto-disabled: {candidate['remark']}",
                f"Outbound {candidate['remark']} on {candidate['server_name']} was automatically disabled after {AUTO_DISABLE_THRESHOLD} consecutive failures.",
                ts, ts, ts, ts,
            ))

    return disabled_outbounds


# ---------------------------------------------------------------------------
# Scheduled reports
# ---------------------------------------------------------------------------

def check_scheduled_reports() -> None:
    """Check if it's time to send a scheduled weekly report."""
    now = datetime.now(timezone.utc)

    # Only send on the configured day and hour
    if now.weekday() != SCHEDULED_REPORT_DAY:
        return
    if now.hour != SCHEDULED_REPORT_HOUR:
        return

    # Check if we already sent a report today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    with connect() as conn:
        existing = conn.execute("""
            SELECT id FROM reports
            WHERE type = 'scheduled_weekly' AND created_at > ?
        """, (today_start,)).fetchone()
        if existing:
            return

    # Generate and send the report
    try:
        from .reports import generate_uptime_report, save_report
        report = generate_uptime_report(days=7)
        report["type"] = "scheduled_weekly"
        save_report(report)

        # Send to notification channels
        send_scheduled_report_notification(report)
    except Exception:
        pass


def send_scheduled_report_notification(report: dict[str, Any]) -> None:
    """Send the scheduled report summary to enabled notification channels."""
    from .notifier import list_channels, send_channel_message

    summary = report.get("summary", {})
    servers = report.get("servers", [])

    # Build message
    lines = [
        "📊 گزارش هفتگی Veltrix",
        "",
        f"🖥 سرورها: {summary.get('total_servers', 0)}",
        f"✅ Availability میانگین: {summary.get('average_availability', 0)}%",
        f"⚠️ رخدادها: {summary.get('total_incidents', 0)}",
        f"🟢 بالای ۹۹٪: {summary.get('servers_above_99', 0)}",
        f"🔴 زیر ۹۵٪: {summary.get('servers_below_95', 0)}",
        "",
    ]

    # Add worst servers
    worst = sorted(servers, key=lambda s: s.get("availability_percent", 100))[:3]
    if worst and worst[0].get("availability_percent", 100) < 99:
        lines.append("⚡ سرورهای نیازمند توجه:")
        for s in worst:
            if s.get("availability_percent", 100) < 99:
                lines.append(f"  • {s['server_name']}: {s['availability_percent']}%")
        lines.append("")

    lines.append("— Veltrix Intelligent Network Control")
    message = "\n".join(lines)

    # Send to all enabled channels
    with connect() as conn:
        channels = rows_to_dicts(
            conn.execute("SELECT * FROM notification_channels WHERE enabled = 1").fetchall()
        )

    for channel in channels:
        try:
            send_channel_message(channel, message, {
                "event": "scheduled_report",
                "product": "Veltrix",
                "report_type": "weekly_uptime",
                "summary": summary,
            })
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Webhook events for external systems
# ---------------------------------------------------------------------------

def emit_webhook_event(event_type: str, payload: dict[str, Any]) -> None:
    """Send an event to all webhook channels (for external integrations like Zapier, n8n)."""
    from .notifier import send_webhook

    with connect() as conn:
        channels = rows_to_dicts(conn.execute("""
            SELECT * FROM notification_channels
            WHERE enabled = 1 AND type = 'webhook'
        """).fetchall())

    import json
    for channel in channels:
        try:
            config_raw = channel.get("config_json", "{}")
            config = json.loads(config_raw) if isinstance(config_raw, str) else {}
            webhook_payload = {
                "event": event_type,
                "product": "Veltrix",
                "timestamp": now_iso(),
                **payload,
            }
            send_webhook(config, webhook_payload)
        except Exception:
            pass
