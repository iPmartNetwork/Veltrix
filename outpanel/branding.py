"""Custom branding support for Veltrix.

Allows customers to customize logo, colors, and product name
through environment variables or settings API.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .db import connect, now_iso


# Default branding
DEFAULT_BRANDING = {
    "product_name": "Veltrix",
    "tagline": "Intelligent Network Control",
    "logo_url": "/assets/veltrix-icon.jpg",
    "mark_url": "/assets/veltrix-mark.jpg",
    "lockup_url": "/assets/veltrix-lockup-light.jpg",
    "primary_color": "#00bfa6",
    "accent_color": "#19f1d2",
    "dark_color": "#071013",
    "favicon_url": "/assets/veltrix-icon.jpg",
    "footer_text": "",
    "support_url": "",
    "support_email": "",
}

# Allowed branding keys that can be customized
ALLOWED_KEYS = set(DEFAULT_BRANDING.keys())


def get_branding() -> dict[str, str]:
    """Get the current branding configuration.

    Priority: database settings > environment variables > defaults
    """
    branding = dict(DEFAULT_BRANDING)

    # Override from environment
    env_overrides = {
        "product_name": os.getenv("OUTPANEL_BRAND_NAME", "").strip(),
        "tagline": os.getenv("OUTPANEL_BRAND_TAGLINE", "").strip(),
        "logo_url": os.getenv("OUTPANEL_BRAND_LOGO", "").strip(),
        "primary_color": os.getenv("OUTPANEL_BRAND_COLOR", "").strip(),
        "support_url": os.getenv("OUTPANEL_SUPPORT_URL", "").strip(),
        "support_email": os.getenv("OUTPANEL_SUPPORT_EMAIL", "").strip(),
        "footer_text": os.getenv("OUTPANEL_BRAND_FOOTER", "").strip(),
    }
    for key, value in env_overrides.items():
        if value:
            branding[key] = value

    # Override from database settings
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'branding'"
            ).fetchone()
            if row:
                db_branding = json.loads(row["value"])
                if isinstance(db_branding, dict):
                    for key, value in db_branding.items():
                        if key in ALLOWED_KEYS and value:
                            branding[key] = str(value).strip()
    except Exception:
        pass

    return branding


def update_branding(updates: dict[str, Any]) -> dict[str, str]:
    """Update branding settings in the database."""
    current = get_branding()

    # Apply updates (only allowed keys)
    for key, value in updates.items():
        if key in ALLOWED_KEYS and value is not None:
            current[key] = str(value).strip()

    # Save to database
    ts = now_iso()
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("branding", json.dumps(current, ensure_ascii=False), ts),
        )

    return current


def get_branding_css_vars() -> str:
    """Generate CSS custom properties from branding config."""
    branding = get_branding()
    return f"""
    :root {{
      --brand-primary: {branding.get('primary_color', '#00bfa6')};
      --brand-accent: {branding.get('accent_color', '#19f1d2')};
      --brand-dark: {branding.get('dark_color', '#071013')};
    }}
    """.strip()
