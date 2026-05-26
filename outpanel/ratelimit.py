"""API rate limiting middleware for Veltrix.

Implements a sliding-window rate limiter using in-memory storage.
Each client IP gets a request budget per time window.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_window: int = 120  # max requests per window
    window_seconds: int = 60       # window duration in seconds
    burst_limit: int = 30          # max burst requests in 5 seconds
    burst_window: int = 5          # burst window in seconds
    cleanup_interval: int = 300    # cleanup old entries every N seconds


@dataclass
class ClientBucket:
    """Tracks request timestamps for a single client."""
    timestamps: list[float] = field(default_factory=list)
    last_cleanup: float = 0.0


class RateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self.config = config or RateLimitConfig()
        self._buckets: dict[str, ClientBucket] = defaultdict(ClientBucket)
        self._lock = threading.Lock()
        self._last_global_cleanup = time.monotonic()

    def is_allowed(self, client_ip: str) -> bool:
        """Check if a request from client_ip is allowed.

        Returns True if allowed, False if rate limited.
        """
        now = time.monotonic()

        with self._lock:
            # Periodic global cleanup
            if now - self._last_global_cleanup > self.config.cleanup_interval:
                self._cleanup_stale_buckets(now)
                self._last_global_cleanup = now

            bucket = self._buckets[client_ip]

            # Remove timestamps outside the main window
            cutoff = now - self.config.window_seconds
            bucket.timestamps = [ts for ts in bucket.timestamps if ts > cutoff]

            # Check main window limit
            if len(bucket.timestamps) >= self.config.requests_per_window:
                return False

            # Check burst limit
            burst_cutoff = now - self.config.burst_window
            burst_count = sum(1 for ts in bucket.timestamps if ts > burst_cutoff)
            if burst_count >= self.config.burst_limit:
                return False

            # Allow and record
            bucket.timestamps.append(now)
            return True

    def get_remaining(self, client_ip: str) -> dict[str, Any]:
        """Get rate limit status for a client."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(client_ip)
            if not bucket:
                return {
                    "remaining": self.config.requests_per_window,
                    "limit": self.config.requests_per_window,
                    "reset_seconds": 0,
                }

            cutoff = now - self.config.window_seconds
            active = [ts for ts in bucket.timestamps if ts > cutoff]
            remaining = max(0, self.config.requests_per_window - len(active))

            # Time until oldest request expires
            reset_seconds = 0
            if active:
                reset_seconds = max(0, int(active[0] - cutoff))

            return {
                "remaining": remaining,
                "limit": self.config.requests_per_window,
                "reset_seconds": reset_seconds,
            }

    def _cleanup_stale_buckets(self, now: float) -> None:
        """Remove buckets with no recent activity."""
        cutoff = now - self.config.window_seconds * 2
        stale_keys = [
            key for key, bucket in self._buckets.items()
            if not bucket.timestamps or bucket.timestamps[-1] < cutoff
        ]
        for key in stale_keys:
            del self._buckets[key]


# Global rate limiter instance
_default_limiter: RateLimiter | None = None
_login_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter."""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter()
    return _default_limiter


def get_login_limiter() -> RateLimiter:
    """Get or create the login-specific rate limiter (stricter)."""
    global _login_limiter
    if _login_limiter is None:
        _login_limiter = RateLimiter(RateLimitConfig(
            requests_per_window=10,
            window_seconds=900,  # 15 minutes
            burst_limit=5,
            burst_window=60,
        ))
    return _login_limiter


def check_rate_limit(client_ip: str, endpoint: str = "") -> tuple[bool, dict[str, Any]]:
    """Check rate limit for a client IP.

    Uses stricter limits for sensitive endpoints (login, setup).
    Returns (allowed, info) where info contains remaining/limit/reset_seconds.
    """
    # Stricter limit for auth endpoints
    if endpoint in ("/api/auth/login", "/api/auth/setup"):
        limiter = get_login_limiter()
    else:
        limiter = get_rate_limiter()

    allowed = limiter.is_allowed(client_ip)
    info = limiter.get_remaining(client_ip)
    return allowed, info
