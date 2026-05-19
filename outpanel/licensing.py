from __future__ import annotations

import os
import socket
import uuid
import ipaddress
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .db import DATA_DIR

PRODUCT = {
    "name": "Veltrix",
    "tagline": "Intelligent Network Control",
    "market": "Outbound sellers and network operators",
    "sales_channel": "support",
    "deployment": "self-hosted with SaaS license validation",
    "license_scope": "single-server-public-ip",
}

LICENSE_CACHE_FILE = DATA_DIR / "license-cache.json"

LICENSE_DURATIONS = {
    "6m": {"label": "6 months", "months": 6},
    "1y": {"label": "1 year", "months": 12},
    "lifetime": {"label": "Lifetime", "months": None},
}

LICENSE_PLANS = {
    "pro": {
        "name": "Pro",
        "max_servers": 20,
        "max_outbounds": None,
        "support_level": "standard",
        "recommended_for": "Small and medium outbound sellers",
        "features": [
            "Manage up to 20 servers",
            "Resource and ping monitoring",
            "X-UI synchronization",
            "In-panel and browser notifications",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "max_servers": 60,
        "max_outbounds": 60,
        "support_level": "priority",
        "recommended_for": "High-traffic teams and sellers",
        "features": [
            "Manage up to 60 servers",
            "Manage up to 60 outbounds according to current product definition",
            "Priority support",
            "Ready for Telegram/Webhook integration",
        ],
    },
}


def get_or_create_instance_id() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(os.getenv("OUTPANEL_INSTANCE_FILE", str(DATA_DIR / "instance.id")))
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = str(uuid.uuid4())
    path.write_text(value + "\n", encoding="utf-8")
    return value


def get_license_status() -> dict[str, Any]:
    """Return the current license status, including cached info and IP validation."""
    cache = load_license_cache()
    cached_license = cache.get("license") if isinstance(cache.get("license"), dict) else {}
    plan_key = os.getenv("OUTPANEL_LICENSE_PLAN", "").strip().lower()
    duration_key = os.getenv("OUTPANEL_LICENSE_DURATION", "").strip().lower()
    license_key = os.getenv("OUTPANEL_LICENSE_KEY", "").strip()
    expires_at = os.getenv("OUTPANEL_LICENSE_EXPIRES_AT", "").strip()
    bound_ip = os.getenv("OUTPANEL_LICENSE_BOUND_IP", "").strip()

    # Fall back to cached license values
    plan_key = plan_key or str(cached_license.get("plan") or "").strip().lower()
    duration_key = duration_key or str(cached_license.get("duration") or "").strip().lower()
    license_key = license_key or str(cached_license.get("license_key") or "").strip()
    expires_at = expires_at or str(cached_license.get("expires_at") or "").strip()
    bound_ip = bound_ip or str(cached_license.get("bound_ip") or "").strip()

    detected_ip, detected_source = detect_server_ip()

    plan = LICENSE_PLANS.get(plan_key)
    duration = LICENSE_DURATIONS.get(duration_key)
    ip_match = compare_ip(bound_ip, detected_ip, detected_source) if bound_ip else None
    remote_state = str(cached_license.get("state") or "").strip()

    # Determine license state
    if not plan or not license_key:
        state = "unlicensed"
    elif remote_state in {"invalid", "invalid_ip", "expired", "revoked"}:
        state = remote_state
    elif not bound_ip:
        state = "pending_ip_binding"
    elif ip_match is False:
        state = "invalid_ip"
    elif remote_state == "active":
        state = "active"
    elif ip_match is None:
        state = "ip_unverified"
    else:
        state = "active"

    return {
        "product": PRODUCT,
        "instance_id": get_or_create_instance_id(),
        "state": state,
        "requires_license": os.getenv("OUTPANEL_REQUIRE_LICENSE", "") == "1",
        "plan_key": plan_key if plan else None,
        "plan": plan,
        "duration_key": duration_key if duration else None,
        "duration": duration,
        "license_key_present": bool(license_key),
        "expires_at": expires_at or None,
        "bound_ip": bound_ip or None,
        "license_server_url": os.getenv("OUTPANEL_LICENSE_SERVER_URL", "").strip() or None,
        "cached_license_present": bool(cached_license),
        "cached_token_present": bool(cache.get("token")),
        "validated_at": cached_license.get("validated_at"),
        "remote_state": remote_state or None,
        "detected_ip": detected_ip,
        "detected_ip_source": detected_source,
        "ip_match": ip_match,
        "activation_rule": "A license is valid for a single server public IP only.",
        "validation_mode": "planned-remote-signed-token",
        "available_plans": LICENSE_PLANS,
        "available_durations": LICENSE_DURATIONS,
    }


def activate_license_with_server(license_key: str) -> dict[str, Any]:
    """Activate a license key with the remote License Server."""
    server_url = os.getenv("OUTPANEL_LICENSE_SERVER_URL", "").strip().rstrip("/")
    if not server_url:
        raise ValueError("OUTPANEL_LICENSE_SERVER_URL is not configured.")
    license_key = (license_key or "").strip().upper()
    if not license_key:
        raise ValueError("License Key is empty.")

    detected_ip, detected_source = detect_server_ip()
    payload = {
        "license_key": license_key,
        "instance_id": get_or_create_instance_id(),
        "product": PRODUCT["name"],
        "detected_ip": detected_ip,
        "detected_ip_source": detected_source,
    }
    request = Request(
        server_url + "/api/activate",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Veltrix Customer App",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise ValueError(f"License Server returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ValueError(f"Could not connect to License Server: {exc.reason}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("License Server response is invalid JSON.") from exc
    if not isinstance(data, dict) or "license" not in data:
        raise ValueError("License Server response is incomplete.")

    save_license_cache(data)
    return data


def get_public_license_catalog() -> dict[str, Any]:
    """Return available license plans and durations."""
    return {
        "product": PRODUCT,
        "plans": LICENSE_PLANS,
        "durations": LICENSE_DURATIONS,
    }


def load_license_cache() -> dict[str, Any]:
    path = Path(os.getenv("OUTPANEL_LICENSE_CACHE_FILE", str(LICENSE_CACHE_FILE)))
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_license_cache(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(os.getenv("OUTPANEL_LICENSE_CACHE_FILE", str(LICENSE_CACHE_FILE)))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_server_ip() -> tuple[str | None, str]:
    """Detect the server's public IP using environment, external service, or local route."""
    explicit = os.getenv("OUTPANEL_SERVER_PUBLIC_IP", "").strip() or os.getenv("OUTPANEL_PUBLIC_IP", "").strip()
    if explicit:
        return explicit, "env"

    check_url = os.getenv("OUTPANEL_PUBLIC_IP_CHECK_URL", "").strip()
    if check_url:
        try:
            with urlopen(check_url, timeout=3) as response:
                value = response.read().decode("utf-8", errors="replace").strip()
            if value:
                return value.split()[0], "public-ip-check-url"
        except Exception:
            pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1)
            sock.connect(("1.1.1.1", 80))
            value = sock.getsockname()[0]
            if value:
                return value, "local-route"
    except OSError:
        pass

    try:
        value = socket.gethostbyname(socket.gethostname())
        if value:
            return value, "hostname"
    except OSError:
        pass

    return None, "unknown"


def compare_ip(bound_ip: str, detected_ip: str | None, detected_source: str) -> bool | None:
    if not bound_ip or not detected_ip:
        return None
    if detected_source in {"local-route", "hostname"} and is_private_or_local_ip(detected_ip):
        return None
    return bound_ip.strip() == detected_ip.strip()


def is_private_or_local_ip(value: str) -> bool:
    try:
        parsed = ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    return parsed.is_private or parsed.is_loopback or parsed.is_link_local
