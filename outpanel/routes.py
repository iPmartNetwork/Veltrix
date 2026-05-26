"""API route handlers for Veltrix.

All endpoint logic is organized here, separated from the HTTP server.
"""
from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from . import __version__
from .auth import (
    auth_status,
    change_password,
    create_manager,
    delete_manager,
    has_permission,
    list_audit_logs,
    list_users,
    login,
    logout,
    permission_catalog,
    public_user,
    record_audit,
    setup_owner,
    update_manager,
)
from .backup import create_backup, delete_backup, get_backup_path, list_backups, restore_backup
from .db import connect, now_iso, row_to_dict, rows_to_dicts
from .licensing import (
    activate_license_with_server,
    get_license_status,
    get_public_license_catalog,
)
from .monitor import calculate_health_score, monitor_once, ping_outbound, sync_server
from .notifier import (
    create_channel,
    delete_channel,
    list_channels,
    send_test_notification,
    update_channel,
)
from .reports import (
    export_incidents_csv,
    export_outbounds_csv,
    export_servers_csv,
    generate_outbound_report,
    generate_uptime_report,
    list_reports,
    save_report,
)
from .router import RequestContext, Router


def build_router() -> Router:
    """Build and return the API router with all routes registered."""
    router = Router()

    # --- Health ---
    router.get("/api/health", handle_health, auth_required=False)

    # --- Overview (combined dashboard data) ---
    router.get("/api/overview", handle_overview)

    # --- Auth (public) ---
    router.get("/api/auth/status", handle_auth_status, auth_required=False)
    router.post("/api/auth/setup", handle_auth_setup, auth_required=False)
    router.post("/api/auth/login", handle_auth_login, auth_required=False)

    # --- Auth (authenticated) ---
    router.get("/api/auth/me", handle_auth_me)
    router.post("/api/auth/logout", handle_auth_logout)
    router.post("/api/auth/password", handle_auth_password)

    # --- License ---
    router.get("/api/license", handle_license_status, permission="license")
    router.post("/api/license/activate", handle_license_activate, permission="license")
    router.get("/api/license/catalog", handle_license_catalog, permission="license")

    # --- Servers ---
    router.get("/api/servers", handle_servers_list, permission="servers")
    router.post("/api/servers", handle_servers_create, permission="servers")
    router.get("/api/servers/{server_id}", handle_server_detail, permission="servers")
    router.put("/api/servers/{server_id}", handle_server_update, permission="servers")
    router.delete("/api/servers/{server_id}", handle_server_delete, permission="servers")
    router.post("/api/servers/{server_id}/sync", handle_server_sync, permission="servers")
    router.get("/api/servers/{server_id}/health", handle_server_health, permission="servers")
    router.get("/api/servers/{server_id}/metrics", handle_server_metrics, permission="history")

    # --- Outbounds ---
    router.get("/api/outbounds", handle_outbounds_list, permission="outbounds")
    router.get("/api/servers/{server_id}/outbounds", handle_server_outbounds, permission="outbounds")
    router.post("/api/outbounds/{outbound_id}/ping", handle_outbound_ping, permission="outbounds")
    router.get("/api/outbounds/{outbound_id}/checks", handle_outbound_checks, permission="history")

    # --- Alerts ---
    router.get("/api/alerts", handle_alerts_list, permission="incidents")
    router.post("/api/alerts/{alert_id}/dismiss", handle_alert_dismiss, permission="incidents")

    # --- Incidents ---
    router.get("/api/incidents", handle_incidents_list, permission="incidents")
    router.post("/api/incidents/{incident_id}/ack", handle_incident_acknowledge, permission="incidents")
    router.post("/api/incidents/{incident_id}/recover", handle_incident_recover, permission="incidents")

    # --- Notifications (support both path styles for frontend compatibility) ---
    router.get("/api/notification-channels", handle_channels_list, permission="notifications")
    router.post("/api/notification-channels", handle_channel_create, permission="notifications")
    router.put("/api/notification-channels/{channel_id}", handle_channel_update, permission="notifications")
    router.delete("/api/notification-channels/{channel_id}", handle_channel_delete, permission="notifications")
    router.post("/api/notification-channels/{channel_id}/test", handle_channel_test, permission="notifications")
    router.get("/api/notifications/channels", handle_channels_list, permission="notifications")
    router.post("/api/notifications/channels", handle_channel_create, permission="notifications")
    router.put("/api/notifications/channels/{channel_id}", handle_channel_update, permission="notifications")
    router.delete("/api/notifications/channels/{channel_id}", handle_channel_delete, permission="notifications")
    router.post("/api/notifications/channels/{channel_id}/test", handle_channel_test, permission="notifications")

    # --- Backups ---
    router.get("/api/backups", handle_backups_list, permission="maintenance")
    router.post("/api/backups", handle_backup_create, permission="maintenance")
    router.post("/api/backups/{name}/restore", handle_backup_restore, permission="maintenance")
    router.delete("/api/backups/{name}", handle_backup_delete, permission="maintenance")

    # --- Users / Managers ---
    router.get("/api/users", handle_users_list, permission="users")
    router.post("/api/users", handle_user_create, permission="users")
    router.put("/api/users/{user_id}", handle_user_update, permission="users")
    router.delete("/api/users/{user_id}", handle_user_delete, permission="users")

    # --- Audit ---
    router.get("/api/audit-logs", handle_audit_list, permission="users")
    router.get("/api/audit", handle_audit_list, permission="users")

    # --- Monitor ---
    router.post("/api/monitor/run", handle_monitor_run, permission="servers")

    # --- SSE (Server-Sent Events) ---
    router.get("/api/events", handle_sse_stream)

    # --- History ---
    router.get("/api/history/outbound-checks", handle_outbound_checks_history, permission="history")

    # --- Reports & Export ---
    router.get("/api/reports", handle_reports_list, permission="history")
    router.get("/api/reports/uptime", handle_report_uptime, permission="history")
    router.get("/api/reports/outbounds", handle_report_outbounds, permission="history")
    router.get("/api/export/servers", handle_export_servers, permission="servers")
    router.get("/api/export/outbounds", handle_export_outbounds, permission="outbounds")
    router.get("/api/export/incidents", handle_export_incidents, permission="incidents")

    # --- Settings ---
    router.get("/api/settings", handle_settings_get)
    router.put("/api/settings", handle_settings_update)

    # --- Branding ---
    router.get("/api/branding", handle_branding_get, auth_required=False)
    router.put("/api/branding", handle_branding_update, permission="maintenance")

    # --- i18n ---
    router.get("/api/i18n", handle_i18n_get, auth_required=False)
    router.get("/api/i18n/labels", handle_i18n_labels, auth_required=False)

    # --- Demo ---
    router.post("/api/demo/seed", handle_demo_seed, permission="maintenance")

    # --- 2FA ---
    router.get("/api/auth/2fa/status", handle_2fa_status)
    router.post("/api/auth/2fa/enable", handle_2fa_enable)
    router.post("/api/auth/2fa/confirm", handle_2fa_confirm)
    router.post("/api/auth/2fa/disable", handle_2fa_disable)

    # --- Backup Schedule ---
    router.get("/api/backups/schedule", handle_backup_schedule, permission="maintenance")
    router.put("/api/backups/schedule", handle_backup_schedule_update, permission="maintenance")

    # --- SSH Remote Management ---
    router.get("/api/servers/{server_id}/ssh", handle_ssh_get, permission="servers")
    router.post("/api/servers/{server_id}/ssh", handle_ssh_save, permission="servers")
    router.delete("/api/servers/{server_id}/ssh", handle_ssh_delete, permission="servers")
    router.post("/api/servers/{server_id}/ssh/restart", handle_ssh_restart, permission="servers")
    router.get("/api/ssh/configs", handle_ssh_list, permission="servers")

    # --- Bulk Operations ---
    router.post("/api/bulk/ping", handle_bulk_ping, permission="servers")
    router.post("/api/bulk/sync", handle_bulk_sync, permission="servers")
    router.post("/api/bulk/toggle-servers", handle_bulk_toggle_servers, permission="servers")
    router.post("/api/bulk/toggle-outbounds", handle_bulk_toggle_outbounds, permission="outbounds")
    router.post("/api/bulk/delete-servers", handle_bulk_delete_servers, permission="servers")

    # --- Server Tags ---
    router.get("/api/tags", handle_tags_list)
    router.get("/api/tags/{tag}/servers", handle_tag_servers, permission="servers")
    router.put("/api/servers/{server_id}/tags", handle_server_tags_update, permission="servers")

    # --- Uptime Badge (public) ---
    router.get("/api/badge/uptime", handle_uptime_badge, auth_required=False)
    router.get("/api/badge/uptime/{server_id}", handle_uptime_badge_server, auth_required=False)

    # --- API Documentation ---
    router.get("/api/docs", handle_api_docs, auth_required=False)

    # --- License Validation ---
    router.get("/api/license/validate", handle_license_validate, permission="license")
    router.get("/api/license/display", handle_license_display, permission="license")

    return router


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def handle_health(ctx: RequestContext) -> dict[str, Any]:
    return {"ok": True, "version": __version__}


# ---------------------------------------------------------------------------
# Overview (combined dashboard endpoint)
# ---------------------------------------------------------------------------

def handle_overview(ctx: RequestContext) -> dict[str, Any]:
    """Return combined dashboard data in a single request."""
    with connect() as conn:
        servers = rows_to_dicts(conn.execute("SELECT * FROM servers ORDER BY id").fetchall())
        outbounds = rows_to_dicts(conn.execute(
            """
            SELECT outbounds.*, servers.name AS server_name
            FROM outbounds
            JOIN servers ON servers.id = outbounds.server_id
            ORDER BY outbounds.server_id, outbounds.id
            """
        ).fetchall())
        alerts = rows_to_dicts(conn.execute(
            """
            SELECT alerts.*, servers.name AS server_name, outbounds.remark AS outbound_remark
            FROM alerts
            LEFT JOIN servers ON servers.id = alerts.server_id
            LEFT JOIN outbounds ON outbounds.id = alerts.outbound_id
            WHERE alerts.active = 1
            ORDER BY alerts.created_at DESC
            """
        ).fetchall())
        incidents = rows_to_dicts(conn.execute(
            """
            SELECT incidents.*, servers.name AS server_name, outbounds.remark AS outbound_remark
            FROM incidents
            LEFT JOIN servers ON servers.id = incidents.server_id
            LEFT JOIN outbounds ON outbounds.id = incidents.outbound_id
            WHERE incidents.status IN ('open', 'acknowledged')
            ORDER BY incidents.last_seen_at DESC
            LIMIT 100
            """
        ).fetchall())

    # Enrich servers with latest metrics
    for server in servers:
        server["has_password"] = bool(server.get("password"))
        server["has_api_token"] = bool(server.get("api_token"))
        server.pop("password", None)
        server.pop("api_token", None)
        with connect() as conn:
            metric = row_to_dict(conn.execute(
                "SELECT cpu_percent, ram_percent, xray_status, uptime FROM metrics WHERE server_id = ? ORDER BY created_at DESC LIMIT 1",
                (server["id"],),
            ).fetchone())
        if metric:
            server["cpu_percent"] = metric.get("cpu_percent")
            server["ram_percent"] = metric.get("ram_percent")
            server["xray_status"] = metric.get("xray_status")
            server["uptime"] = metric.get("uptime")
        else:
            server["cpu_percent"] = None
            server["ram_percent"] = None
            server["xray_status"] = None
            server["uptime"] = None
        server["outbound_count"] = sum(1 for o in outbounds if o.get("server_id") == server["id"])
        server["has_password"] = bool(server.get("password"))

    # Compute counts
    enabled_servers = [s for s in servers if s.get("enabled")]
    online_servers = [s for s in enabled_servers if s.get("last_status") == "online"]
    bad_outbounds = [o for o in outbounds if o.get("last_status") in ("high", "timeout", "error")]
    open_incidents = [i for i in incidents if i.get("status") == "open"]

    # License status
    license_data = None
    if has_permission(ctx.user, "license"):
        license_data = get_license_status()

    # Add duration_seconds to incidents
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for incident in incidents:
        first_seen = incident.get("first_seen_at")
        if first_seen:
            try:
                first_dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
                incident["duration_seconds"] = int((now - first_dt).total_seconds())
            except (ValueError, TypeError):
                incident["duration_seconds"] = 0
        else:
            incident["duration_seconds"] = 0

    return {
        "servers": servers,
        "outbounds": outbounds,
        "alerts": alerts,
        "incidents": incidents,
        "license": license_data,
        "counts": {
            "servers": len(servers),
            "enabled_servers": len(enabled_servers),
            "online_servers": len(online_servers),
            "outbounds": len(outbounds),
            "bad_outbounds": len(bad_outbounds),
            "active_alerts": len(alerts),
            "active_incidents": len(incidents),
            "open_incidents": len(open_incidents),
        },
    }


# ---------------------------------------------------------------------------
# Auth handlers
# ---------------------------------------------------------------------------

def handle_auth_status(ctx: RequestContext) -> dict[str, Any]:
    return auth_status(ctx.session_token)


def handle_auth_setup(ctx: RequestContext) -> dict[str, Any]:
    result = setup_owner(ctx.body, ctx.client_ip)
    return {"ok": True, "__set_session": result.get("token"), **result, "permissions": permission_catalog()}


def handle_auth_login(ctx: RequestContext) -> dict[str, Any]:
    result = login(ctx.body, ctx.client_ip, ctx.user_agent)
    return {"ok": True, "__set_session": result.get("token"), **result, "permissions": permission_catalog()}


def handle_auth_me(ctx: RequestContext) -> dict[str, Any]:
    return {"user": public_user(ctx.user), "permissions": permission_catalog()}


def handle_auth_logout(ctx: RequestContext) -> dict[str, Any]:
    logout(ctx.session_token, ctx.user, ctx.client_ip)
    return {"ok": True, "__clear_session": True}


def handle_auth_password(ctx: RequestContext) -> dict[str, Any]:
    return change_password(ctx.user, ctx.body, ctx.client_ip, ctx.session_token)


# ---------------------------------------------------------------------------
# License handlers
# ---------------------------------------------------------------------------

def handle_license_status(ctx: RequestContext) -> dict[str, Any]:
    return {"license": get_license_status()}


def handle_license_activate(ctx: RequestContext) -> dict[str, Any]:
    data = activate_license_with_server(str(ctx.body.get("license_key") or ""))
    _audit(ctx, "license.activate", "license", None, {"state": data.get("license", {}).get("state")})
    return {"ok": True, **data, "status": get_license_status()}


def handle_license_catalog(ctx: RequestContext) -> dict[str, Any]:
    return get_public_license_catalog()


# ---------------------------------------------------------------------------
# Server handlers
# ---------------------------------------------------------------------------

def handle_servers_list(ctx: RequestContext) -> dict[str, Any]:
    with connect() as conn:
        servers = rows_to_dicts(conn.execute("SELECT * FROM servers ORDER BY id").fetchall())
    # Remove sensitive fields
    for s in servers:
        s.pop("password", None)
    return {"servers": servers}


def handle_servers_create(ctx: RequestContext) -> dict[str, Any]:
    payload = ctx.body
    name = str(payload.get("name") or "").strip()
    host = str(payload.get("host") or "").strip()
    if not name:
        raise ValueError("Server name is required.")
    if not host:
        raise ValueError("Server host is required.")

    # License enforcement
    _enforce_server_limit()

    auth_mode = str(payload.get("auth_mode") or "credentials").strip()
    if auth_mode not in ("credentials", "api_token"):
        auth_mode = "credentials"

    ts = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO servers (
                name, host, panel_url, username, password, auth_mode, api_token,
                verify_tls, enabled,
                cpu_warn, ram_warn, ping_warn_ms, timeout_ms,
                last_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', ?, ?)
            """,
            (
                name, host,
                str(payload.get("panel_url") or "").strip(),
                str(payload.get("username") or "").strip() if auth_mode == "credentials" else "",
                str(payload.get("password") or "").strip() if auth_mode == "credentials" else "",
                auth_mode,
                str(payload.get("api_token") or "").strip() if auth_mode == "api_token" else "",
                1 if payload.get("verify_tls", True) else 0,
                1 if payload.get("enabled", True) else 0,
                float(payload.get("cpu_warn") or 85),
                float(payload.get("ram_warn") or 85),
                int(payload.get("ping_warn_ms") or 350),
                int(payload.get("timeout_ms") or 2500),
                ts, ts,
            ),
        )
        server_id = cursor.lastrowid
    _audit(ctx, "server.create", "server", server_id, {"name": name})
    return {"ok": True, "id": server_id}


def handle_server_detail(ctx: RequestContext) -> dict[str, Any]:
    server_id = int(ctx.get_param("server_id"))
    with connect() as conn:
        server = row_to_dict(conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone())
    if not server:
        raise ValueError("Server not found.")
    server.pop("password", None)
    return {"server": server}


def handle_server_update(ctx: RequestContext) -> dict[str, Any]:
    server_id = int(ctx.get_param("server_id"))
    payload = ctx.body
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone())
        if not existing:
            raise ValueError("Server not found.")

        auth_mode = str(payload.get("auth_mode") or existing.get("auth_mode") or "credentials").strip()
        if auth_mode not in ("credentials", "api_token"):
            auth_mode = "credentials"

        ts = now_iso()
        conn.execute(
            """
            UPDATE servers SET
                name = ?, host = ?, panel_url = ?, username = ?,
                auth_mode = ?,
                verify_tls = ?, enabled = ?,
                cpu_warn = ?, ram_warn = ?, ping_warn_ms = ?, timeout_ms = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                str(payload.get("name") or existing["name"]).strip(),
                str(payload.get("host") or existing["host"]).strip(),
                str(payload.get("panel_url") if "panel_url" in payload else existing["panel_url"] or "").strip(),
                str(payload.get("username") if "username" in payload else existing["username"] or "").strip() if auth_mode == "credentials" else "",
                auth_mode,
                1 if payload.get("verify_tls", existing["verify_tls"]) else 0,
                1 if payload.get("enabled", existing["enabled"]) else 0,
                float(payload.get("cpu_warn") or existing["cpu_warn"]),
                float(payload.get("ram_warn") or existing["ram_warn"]),
                int(payload.get("ping_warn_ms") or existing["ping_warn_ms"]),
                int(payload.get("timeout_ms") or existing["timeout_ms"]),
                ts, server_id,
            ),
        )
        # Update password only if provided (credentials mode)
        if auth_mode == "credentials":
            new_password = payload.get("password")
            if new_password:
                conn.execute("UPDATE servers SET password = ?, api_token = '' WHERE id = ?", (str(new_password).strip(), server_id))
        # Update API token only if provided (api_token mode)
        elif auth_mode == "api_token":
            new_token = payload.get("api_token")
            if new_token:
                conn.execute("UPDATE servers SET api_token = ?, password = '', username = '' WHERE id = ?", (str(new_token).strip(), server_id))

    _audit(ctx, "server.update", "server", server_id, {"name": payload.get("name")})
    return {"ok": True}


def handle_server_delete(ctx: RequestContext) -> dict[str, Any]:
    server_id = int(ctx.get_param("server_id"))
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone())
        if not existing:
            raise ValueError("Server not found.")
        conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))
    _audit(ctx, "server.delete", "server", server_id, {"name": existing["name"]})
    return {"ok": True}


def handle_server_sync(ctx: RequestContext) -> dict[str, Any]:
    server_id = int(ctx.get_param("server_id"))
    result = sync_server(server_id)
    _audit(ctx, "server.sync", "server", server_id, result)
    return result


def handle_server_health(ctx: RequestContext) -> dict[str, Any]:
    server_id = int(ctx.get_param("server_id"))
    return calculate_health_score(server_id)


def handle_server_metrics(ctx: RequestContext) -> dict[str, Any]:
    server_id = int(ctx.get_param("server_id"))
    limit = ctx.get_query_int("limit", 50)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM metrics WHERE server_id = ? ORDER BY created_at DESC LIMIT ?",
            (server_id, min(limit, 200)),
        ).fetchall()
    return {"metrics": rows_to_dicts(rows)}


# ---------------------------------------------------------------------------
# Outbound handlers
# ---------------------------------------------------------------------------

def handle_outbounds_list(ctx: RequestContext) -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT outbounds.*, servers.name AS server_name
            FROM outbounds
            JOIN servers ON servers.id = outbounds.server_id
            ORDER BY outbounds.server_id, outbounds.id
            """
        ).fetchall()
    return {"outbounds": rows_to_dicts(rows)}


def handle_server_outbounds(ctx: RequestContext) -> dict[str, Any]:
    server_id = int(ctx.get_param("server_id"))
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM outbounds WHERE server_id = ? ORDER BY id",
            (server_id,),
        ).fetchall()
    return {"outbounds": rows_to_dicts(rows)}


def handle_outbound_ping(ctx: RequestContext) -> dict[str, Any]:
    outbound_id = int(ctx.get_param("outbound_id"))
    return ping_outbound(outbound_id)


def handle_outbound_checks(ctx: RequestContext) -> dict[str, Any]:
    """Get ping check history for a specific outbound."""
    outbound_id = int(ctx.get_param("outbound_id"))
    limit = ctx.get_query_int("limit", 70)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM outbound_checks WHERE outbound_id = ? ORDER BY created_at DESC LIMIT ?",
            (outbound_id, min(limit, 500)),
        ).fetchall()
    return {"checks": rows_to_dicts(rows)}


# ---------------------------------------------------------------------------
# Alert handlers
# ---------------------------------------------------------------------------

def handle_alerts_list(ctx: RequestContext) -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT alerts.*, servers.name AS server_name, outbounds.remark AS outbound_remark
            FROM alerts
            LEFT JOIN servers ON servers.id = alerts.server_id
            LEFT JOIN outbounds ON outbounds.id = alerts.outbound_id
            WHERE alerts.active = 1
            ORDER BY alerts.created_at DESC
            """
        ).fetchall()
    return {"alerts": rows_to_dicts(rows)}


def handle_alert_dismiss(ctx: RequestContext) -> dict[str, Any]:
    alert_id = int(ctx.get_param("alert_id"))
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            "UPDATE alerts SET active = 0, seen_at = ?, resolved_at = ? WHERE id = ?",
            (ts, ts, alert_id),
        )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Incident handlers
# ---------------------------------------------------------------------------

def handle_incidents_list(ctx: RequestContext) -> dict[str, Any]:
    status_filter = ctx.get_query("status", "")
    with connect() as conn:
        if status_filter:
            rows = conn.execute(
                """
                SELECT incidents.*, servers.name AS server_name, outbounds.remark AS outbound_remark
                FROM incidents
                LEFT JOIN servers ON servers.id = incidents.server_id
                LEFT JOIN outbounds ON outbounds.id = incidents.outbound_id
                WHERE incidents.status = ?
                ORDER BY incidents.last_seen_at DESC
                """,
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT incidents.*, servers.name AS server_name, outbounds.remark AS outbound_remark
                FROM incidents
                LEFT JOIN servers ON servers.id = incidents.server_id
                LEFT JOIN outbounds ON outbounds.id = incidents.outbound_id
                ORDER BY incidents.last_seen_at DESC
                LIMIT 100
                """
            ).fetchall()
    return {"incidents": rows_to_dicts(rows)}


def handle_incident_acknowledge(ctx: RequestContext) -> dict[str, Any]:
    incident_id = int(ctx.get_param("incident_id"))
    ts = now_iso()
    username = ctx.user.get("username") if ctx.user else "unknown"
    with connect() as conn:
        conn.execute(
            """
            UPDATE incidents SET status = 'acknowledged', acknowledged_at = ?,
                acknowledged_by = ?, updated_at = ?
            WHERE id = ? AND status = 'open'
            """,
            (ts, username, ts, incident_id),
        )
    _audit(ctx, "incident.acknowledge", "incident", incident_id, {})
    return {"ok": True}


def handle_incident_recover(ctx: RequestContext) -> dict[str, Any]:
    incident_id = int(ctx.get_param("incident_id"))
    ts = now_iso()
    message = str(ctx.body.get("message") or "Manually recovered")
    with connect() as conn:
        conn.execute(
            """
            UPDATE incidents SET status = 'recovered', recovered_at = ?,
                recovery_message = ?, updated_at = ?
            WHERE id = ? AND status IN ('open', 'acknowledged')
            """,
            (ts, message, ts, incident_id),
        )
    _audit(ctx, "incident.recover", "incident", incident_id, {"message": message})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Notification handlers
# ---------------------------------------------------------------------------

def handle_channels_list(ctx: RequestContext) -> dict[str, Any]:
    return {"channels": list_channels()}


def handle_channel_create(ctx: RequestContext) -> dict[str, Any]:
    channel = create_channel(ctx.body)
    _audit(ctx, "notification.create_channel", "notification_channel", channel.get("id"), {"name": channel.get("name")})
    return {"ok": True, "channel": channel}


def handle_channel_update(ctx: RequestContext) -> dict[str, Any]:
    channel_id = int(ctx.get_param("channel_id"))
    channel = update_channel(channel_id, ctx.body)
    return {"ok": True, "channel": channel}


def handle_channel_delete(ctx: RequestContext) -> dict[str, Any]:
    channel_id = int(ctx.get_param("channel_id"))
    delete_channel(channel_id)
    _audit(ctx, "notification.delete_channel", "notification_channel", channel_id, {})
    return {"ok": True}


def handle_channel_test(ctx: RequestContext) -> dict[str, Any]:
    channel_id = int(ctx.get_param("channel_id"))
    return send_test_notification(channel_id)


# ---------------------------------------------------------------------------
# Backup handlers
# ---------------------------------------------------------------------------

def handle_backups_list(ctx: RequestContext) -> dict[str, Any]:
    return {"backups": list_backups()}


def handle_backup_create(ctx: RequestContext) -> dict[str, Any]:
    backup = create_backup(ctx.user, reason="manual")
    _audit(ctx, "backup.create", "backup", backup.get("name"), {})
    return {"ok": True, "backup": backup}


def handle_backup_restore(ctx: RequestContext) -> dict[str, Any]:
    name = ctx.get_param("name")
    result = restore_backup(name, ctx.user)
    _audit(ctx, "backup.restore", "backup", name, {})
    return result


def handle_backup_delete(ctx: RequestContext) -> dict[str, Any]:
    name = ctx.get_param("name")
    delete_backup(name)
    _audit(ctx, "backup.delete", "backup", name, {})
    return {"ok": True}


# ---------------------------------------------------------------------------
# User/Manager handlers
# ---------------------------------------------------------------------------

def handle_users_list(ctx: RequestContext) -> dict[str, Any]:
    return {"users": list_users(), "permissions": permission_catalog(), "manager_limit": 10}


def handle_user_create(ctx: RequestContext) -> dict[str, Any]:
    user = create_manager(ctx.body, ctx.user, ctx.client_ip)
    return {"ok": True, "user": user}


def handle_user_update(ctx: RequestContext) -> dict[str, Any]:
    user_id = int(ctx.get_param("user_id"))
    user = update_manager(user_id, ctx.body, ctx.user, ctx.client_ip)
    return {"ok": True, "user": user}


def handle_user_delete(ctx: RequestContext) -> dict[str, Any]:
    user_id = int(ctx.get_param("user_id"))
    delete_manager(user_id, ctx.user, ctx.client_ip)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Audit handler
# ---------------------------------------------------------------------------

def handle_audit_list(ctx: RequestContext) -> dict[str, Any]:
    limit = ctx.get_query_int("limit", 100)
    offset = ctx.get_query_int("offset", 0)
    return {"logs": list_audit_logs(limit=min(limit, 500), offset=offset)}


# ---------------------------------------------------------------------------
# Monitor handler
# ---------------------------------------------------------------------------

def handle_monitor_run(ctx: RequestContext) -> dict[str, Any]:
    monitor_once()
    _audit(ctx, "monitor.manual_run", None, None, {})
    return {"ok": True}


def handle_sse_stream(ctx: RequestContext) -> dict[str, Any]:
    """Marker for SSE stream — actual handling is in app.py."""
    return {"__sse_stream": True}


# ---------------------------------------------------------------------------
# History handler
# ---------------------------------------------------------------------------

def handle_outbound_checks_history(ctx: RequestContext) -> dict[str, Any]:
    outbound_id = ctx.get_query_int("outbound_id", 0)
    server_id = ctx.get_query_int("server_id", 0)
    limit = ctx.get_query_int("limit", 50)

    with connect() as conn:
        if outbound_id:
            rows = conn.execute(
                "SELECT * FROM outbound_checks WHERE outbound_id = ? ORDER BY created_at DESC LIMIT ?",
                (outbound_id, min(limit, 200)),
            ).fetchall()
        elif server_id:
            rows = conn.execute(
                "SELECT * FROM outbound_checks WHERE server_id = ? ORDER BY created_at DESC LIMIT ?",
                (server_id, min(limit, 500)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM outbound_checks ORDER BY created_at DESC LIMIT ?",
                (min(limit, 200),),
            ).fetchall()
    return {"checks": rows_to_dicts(rows)}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _audit(ctx: RequestContext, action: str, target_type: str | None, target_id: Any, details: dict[str, Any]) -> None:
    """Record an audit log entry from a route handler."""
    record_audit(ctx.user, action, target_type, target_id, details, ctx.client_ip)


def _enforce_server_limit() -> None:
    """Enforce license server limit."""
    import os
    from .licensing import get_license_status

    status = get_license_status()
    if not status.get("requires_license"):
        return

    plan = status.get("plan")
    if not plan:
        raise PermissionError("A valid license is required to add servers.")

    max_servers = plan.get("max_servers")
    if max_servers is None:
        return

    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS count FROM servers").fetchone()["count"]
    if count >= max_servers:
        raise PermissionError(f"Server limit reached ({max_servers}). Upgrade your license to add more servers.")


# ---------------------------------------------------------------------------
# Report & Export handlers
# ---------------------------------------------------------------------------

def handle_reports_list(ctx: RequestContext) -> dict[str, Any]:
    limit = ctx.get_query_int("limit", 20)
    return {"reports": list_reports(limit=min(limit, 100))}


def handle_report_uptime(ctx: RequestContext) -> dict[str, Any]:
    server_id = ctx.get_query_int("server_id", 0) or None
    days = ctx.get_query_int("days", 7)
    days = max(1, min(days, 90))
    report = generate_uptime_report(server_id=server_id, days=days)
    # Save report
    user_id = ctx.user.get("id") if ctx.user else None
    save_report(report, generated_by=user_id)
    return report


def handle_report_outbounds(ctx: RequestContext) -> dict[str, Any]:
    server_id = ctx.get_query_int("server_id", 0) or None
    days = ctx.get_query_int("days", 7)
    days = max(1, min(days, 90))
    report = generate_outbound_report(server_id=server_id, days=days)
    user_id = ctx.user.get("id") if ctx.user else None
    save_report(report, generated_by=user_id)
    return report


def handle_export_servers(ctx: RequestContext) -> dict[str, Any]:
    csv_data = export_servers_csv()
    return {"csv": csv_data, "filename": "veltrix-servers.csv", "__content_type": "text/csv"}


def handle_export_outbounds(ctx: RequestContext) -> dict[str, Any]:
    csv_data = export_outbounds_csv()
    return {"csv": csv_data, "filename": "veltrix-outbounds.csv", "__content_type": "text/csv"}


def handle_export_incidents(ctx: RequestContext) -> dict[str, Any]:
    days = ctx.get_query_int("days", 30)
    csv_data = export_incidents_csv(days=max(1, min(days, 365)))
    return {"csv": csv_data, "filename": "veltrix-incidents.csv", "__content_type": "text/csv"}


# ---------------------------------------------------------------------------
# Settings handlers
# ---------------------------------------------------------------------------

def handle_settings_get(ctx: RequestContext) -> dict[str, Any]:
    """Get app settings (theme, preferences)."""
    with connect() as conn:
        try:
            rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
            settings = {row["key"]: row["value"] for row in rows}
        except Exception:
            settings = {}
    return {"settings": settings}


def handle_settings_update(ctx: RequestContext) -> dict[str, Any]:
    """Update app settings."""
    payload = ctx.body
    ts = now_iso()
    allowed_keys = {"theme", "language", "monitor_sound", "auto_refresh_interval"}

    with connect() as conn:
        # Ensure table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        for key, value in payload.items():
            if key not in allowed_keys:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, str(value), ts),
            )

    # Update language if changed
    if "language" in payload:
        from .i18n import set_language
        set_language(str(payload["language"]))

    return {"ok": True}


# ---------------------------------------------------------------------------
# Branding handlers
# ---------------------------------------------------------------------------

def handle_branding_get(ctx: RequestContext) -> dict[str, Any]:
    """Get current branding configuration."""
    from .branding import get_branding
    return {"branding": get_branding()}


def handle_branding_update(ctx: RequestContext) -> dict[str, Any]:
    """Update branding configuration."""
    from .branding import update_branding
    branding = update_branding(ctx.body)
    _audit(ctx, "branding.update", "settings", None, ctx.body)
    return {"ok": True, "branding": branding}


# ---------------------------------------------------------------------------
# i18n handlers
# ---------------------------------------------------------------------------

def handle_i18n_get(ctx: RequestContext) -> dict[str, Any]:
    """Get all translations for the current or requested language."""
    from .i18n import get_language, get_translations, SUPPORTED_LANGUAGES
    lang = ctx.get_query("lang", "") or get_language()
    return {
        "language": lang,
        "supported": SUPPORTED_LANGUAGES,
        "translations": get_translations(lang),
    }


def handle_i18n_labels(ctx: RequestContext) -> dict[str, Any]:
    """Get UI labels for the frontend."""
    from .i18n import get_language, get_ui_labels, SUPPORTED_LANGUAGES
    lang = ctx.get_query("lang", "") or get_language()
    return {
        "language": lang,
        "supported": SUPPORTED_LANGUAGES,
        "labels": get_ui_labels(lang),
    }


# ---------------------------------------------------------------------------
# Demo handler
# ---------------------------------------------------------------------------

def handle_demo_seed(ctx: RequestContext) -> dict[str, Any]:
    """Seed demo data for demonstration purposes."""
    from .demo import seed_demo_data
    result = seed_demo_data()
    _audit(ctx, "demo.seed", None, None, result)
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# Bulk Operations handlers
# ---------------------------------------------------------------------------

def handle_bulk_ping(ctx: RequestContext) -> dict[str, Any]:
    from .alerts_advanced import bulk_ping_servers
    server_ids = ctx.body.get("server_ids", [])
    if not server_ids or not isinstance(server_ids, list):
        raise ValueError("server_ids array is required.")
    results = bulk_ping_servers([int(sid) for sid in server_ids[:20]])
    return {"ok": True, "results": results}


def handle_bulk_sync(ctx: RequestContext) -> dict[str, Any]:
    from .alerts_advanced import bulk_sync_servers
    server_ids = ctx.body.get("server_ids", [])
    if not server_ids or not isinstance(server_ids, list):
        raise ValueError("server_ids array is required.")
    results = bulk_sync_servers([int(sid) for sid in server_ids[:20]])
    return {"ok": True, "results": results}


def handle_bulk_toggle_servers(ctx: RequestContext) -> dict[str, Any]:
    from .alerts_advanced import bulk_toggle_servers
    server_ids = ctx.body.get("server_ids", [])
    enabled = bool(ctx.body.get("enabled", True))
    if not server_ids:
        raise ValueError("server_ids array is required.")
    count = bulk_toggle_servers([int(sid) for sid in server_ids], enabled)
    _audit(ctx, "bulk.toggle_servers", "server", None, {"count": count, "enabled": enabled})
    return {"ok": True, "affected": count}


def handle_bulk_toggle_outbounds(ctx: RequestContext) -> dict[str, Any]:
    from .alerts_advanced import bulk_toggle_outbounds
    outbound_ids = ctx.body.get("outbound_ids", [])
    enabled = bool(ctx.body.get("enabled", True))
    if not outbound_ids:
        raise ValueError("outbound_ids array is required.")
    count = bulk_toggle_outbounds([int(oid) for oid in outbound_ids], enabled)
    return {"ok": True, "affected": count}


def handle_bulk_delete_servers(ctx: RequestContext) -> dict[str, Any]:
    from .alerts_advanced import bulk_delete_servers
    server_ids = ctx.body.get("server_ids", [])
    if not server_ids:
        raise ValueError("server_ids array is required.")
    count = bulk_delete_servers([int(sid) for sid in server_ids])
    _audit(ctx, "bulk.delete_servers", "server", None, {"count": count})
    return {"ok": True, "deleted": count}


# ---------------------------------------------------------------------------
# Server Tags handlers
# ---------------------------------------------------------------------------

def handle_tags_list(ctx: RequestContext) -> dict[str, Any]:
    from .alerts_advanced import get_server_tags
    return {"tags": get_server_tags()}


def handle_tag_servers(ctx: RequestContext) -> dict[str, Any]:
    from .alerts_advanced import get_servers_by_tag
    tag = ctx.get_param("tag")
    return {"tag": tag, "servers": get_servers_by_tag(tag)}


def handle_server_tags_update(ctx: RequestContext) -> dict[str, Any]:
    from .alerts_advanced import set_server_tags
    server_id = int(ctx.get_param("server_id"))
    tags = ctx.body.get("tags", [])
    if not isinstance(tags, list):
        raise ValueError("tags must be an array of strings.")
    result = set_server_tags(server_id, tags)
    return {"ok": True, "tags": result}


# ---------------------------------------------------------------------------
# Uptime Badge handlers
# ---------------------------------------------------------------------------

def handle_uptime_badge(ctx: RequestContext) -> dict[str, Any]:
    from .alerts_advanced import generate_uptime_badge
    days = ctx.get_query_int("days", 7)
    return generate_uptime_badge(server_id=None, days=max(1, min(days, 90)))


def handle_uptime_badge_server(ctx: RequestContext) -> dict[str, Any]:
    from .alerts_advanced import generate_uptime_badge
    server_id = int(ctx.get_param("server_id"))
    days = ctx.get_query_int("days", 7)
    return generate_uptime_badge(server_id=server_id, days=max(1, min(days, 90)))


# ---------------------------------------------------------------------------
# API Documentation handler
# ---------------------------------------------------------------------------

def handle_api_docs(ctx: RequestContext) -> dict[str, Any]:
    from .api_docs import generate_api_docs
    from .routes import build_router
    router = build_router()
    return generate_api_docs(router.routes)


# ---------------------------------------------------------------------------
# License Validation handlers
# ---------------------------------------------------------------------------

def handle_license_validate(ctx: RequestContext) -> dict[str, Any]:
    from .license_validator import periodic_license_check, validate_cached_token
    token_result = validate_cached_token()
    check_result = periodic_license_check()
    return {"token_validation": token_result, "server_check": check_result}


def handle_license_display(ctx: RequestContext) -> dict[str, Any]:
    from .license_validator import get_license_display_info
    return {"license": get_license_display_info()}


# ---------------------------------------------------------------------------
# 2FA handlers
# ---------------------------------------------------------------------------

def handle_2fa_status(ctx: RequestContext) -> dict[str, Any]:
    from .totp import get_2fa_status
    user_id = ctx.user.get("id") if ctx.user else None
    if not user_id:
        raise PermissionError("Login required.")
    return get_2fa_status(user_id)


def handle_2fa_enable(ctx: RequestContext) -> dict[str, Any]:
    from .totp import enable_2fa
    user_id = ctx.user.get("id") if ctx.user else None
    if not user_id:
        raise PermissionError("Login required.")
    result = enable_2fa(user_id)
    return {"ok": True, **result}


def handle_2fa_confirm(ctx: RequestContext) -> dict[str, Any]:
    from .totp import confirm_2fa
    user_id = ctx.user.get("id") if ctx.user else None
    if not user_id:
        raise PermissionError("Login required.")
    code = str(ctx.body.get("code") or "").strip()
    if not code:
        raise ValueError("TOTP code is required.")
    success = confirm_2fa(user_id, code)
    if not success:
        raise ValueError("Invalid code. Please try again.")
    _audit(ctx, "auth.2fa_enabled", "user", user_id, {})
    return {"ok": True, "message": "2FA activated successfully."}


def handle_2fa_disable(ctx: RequestContext) -> dict[str, Any]:
    from .totp import disable_2fa
    user_id = ctx.user.get("id") if ctx.user else None
    if not user_id:
        raise PermissionError("Login required.")
    # Require current password for security
    password = str(ctx.body.get("password") or "")
    if not password:
        raise ValueError("Current password is required to disable 2FA.")
    from .auth import verify_password
    with connect() as conn:
        user_row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user_row or not verify_password(password, user_row["password_hash"]):
        raise ValueError("Incorrect password.")
    disable_2fa(user_id)
    _audit(ctx, "auth.2fa_disabled", "user", user_id, {})
    return {"ok": True, "message": "2FA disabled."}


# ---------------------------------------------------------------------------
# Backup Schedule handler
# ---------------------------------------------------------------------------

def handle_backup_schedule(ctx: RequestContext) -> dict[str, Any]:
    from .scheduled_backup import get_backup_schedule_info
    return get_backup_schedule_info()


def handle_backup_schedule_update(ctx: RequestContext) -> dict[str, Any]:
    """Update backup schedule settings."""
    ts = now_iso()
    payload = ctx.body
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        if "hour" in payload:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('backup_hour', ?, ?)",
                (str(int(payload["hour"])), ts),
            )
        if "retention" in payload:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('backup_retention', ?, ?)",
                (str(int(payload["retention"])), ts),
            )
        if "enabled" in payload:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES ('backup_enabled', ?, ?)",
                ("1" if payload["enabled"] else "0", ts),
            )
    return {"ok": True}


# ---------------------------------------------------------------------------
# SSH Remote Management handlers
# ---------------------------------------------------------------------------

def handle_ssh_get(ctx: RequestContext) -> dict[str, Any]:
    from .ssh_manager import get_ssh_config
    server_id = int(ctx.get_param("server_id"))
    config = get_ssh_config(server_id)
    return {"ssh": config}


def handle_ssh_save(ctx: RequestContext) -> dict[str, Any]:
    from .ssh_manager import save_ssh_credentials, init_ssh_table
    init_ssh_table()
    server_id = int(ctx.get_param("server_id"))
    payload = ctx.body
    result = save_ssh_credentials(
        server_id=server_id,
        ssh_host=str(payload.get("ssh_host") or "").strip(),
        ssh_port=int(payload.get("ssh_port") or 22),
        ssh_user=str(payload.get("ssh_user") or "root").strip(),
        ssh_password=str(payload.get("ssh_password") or "").strip(),
        restart_enabled=bool(payload.get("restart_enabled", True)),
        restart_delay_minutes=int(payload.get("restart_delay_minutes") or 5),
        restart_command=str(payload.get("restart_command") or "").strip(),
    )
    _audit(ctx, "ssh.save", "server", server_id, {"ssh_host": payload.get("ssh_host")})
    return result


def handle_ssh_delete(ctx: RequestContext) -> dict[str, Any]:
    from .ssh_manager import delete_ssh_config
    server_id = int(ctx.get_param("server_id"))
    delete_ssh_config(server_id)
    _audit(ctx, "ssh.delete", "server", server_id, {})
    return {"ok": True}


def handle_ssh_restart(ctx: RequestContext) -> dict[str, Any]:
    """Manually trigger SSH restart for a server."""
    from .ssh_manager import get_ssh_config, _execute_restart, init_ssh_table
    from .crypto import decrypt_value
    init_ssh_table()
    server_id = int(ctx.get_param("server_id"))

    with connect() as conn:
        config = row_to_dict(conn.execute(
            "SELECT * FROM server_ssh WHERE server_id = ?", (server_id,)
        ).fetchone())

    if not config:
        raise ValueError("SSH not configured for this server.")

    # Add server name
    with connect() as conn:
        server = row_to_dict(conn.execute("SELECT name FROM servers WHERE id=?", (server_id,)).fetchone())
    config["server_name"] = server["name"] if server else "unknown"

    result = _execute_restart(config)
    _audit(ctx, "ssh.manual_restart", "server", server_id, result)
    return result


def handle_ssh_list(ctx: RequestContext) -> dict[str, Any]:
    from .ssh_manager import list_ssh_configs, init_ssh_table
    init_ssh_table()
    return {"configs": list_ssh_configs()}
