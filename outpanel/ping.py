from __future__ import annotations

import socket
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PingResult:
    status: str
    latency_ms: float | None
    error: str | None = None


def tcp_ping(host: str, port: int, timeout_ms: int) -> PingResult:
    """Perform a TCP ping to the given host and port.

    Returns a PingResult with status, latency in ms, and optional error message.
    """
    target = (host or "").strip()
    if not target:
        return PingResult("error", None, "Host is empty.")
    if not port:
        return PingResult("error", None, "Port is empty.")

    timeout = max(timeout_ms, 250) / 1000
    start_time = time.perf_counter()
    try:
        with socket.create_connection((target, int(port)), timeout=timeout):
            elapsed = (time.perf_counter() - start_time) * 1000
            return PingResult("ok", round(elapsed, 1))
    except socket.timeout:
        return PingResult("timeout", None, "Connection timed out.")
    except OSError as exc:
        return PingResult("error", None, str(exc))
