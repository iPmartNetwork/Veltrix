"""Operational reporting for Veltrix.

Generates uptime/downtime reports, performance summaries, and CSV exports.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connect, now_iso, row_to_dict, rows_to_dicts


def generate_uptime_report(
    server_id: int | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """Generate an uptime/availability report for servers and outbounds.

    Args:
        server_id: Optional specific server. None = all servers.
        days: Number of days to look back.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")

    with connect() as conn:
        # Server uptime based on outbound checks
        if server_id:
            servers = rows_to_dicts(conn.execute(
                "SELECT * FROM servers WHERE id = ?", (server_id,)
            ).fetchall())
        else:
            servers = rows_to_dicts(conn.execute(
                "SELECT * FROM servers WHERE enabled = 1 ORDER BY id"
            ).fetchall())

        report_servers = []
        for server in servers:
            sid = server["id"]

            # Get check stats for this server's outbounds
            stats = row_to_dict(conn.execute("""
                SELECT
                    COUNT(*) as total_checks,
                    SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) as ok_checks,
                    SUM(CASE WHEN status = 'high' THEN 1 ELSE 0 END) as high_checks,
                    SUM(CASE WHEN status IN ('timeout', 'error') THEN 1 ELSE 0 END) as failed_checks,
                    AVG(CASE WHEN latency_ms IS NOT NULL THEN latency_ms END) as avg_latency,
                    MIN(CASE WHEN latency_ms IS NOT NULL THEN latency_ms END) as min_latency,
                    MAX(CASE WHEN latency_ms IS NOT NULL THEN latency_ms END) as max_latency
                FROM outbound_checks
                WHERE server_id = ? AND created_at > ?
            """, (sid, cutoff)).fetchone())

            total = stats.get("total_checks") or 0
            ok = (stats.get("ok_checks") or 0) + (stats.get("high_checks") or 0)
            availability = round((ok / total * 100), 2) if total > 0 else 0.0

            # Get incident count
            incident_count = conn.execute("""
                SELECT COUNT(*) as count FROM incidents
                WHERE server_id = ? AND created_at > ?
            """, (sid, cutoff)).fetchone()["count"]

            # Get metric averages
            metric_avg = row_to_dict(conn.execute("""
                SELECT
                    AVG(cpu_percent) as avg_cpu,
                    AVG(ram_percent) as avg_ram,
                    MAX(cpu_percent) as max_cpu,
                    MAX(ram_percent) as max_ram
                FROM metrics
                WHERE server_id = ? AND created_at > ?
            """, (sid, cutoff)).fetchone())

            report_servers.append({
                "server_id": sid,
                "server_name": server["name"],
                "host": server["host"],
                "current_status": server["last_status"],
                "availability_percent": availability,
                "total_checks": total,
                "ok_checks": ok,
                "failed_checks": stats.get("failed_checks") or 0,
                "avg_latency_ms": round(stats.get("avg_latency") or 0, 1),
                "min_latency_ms": round(stats.get("min_latency") or 0, 1),
                "max_latency_ms": round(stats.get("max_latency") or 0, 1),
                "incident_count": incident_count,
                "avg_cpu": round(metric_avg.get("avg_cpu") or 0, 1) if metric_avg else 0,
                "avg_ram": round(metric_avg.get("avg_ram") or 0, 1) if metric_avg else 0,
                "max_cpu": round(metric_avg.get("max_cpu") or 0, 1) if metric_avg else 0,
                "max_ram": round(metric_avg.get("max_ram") or 0, 1) if metric_avg else 0,
            })

    # Overall summary
    total_servers = len(report_servers)
    avg_availability = (
        sum(s["availability_percent"] for s in report_servers) / total_servers
        if total_servers else 0
    )

    return {
        "type": "uptime",
        "period_days": days,
        "period_start": cutoff,
        "period_end": now_iso(),
        "generated_at": now_iso(),
        "summary": {
            "total_servers": total_servers,
            "average_availability": round(avg_availability, 2),
            "total_incidents": sum(s["incident_count"] for s in report_servers),
            "servers_above_99": sum(1 for s in report_servers if s["availability_percent"] >= 99),
            "servers_below_95": sum(1 for s in report_servers if s["availability_percent"] < 95),
        },
        "servers": report_servers,
    }


def generate_outbound_report(server_id: int | None = None, days: int = 7) -> dict[str, Any]:
    """Generate a detailed outbound performance report."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")

    with connect() as conn:
        query = """
            SELECT
                outbounds.id,
                outbounds.remark,
                outbounds.protocol,
                outbounds.address,
                outbounds.port,
                outbounds.last_status,
                servers.name as server_name,
                COUNT(outbound_checks.id) as total_checks,
                SUM(CASE WHEN outbound_checks.status = 'ok' THEN 1 ELSE 0 END) as ok_checks,
                SUM(CASE WHEN outbound_checks.status IN ('timeout', 'error') THEN 1 ELSE 0 END) as failed_checks,
                AVG(CASE WHEN outbound_checks.latency_ms IS NOT NULL THEN outbound_checks.latency_ms END) as avg_latency,
                MIN(CASE WHEN outbound_checks.latency_ms IS NOT NULL THEN outbound_checks.latency_ms END) as min_latency,
                MAX(CASE WHEN outbound_checks.latency_ms IS NOT NULL THEN outbound_checks.latency_ms END) as max_latency
            FROM outbounds
            JOIN servers ON servers.id = outbounds.server_id
            LEFT JOIN outbound_checks ON outbound_checks.outbound_id = outbounds.id
                AND outbound_checks.created_at > ?
            WHERE outbounds.enabled = 1
        """
        params: list[Any] = [cutoff]
        if server_id:
            query += " AND outbounds.server_id = ?"
            params.append(server_id)
        query += " GROUP BY outbounds.id ORDER BY avg_latency DESC"

        rows = rows_to_dicts(conn.execute(query, params).fetchall())

    outbounds = []
    for row in rows:
        total = row.get("total_checks") or 0
        ok = row.get("ok_checks") or 0
        availability = round((ok / total * 100), 2) if total > 0 else 0.0
        outbounds.append({
            **row,
            "availability_percent": availability,
            "avg_latency": round(row.get("avg_latency") or 0, 1),
            "min_latency": round(row.get("min_latency") or 0, 1),
            "max_latency": round(row.get("max_latency") or 0, 1),
        })

    return {
        "type": "outbound_performance",
        "period_days": days,
        "period_start": cutoff,
        "period_end": now_iso(),
        "generated_at": now_iso(),
        "total_outbounds": len(outbounds),
        "outbounds": outbounds,
    }


def export_servers_csv() -> str:
    """Export all servers as CSV."""
    with connect() as conn:
        servers = rows_to_dicts(conn.execute(
            "SELECT id, name, host, panel_url, enabled, last_status, cpu_warn, ram_warn, ping_warn_ms, last_checked_at, created_at FROM servers ORDER BY id"
        ).fetchall())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "id", "name", "host", "panel_url", "enabled", "last_status",
        "cpu_warn", "ram_warn", "ping_warn_ms", "last_checked_at", "created_at",
    ])
    writer.writeheader()
    writer.writerows(servers)
    return output.getvalue()


def export_outbounds_csv() -> str:
    """Export all outbounds as CSV."""
    with connect() as conn:
        outbounds = rows_to_dicts(conn.execute("""
            SELECT outbounds.id, outbounds.remark, outbounds.protocol, outbounds.address,
                   outbounds.port, outbounds.last_status, outbounds.last_ping_ms,
                   outbounds.up_bytes, outbounds.down_bytes, outbounds.total_bytes,
                   outbounds.last_checked_at, servers.name as server_name
            FROM outbounds
            JOIN servers ON servers.id = outbounds.server_id
            ORDER BY outbounds.server_id, outbounds.id
        """).fetchall())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "id", "server_name", "remark", "protocol", "address", "port",
        "last_status", "last_ping_ms", "up_bytes", "down_bytes", "total_bytes", "last_checked_at",
    ])
    writer.writeheader()
    writer.writerows(outbounds)
    return output.getvalue()


def export_incidents_csv(days: int = 30) -> str:
    """Export incidents as CSV."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    with connect() as conn:
        incidents = rows_to_dicts(conn.execute("""
            SELECT incidents.id, incidents.kind, incidents.severity, incidents.title,
                   incidents.message, incidents.status, incidents.first_seen_at,
                   incidents.last_seen_at, incidents.recovered_at,
                   servers.name as server_name, outbounds.remark as outbound_remark
            FROM incidents
            LEFT JOIN servers ON servers.id = incidents.server_id
            LEFT JOIN outbounds ON outbounds.id = incidents.outbound_id
            WHERE incidents.created_at > ?
            ORDER BY incidents.created_at DESC
        """, (cutoff,)).fetchall())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "id", "server_name", "outbound_remark", "kind", "severity", "title",
        "message", "status", "first_seen_at", "last_seen_at", "recovered_at",
    ])
    writer.writeheader()
    writer.writerows(incidents)
    return output.getvalue()


def save_report(report: dict[str, Any], generated_by: int | None = None) -> dict[str, Any]:
    """Save a generated report to the database."""
    ts = now_iso()
    with connect() as conn:
        cursor = conn.execute("""
            INSERT INTO reports (type, title, period_start, period_end, data_json, generated_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            report.get("type", "unknown"),
            f"{report.get('type', 'Report')} - {report.get('period_days', '?')} days",
            report.get("period_start", ts),
            report.get("period_end", ts),
            json.dumps(report, ensure_ascii=False),
            generated_by,
            ts,
        ))
        return {"id": cursor.lastrowid, "created_at": ts}


def list_reports(limit: int = 20) -> list[dict[str, Any]]:
    """List saved reports."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, type, title, period_start, period_end, generated_by, created_at FROM reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return rows_to_dicts(rows)
