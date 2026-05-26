"""SSH Remote Management for Veltrix.

Allows automatic server restart via SSH when a server is detected as down.
Validates that the SSH target IP matches the server/outbound IP for safety.

Security:
- SSH credentials are encrypted at rest (AES-256)
- IP validation prevents accidental restart of wrong server
- Configurable cooldown between restart attempts
- Maximum retry limit per incident
"""
from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .crypto import decrypt_value, encrypt_value
from .db import connect, now_iso, row_to_dict, rows_to_dicts


# Configuration
RESTART_COOLDOWN_MINUTES = int(os.getenv("OUTPANEL_RESTART_COOLDOWN", "10"))
MAX_RESTARTS_PER_INCIDENT = int(os.getenv("OUTPANEL_MAX_RESTARTS", "3"))
DEFAULT_SSH_PORT = 22
DEFAULT_RESTART_COMMAND = "systemctl restart xray 2>/dev/null || systemctl restart x-ui 2>/dev/null || reboot"


# ---------------------------------------------------------------------------
# SSH Credential Management
# ---------------------------------------------------------------------------

def save_ssh_credentials(server_id: int, ssh_host: str, ssh_port: int,
                         ssh_user: str, ssh_password: str,
                         restart_enabled: bool = True,
                         restart_delay_minutes: int = 5,
                         restart_command: str = "") -> dict[str, Any]:
    """Save SSH credentials for a server (encrypted)."""
    # Validate server exists and IP matches
    with connect() as conn:
        server = row_to_dict(conn.execute(
            "SELECT id, name, host FROM servers WHERE id = ?", (server_id,)
        ).fetchone())

    if not server:
        raise ValueError("Server not found.")

    # Validate IP match for safety
    server_host = server.get("host", "").strip()
    ssh_host_clean = ssh_host.strip()

    if not _validate_ip_match(server_host, ssh_host_clean):
        raise ValueError(
            f"SSH host ({ssh_host_clean}) does not match server host ({server_host}). "
            "For safety, SSH target must match the server IP/domain."
        )

    # Encrypt password
    encrypted_password = encrypt_value(ssh_password)

    ts = now_iso()
    with connect() as conn:
        # Check if SSH config already exists
        existing = conn.execute(
            "SELECT id FROM server_ssh WHERE server_id = ?", (server_id,)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE server_ssh SET
                    ssh_host = ?, ssh_port = ?, ssh_user = ?, ssh_password = ?,
                    restart_enabled = ?, restart_delay_minutes = ?,
                    restart_command = ?, updated_at = ?
                WHERE server_id = ?
            """, (
                ssh_host_clean, ssh_port, ssh_user, encrypted_password,
                1 if restart_enabled else 0, restart_delay_minutes,
                restart_command or DEFAULT_RESTART_COMMAND, ts, server_id,
            ))
        else:
            conn.execute("""
                INSERT INTO server_ssh (
                    server_id, ssh_host, ssh_port, ssh_user, ssh_password,
                    restart_enabled, restart_delay_minutes, restart_command,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                server_id, ssh_host_clean, ssh_port, ssh_user, encrypted_password,
                1 if restart_enabled else 0, restart_delay_minutes,
                restart_command or DEFAULT_RESTART_COMMAND, ts, ts,
            ))

    return {"ok": True, "server_id": server_id}


def get_ssh_config(server_id: int) -> dict[str, Any] | None:
    """Get SSH config for a server (password redacted)."""
    with connect() as conn:
        row = row_to_dict(conn.execute(
            "SELECT * FROM server_ssh WHERE server_id = ?", (server_id,)
        ).fetchone())

    if not row:
        return None

    return {
        "server_id": row["server_id"],
        "ssh_host": row["ssh_host"],
        "ssh_port": row["ssh_port"],
        "ssh_user": row["ssh_user"],
        "has_password": bool(row.get("ssh_password")),
        "restart_enabled": bool(row.get("restart_enabled")),
        "restart_delay_minutes": row.get("restart_delay_minutes", 5),
        "restart_command": row.get("restart_command", DEFAULT_RESTART_COMMAND),
        "last_restart_at": row.get("last_restart_at"),
        "restart_count": row.get("restart_count", 0),
    }


def delete_ssh_config(server_id: int) -> None:
    """Remove SSH config for a server."""
    with connect() as conn:
        conn.execute("DELETE FROM server_ssh WHERE server_id = ?", (server_id,))


def list_ssh_configs() -> list[dict[str, Any]]:
    """List all SSH configs (passwords redacted)."""
    with connect() as conn:
        rows = rows_to_dicts(conn.execute("""
            SELECT server_ssh.*, servers.name as server_name, servers.host as server_host
            FROM server_ssh
            JOIN servers ON servers.id = server_ssh.server_id
            ORDER BY server_ssh.server_id
        """).fetchall())

    result = []
    for row in rows:
        row.pop("ssh_password", None)
        row["has_password"] = True
        result.append(row)
    return result


# ---------------------------------------------------------------------------
# Auto-Restart Logic
# ---------------------------------------------------------------------------

def check_and_restart_servers() -> list[dict[str, Any]]:
    """Check all servers with SSH config and restart if needed.

    Called by the worker loop. Only restarts if:
    1. Server status is 'error' for longer than restart_delay_minutes
    2. Cooldown period has passed since last restart
    3. Max restart count not exceeded
    4. restart_enabled is True
    """
    results = []

    with connect() as conn:
        configs = rows_to_dicts(conn.execute("""
            SELECT server_ssh.*, servers.name as server_name,
                   servers.host as server_host, servers.last_status,
                   servers.last_checked_at
            FROM server_ssh
            JOIN servers ON servers.id = server_ssh.server_id
            WHERE server_ssh.restart_enabled = 1
              AND servers.enabled = 1
              AND servers.last_status = 'error'
        """).fetchall())

    for config in configs:
        server_id = config["server_id"]
        delay_minutes = config.get("restart_delay_minutes", 5)
        last_restart = config.get("last_restart_at")
        restart_count = config.get("restart_count", 0)

        # Check if server has been down long enough
        last_checked = config.get("last_checked_at")
        if not last_checked:
            continue

        try:
            checked_dt = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            down_minutes = (now - checked_dt).total_seconds() / 60

            if down_minutes < delay_minutes:
                continue  # Not down long enough
        except (ValueError, TypeError):
            continue

        # Check cooldown
        if last_restart:
            try:
                last_restart_dt = datetime.fromisoformat(last_restart.replace("Z", "+00:00"))
                cooldown_elapsed = (now - last_restart_dt).total_seconds() / 60
                if cooldown_elapsed < RESTART_COOLDOWN_MINUTES:
                    continue  # Still in cooldown
            except (ValueError, TypeError):
                pass

        # Check max restarts
        if restart_count >= MAX_RESTARTS_PER_INCIDENT:
            continue  # Too many restarts

        # Perform restart
        result = _execute_restart(config)
        results.append(result)

        # Update restart tracking
        ts = now_iso()
        with connect() as conn:
            conn.execute("""
                UPDATE server_ssh SET
                    last_restart_at = ?, restart_count = restart_count + 1, updated_at = ?
                WHERE server_id = ?
            """, (ts, ts, server_id))

            # Log the restart as an incident
            conn.execute("""
                INSERT INTO incidents (
                    server_id, kind, severity, title, message, status,
                    first_seen_at, last_seen_at, created_at, updated_at
                ) VALUES (?, 'server.auto_restart', 'warning', ?, ?, 'open', ?, ?, ?, ?)
            """, (
                server_id,
                f"Auto-restart: {config['server_name']}",
                f"Server {config['server_name']} was automatically restarted via SSH after being down for {int(down_minutes)} minutes.",
                ts, ts, ts, ts,
            ))

    return results


def reset_restart_count(server_id: int) -> None:
    """Reset the restart counter (called when server comes back online)."""
    with connect() as conn:
        conn.execute(
            "UPDATE server_ssh SET restart_count = 0, updated_at = ? WHERE server_id = ?",
            (now_iso(), server_id),
        )


def _execute_restart(config: dict[str, Any]) -> dict[str, Any]:
    """Execute SSH restart command on a server."""
    ssh_host = config["ssh_host"]
    ssh_port = config.get("ssh_port", DEFAULT_SSH_PORT)
    ssh_user = config["ssh_user"]
    ssh_password = decrypt_value(config.get("ssh_password", ""))
    command = config.get("restart_command", DEFAULT_RESTART_COMMAND)
    server_name = config.get("server_name", "unknown")

    try:
        # Use sshpass for password-based SSH (non-interactive)
        ssh_cmd = [
            "sshpass", "-p", ssh_password,
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=no",
            "-p", str(ssh_port),
            f"{ssh_user}@{ssh_host}",
            command,
        ]

        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return {
                "server_id": config["server_id"],
                "server_name": server_name,
                "status": "restarted",
                "output": result.stdout[:200],
            }
        else:
            return {
                "server_id": config["server_id"],
                "server_name": server_name,
                "status": "failed",
                "error": result.stderr[:200] or f"Exit code: {result.returncode}",
            }

    except subprocess.TimeoutExpired:
        return {
            "server_id": config["server_id"],
            "server_name": server_name,
            "status": "timeout",
            "error": "SSH connection timed out.",
        }
    except FileNotFoundError:
        # sshpass not installed — try without password (key-based)
        return _execute_restart_keyonly(config)
    except Exception as exc:
        return {
            "server_id": config["server_id"],
            "server_name": server_name,
            "status": "error",
            "error": str(exc)[:200],
        }


def _execute_restart_keyonly(config: dict[str, Any]) -> dict[str, Any]:
    """Fallback: SSH restart using key-based auth (no password)."""
    ssh_host = config["ssh_host"]
    ssh_port = config.get("ssh_port", DEFAULT_SSH_PORT)
    ssh_user = config["ssh_user"]
    command = config.get("restart_command", DEFAULT_RESTART_COMMAND)

    try:
        ssh_cmd = [
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",
            "-p", str(ssh_port),
            f"{ssh_user}@{ssh_host}",
            command,
        ]

        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)

        return {
            "server_id": config["server_id"],
            "server_name": config.get("server_name", "unknown"),
            "status": "restarted" if result.returncode == 0 else "failed",
            "error": result.stderr[:200] if result.returncode != 0 else None,
            "note": "Used key-based auth (sshpass not installed)",
        }
    except Exception as exc:
        return {
            "server_id": config["server_id"],
            "server_name": config.get("server_name", "unknown"),
            "status": "error",
            "error": f"SSH failed: {exc}. Install sshpass for password auth.",
        }


def _validate_ip_match(server_host: str, ssh_host: str) -> bool:
    """Validate that SSH host matches the server host (IP or domain).

    This prevents accidentally restarting the wrong server.
    """
    if not server_host or not ssh_host:
        return False

    # Direct match
    if server_host.lower() == ssh_host.lower():
        return True

    # Resolve both to IP and compare
    try:
        server_ip = socket.gethostbyname(server_host)
        ssh_ip = socket.gethostbyname(ssh_host)
        return server_ip == ssh_ip
    except (socket.gaierror, OSError):
        pass

    return False


# ---------------------------------------------------------------------------
# Database schema for SSH configs
# ---------------------------------------------------------------------------

def init_ssh_table() -> None:
    """Create the server_ssh table if it doesn't exist."""
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS server_ssh (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER NOT NULL UNIQUE REFERENCES servers(id) ON DELETE CASCADE,
                ssh_host TEXT NOT NULL,
                ssh_port INTEGER NOT NULL DEFAULT 22,
                ssh_user TEXT NOT NULL DEFAULT 'root',
                ssh_password TEXT,
                restart_enabled INTEGER NOT NULL DEFAULT 1,
                restart_delay_minutes INTEGER NOT NULL DEFAULT 5,
                restart_command TEXT NOT NULL DEFAULT 'systemctl restart xray',
                last_restart_at TEXT,
                restart_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
