"""Unit tests for the router module."""
import pytest
from outpanel.router import Router, Route, RequestContext


class TestRouter:
    def test_simple_route_match(self):
        router = Router()
        router.get("/api/health", lambda ctx: {"ok": True}, auth_required=False)
        result = router.resolve("GET", "/api/health")
        assert result is not None
        route, params = result
        assert params == {}

    def test_parameterized_route(self):
        router = Router()
        router.get("/api/servers/{server_id}", lambda ctx: {}, permission="servers")
        result = router.resolve("GET", "/api/servers/42")
        assert result is not None
        route, params = result
        assert params == {"server_id": "42"}

    def test_multiple_params(self):
        router = Router()
        router.get("/api/{type}/{id}/detail", lambda ctx: {})
        result = router.resolve("GET", "/api/servers/5/detail")
        assert result is not None
        _, params = result
        assert params == {"type": "servers", "id": "5"}

    def test_method_mismatch(self):
        router = Router()
        router.get("/api/test", lambda ctx: {})
        assert router.resolve("POST", "/api/test") is None

    def test_path_mismatch(self):
        router = Router()
        router.get("/api/test", lambda ctx: {})
        assert router.resolve("GET", "/api/other") is None

    def test_route_permission(self):
        router = Router()
        router.get("/api/servers", lambda ctx: {}, permission="servers")
        result = router.resolve("GET", "/api/servers")
        assert result is not None
        route, _ = result
        assert route.permission == "servers"
        assert route.auth_required is True

    def test_public_route(self):
        router = Router()
        router.get("/api/health", lambda ctx: {}, auth_required=False)
        result = router.resolve("GET", "/api/health")
        route, _ = result
        assert route.auth_required is False


class TestRequestContext:
    def test_get_param(self):
        ctx = RequestContext(
            method="GET", path="/api/servers/5", params={"server_id": "5"},
            query={}, body={}, user=None, client_ip="127.0.0.1",
            session_token=None, user_agent=None,
        )
        assert ctx.get_param("server_id") == "5"
        assert ctx.get_param("missing") == ""

    def test_get_query(self):
        ctx = RequestContext(
            method="GET", path="/api/test", params={},
            query={"limit": ["50"], "page": ["2"]},
            body={}, user=None, client_ip="127.0.0.1",
            session_token=None, user_agent=None,
        )
        assert ctx.get_query("limit") == "50"
        assert ctx.get_query("missing", "default") == "default"
        assert ctx.get_query_int("limit") == 50
        assert ctx.get_query_int("page") == 2
        assert ctx.get_query_int("missing", 10) == 10


class TestRouteCount:
    def test_full_router_has_routes(self):
        from outpanel.routes import build_router
        router = build_router()
        assert len(router.routes) >= 70
