"""Webhook event dispatcher for external integrations.

Sends structured events to all configured webhook channels,
enabling integration with Zapier, n8n, Make, and custom systems.

Event types:
- server.online / server.error / server.disabled
- outbound.timeout / outbound.error / outbound.auto_disabled
- incident.opened / incident.acknowledged / incident.recovered
- monitor.cycle_complete
- backup.created / backup.restored
- license.activated / license.expired
"""
from __future__ import annotations

import json
import threading
from typing import Any

from .db import connect, now_iso, rows_to_dicts


def dispatch_webhook_event(event_type: str, payload: dict[str, Any]) -> None:
    """Dispatch a webhook event to all enabled webhook channels.

    Runs in a background thread to avoid blocking the main request.
    """
    thread = threading.Thread(
        target=_send_webhook_event,
        args=(event_type, payload),
        daemon=True,
        name=f"webhook-{event_type}",
    )
    thread.start()


def _send_webhook_event(event_type: str, payload: dict[str, Any]) -> None:
    """Internal: send webhook event to all enabled webhook channels."""
    import urllib.error
    import urllib.request

    with connect() as conn:
        channels = rows_to_dicts(conn.execute("""
            SELECT id, config_json FROM notification_channels
            WHERE enabled = 1 AND type = 'webhook'
        """).fetchall())

    if not channels:
        return

    event_payload = {
        "event": event_type,
        "product": "Veltrix",
        "version": "0.2.0",
        "timestamp": now_iso(),
        "data": payload,
    }
    body = json.dumps(event_payload, ensure_ascii=False).encode("utf-8")

    for channel in channels:
        try:
            config = json.loads(channel.get("config_json", "{}"))
            url = config.get("url", "").strip()
            if not url:
                continue

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Veltrix-Webhook/0.2.0",
                "X-Veltrix-Event": event_type,
            }
            secret = config.get("secret", "").strip()
            if secret:
                headers["X-Veltrix-Secret"] = secret

            request = urllib.request.Request(url, data=body, method="POST", headers=headers)
            urllib.request.urlopen(request, timeout=10)
        except Exception:
            # Webhook delivery failures are non-critical
            pass


# ---------------------------------------------------------------------------
# Convenience functions for common events
# ---------------------------------------------------------------------------

def webhook_server_status(server_id: int, server_name: str, status: str, error: str | None = None) -> None:
    """Fire webhook for server status change."""
    dispatch_webhook_event(f"server.{status}", {
        "server_id": server_id,
        "server_name": server_name,
        "status": status,
        "error": error,
    })


def webhook_outbound_issue(outbound_id: int, remark: str, server_name: str, status: str, latency_ms: float | None = None) -> None:
    """Fire webhook for outbound issues."""
    dispatch_webhook_event(f"outbound.{status}", {
        "outbound_id": outbound_id,
        "remark": remark,
        "server_name": server_name,
        "status": status,
        "latency_ms": latency_ms,
    })


def webhook_incident(incident_id: int, action: str, title: str, severity: str, server_name: str | None = None) -> None:
    """Fire webhook for incident lifecycle events."""
    dispatch_webhook_event(f"incident.{action}", {
        "incident_id": incident_id,
        "action": action,
        "title": title,
        "severity": severity,
        "server_name": server_name,
    })


def webhook_backup(action: str, backup_name: str, actor: str | None = None) -> None:
    """Fire webhook for backup events."""
    dispatch_webhook_event(f"backup.{action}", {
        "action": action,
        "backup_name": backup_name,
        "actor": actor,
    })


def webhook_license(action: str, state: str, plan: str | None = None) -> None:
    """Fire webhook for license events."""
    dispatch_webhook_event(f"license.{action}", {
        "action": action,
        "state": state,
        "plan": plan,
    })
