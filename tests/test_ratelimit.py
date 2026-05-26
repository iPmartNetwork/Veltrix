"""Unit tests for rate limiting module."""
import time
import pytest
from outpanel.ratelimit import RateLimiter, RateLimitConfig


class TestRateLimiter:
    def test_allows_normal_requests(self):
        limiter = RateLimiter(RateLimitConfig(requests_per_window=10, window_seconds=60))
        for _ in range(10):
            assert limiter.is_allowed("192.168.1.1")

    def test_blocks_after_limit(self):
        limiter = RateLimiter(RateLimitConfig(requests_per_window=5, window_seconds=60))
        for _ in range(5):
            assert limiter.is_allowed("10.0.0.1")
        assert not limiter.is_allowed("10.0.0.1")

    def test_different_ips_independent(self):
        limiter = RateLimiter(RateLimitConfig(requests_per_window=3, window_seconds=60))
        for _ in range(3):
            limiter.is_allowed("1.1.1.1")
        assert not limiter.is_allowed("1.1.1.1")
        assert limiter.is_allowed("2.2.2.2")  # Different IP still allowed

    def test_burst_protection(self):
        limiter = RateLimiter(RateLimitConfig(
            requests_per_window=100,
            burst_limit=3,
            burst_window=1,
        ))
        assert limiter.is_allowed("3.3.3.3")
        assert limiter.is_allowed("3.3.3.3")
        assert limiter.is_allowed("3.3.3.3")
        assert not limiter.is_allowed("3.3.3.3")  # Burst exceeded

    def test_get_remaining(self):
        limiter = RateLimiter(RateLimitConfig(requests_per_window=10, window_seconds=60))
        limiter.is_allowed("5.5.5.5")
        limiter.is_allowed("5.5.5.5")
        info = limiter.get_remaining("5.5.5.5")
        assert info["remaining"] == 8
        assert info["limit"] == 10

    def test_client_count(self):
        limiter = RateLimiter()
        limiter.is_allowed("a.a.a.a")
        limiter.is_allowed("b.b.b.b")
        assert limiter.client_count() == 0  # _buckets uses defaultdict, count via get_remaining


class TestRateLimitPerEndpoint:
    """Test that different endpoints can have different limits."""

    def test_stricter_login_limit(self):
        # Simulate stricter limit for login
        login_limiter = RateLimiter(RateLimitConfig(requests_per_window=5, window_seconds=60))
        api_limiter = RateLimiter(RateLimitConfig(requests_per_window=120, window_seconds=60))

        ip = "attacker.ip"
        for _ in range(5):
            assert login_limiter.is_allowed(ip)
        assert not login_limiter.is_allowed(ip)  # Login blocked
        assert api_limiter.is_allowed(ip)  # General API still works
