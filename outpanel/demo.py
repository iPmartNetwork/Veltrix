"""Demo mode for Veltrix.

Generates realistic fake data for demonstration purposes.
Activated via OUTPANEL_DEMO_MODE=1 environment variable.
"""
from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connect, now_iso


DEMO_MODE = os.getenv("OUTPANEL_DEMO_MODE", "") == "1"

DEMO_SERVERS = [
    {"name": "Germany Frankfurt 01", "host": "185.220.101.42", "panel_url": "http://185.220.101.42:54321"},
    {"name": "Germany Munich 02", "host": "91.132.147.88", "panel_url": "http://91.132.147.88:54321"},
    {"name": "Netherlands Amsterdam 01", "host": "45.153.243.15", "panel_url": "http://45.153.243.15:54321"},
    {"name": "Finland Helsinki 01", "host": "95.216.78.120", "panel_url": "http://95.216.78.120:54321"},
    {"name": "France Paris 01", "host": "51.158.166.92", "panel_url": "http://51.158.166.92:54321"},
    {"name": "UK London 01", "host": "178.62.44.201", "panel_url": "http://178.62.44.201:54321"},
    {"name": "Sweden Stockholm 01", "host": "194.36.25.18", "panel_url": "http://194.36.25.18:54321"},
    {"name": "Turkey Istanbul 01", "host": "176.53.147.65", "panel_url": "http://176.53.147.65:54321"},
]

DEMO_PROTOCOLS = ["vless", "vmess", "trojan", "shadowsocks"]
DEMO_REMARKS = [
    "Direct-TLS", "CDN-WS", "gRPC-Reality", "TCP-Vision",
    "WS-CDN-Cloudflare", "H2-Direct", "XTLS-Reality", "Hysteria2",
]


def is_demo_mode() -> bool:
    """Check if demo mode is active."""
    return DEMO_MODE


def seed_demo_data() -> dict[str, Any]:
    """Generate and insert demo data into the database.

    Returns summary of created data.
    """
    with connect() as conn:
        # Check if demo data already exists
        count = conn.execute("SELECT COUNT(*) as c FROM servers WHERE name LIKE 'Germany%' OR name LIKE 'Netherlands%'").fetchone()["c"]
        if count >= 4:
            return {"status": "already_seeded", "servers": count}

    ts_now = datetime.now(timezone.utc)
    created_servers = 0
    created_outbounds = 0
    created_metrics = 0
    created_checks = 0

    with connect() as conn:
        for i, server_data in enumerate(DEMO_SERVERS):
            ts = (ts_now - timedelta(days=random.randint(5, 30))).isoformat(timespec="seconds")
            status = random.choice(["online", "online", "online", "online", "error"])

            cursor = conn.execute("""
                INSERT INTO servers (
                    name, host, panel_url, username, password, verify_tls, enabled,
                    cpu_warn, ram_warn, ping_warn_ms, timeout_ms,
                    last_status, last_checked_at, created_at, updated_at
                ) VALUES (?, ?, ?, 'admin', 'demo', 1, 1, 85, 85, 350, 2500, ?, ?, ?, ?)
            """, (
                server_data["name"], server_data["host"], server_data["panel_url"],
                status, now_iso(), ts, ts,
            ))
            server_id = cursor.lastrowid
            created_servers += 1

            # Create outbounds for this server
            num_outbounds = random.randint(3, 8)
            for j in range(num_outbounds):
                protocol = random.choice(DEMO_PROTOCOLS)
                remark = f"{random.choice(DEMO_REMARKS)}-{j+1}"
                port = random.randint(443, 65000)
                outbound_status = random.choice(["ok", "ok", "ok", "ok", "high", "timeout", "error"])
                latency = random.uniform(20, 500) if outbound_status != "timeout" else None

                cursor = conn.execute("""
                    INSERT INTO outbounds (
                        server_id, xui_id, remark, protocol, address, port, enabled,
                        last_ping_ms, last_status, last_checked_at,
                        up_bytes, down_bytes, total_bytes,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    server_id, str(j + 1), remark, protocol,
                    server_data["host"], port,
                    round(latency, 1) if latency else None,
                    outbound_status, now_iso(),
                    random.randint(100_000_000, 50_000_000_000),
                    random.randint(500_000_000, 200_000_000_000),
                    random.randint(600_000_000, 250_000_000_000),
                    ts, ts,
                ))
                outbound_id = cursor.lastrowid
                created_outbounds += 1

                # Create check history
                for k in range(random.randint(20, 50)):
                    check_ts = (ts_now - timedelta(minutes=k * 30 + random.randint(0, 10))).isoformat(timespec="seconds")
                    check_status = random.choice(["ok", "ok", "ok", "ok", "ok", "high", "timeout"])
                    check_latency = random.uniform(30, 400) if check_status != "timeout" else None
                    conn.execute("""
                        INSERT INTO outbound_checks (outbound_id, server_id, latency_ms, status, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (outbound_id, server_id, round(check_latency, 1) if check_latency else None, check_status, check_ts))
                    created_checks += 1

            # Create metrics history
            for k in range(random.randint(30, 60)):
                metric_ts = (ts_now - timedelta(minutes=k * 30 + random.randint(0, 15))).isoformat(timespec="seconds")
                cpu = random.uniform(15, 92)
                ram = random.uniform(30, 88)
                conn.execute("""
                    INSERT INTO metrics (server_id, cpu_percent, ram_percent, ram_used, ram_total, disk_percent, xray_status, uptime, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)
                """, (
                    server_id, round(cpu, 1), round(ram, 1),
                    int(ram / 100 * 8_000_000_000), 8_000_000_000,
                    random.uniform(20, 65),
                    f"{random.randint(1, 90)} days",
                    metric_ts,
                ))
                created_metrics += 1

        # Create some demo alerts
        alert_servers = random.sample(range(1, created_servers + 1), min(3, created_servers))
        for sid in alert_servers:
            conn.execute("""
                INSERT INTO alerts (server_id, kind, severity, message, active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (
                sid,
                random.choice(["server.cpu.high", "server.ram.high", "outbound.ping.high"]),
                random.choice(["warning", "critical"]),
                f"Demo alert for server {sid}",
                now_iso(),
            ))

        # Create some demo incidents
        conn.execute("""
            INSERT INTO incidents (
                server_id, kind, severity, title, message, status,
                first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, 'outbound.ping.timeout', 'critical', ?, ?, 'open', ?, ?, ?, ?)
        """, (
            1, "Outbound timeout on Germany Frankfurt 01",
            "Multiple outbounds on this server are experiencing timeouts.",
            now_iso(), now_iso(), now_iso(), now_iso(),
        ))

    return {
        "status": "seeded",
        "servers": created_servers,
        "outbounds": created_outbounds,
        "metrics": created_metrics,
        "checks": created_checks,
    }
