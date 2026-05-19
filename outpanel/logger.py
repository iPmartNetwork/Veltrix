"""Request logging middleware for Veltrix.

Provides structured request/response logging with configurable output.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------

LOG_DIR = Path(os.getenv("OUTPANEL_LOG_DIR", "logs"))
LOG_LEVEL = os.getenv("OUTPANEL_LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("OUTPANEL_LOG_FORMAT", "json")  # "json" or "text"
LOG_FILE = os.getenv("OUTPANEL_LOG_FILE", "")  # empty = stdout only


def setup_logger(name: str = "veltrix") -> logging.Logger:
    """Configure and return the application logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if LOG_FORMAT == "json":
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    logger.addHandler(console_handler)

    # File handler (optional)
    if LOG_FILE:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_path = LOG_DIR / LOG_FILE if not os.path.isabs(LOG_FILE) else Path(LOG_FILE)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(file_path), encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)

    return logger


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add extra fields if present
        if hasattr(record, "request_data"):
            log_entry["request"] = record.request_data  # type: ignore[attr-defined]
        if hasattr(record, "response_data"):
            log_entry["response"] = record.response_data  # type: ignore[attr-defined]
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)  # type: ignore[attr-defined]

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(log_entry, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Request logging
# ---------------------------------------------------------------------------

class RequestLogger:
    """Logs HTTP request/response pairs with timing."""

    def __init__(self) -> None:
        self.logger = setup_logger("veltrix.http")

    def log_request(
        self,
        method: str,
        path: str,
        client_ip: str,
        status_code: int,
        duration_ms: float,
        user_agent: str | None = None,
        user_id: int | None = None,
        error: str | None = None,
    ) -> None:
        """Log a completed HTTP request."""
        level = logging.INFO
        if status_code >= 500:
            level = logging.ERROR
        elif status_code >= 400:
            level = logging.WARNING

        message = f"{method} {path} {status_code} {duration_ms:.1f}ms"

        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
        )

        record.request_data = {  # type: ignore[attr-defined]
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "user_id": user_id,
        }
        record.response_data = {  # type: ignore[attr-defined]
            "status": status_code,
            "duration_ms": round(duration_ms, 2),
        }

        if error:
            record.response_data["error"] = error  # type: ignore[attr-defined]

        self.logger.handle(record)

    def log_event(self, event: str, details: dict[str, Any] | None = None) -> None:
        """Log an application event."""
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=logging.INFO,
            fn="",
            lno=0,
            msg=event,
            args=(),
            exc_info=None,
        )
        if details:
            record.extra_data = details  # type: ignore[attr-defined]
        self.logger.handle(record)

    def log_error(self, message: str, error: Exception | None = None) -> None:
        """Log an error."""
        self.logger.error(message, exc_info=error)

    def log_startup(self, host: str, port: int, version: str) -> None:
        """Log server startup."""
        self.log_event("server.startup", {
            "host": host,
            "port": port,
            "version": version,
        })

    def log_monitor_cycle(self, servers_checked: int, duration_ms: float) -> None:
        """Log a monitoring cycle completion."""
        self.log_event("monitor.cycle_complete", {
            "servers_checked": servers_checked,
            "duration_ms": round(duration_ms, 2),
        })


# Global request logger instance
_request_logger: RequestLogger | None = None


def get_request_logger() -> RequestLogger:
    """Get or create the global request logger."""
    global _request_logger
    if _request_logger is None:
        _request_logger = RequestLogger()
    return _request_logger
