"""Scheduled automatic backup for Veltrix.

Creates nightly backups and manages retention (keeps last N backups).
Runs as part of the worker loop.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

from .backup import create_backup, list_backups, delete_backup
from .db import connect, now_iso


# Configuration
BACKUP_ENABLED = os.getenv("OUTPANEL_AUTO_BACKUP", "1").strip() != "0"
BACKUP_HOUR = int(os.getenv("OUTPANEL_BACKUP_HOUR", "3"))  # UTC hour (default 3 AM)
BACKUP_RETENTION = int(os.getenv("OUTPANEL_BACKUP_RETENTION", "7"))  # Keep last N backups


def should_run_backup() -> bool:
    """Check if it's time to run the scheduled backup."""
    if not BACKUP_ENABLED:
        return False

    now = datetime.now(timezone.utc)
    if now.hour != BACKUP_HOUR:
        return False

    # Check if we already ran today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    backups = list_backups()
    for backup in backups:
        if backup.get("reason") == "scheduled" and backup.get("created_at", "") > today_start:
            return False

    return True


def run_scheduled_backup() -> dict[str, Any] | None:
    """Run the scheduled backup if conditions are met."""
    if not should_run_backup():
        return None

    try:
        result = create_backup(actor=None, reason="scheduled")
        cleanup_old_backups()
        return result
    except Exception as exc:
        return {"error": str(exc)}


def cleanup_old_backups() -> int:
    """Remove old scheduled backups beyond retention limit."""
    if BACKUP_RETENTION <= 0:
        return 0

    backups = list_backups()
    scheduled = [b for b in backups if b.get("reason") == "scheduled"]

    removed = 0
    if len(scheduled) > BACKUP_RETENTION:
        # Remove oldest (list is sorted newest first)
        for old_backup in scheduled[BACKUP_RETENTION:]:
            try:
                delete_backup(old_backup["name"])
                removed += 1
            except Exception:
                pass

    return removed


def get_backup_schedule_info() -> dict[str, Any]:
    """Get info about the backup schedule."""
    backups = list_backups()
    scheduled = [b for b in backups if b.get("reason") == "scheduled"]
    last_scheduled = scheduled[0] if scheduled else None

    return {
        "enabled": BACKUP_ENABLED,
        "hour_utc": BACKUP_HOUR,
        "retention": BACKUP_RETENTION,
        "total_scheduled": len(scheduled),
        "last_backup": last_scheduled.get("created_at") if last_scheduled else None,
        "last_backup_name": last_scheduled.get("name") if last_scheduled else None,
    }
