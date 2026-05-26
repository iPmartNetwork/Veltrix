"""License validation worker for Veltrix.

Periodically validates the license with the remote License Server,
handles grace periods, expiration warnings, and signed token verification.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .db import DATA_DIR, connect, now_iso
from .licensing import (
    activate_license_with_server,
    get_license_status,
    load_license_cache,
    save_license_cache,
)
from .token_verify import validate_license_payload, verify_license_token


# Configuration
VALIDATION_INTERVAL_HOURS = int(os.getenv("OUTPANEL_LICENSE_CHECK_HOURS", "24"))
GRACE_PERIOD_DAYS = int(os.getenv("OUTPANEL_LICENSE_GRACE_DAYS", "7"))
EXPIRY_WARN_DAYS = int(os.getenv("OUTPANEL_LICENSE_WARN_DAYS", "14"))

# Public key file path
PUBLIC_KEY_FILE = DATA_DIR / "license-public-key.pem"


def get_days_remaining() -> int | None:
    """Get the number of days remaining on the license. None if no expiry."""
    status = get_license_status()
    expires_at = status.get("expires_at")
    if not expires_at:
        return None
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = expires - now
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None


def is_in_grace_period() -> bool:
    """Check if the license is in grace period (expired but within grace window)."""
    days = get_days_remaining()
    if days is None:
        return False
    return days == 0 and _days_since_expiry() <= GRACE_PERIOD_DAYS


def _days_since_expiry() -> int:
    """Get days since license expired."""
    status = get_license_status()
    expires_at = status.get("expires_at")
    if not expires_at:
        return 0
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if now > expires:
            return (now - expires).days
        return 0
    except (ValueError, TypeError):
        return 0


def should_warn_expiry() -> bool:
    """Check if we should warn about upcoming expiration."""
    days = get_days_remaining()
    if days is None:
        return False
    return 0 < days <= EXPIRY_WARN_DAYS


def get_license_display_info() -> dict[str, Any]:
    """Get license info formatted for dashboard display."""
    status = get_license_status()
    days_remaining = get_days_remaining()
    in_grace = is_in_grace_period()
    warn_expiry = should_warn_expiry()

    return {
        **status,
        "days_remaining": days_remaining,
        "in_grace_period": in_grace,
        "grace_period_days": GRACE_PERIOD_DAYS,
        "expiry_warning": warn_expiry,
        "expiry_warn_days": EXPIRY_WARN_DAYS,
        "validation_interval_hours": VALIDATION_INTERVAL_HOURS,
    }


def validate_cached_token() -> dict[str, Any]:
    """Validate the cached signed license token."""
    cache = load_license_cache()
    token = cache.get("token")
    if not token:
        return {"valid": False, "reason": "no_token"}

    payload = verify_license_token(token)
    if not payload:
        return {"valid": False, "reason": "invalid_signature"}

    validation = validate_license_payload(payload)
    return validation


def periodic_license_check() -> dict[str, Any]:
    """Run a periodic license validation against the License Server.

    Called by the worker every VALIDATION_INTERVAL_HOURS.
    """
    cache = load_license_cache()
    last_validated = cache.get("last_validated_at")

    # Check if we need to validate
    if last_validated:
        try:
            last_dt = datetime.fromisoformat(last_validated.replace("Z", "+00:00"))
            hours_since = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
            if hours_since < VALIDATION_INTERVAL_HOURS:
                return {"status": "skipped", "hours_since_last": round(hours_since, 1)}
        except (ValueError, TypeError):
            pass

    # Try to validate with License Server
    server_url = os.getenv("OUTPANEL_LICENSE_SERVER_URL", "").strip().rstrip("/")
    license_key = os.getenv("OUTPANEL_LICENSE_KEY", "").strip() or str(cache.get("license", {}).get("license_key", "")).strip()

    if not server_url or not license_key:
        return {"status": "skipped", "reason": "no_server_or_key"}

    try:
        from .licensing import get_or_create_instance_id, detect_server_ip
        import urllib.request
        import urllib.error

        detected_ip, detected_source = detect_server_ip()
        payload = {
            "license_key": license_key,
            "instance_id": get_or_create_instance_id(),
            "product": "Veltrix",
            "action": "validate",
            "detected_ip": detected_ip,
        }

        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            server_url + "/api/validate",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Veltrix Customer App",
            },
        )

        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Update cache with validation result
        cache["last_validated_at"] = now_iso()
        cache["last_validation_result"] = data
        if "license" in data:
            cache["license"] = data["license"]
        if "token" in data:
            cache["token"] = data["token"]
        save_license_cache(cache)

        return {"status": "validated", "result": data.get("license", {}).get("state", "unknown")}

    except Exception as exc:
        # Validation failed — use grace period
        cache["last_validation_error"] = str(exc)
        cache["last_validation_attempt"] = now_iso()
        save_license_cache(cache)
        return {"status": "failed", "error": str(exc), "grace_active": is_in_grace_period()}


def license_check_loop(stop_event: threading.Event) -> None:
    """Background loop for periodic license validation."""
    # Wait 60 seconds after startup before first check
    stop_event.wait(60)

    while not stop_event.is_set():
        try:
            periodic_license_check()
        except Exception:
            pass
        # Check every hour (actual validation respects VALIDATION_INTERVAL_HOURS)
        stop_event.wait(3600)
