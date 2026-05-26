"""Two-Factor Authentication (2FA) with TOTP for Veltrix.

Implements RFC 6238 TOTP (Time-based One-Time Password) for admin login security.
Compatible with Google Authenticator, Authy, and other TOTP apps.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from typing import Any

from .db import connect, now_iso


# TOTP Configuration
TOTP_DIGITS = 6
TOTP_PERIOD = 30  # seconds
TOTP_ALGORITHM = "sha1"
TOTP_ISSUER = "Veltrix"
TOTP_WINDOW = 1  # Allow 1 period before/after for clock skew


def generate_secret() -> str:
    """Generate a new TOTP secret (base32 encoded, 20 bytes)."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def get_totp_uri(secret: str, username: str, issuer: str = TOTP_ISSUER) -> str:
    """Generate an otpauth:// URI for QR code generation.

    Format: otpauth://totp/Issuer:username?secret=XXX&issuer=Issuer&digits=6&period=30
    """
    import urllib.parse
    label = urllib.parse.quote(f"{issuer}:{username}")
    params = urllib.parse.urlencode({
        "secret": secret,
        "issuer": issuer,
        "digits": TOTP_DIGITS,
        "period": TOTP_PERIOD,
        "algorithm": TOTP_ALGORITHM.upper(),
    })
    return f"otpauth://totp/{label}?{params}"


def compute_totp(secret: str, timestamp: int | None = None) -> str:
    """Compute the current TOTP code for a given secret."""
    if timestamp is None:
        timestamp = int(time.time())

    # Decode base32 secret (add padding if needed)
    padded = secret + "=" * (8 - len(secret) % 8) if len(secret) % 8 else secret
    try:
        key = base64.b32decode(padded.upper())
    except Exception:
        return ""

    # Calculate time counter
    counter = timestamp // TOTP_PERIOD

    # HMAC-SHA1
    counter_bytes = struct.pack(">Q", counter)
    mac = hmac.new(key, counter_bytes, hashlib.sha1).digest()

    # Dynamic truncation
    offset = mac[-1] & 0x0F
    code_int = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    code = code_int % (10 ** TOTP_DIGITS)

    return str(code).zfill(TOTP_DIGITS)


def verify_totp(secret: str, code: str, window: int = TOTP_WINDOW) -> bool:
    """Verify a TOTP code against a secret.

    Checks current time period and +/- window periods for clock skew tolerance.
    """
    if not secret or not code or len(code) != TOTP_DIGITS:
        return False

    now = int(time.time())
    for offset in range(-window, window + 1):
        timestamp = now + (offset * TOTP_PERIOD)
        expected = compute_totp(secret, timestamp)
        if hmac.compare_digest(code, expected):
            return True

    return False


# ---------------------------------------------------------------------------
# Database operations for 2FA
# ---------------------------------------------------------------------------

def enable_2fa(user_id: int) -> dict[str, Any]:
    """Generate and store a 2FA secret for a user. Returns secret + URI."""
    secret = generate_secret()
    ts = now_iso()

    with connect() as conn:
        user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise ValueError("User not found.")

        # Store secret (not yet verified — user must confirm with a code first)
        conn.execute("""
            INSERT OR REPLACE INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (f"2fa_pending_{user_id}", secret, ts))

    username = user["username"]
    uri = get_totp_uri(secret, username)

    return {
        "secret": secret,
        "uri": uri,
        "qr_data": uri,  # Frontend can generate QR from this
        "issuer": TOTP_ISSUER,
        "digits": TOTP_DIGITS,
        "period": TOTP_PERIOD,
    }


def confirm_2fa(user_id: int, code: str) -> bool:
    """Confirm 2FA setup by verifying the first code. Activates 2FA."""
    with connect() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (f"2fa_pending_{user_id}",),
        ).fetchone()

        if not row:
            raise ValueError("No pending 2FA setup found. Start setup first.")

        secret = row["value"]
        if not verify_totp(secret, code):
            return False

        # Activate: move from pending to active
        ts = now_iso()
        conn.execute("""
            INSERT OR REPLACE INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (f"2fa_active_{user_id}", secret, ts))
        conn.execute("DELETE FROM app_settings WHERE key = ?", (f"2fa_pending_{user_id}",))

    return True


def disable_2fa(user_id: int) -> None:
    """Disable 2FA for a user."""
    with connect() as conn:
        conn.execute("DELETE FROM app_settings WHERE key = ?", (f"2fa_active_{user_id}",))
        conn.execute("DELETE FROM app_settings WHERE key = ?", (f"2fa_pending_{user_id}",))


def is_2fa_enabled(user_id: int) -> bool:
    """Check if 2FA is active for a user."""
    with connect() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (f"2fa_active_{user_id}",),
        ).fetchone()
    return row is not None


def validate_2fa_code(user_id: int, code: str) -> bool:
    """Validate a 2FA code during login."""
    with connect() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (f"2fa_active_{user_id}",),
        ).fetchone()

    if not row:
        return True  # 2FA not enabled — always pass

    return verify_totp(row["value"], code)


def get_2fa_status(user_id: int) -> dict[str, Any]:
    """Get 2FA status for a user."""
    return {
        "enabled": is_2fa_enabled(user_id),
        "user_id": user_id,
    }
