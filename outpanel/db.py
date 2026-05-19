from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "veltrix.db"
LEGACY_DB_PATH = DATA_DIR / "outpanel.db"


def now_iso() -> str:
    """Return the current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_path() -> Path:
    """Determine the database file path, checking environment or legacy DB."""
    configured = os.getenv("OUTPANEL_DB")
    if configured:
        return Path(configured).expanduser().resolve()
    if LEGACY_DB_PATH.exists() and not DEFAULT_DB_PATH.exists():
        return LEGACY_DB_PATH.resolve()
    return DEFAULT_DB_PATH.resolve()


def connect() -> sqlite3.Connection:
    """Create a SQLite connection with WAL and foreign keys enabled."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) or {} for row in rows]


def init_db() -> None:
    """Initialize database schema for Veltrix OutPanel."""
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                host TEXT NOT NULL,
                panel_url TEXT,
                username TEXT,
                password TEXT,
                verify_tls INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                cpu_warn REAL NOT NULL DEFAULT 85,
                ram_warn REAL NOT NULL DEFAULT 85,
                ping_warn_ms INTEGER NOT NULL DEFAULT 350,
                timeout_ms INTEGER NOT NULL DEFAULT 2500,
                last_status TEXT NOT NULL DEFAULT 'unknown',
                last_error TEXT,
                last_checked_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS outbounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                xui_id TEXT,
                remark TEXT NOT NULL,
                protocol TEXT,
                address TEXT NOT NULL,
                port INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_ping_ms REAL,
                last_status TEXT NOT NULL DEFAULT 'unknown',
                last_error TEXT,
                last_checked_at TEXT,
                up_bytes INTEGER NOT NULL DEFAULT 0,
                down_bytes INTEGER NOT NULL DEFAULT 0,
                total_bytes INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(server_id, xui_id)
            );

            CREATE INDEX IF NOT EXISTS idx_outbounds_server_id
                ON outbounds(server_id);

            CREATE INDEX IF NOT EXISTS idx_outbounds_status
                ON outbounds(last_status);

            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                cpu_percent REAL,
                ram_percent REAL,
                ram_used INTEGER,
                ram_total INTEGER,
                disk_percent REAL,
                xray_status TEXT,
                uptime TEXT,
                raw_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_metrics_server_created
                ON metrics(server_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS outbound_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                outbound_id INTEGER NOT NULL REFERENCES outbounds(id) ON DELETE CASCADE,
                server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                latency_ms REAL,
                status TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_outbound_checks_outbound_created
                ON outbound_checks(outbound_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_outbound_checks_server_created
                ON outbound_checks(server_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
                outbound_id INTEGER REFERENCES outbounds(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                seen_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_alerts_active
                ON alerts(active, created_at DESC);

            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
                outbound_id INTEGER REFERENCES outbounds(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                acknowledged_at TEXT,
                acknowledged_by TEXT,
                recovered_at TEXT,
                recovery_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_incidents_status
                ON incidents(status, last_seen_at DESC);

            CREATE INDEX IF NOT EXISTS idx_incidents_scope
                ON incidents(kind, server_id, outbound_id, status);

            CREATE TABLE IF NOT EXISTS notification_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                config_json TEXT NOT NULL,
                last_error TEXT,
                last_sent_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_notification_channels_enabled
                ON notification_channels(enabled, type);

            CREATE TABLE IF NOT EXISTS notification_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL REFERENCES notification_channels(id) ON DELETE CASCADE,
                incident_id INTEGER REFERENCES incidents(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(channel_id, incident_id, event_type)
            );

            CREATE INDEX IF NOT EXISTS idx_notification_deliveries_incident
                ON notification_deliveries(incident_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('owner', 'manager')),
                password_hash TEXT NOT NULL,
                permissions_json TEXT NOT NULL DEFAULT '[]',
                active INTEGER NOT NULL DEFAULT 1,
                created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                last_login_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_role
                ON users(role, active);

            CREATE TABLE IF NOT EXISTS user_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                user_agent TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_user_sessions_user
                ON user_sessions(user_id, expires_at);

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                actor_username TEXT,
                action TEXT NOT NULL,
                target_type TEXT,
                target_id TEXT,
                detail_json TEXT NOT NULL DEFAULT '{}',
                ip_address TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_logs_created
                ON audit_logs(created_at DESC);
            """
        )


def seed_demo_if_empty() -> None:
    """Populate demo data if database is empty for first boot."""
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS count FROM servers").fetchone()["count"]
        if count:
            return
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO servers (
                name, host, panel_url, username, password, verify_tls, enabled,
                cpu_warn, ram_warn, ping_warn_ms, timeout_ms,
                last_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Demo Server",
                "127.0.0.1",
                "",
                "",
                "",
                1,
                0,
                85,
                85,
                350,
                2500,
                "disabled",
                ts,
                ts,
            ),
        )
