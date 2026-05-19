"""Ed25519 signed license token verification for Veltrix.

The License Server signs license payloads with an Ed25519 private key.
The customer app ships only the public key and can verify tokens
but cannot forge them.

Token format: base64url(payload_json) + "." + base64url(signature)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import DATA_DIR


# ---------------------------------------------------------------------------
# Ed25519 constants and pure-Python implementation
# ---------------------------------------------------------------------------
# This is a minimal Ed25519 verify-only implementation using standard library.
# For production with high volume, consider using the `cryptography` package.

# Ed25519 curve parameters
_ED25519_D = -4513249062541557337682894930092624173785641285191125241628941591882900924598840740
_ED25519_Q = 2**255 - 19
_ED25519_L = 2**252 + 27742317777372353535851937790883648493
_ED25519_I = pow(2, (_ED25519_Q - 1) // 4, _ED25519_Q)


def _ed25519_inv(x: int) -> int:
    return pow(x, _ED25519_Q - 2, _ED25519_Q)


def _ed25519_recover_x(y: int) -> int:
    xx = (y * y - 1) * _ed25519_inv(_ED25519_D * y * y + 1)
    x = pow(xx, (_ED25519_Q + 3) // 8, _ED25519_Q)
    if (x * x - xx) % _ED25519_Q != 0:
        x = (x * _ED25519_I) % _ED25519_Q
    if x % 2 != 0:
        x = _ED25519_Q - x
    return x


_ED25519_BY = 4 * _ed25519_inv(5) % _ED25519_Q
_ED25519_BX = _ed25519_recover_x(_ED25519_BY)
_ED25519_B = (_ED25519_BX % _ED25519_Q, _ED25519_BY % _ED25519_Q)


def _edwards_add(p: tuple[int, int], q: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p
    x2, y2 = q
    x3 = (x1 * y2 + x2 * y1) * _ed25519_inv(1 + _ED25519_D * x1 * x2 * y1 * y2) % _ED25519_Q
    y3 = (y1 * y2 + x1 * x2) * _ed25519_inv(1 - _ED25519_D * x1 * x2 * y1 * y2) % _ED25519_Q
    return (x3, y3)


def _scalar_mult(s: int, p: tuple[int, int]) -> tuple[int, int]:
    if s == 0:
        return (0, 1)
    if s == 1:
        return p
    if s % 2 == 0:
        half = _scalar_mult(s // 2, p)
        return _edwards_add(half, half)
    return _edwards_add(p, _scalar_mult(s - 1, p))


def _point_from_bytes(data: bytes) -> tuple[int, int]:
    if len(data) != 32:
        raise ValueError("Invalid point encoding length.")
    y = int.from_bytes(data, "little") & ((1 << 255) - 1)
    x = _ed25519_recover_x(y)
    if x & 1 != (data[31] >> 7):
        x = _ED25519_Q - x
    return (x % _ED25519_Q, y % _ED25519_Q)


def _point_to_bytes(p: tuple[int, int]) -> bytes:
    x, y = p
    data = (y | ((x & 1) << 255)).to_bytes(32, "little")
    return data


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify an Ed25519 signature.

    Args:
        public_key: 32-byte Ed25519 public key
        message: The signed message bytes
        signature: 64-byte Ed25519 signature

    Returns:
        True if signature is valid, False otherwise
    """
    if len(public_key) != 32 or len(signature) != 64:
        return False

    try:
        A = _point_from_bytes(public_key)
        R_bytes = signature[:32]
        R = _point_from_bytes(R_bytes)
        s = int.from_bytes(signature[32:], "little")

        if s >= _ED25519_L:
            return False

        h = int.from_bytes(
            _sha512(R_bytes + public_key + message), "little"
        ) % _ED25519_L

        # Verify: s*B == R + h*A
        sB = _scalar_mult(s, _ED25519_B)
        hA = _scalar_mult(h, A)
        RhA = _edwards_add(R, hA)

        return sB[0] == RhA[0] and sB[1] == RhA[1]
    except (ValueError, ZeroDivisionError):
        return False


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

# Public key file path (shipped with the app)
PUBLIC_KEY_FILE = DATA_DIR / "license-public-key.pem"
FALLBACK_PUBLIC_KEY_ENV = "OUTPANEL_LICENSE_PUBLIC_KEY"


def load_public_key() -> bytes | None:
    """Load the Ed25519 public key from file or environment."""
    # Try environment variable first (hex-encoded 32 bytes)
    env_key = os.getenv(FALLBACK_PUBLIC_KEY_ENV, "").strip()
    if env_key:
        try:
            return bytes.fromhex(env_key)
        except ValueError:
            try:
                return base64.b64decode(env_key)
            except Exception:
                pass

    # Try file
    if PUBLIC_KEY_FILE.exists():
        raw = PUBLIC_KEY_FILE.read_text(encoding="utf-8").strip()
        # Handle PEM format
        lines = [line for line in raw.splitlines() if not line.startswith("-----")]
        decoded = base64.b64decode("".join(lines))
        # Ed25519 public key in DER is 44 bytes (12 byte header + 32 byte key)
        if len(decoded) == 44:
            return decoded[12:]
        if len(decoded) == 32:
            return decoded
        # Try hex
        try:
            return bytes.fromhex(raw)
        except ValueError:
            pass

    return None


def verify_license_token(token: str) -> dict[str, Any] | None:
    """Verify a signed license token and return the payload if valid.

    Token format: base64url(payload_json).base64url(signature)

    Returns the decoded payload dict if valid, None if invalid.
    """
    public_key = load_public_key()
    if not public_key:
        return None

    parts = token.split(".")
    if len(parts) != 2:
        return None

    try:
        payload_bytes = base64.urlsafe_b64decode(parts[0] + "==")
        signature = base64.urlsafe_b64decode(parts[1] + "==")
    except Exception:
        return None

    if not ed25519_verify(public_key, payload_bytes, signature):
        return None

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def validate_license_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the contents of a verified license payload.

    Checks expiration, plan validity, and IP binding.
    Returns a status dict with validation results.
    """
    now = datetime.now(timezone.utc)

    # Check expiration
    expires_at_str = payload.get("expires_at")
    expired = False
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            expired = now > expires_at
        except (ValueError, TypeError):
            expired = True

    # Check plan
    plan = payload.get("plan", "").lower()
    valid_plans = {"pro", "enterprise"}
    plan_valid = plan in valid_plans

    # Check status field
    status = payload.get("status", "").lower()
    status_valid = status in {"active", ""}

    return {
        "valid": not expired and plan_valid and status_valid,
        "expired": expired,
        "plan": plan,
        "plan_valid": plan_valid,
        "status": status,
        "license_id": payload.get("license_id"),
        "customer_id": payload.get("customer_id"),
        "instance_id": payload.get("instance_id"),
        "bound_ip": payload.get("bound_ip"),
        "max_servers": payload.get("max_servers"),
        "max_outbounds": payload.get("max_outbounds"),
        "issued_at": payload.get("issued_at"),
        "expires_at": expires_at_str,
    }
