from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connect, now_iso, row_to_dict, rows_to_dicts


ROLE_OWNER = "owner"
ROLE_MANAGER = "manager"
MANAGER_LIMIT = 10
HASH_ITERATIONS = 260_000
SESSION_DAYS = 7
LOGIN_WINDOW_MINUTES = 15
LOGIN_MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

PERMISSION_CATALOG = [
    {
        "key": "servers",
        "label": "Servers",
        "description": "Register, edit, delete, synchronize, and monitor servers",
    },
    {
        "key": "outbounds",
        "label": "Outbounds",
        "description": "View outbound connections and test ping routes",
    },
    {
        "key": "history",
        "label": "Analytics",
        "description": "View CPU/RAM charts and ping history",
    },
    {
        "key": "incidents",
        "label": "Incidents",
        "description": "View, confirm, and close active incidents and alerts",
    },
    {
        "key": "notifications",
        "label": "Notification Channels",
        "description": "Create and manage Telegram and Webhook channels",
    },
    {
        "key": "license",
        "label": "License",
        "description": "View license status and activate a license key",
    },
    {
        "key": "users",
        "label": "Managers",
        "description": "Create managers, assign permissions, and view security logs",
    },
    {
        "key": "maintenance",
        "label": "Backup & Maintenance",
        "description": "Create, download, delete, and restore Veltrix backups",
    },
]

PERMISSION_KEYS = tuple(item["key"] for item in PERMISSION_CATALOG)
MANAGER_PERMISSION_KEYS = tuple(key for key in PERMISSION_KEYS if key != "users")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,40}$")


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def permission_catalog() -> list[dict[str, str]]:
    return [dict(item) for item in PERMISSION_CATALOG]


def all_permissions() -> list[str]:
    return list(PERMISSION_KEYS)


def manager_permissions() -> list[str]:
    return list(MANAGER_PERMISSION_KEYS)


def has_permission(user: dict[str, Any] | None, permission: str) -> bool:
    if not user:
        return False
    if user.get("role") == ROLE_OWNER:
        return True
    permissions = user.get("permissions")
    if permissions is None:
        permissions = parse_permissions(user)
    return permission in set(permissions or [])


def parse_permissions(user: dict[str, Any]) -> list[str]:
    """Parse permissions from user dict or permissions_json field."""
    perms = user.get("permissions")
    if isinstance(perms, list):
        return perms
    raw = user.get("permissions_json", "[]")
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        parsed = []
    return parsed if isinstance(parsed, list) else []


# ---------------------------------------------------------------------------
# Public user representation
# ---------------------------------------------------------------------------

def public_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if not user:
        return None
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "display_name": user.get("display_name"),
        "role": user.get("role"),
        "active": int(user.get("active", 1)),
        "permissions": all_permissions() if user.get("role") == ROLE_OWNER else parse_permissions(user),
        "last_login_at": user.get("last_login_at"),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
    }


def service_user() -> dict[str, Any]:
    return {
        "id": None,
        "username": "api-token",
        "display_name": "API Token",
        "role": ROLE_OWNER,
        "active": 1,
        "permissions": all_permissions(),
    }


# ---------------------------------------------------------------------------
# Auth status & setup
# ---------------------------------------------------------------------------

def auth_status(token: str | None = None) -> dict[str, Any]:
    """Return authentication status and setup requirement."""
    with connect() as conn:
        user_count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    user = get_user_by_session(token) if token else None
    return {
        "requires_setup": user_count == 0,
        "authenticated": bool(user),
        "user": public_user(user),
        "permissions": permission_catalog(),
        "manager_limit": MANAGER_LIMIT,
    }


def setup_owner(payload: dict[str, Any], ip_address: str | None = None) -> dict[str, Any]:
    """Create the main owner/admin account."""
    with connect() as conn:
        user_count = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        if user_count:
            raise ValueError("The main owner account has already been created.")
        username = normalize_username(payload.get("username") or "admin")
        display_name = normalize_display_name(payload.get("display_name") or "Main Owner")
        password = validate_password(payload.get("password"))
        ts = now_iso()
        cursor = conn.execute(
            """
            INSERT INTO users (
                username, display_name, role, password_hash, permissions_json,
                active, created_at, updated_at
            )
            VALUES (?, ?, 'owner', ?, ?, 1, ?, ?)
            """,
            (username, display_name, hash_password(password), json.dumps(all_permissions()), ts, ts),
        )
        user_id = cursor.lastrowid
        token = create_session(conn, user_id)
        record_audit_conn(
            conn,
            {"id": user_id, "username": username},
            "auth.setup_owner",
            "user",
            user_id,
            {"username": username},
            ip_address,
        )
    return {"token": token, "user": public_user(get_user_by_id(user_id))}


# ---------------------------------------------------------------------------
# Login / Logout / Password
# ---------------------------------------------------------------------------

def login(payload: dict[str, Any], ip_address: str | None, user_agent: str | None) -> dict[str, Any]:
    """Authenticate a user and create a session token."""
    username = normalize_username(payload.get("username"))
    password = str(payload.get("password") or "")
    with connect() as conn:
        cleanup_expired_sessions_conn(conn)
        ensure_login_allowed(conn, username, ip_address)
        user = row_to_dict(conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone())
        if not user or not user.get("active") or not verify_password(password, user["password_hash"]):
            record_audit_conn(conn, None, "auth.login_failed", "user", None, {"username": username}, ip_address)
            conn.commit()
            raise ValueError("Incorrect username or password.")
        token = create_session(conn, int(user["id"]), user_agent)
        ts = now_iso()
        conn.execute("UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?", (ts, ts, user["id"]))
        user["last_login_at"] = ts
        record_audit_conn(conn, user, "auth.login", "user", user["id"], {}, ip_address)
    return {"token": token, "user": public_user(user)}


def change_password(user: dict[str, Any] | None, payload: dict[str, Any], ip_address: str | None, current_token: str | None = None) -> dict[str, Any]:
    """Change the password for the logged-in user."""
    if not user or not user.get("id"):
        raise PermissionError("You must be logged in to change your password.")
    current_password = str(payload.get("current_password") or "")
    new_password = validate_password(payload.get("new_password"))
    if current_password == new_password:
        raise ValueError("The new password must be different from the current one.")

    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT * FROM users WHERE id = ?", (int(user["id"]),)).fetchone())
        if not existing or not existing.get("active"):
            raise PermissionError("The user account is not active.")
        if not verify_password(current_password, existing["password_hash"]):
            record_audit_conn(conn, existing, "auth.password_change_failed", "user", existing["id"], {}, ip_address)
            conn.commit()
            raise ValueError("The current password is incorrect.")

        ts = now_iso()
        conn.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?", (hash_password(new_password), ts, existing["id"]))
        if current_token:
            conn.execute("DELETE FROM user_sessions WHERE user_id = ? AND token_hash != ?", (existing["id"], session_token_hash(current_token)))
        else:
            conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (existing["id"],))
        record_audit_conn(conn, existing, "auth.password_change", "user", existing["id"], {}, ip_address)
    return {"ok": True}


def logout(token: str | None, actor: dict[str, Any] | None, ip_address: str | None) -> None:
    """Logout the current session by deleting the session token."""
    if not token:
        return
    token_hash = session_token_hash(token)
    with connect() as conn:
        conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash,))
        record_audit_conn(conn, actor, "auth.logout", "session", None, {}, ip_address)


# ---------------------------------------------------------------------------
# Manager CRUD
# ---------------------------------------------------------------------------

def list_users() -> list[dict[str, Any]]:
    """List all users (owner and managers)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY role DESC, id ASC"
        ).fetchall()
    return [public_user(row_to_dict(row)) for row in rows]


def create_manager(payload: dict[str, Any], actor: dict[str, Any] | None, ip_address: str | None) -> dict[str, Any]:
    """Create a new manager account."""
    with connect() as conn:
        manager_count = conn.execute(
            "SELECT COUNT(*) AS count FROM users WHERE role = ?", (ROLE_MANAGER,)
        ).fetchone()["count"]
        if manager_count >= MANAGER_LIMIT:
            raise ValueError(f"Maximum number of managers ({MANAGER_LIMIT}) reached.")

        username = normalize_username(payload.get("username"))
        display_name = normalize_display_name(payload.get("display_name") or username)
        password = validate_password(payload.get("password"))
        permissions = validate_manager_permissions(payload.get("permissions"))
        active = 1 if payload.get("active", True) else 0

        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise ValueError(f"Username '{username}' is already taken.")

        ts = now_iso()
        cursor = conn.execute(
            """
            INSERT INTO users (
                username, display_name, role, password_hash, permissions_json,
                active, created_by, created_at, updated_at
            )
            VALUES (?, ?, 'manager', ?, ?, ?, ?, ?, ?)
            """,
            (
                username, display_name, hash_password(password),
                json.dumps(permissions), active,
                actor.get("id") if actor else None, ts, ts,
            ),
        )
        user_id = cursor.lastrowid
        record_audit_conn(conn, actor, "user.create_manager", "user", user_id,
                          {"username": username, "permissions": permissions}, ip_address)
    return public_user(get_user_by_id(user_id)) or {}


def update_manager(manager_id: int, payload: dict[str, Any], actor: dict[str, Any] | None, ip_address: str | None) -> dict[str, Any]:
    """Update an existing manager account."""
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT * FROM users WHERE id = ?", (manager_id,)).fetchone())
        if not existing:
            raise ValueError("Manager not found.")
        if existing["role"] == ROLE_OWNER:
            raise PermissionError("Cannot modify the owner account through this endpoint.")

        display_name = normalize_display_name(payload.get("display_name") or existing["display_name"])
        permissions = validate_manager_permissions(payload.get("permissions") or parse_permissions(existing))
        active = 1 if payload.get("active", existing["active"]) else 0

        ts = now_iso()
        updates = "display_name = ?, permissions_json = ?, active = ?, updated_at = ?"
        params: list[Any] = [display_name, json.dumps(permissions), active, ts]

        # Update password if provided
        new_password = payload.get("password")
        if new_password:
            validated = validate_password(new_password)
            updates = "display_name = ?, permissions_json = ?, active = ?, password_hash = ?, updated_at = ?"
            params = [display_name, json.dumps(permissions), active, hash_password(validated), ts]

        params.append(manager_id)
        conn.execute(f"UPDATE users SET {updates} WHERE id = ?", tuple(params))

        # Deactivate sessions if account disabled
        if not active:
            conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (manager_id,))

        record_audit_conn(conn, actor, "user.update_manager", "user", manager_id,
                          {"display_name": display_name, "permissions": permissions, "active": active}, ip_address)
    return public_user(get_user_by_id(manager_id)) or {}


def delete_manager(manager_id: int, actor: dict[str, Any] | None, ip_address: str | None) -> None:
    """Delete a manager account."""
    with connect() as conn:
        existing = row_to_dict(conn.execute("SELECT * FROM users WHERE id = ?", (manager_id,)).fetchone())
        if not existing:
            raise ValueError("Manager not found.")
        if existing["role"] == ROLE_OWNER:
            raise PermissionError("Cannot delete the owner account.")
        conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (manager_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (manager_id,))
        record_audit_conn(conn, actor, "user.delete_manager", "user", manager_id,
                          {"username": existing["username"]}, ip_address)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def create_session(conn: Any, user_id: int, user_agent: str | None = None) -> str:
    """Create a new session token for a user."""
    token = secrets.token_urlsafe(48)
    token_hash = session_token_hash(token)
    ts = now_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO user_sessions (token_hash, user_id, user_agent, expires_at, created_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (token_hash, user_id, user_agent, expires_at, ts, ts),
    )
    return token


def get_user_by_session(token: str | None) -> dict[str, Any] | None:
    """Retrieve user by session token."""
    if not token:
        return None
    token_hash = session_token_hash(token)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT users.* FROM users
            JOIN user_sessions ON user_sessions.user_id = users.id
            WHERE user_sessions.token_hash = ?
              AND user_sessions.expires_at > ?
              AND users.active = 1
            """,
            (token_hash, now_iso()),
        ).fetchone()
        if row:
            # Update last_seen_at
            conn.execute(
                "UPDATE user_sessions SET last_seen_at = ? WHERE token_hash = ?",
                (now_iso(), token_hash),
            )
        return row_to_dict(row)


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """Retrieve user by ID."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row_to_dict(row)


def cleanup_expired_sessions_conn(conn: Any) -> None:
    """Remove expired sessions."""
    conn.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now_iso(),))


def session_token_hash(token: str) -> str:
    """Hash a session token for storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def ensure_login_allowed(conn: Any, username: str, ip_address: str | None) -> None:
    """Check if login attempts are within rate limits."""
    window_start = (
        datetime.now(timezone.utc) - timedelta(minutes=LOGIN_WINDOW_MINUTES)
    ).isoformat(timespec="seconds")

    # Check by username
    count = conn.execute(
        """
        SELECT COUNT(*) AS count FROM audit_logs
        WHERE action = 'auth.login_failed'
          AND detail_json LIKE ?
          AND created_at > ?
        """,
        (f'%"{username}"%', window_start),
    ).fetchone()["count"]

    if count >= LOGIN_MAX_ATTEMPTS:
        raise ValueError(
            f"Too many failed login attempts. Please try again in {LOCKOUT_MINUTES} minutes."
        )

    # Check by IP
    if ip_address:
        ip_count = conn.execute(
            """
            SELECT COUNT(*) AS count FROM audit_logs
            WHERE action = 'auth.login_failed'
              AND ip_address = ?
              AND created_at > ?
            """,
            (ip_address, window_start),
        ).fetchone()["count"]
        if ip_count >= LOGIN_MAX_ATTEMPTS * 3:
            raise ValueError(
                f"Too many failed login attempts from this IP. Please try again in {LOCKOUT_MINUTES} minutes."
            )


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def record_audit(
    actor: dict[str, Any] | None,
    action: str,
    target_type: str | None,
    target_id: int | str | None,
    details: dict[str, Any],
    ip_address: str | None,
) -> None:
    """Record an audit log entry."""
    with connect() as conn:
        record_audit_conn(conn, actor, action, target_type, target_id, details, ip_address)


def record_audit_conn(
    conn: Any,
    actor: dict[str, Any] | None,
    action: str,
    target_type: str | None,
    target_id: int | str | None,
    details: dict[str, Any],
    ip_address: str | None,
) -> None:
    """Record an audit log entry using an existing connection."""
    conn.execute(
        """
        INSERT INTO audit_logs (
            actor_user_id, actor_username, action, target_type, target_id,
            detail_json, ip_address, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor.get("id") if actor else None,
            actor.get("username") if actor else None,
            action,
            target_type,
            str(target_id) if target_id is not None else None,
            json.dumps(details, ensure_ascii=False),
            ip_address,
            now_iso(),
        ),
    )


def list_audit_logs(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """List audit log entries."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-SHA256."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    key_b64 = base64.b64encode(key).decode("ascii")
    return f"pbkdf2:sha256:{HASH_ITERATIONS}${salt_b64}${key_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash."""
    if not password or not password_hash:
        return False
    try:
        parts = password_hash.split("$")
        if len(parts) != 3:
            return False
        header = parts[0]
        salt_b64 = parts[1]
        key_b64 = parts[2]
        iterations = int(header.split(":")[-1])
        salt = base64.b64decode(salt_b64)
        expected_key = base64.b64decode(key_b64)
        actual_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual_key, expected_key)
    except (ValueError, IndexError):
        return False


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def normalize_username(value: Any) -> str:
    """Normalize and validate a username."""
    username = str(value or "").strip().lower()
    if not username:
        raise ValueError("Username is required.")
    if not USERNAME_PATTERN.match(username):
        raise ValueError("Username must be 3-40 characters: letters, digits, underscore, dot, or dash.")
    return username


def normalize_display_name(value: Any) -> str:
    """Normalize a display name."""
    name = str(value or "").strip()
    if not name:
        raise ValueError("Display name is required.")
    if len(name) > 80:
        raise ValueError("Display name must be 80 characters or fewer.")
    return name


def validate_password(value: Any) -> str:
    """Validate password strength."""
    password = str(value or "")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(password) > 128:
        raise ValueError("Password must be 128 characters or fewer.")
    return password


def validate_manager_permissions(permissions: Any) -> list[str]:
    """Validate and filter manager permissions."""
    if not isinstance(permissions, list):
        return []
    valid = set(MANAGER_PERMISSION_KEYS)
    return [p for p in permissions if isinstance(p, str) and p in valid]
