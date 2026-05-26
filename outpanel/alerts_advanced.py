"""Advanced alerting features for Veltrix.

- IP Rotation detection
- Traffic limit alerts
- Bulk operations
- Server groups/tags
- Public uptime badge
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connect, now_iso, row_to_dict, rows_to_dicts


# ---------------------------------------------------------------------------
# IP Rotation Detection
# ---------------------------------------------------------------------------

def check_ip_rotation(server_id: int) -> dict[str, Any] | None:
    """Check if a server's IP has changed since last check.

    Compares the current detected IP with the stored host.
    Returns alert info if IP changed, None otherwise.
    """
    with connect() as conn:
        server = row_to_dict(conn.execute(
            "SELECT id, name, host, last_detected_ip FROM servers WHERE id = ?",
            (server_id,),
        ).fetchone())

    if not server:
        return None

    current_ip = server.get("last_detected_ip") or ""
    stored_host = server.get("host") or ""

    if not current_ip or not stored_host:
        return None

    # Compare (simple string comparison — works for IP addresses)
    if current_ip != stored_host and current_ip != server.get("last_detected_ip"):
        return {
            "server_id": server_id,
            "server_name": server["name"],
            "old_ip": stored_host,
            "new_ip": current_ip,
            "detected_at": now_iso(),
        }

    return None


def record_server_ip(server_id: int, detected_ip: str) -> None:
    """Record the detected IP for a server (called during sync)."""
    if not detected_ip:
        return
    ts = now_iso()
    with connect() as conn:
        # Check if IP changed
        current = conn.execute(
            "SELECT last_detected_ip FROM servers WHERE id = ?", (server_id,)
        ).fetchone()

        if current and current["last_detected_ip"] and current["last_detected_ip"] != detected_ip:
            # IP changed — create alert
            server = row_to_dict(conn.execute("SELECT name FROM servers WHERE id=?", (server_id,)).fetchone())
            conn.execute("""
                INSERT INTO alerts (server_id, kind, severity, message, active, created_at)
                VALUES (?, 'server.ip_changed', 'warning', ?, 1, ?)
            """, (
                server_id,
                f"IP address changed for {server['name'] if server else 'server'}: {current['last_detected_ip']} → {detected_ip}",
                ts,
            ))

        conn.execute(
            "UPDATE servers SET last_detected_ip = ?, updated_at = ? WHERE id = ?",
            (detected_ip, ts, server_id),
        )


# ---------------------------------------------------------------------------
# Traffic Limit Alerts
# ---------------------------------------------------------------------------

# Default traffic limit (bytes) — 0 means no limit
DEFAULT_TRAFFIC_LIMIT = int(os.getenv("OUTPANEL_TRAFFIC_LIMIT_GB", "0")) * 1_073_741_824


def check_traffic_limits() -> list[dict[str, Any]]:
    """Check all outbounds for traffic limit violations."""
    if DEFAULT_TRAFFIC_LIMIT <= 0:
        return []

    alerts_created = []
    with connect() as conn:
        outbounds = rows_to_dicts(conn.execute("""
            SELECT outbounds.id, outbounds.remark, outbounds.total_bytes,
                   outbounds.traffic_limit, outbounds.server_id,
                   servers.name as server_name
            FROM outbounds
            JOIN servers ON servers.id = outbounds.server_id
            WHERE outbounds.enabled = 1
        """).fetchall())

        ts = now_iso()
        for outbound in outbounds:
            limit = outbound.get("traffic_limit") or DEFAULT_TRAFFIC_LIMIT
            if limit <= 0:
                continue

            total = outbound.get("total_bytes") or 0
            if total >= limit:
                # Check if alert already exists
                existing = conn.execute("""
                    SELECT id FROM alerts
                    WHERE outbound_id = ? AND kind = 'outbound.traffic_limit' AND active = 1
                """, (outbound["id"],)).fetchone()

                if not existing:
                    used_gb = round(total / 1_073_741_824, 2)
                    limit_gb = round(limit / 1_073_741_824, 2)
                    conn.execute("""
                        INSERT INTO alerts (server_id, outbound_id, kind, severity, message, active, created_at)
                        VALUES (?, ?, 'outbound.traffic_limit', 'warning', ?, 1, ?)
                    """, (
                        outbound["server_id"],
                        outbound["id"],
                        f"Traffic limit reached for {outbound['remark']} on {outbound['server_name']}: {used_gb}GB / {limit_gb}GB",
                        ts,
                    ))
                    alerts_created.append({
                        "outbound_id": outbound["id"],
                        "remark": outbound["remark"],
                        "used_gb": used_gb,
                        "limit_gb": limit_gb,
                    })

            # Warn at 80%
            elif total >= limit * 0.8:
                existing = conn.execute("""
                    SELECT id FROM alerts
                    WHERE outbound_id = ? AND kind = 'outbound.traffic_warning' AND active = 1
                """, (outbound["id"],)).fetchone()

                if not existing:
                    used_gb = round(total / 1_073_741_824, 2)
                    limit_gb = round(limit / 1_073_741_824, 2)
                    percent = round(total / limit * 100)
                    conn.execute("""
                        INSERT INTO alerts (server_id, outbound_id, kind, severity, message, active, created_at)
                        VALUES (?, ?, 'outbound.traffic_warning', 'warning', ?, 1, ?)
                    """, (
                        outbound["server_id"],
                        outbound["id"],
                        f"Traffic at {percent}% for {outbound['remark']}: {used_gb}GB / {limit_gb}GB",
                        ts,
                    ))

    return alerts_created


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------

def bulk_ping_servers(server_ids: list[int]) -> list[dict[str, Any]]:
    """Ping all outbounds for multiple servers."""
    from .monitor import ping_server_outbounds
    results = []
    for server_id in server_ids:
        try:
            pings = ping_server_outbounds(server_id)
            results.append({"server_id": server_id, "status": "ok", "results": pings})
        except Exception as exc:
            results.append({"server_id": server_id, "status": "error", "error": str(exc)})
    return results


def bulk_sync_servers(server_ids: list[int]) -> list[dict[str, Any]]:
    """Sync multiple servers."""
    from .monitor import sync_server
    results = []
    for server_id in server_ids:
        try:
            result = sync_server(server_id)
            results.append({"server_id": server_id, **result})
        except Exception as exc:
            results.append({"server_id": server_id, "status": "error", "error": str(exc)})
    return results


def bulk_toggle_servers(server_ids: list[int], enabled: bool) -> int:
    """Enable or disable multiple servers."""
    ts = now_iso()
    with connect() as conn:
        placeholders = ",".join("?" for _ in server_ids)
        conn.execute(
            f"UPDATE servers SET enabled = ?, updated_at = ? WHERE id IN ({placeholders})",
            (1 if enabled else 0, ts, *server_ids),
        )
    return len(server_ids)


def bulk_toggle_outbounds(outbound_ids: list[int], enabled: bool) -> int:
    """Enable or disable multiple outbounds."""
    ts = now_iso()
    with connect() as conn:
        placeholders = ",".join("?" for _ in outbound_ids)
        conn.execute(
            f"UPDATE outbounds SET enabled = ?, updated_at = ? WHERE id IN ({placeholders})",
            (1 if enabled else 0, ts, *outbound_ids),
        )
    return len(outbound_ids)


def bulk_delete_servers(server_ids: list[int]) -> int:
    """Delete multiple servers."""
    with connect() as conn:
        placeholders = ",".join("?" for _ in server_ids)
        conn.execute(f"DELETE FROM servers WHERE id IN ({placeholders})", server_ids)
    return len(server_ids)


# ---------------------------------------------------------------------------
# Server Groups / Tags
# ---------------------------------------------------------------------------

def get_server_tags() -> list[str]:
    """Get all unique tags used across servers."""
    with connect() as conn:
        rows = conn.execute("SELECT tags_json FROM servers WHERE tags_json != '[]'").fetchall()

    all_tags = set()
    for row in rows:
        try:
            tags = json.loads(row["tags_json"])
            if isinstance(tags, list):
                all_tags.update(t for t in tags if isinstance(t, str))
        except (json.JSONDecodeError, TypeError):
            pass

    return sorted(all_tags)


def set_server_tags(server_id: int, tags: list[str]) -> list[str]:
    """Set tags for a server."""
    clean_tags = sorted(set(t.strip().lower() for t in tags if t.strip()))[:10]  # Max 10 tags
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            "UPDATE servers SET tags_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(clean_tags, ensure_ascii=False), ts, server_id),
        )
    return clean_tags


def get_servers_by_tag(tag: str) -> list[dict[str, Any]]:
    """Get all servers with a specific tag."""
    with connect() as conn:
        servers = rows_to_dicts(conn.execute("SELECT * FROM servers ORDER BY id").fetchall())

    result = []
    for server in servers:
        try:
            tags = json.loads(server.get("tags_json") or "[]")
            if tag.lower() in [t.lower() for t in tags]:
                server.pop("password", None)
                server.pop("api_token", None)
                result.append(server)
        except (json.JSONDecodeError, TypeError):
            pass

    return result


# ---------------------------------------------------------------------------
# Public Uptime Badge
# ---------------------------------------------------------------------------

def generate_uptime_badge(server_id: int | None = None, days: int = 7) -> dict[str, Any]:
    """Generate uptime badge data (compatible with shields.io endpoint format).

    Returns data that can be used to create a badge like:
    https://img.shields.io/endpoint?url=YOUR_VELTRIX/api/badge/uptime
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")

    with connect() as conn:
        if server_id:
            query = """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status IN ('ok', 'high') THEN 1 ELSE 0 END) as ok
                FROM outbound_checks
                WHERE server_id = ? AND created_at > ?
            """
            row = conn.execute(query, (server_id, cutoff)).fetchone()
        else:
            query = """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status IN ('ok', 'high') THEN 1 ELSE 0 END) as ok
                FROM outbound_checks
                WHERE created_at > ?
            """
            row = conn.execute(query, (cutoff,)).fetchone()

    total = row["total"] or 0
    ok = row["ok"] or 0
    uptime = round((ok / total * 100), 2) if total > 0 else 0

    # Shields.io endpoint format
    if uptime >= 99:
        color = "brightgreen"
    elif uptime >= 95:
        color = "green"
    elif uptime >= 90:
        color = "yellowgreen"
    elif uptime >= 80:
        color = "yellow"
    else:
        color = "red"

    return {
        "schemaVersion": 1,
        "label": "uptime",
        "message": f"{uptime}%",
        "color": color,
        "namedLogo": "statuspage",
    }
