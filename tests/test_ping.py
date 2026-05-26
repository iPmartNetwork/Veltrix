"""Unit tests for TCP ping module."""
import pytest
from outpanel.ping import tcp_ping, PingResult


class TestTcpPing:
    def test_empty_host_returns_error(self):
        result = tcp_ping("", 80, 1000)
        assert result.status == "error"
        assert result.latency_ms is None
        assert "empty" in result.error.lower()

    def test_empty_port_returns_error(self):
        result = tcp_ping("127.0.0.1", 0, 1000)
        assert result.status == "error"
        assert result.latency_ms is None

    def test_unreachable_host_returns_error(self):
        # Use a non-routable IP to test timeout/error
        result = tcp_ping("192.0.2.1", 12345, 500)
        assert result.status in ("timeout", "error")
        assert result.latency_ms is None

    def test_localhost_connection(self):
        # This may or may not work depending on what's running
        # Just verify the function doesn't crash
        result = tcp_ping("127.0.0.1", 1, 250)
        assert isinstance(result, PingResult)
        assert result.status in ("ok", "error", "timeout")

    def test_minimum_timeout(self):
        # Timeout should be at least 250ms
        result = tcp_ping("192.0.2.1", 80, 10)
        assert result.status in ("timeout", "error")


class TestPingResult:
    def test_dataclass_fields(self):
        result = PingResult(status="ok", latency_ms=42.5)
        assert result.status == "ok"
        assert result.latency_ms == 42.5
        assert result.error is None

    def test_error_result(self):
        result = PingResult(status="error", latency_ms=None, error="Connection refused")
        assert result.status == "error"
        assert result.error == "Connection refused"
