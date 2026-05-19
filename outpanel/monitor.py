from __future__ import annotations

import json
import threading
from typing import Any

from .db import connect, now_iso, row_to_dict, rows_to_dicts
from .ping import tcp_ping
from .xui import XUIClient, XUIError

# Alert types
ALERT_CPU = "server.cpu.high"
ALERT_RAM = "server.ram.high"
ALERT_XUI = "server.xui.error"
ALERT_PING_HIGH = "outbound.ping.high"
ALERT_PING_TIMEOUT = "outbound.ping.timeout"
ALERT_PING_ERROR = "outbound.ping.error"


def monitor_loop(stop_event: threading.Event, interval: int) -> None:
    """Background loop to monitor servers continuously."""
    while not stop_event.is_set():
        try:
            monitor_once()
        except Exception:
            # Background monitoring must never kill the web process.
            pass
        stop_event.wait(interval)


def monitor_once() -> None:
    """Run a single monitoring cycle for all enabled servers."""
    with connect() as conn:
        servers = rows_to_dicts(
            conn.execute("SELECT * FROM servers WHERE enabled = 1 ORDER BY id").fetchall()
        )
    for server in servers:
        sync_server(server["id"])
        ping_server_outbounds(server["id"])


def sync_server(server_id: int) -> dict[str, Any]:
    """Sync a server via X-UI and store metrics and alerts."""
    with connect() as conn:
        server = row_to_dict(conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone())
    if not server:
        raise ValueError("Server not found.")
    if not server["enabled"]:
        return {"status": "disabled", "synced": 0}

    synced = 0
    ts = now_iso()
    try:
        if server.get("panel_url"):
            auth_mode = server.get("auth_mode") or "credentials"
            api_token = server.get("api_token") or ""

            client = XUIClient(
                server["panel_url"],
                server.get("username") or "",
                server.get("password") or "",
                verify_tls=bool(server.get("verify_tls")),
                timeout=max(int(server.get("timeout_ms") or 2500), 500) / 1000,
                api_token=api_token if auth_mode == "api_token" else "",
            )
            client.login()
            status_response = client.get_status()
            metrics = parse_server_metrics(status_response)
            inbounds = client.list_inbounds()
            synced = upsert_inbounds(server, inbounds)
            store_metrics_and_alerts(server, metrics, status_response)

        with connect() as conn:
            conn.execute(
                """
                UPDATE servers
                SET last_status = 'online',
                    last_error = NULL,
                    last_checked_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (ts, ts, server_id),
            )
            resolve_alerts(conn, server_id, None, [ALERT_XUI])
        return {"status": "online", "synced": synced}

    except Exception as exc:
        message = str(exc)
        with connect() as conn:
            conn.execute(
                """
                UPDATE servers
                SET last_status = 'error',
                    last_error = ?,
                    last_checked_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (message[:500], ts, ts, server_id),
            )
            raise_alert(
                conn,
                server_id,
                None,
                ALERT_XUI,
                "critical",
                f"X-UI connection or sync failed for {server['name']}: {message}",
            )
        if isinstance(exc, XUIError):
            return {"status": "error", "synced": 0, "error": message}
        return {"status": "error", "synced": 0, "error": message}


def ping_server_outbounds(server_id: int) -> list[dict[str, Any]]:
    """Ping all outbounds of a server and record results."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT outbounds.*, servers.ping_warn_ms, servers.timeout_ms, servers.name AS server_name
            FROM outbounds
            JOIN servers ON servers.id = outbounds.server_id
            WHERE outbounds.server_id = ? AND servers.enabled = 1
            ORDER BY outbounds.id
            """,
            (server_id,),
        ).fetchall()
    return [ping_outbound(row["id"]) for row in rows]


def ping_outbound(outbound_id: int) -> dict[str, Any]:
    """Ping a single outbound and generate alerts if necessary."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT outbounds.*, servers.ping_warn_ms, servers.timeout_ms, servers.name AS server_name
            FROM outbounds
            JOIN servers ON servers.id = outbounds.server_id
            WHERE outbounds.id = ?
            """,
            (outbound_id,),
        ).fetchone()
        outbound = row_to_dict(row)

    if not outbound:
        raise ValueError("Outbound not found.")

    ts = now_iso()
    if not outbound["enabled"]:
        with connect() as conn:
            conn.execute(
                """
                UPDATE outbounds
                SET last_status = 'disabled',
                    last_checked_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (ts, ts, outbound_id),
            )
            record_outbound_check(conn, outbound_id, outbound["server_id"], None, "disabled", None, ts)
            resolve_alerts(conn, outbound["server_id"], outbound_id,
                           [ALERT_PING_HIGH, ALERT_PING_TIMEOUT, ALERT_PING_ERROR])
        return {"id": outbound_id, "status": "disabled", "latency_ms": None}

    result = tcp_ping(outbound["address"], int(outbound["port"]), outbound["timeout_ms"])
    warn_ms = int(outbound["ping_warn_ms"] or 350)
    status = result.status
    if status == "ok" and result.latency_ms is not None and result.latency_ms > warn_ms:
        status = "high"

    with connect() as conn:
        conn.execute(
            """
            UPDATE outbounds
            SET last_ping_ms = ?, last_status = ?, last_error = ?,
                last_checked_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (result.latency_ms, status, result.error, ts, ts, outbound_id),
        )
        record_outbound_check(conn, outbound_id, outbound["server_id"], result.latency_ms,
                              status, result.error, ts)

        if status == "ok":
            resolve_alerts(conn, outbound["server_id"], outbound_id,
                           [ALERT_PING_HIGH, ALERT_PING_TIMEOUT, ALERT_PING_ERROR])
        elif status == "high":
            resolve_alerts(conn, outbound["server_id"], outbound_id, [ALERT_PING_TIMEOUT, ALERT_PING_ERROR])
            raise_alert(conn, outbound["server_id"], outbound_id, ALERT_PING_HIGH, "warning",
                        f"Ping for {outbound['remark']} on {outbound['server_name']} exceeds {warn_ms}ms.")
        elif status == "timeout":
            resolve_alerts(conn, outbound["server_id"], outbound_id, [ALERT_PING_HIGH, ALERT_PING_ERROR])
            raise_alert(conn, outbound["server_id"], outbound_id, ALERT_PING_TIMEOUT, "critical",
                        f"Outbound {outbound['remark']} on {outbound['server_name']} timed out.")
        else:
            resolve_alerts(conn, outbound["server_id"], outbound_id, [ALERT_PING_HIGH, ALERT_PING_TIMEOUT])
            raise_alert(conn, outbound["server_id"], outbound_id, ALERT_PING_ERROR, "warning",
                        f"Connectivity test for {outbound['remark']} on {outbound['server_name']} failed: {result.error}")

    return {"id": outbound_id, "status": status, "latency_ms": result.latency_ms}


# ---------------------------------------------------------------------------
# Health Score calculation
# ---------------------------------------------------------------------------

def calculate_health_score(server_id: int) -> dict[str, Any]:
    """Calculate a health score (0-100) for a server based on recent metrics and outbound status.

    Scoring weights:
    - Server connectivity: 30%
    - CPU usage: 15%
    - RAM usage: 15%
    - Outbound availability: 40%
    """
    with connect() as conn:
        server = row_to_dict(conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone())
        if not server:
            return {"score": 0, "breakdown": {}, "grade": "F"}

        # Server connectivity score (30 points)
        connectivity_score = 30.0
        if server["last_status"] == "error":
            connectivity_score = 0.0
        elif server["last_status"] == "disabled":
            connectivity_score = 15.0
        elif server["last_status"] == "unknown":
            connectivity_score = 10.0

        # CPU score (15 points) - based on latest metric
        cpu_score = 15.0
        ram_score = 15.0
        latest_metric = row_to_dict(conn.execute(
            "SELECT * FROM metrics WHERE server_id = ? ORDER BY created_at DESC LIMIT 1",
            (server_id,),
        ).fetchone())

        if latest_metric:
            cpu = latest_metric.get("cpu_percent")
            ram = latest_metric.get("ram_percent")
            if cpu is not None:
                if cpu > 95:
                    cpu_score = 0.0
                elif cpu > 85:
                    cpu_score = 5.0
                elif cpu > 70:
                    cpu_score = 10.0
            if ram is not None:
                if ram > 95:
                    ram_score = 0.0
                elif ram > 85:
                    ram_score = 5.0
                elif ram > 70:
                    ram_score = 10.0

        # Outbound availability score (40 points)
        outbound_score = 40.0
        outbounds = rows_to_dicts(conn.execute(
            "SELECT last_status FROM outbounds WHERE server_id = ? AND enabled = 1",
            (server_id,),
        ).fetchall())

        if outbounds:
            total = len(outbounds)
            ok_count = sum(1 for o in outbounds if o["last_status"] == "ok")
            high_count = sum(1 for o in outbounds if o["last_status"] == "high")
            bad_count = total - ok_count - high_count
            if total > 0:
                outbound_score = 40.0 * ((ok_count + high_count * 0.7) / total)

        total_score = round(connectivity_score + cpu_score + ram_score + outbound_score)
        total_score = max(0, min(100, total_score))

        # Grade assignment
        if total_score >= 90:
            grade = "A"
        elif total_score >= 75:
            grade = "B"
        elif total_score >= 60:
            grade = "C"
        elif total_score >= 40:
            grade = "D"
        else:
            grade = "F"

        return {
            "score": total_score,
            "grade": grade,
            "breakdown": {
                "connectivity": round(connectivity_score, 1),
                "cpu": round(cpu_score, 1),
                "ram": round(ram_score, 1),
                "outbounds": round(outbound_score, 1),
            },
            "max_scores": {
                "connectivity": 30,
                "cpu": 15,
                "ram": 15,
                "outbounds": 40,
            },
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def parse_server_metrics(status_response: dict[str, Any]) -> dict[str, Any]:
    """Parse x-ui status response into normalized metrics."""
    obj = status_response.get("obj") if isinstance(status_response, dict) else {}
    if not isinstance(obj, dict):
        obj = status_response if isinstance(status_response, dict) else {}

    cpu = obj.get("cpu")
    mem = obj.get("mem") or {}
    disk = obj.get("disk") or {}
    xray = obj.get("xray") or {}

    ram_current = mem.get("current") or 0
    ram_total = mem.get("total") or 1
    ram_percent = (ram_current / ram_total * 100) if ram_total else 0

    disk_current = disk.get("current") or 0
    disk_total = disk.get("total") or 1
    disk_percent = (disk_current / disk_total * 100) if disk_total else 0

    return {
        "cpu_percent": round(cpu, 1) if cpu is not None else None,
        "ram_percent": round(ram_percent, 1),
        "ram_used": ram_current,
        "ram_total": ram_total,
        "disk_percent": round(disk_percent, 1),
        "xray_status": xray.get("state") or "unknown",
        "uptime": obj.get("uptime") or "",
    }


def upsert_inbounds(server: dict[str, Any], inbounds: list[dict[str, Any]]) -> int:
    """Upsert x-ui inbounds as outbounds for the server."""
    server_id = server["id"]
    ts = now_iso()
    synced = 0

    with connect() as conn:
        for inbound in inbounds:
            xui_id = str(inbound.get("id") or "")
            if not xui_id:
                continue

            remark = str(inbound.get("remark") or inbound.get("tag") or f"inbound-{xui_id}")
            protocol = str(inbound.get("protocol") or "unknown")
            port = int(inbound.get("port") or 0)
            enabled = 1 if inbound.get("enable", True) else 0

            # Parse settings for address
            settings_raw = inbound.get("settings") or "{}"
            if isinstance(settings_raw, str):
                try:
                    settings = json.loads(settings_raw)
                except json.JSONDecodeError:
                    settings = {}
            else:
                settings = settings_raw if isinstance(settings_raw, dict) else {}

            address = server.get("host") or "127.0.0.1"

            # Traffic stats
            up = int(inbound.get("up") or 0)
            down = int(inbound.get("down") or 0)
            total = up + down

            existing = conn.execute(
                "SELECT id FROM outbounds WHERE server_id = ? AND xui_id = ?",
                (server_id, xui_id),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE outbounds
                    SET remark = ?, protocol = ?, port = ?, enabled = ?,
                        up_bytes = ?, down_bytes = ?, total_bytes = ?,
                        raw_json = ?, updated_at = ?
                    WHERE server_id = ? AND xui_id = ?
                    """,
                    (remark, protocol, port, enabled, up, down, total,
                     json.dumps(inbound, ensure_ascii=False), ts, server_id, xui_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO outbounds (
                        server_id, xui_id, remark, protocol, address, port, enabled,
                        up_bytes, down_bytes, total_bytes, raw_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (server_id, xui_id, remark, protocol, address, port, enabled,
                     up, down, total, json.dumps(inbound, ensure_ascii=False), ts, ts),
                )
            synced += 1

    return synced


def store_metrics_and_alerts(server: dict[str, Any], metrics: dict[str, Any], raw_response: dict[str, Any]) -> None:
    """Store server metrics and generate CPU/RAM alerts if thresholds exceeded."""
    server_id = server["id"]
    ts = now_iso()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO metrics (
                server_id, cpu_percent, ram_percent, ram_used, ram_total,
                disk_percent, xray_status, uptime, raw_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                server_id,
                metrics.get("cpu_percent"),
                metrics.get("ram_percent"),
                metrics.get("ram_used"),
                metrics.get("ram_total"),
                metrics.get("disk_percent"),
                metrics.get("xray_status"),
                metrics.get("uptime"),
                json.dumps(raw_response, ensure_ascii=False),
                ts,
            ),
        )

        # CPU alert
        cpu = metrics.get("cpu_percent")
        cpu_warn = float(server.get("cpu_warn") or 85)
        if cpu is not None and cpu > cpu_warn:
            raise_alert(conn, server_id, None, ALERT_CPU, "warning",
                        f"CPU usage on {server['name']} is {cpu:.1f}% (threshold: {cpu_warn}%).")
        elif cpu is not None:
            resolve_alerts(conn, server_id, None, [ALERT_CPU])

        # RAM alert
        ram = metrics.get("ram_percent")
        ram_warn = float(server.get("ram_warn") or 85)
        if ram is not None and ram > ram_warn:
            raise_alert(conn, server_id, None, ALERT_RAM, "warning",
                        f"RAM usage on {server['name']} is {ram:.1f}% (threshold: {ram_warn}%).")
        elif ram is not None:
            resolve_alerts(conn, server_id, None, [ALERT_RAM])

        # Cleanup old metrics (keep last 1000 per server)
        conn.execute(
            """
            DELETE FROM metrics WHERE server_id = ? AND id NOT IN (
                SELECT id FROM metrics WHERE server_id = ? ORDER BY created_at DESC LIMIT 1000
            )
            """,
            (server_id, server_id),
        )


def record_outbound_check(
    conn: Any,
    outbound_id: int,
    server_id: int,
    latency_ms: float | None,
    status: str,
    error: str | None,
    ts: str,
) -> None:
    """Record an outbound ping check result."""
    conn.execute(
        """
        INSERT INTO outbound_checks (outbound_id, server_id, latency_ms, status, error, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (outbound_id, server_id, latency_ms, status, error, ts),
    )
    # Cleanup old checks (keep last 500 per outbound)
    conn.execute(
        """
        DELETE FROM outbound_checks WHERE outbound_id = ? AND id NOT IN (
            SELECT id FROM outbound_checks WHERE outbound_id = ? ORDER BY created_at DESC LIMIT 500
        )
        """,
        (outbound_id, outbound_id),
    )


def raise_alert(
    conn: Any,
    server_id: int,
    outbound_id: int | None,
    kind: str,
    severity: str,
    message: str,
) -> None:
    """Create or update an active alert."""
    existing = conn.execute(
        """
        SELECT id FROM alerts
        WHERE server_id = ? AND (outbound_id IS ? OR outbound_id = ?)
          AND kind = ? AND active = 1
        """,
        (server_id, outbound_id, outbound_id, kind),
    ).fetchone()

    ts = now_iso()
    if existing:
        conn.execute(
            "UPDATE alerts SET message = ?, severity = ?, created_at = ? WHERE id = ?",
            (message, severity, ts, existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO alerts (server_id, outbound_id, kind, severity, message, active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (server_id, outbound_id, kind, severity, message, ts),
        )


def resolve_alerts(
    conn: Any,
    server_id: int,
    outbound_id: int | None,
    kinds: list[str],
) -> None:
    """Resolve active alerts of specified kinds."""
    if not kinds:
        return
    placeholders = ",".join("?" for _ in kinds)
    ts = now_iso()
    if outbound_id is not None:
        conn.execute(
            f"""
            UPDATE alerts SET active = 0, resolved_at = ?
            WHERE server_id = ? AND outbound_id = ? AND kind IN ({placeholders}) AND active = 1
            """,
            (ts, server_id, outbound_id, *kinds),
        )
    else:
        conn.execute(
            f"""
            UPDATE alerts SET active = 0, resolved_at = ?
            WHERE server_id = ? AND outbound_id IS NULL AND kind IN ({placeholders}) AND active = 1
            """,
            (ts, server_id, *kinds),
        )
