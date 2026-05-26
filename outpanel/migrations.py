"""Database migration system for Veltrix.

Manages schema changes across versions without data loss.
Migrations are defined as sequential functions and tracked in a migrations table.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from .db import connect, now_iso


MigrationFn = Callable[[Any], None]

# Registry of all migrations in order
_MIGRATIONS: list[tuple[str, str, MigrationFn]] = []


def migration(version: str, description: str) -> Callable[[MigrationFn], MigrationFn]:
    """Decorator to register a migration function."""
    def decorator(fn: MigrationFn) -> MigrationFn:
        _MIGRATIONS.append((version, description, fn))
        return fn
    return decorator


def ensure_migrations_table() -> None:
    """Create the migrations tracking table if it doesn't exist."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                description TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                checksum TEXT
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_migrations_version
            ON _migrations(version)
        """)


def get_applied_migrations() -> set[str]:
    """Get the set of already-applied migration versions."""
    ensure_migrations_table()
    with connect() as conn:
        rows = conn.execute("SELECT version FROM _migrations ORDER BY id").fetchall()
    return {row["version"] for row in rows}


def run_pending_migrations() -> list[dict[str, Any]]:
    """Run all pending migrations in order. Returns list of applied migrations."""
    ensure_migrations_table()
    applied = get_applied_migrations()
    results: list[dict[str, Any]] = []

    for version, description, fn in _MIGRATIONS:
        if version in applied:
            continue

        with connect() as conn:
            try:
                fn(conn)
                conn.execute(
                    "INSERT INTO _migrations (version, description, applied_at) VALUES (?, ?, ?)",
                    (version, description, now_iso()),
                )
                results.append({
                    "version": version,
                    "description": description,
                    "status": "applied",
                    "applied_at": now_iso(),
                })
            except Exception as exc:
                results.append({
                    "version": version,
                    "description": description,
                    "status": "failed",
                    "error": str(exc),
                })
                # Stop on first failure
                break

    return results


def migration_status() -> list[dict[str, Any]]:
    """Get status of all migrations (applied and pending)."""
    applied = get_applied_migrations()
    status = []
    for version, description, _ in _MIGRATIONS:
        status.append({
            "version": version,
            "description": description,
            "applied": version in applied,
        })
    return status


# ---------------------------------------------------------------------------
# Migration definitions
# ---------------------------------------------------------------------------

@migration("0.2.0-001", "Add encrypted flag to servers table")
def m_001_encrypted_flag(conn: Any) -> None:
    """Add column to track if password is encrypted."""
    try:
        conn.execute("ALTER TABLE servers ADD COLUMN password_encrypted INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # Column may already exist


@migration("0.2.0-002", "Add server tags column")
def m_002_server_tags(conn: Any) -> None:
    """Add tags column for server categorization."""
    try:
        conn.execute("ALTER TABLE servers ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE servers ADD COLUMN auth_mode TEXT NOT NULL DEFAULT 'credentials'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE servers ADD COLUMN api_token TEXT")
    except Exception:
        pass


@migration("0.2.0-003", "Add outbound avg_ping and availability columns")
def m_003_outbound_stats(conn: Any) -> None:
    """Add computed stats columns to outbounds for dashboard display."""
    try:
        conn.execute("ALTER TABLE outbounds ADD COLUMN avg_ping_ms REAL")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE outbounds ADD COLUMN availability_percent REAL")
    except Exception:
        pass


@migration("0.2.0-004", "Add reports table")
def m_004_reports_table(conn: Any) -> None:
    """Create reports table for operational reporting."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            data_json TEXT NOT NULL,
            generated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_reports_type_period
        ON reports(type, period_start DESC)
    """)


@migration("0.2.0-005", "Add notification preferences to users")
def m_005_user_preferences(conn: Any) -> None:
    """Add preferences column for user-specific settings."""
    try:
        conn.execute("ALTER TABLE users ADD COLUMN preferences_json TEXT NOT NULL DEFAULT '{}'")
    except Exception:
        pass


@migration("0.2.0-006", "Add dark_mode setting table")
def m_006_settings_table(conn: Any) -> None:
    """Create app settings table for UI preferences."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)


@migration("0.2.0-007", "Add panel_type and traffic_limit columns")
def m_007_panel_type(conn: Any) -> None:
    """Add panel_type to servers and traffic_limit to outbounds."""
    try:
        conn.execute("ALTER TABLE servers ADD COLUMN panel_type TEXT NOT NULL DEFAULT 'x-ui'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE servers ADD COLUMN last_detected_ip TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE outbounds ADD COLUMN traffic_limit INTEGER DEFAULT 0")
    except Exception:
        pass
