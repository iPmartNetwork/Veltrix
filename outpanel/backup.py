from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .db import PROJECT_ROOT, db_path, now_iso


BACKUP_NAME_PATTERN = re.compile(r"^veltrix-backup-\d{8}T\d{6}Z-[a-f0-9]{8}\.zip$")
REQUIRED_TABLES = {
    "users",
    "servers",
    "outbounds",
    "incidents",
    "notification_channels",
    "audit_logs",
}
BACKUP_DATABASE_FILE = "veltrix.db"
LEGACY_BACKUP_DATABASE_FILE = "outpanel.db"


def backup_dir() -> Path:
    path = Path(os.getenv("OUTPANEL_BACKUP_DIR", str(PROJECT_ROOT / "backups")))
    return path.expanduser().resolve()


def list_backups() -> list[dict[str, Any]]:
    directory = backup_dir()
    if not directory.exists():
        return []
    backups = []
    for path in directory.glob("veltrix-backup-*.zip"):
        if not BACKUP_NAME_PATTERN.match(path.name):
            continue
        item = backup_info(path)
        if item:
            backups.append(item)
    return sorted(backups, key=lambda item: item.get("created_at") or "", reverse=True)


def create_backup(actor: dict[str, Any] | None = None, reason: str = "manual") -> dict[str, Any]:
    directory = backup_dir()
    directory.mkdir(parents=True, exist_ok=True)
    source_db = db_path()
    if not source_db.exists():
        raise ValueError("Database file was not found.")

    created_at = now_iso()
    safe_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = os.urandom(4).hex()
    archive_path = directory / f"veltrix-backup-{safe_stamp}-{suffix}.zip"

    with tempfile.TemporaryDirectory(prefix="veltrix-backup-") as tmp_dir:
        snapshot_path = Path(tmp_dir) / BACKUP_DATABASE_FILE
        copy_sqlite_snapshot(source_db, snapshot_path)
        metadata = {
            "product": "Veltrix",
            "version": __version__,
            "created_at": created_at,
            "reason": reason,
            "actor": {
                "id": actor.get("id") if actor else None,
                "username": actor.get("username") if actor else None,
                "role": actor.get("role") if actor else None,
            },
            "database_file": BACKUP_DATABASE_FILE,
            "database_size": snapshot_path.stat().st_size,
        }
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot_path, BACKUP_DATABASE_FILE)
            archive.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))

    return backup_info(archive_path) or {"name": archive_path.name, "path": str(archive_path)}


def get_backup_path(name: str) -> Path:
    if not BACKUP_NAME_PATTERN.match(name):
        raise ValueError("Backup name is invalid.")
    path = (backup_dir() / name).resolve()
    if not str(path).startswith(str(backup_dir())) or not path.is_file():
        raise ValueError("Backup file was not found.")
    return path


def backup_info(path: Path) -> dict[str, Any] | None:
    try:
        stat = path.stat()
        metadata = read_metadata(path)
        return {
            "name": path.name,
            "created_at": metadata.get("created_at"),
            "version": metadata.get("version"),
            "reason": metadata.get("reason"),
            "actor": metadata.get("actor") or {},
            "size": stat.st_size,
            "database_size": metadata.get("database_size"),
        }
    except (OSError, ValueError, zipfile.BadZipFile):
        return None


def restore_backup(name: str, actor: dict[str, Any] | None = None) -> dict[str, Any]:
    archive_path = get_backup_path(name)
    metadata = read_metadata(archive_path)
    if metadata.get("product") != "Veltrix":
        raise ValueError("This backup does not belong to Veltrix.")

    safety_backup = create_backup(actor, reason=f"pre-restore:{name}")
    destination = db_path()
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="veltrix-restore-") as tmp_dir:
        restored_db = Path(tmp_dir) / BACKUP_DATABASE_FILE
        with zipfile.ZipFile(archive_path, "r") as archive:
            database_member = metadata.get("database_file") or BACKUP_DATABASE_FILE
            if database_member not in archive.namelist() and LEGACY_BACKUP_DATABASE_FILE in archive.namelist():
                database_member = LEGACY_BACKUP_DATABASE_FILE
            if database_member not in archive.namelist():
                raise ValueError("Backup does not contain a database snapshot.")
            with archive.open(database_member) as source, restored_db.open("wb") as destination_file:
                destination_file.write(source.read())
        validate_sqlite_database(restored_db)
        restore_sqlite_snapshot(restored_db, destination)
        remove_sqlite_sidecars(destination)

    return {
        "ok": True,
        "restored": backup_info(archive_path),
        "safety_backup": safety_backup,
    }


def delete_backup(name: str) -> None:
    path = get_backup_path(name)
    path.unlink()


def read_metadata(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path, "r") as archive:
        if "metadata.json" not in archive.namelist():
            raise ValueError("Backup metadata was not found.")
        raw = archive.read("metadata.json").decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Backup metadata is invalid.")
    return data


def copy_sqlite_snapshot(source: Path, destination: Path) -> None:
    source_conn = sqlite3.connect(str(source), timeout=30)
    try:
        destination_conn = sqlite3.connect(str(destination))
        try:
            source_conn.backup(destination_conn)
        finally:
            destination_conn.close()
    finally:
        source_conn.close()


def restore_sqlite_snapshot(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(str(source), timeout=30)
    try:
        destination_conn = sqlite3.connect(str(destination), timeout=30)
        try:
            source_conn.backup(destination_conn)
        finally:
            destination_conn.close()
    finally:
        source_conn.close()


def validate_sqlite_database(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise ValueError(f"Backup database integrity check failed: {result}")
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing = REQUIRED_TABLES - tables
        if missing:
            raise ValueError("Backup database is missing required tables: " + ", ".join(sorted(missing)))
    finally:
        conn.close()


def remove_sqlite_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(path) + suffix)
        try:
            if sidecar.exists():
                sidecar.unlink()
        except OSError:
            pass
