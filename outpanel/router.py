"""API Router for Veltrix.

Provides a clean routing mechanism to separate endpoint handlers
from the HTTP server implementation.
"""
from __future__ import annotations

import re
from typing import Any, Callable

# Type alias for route handlers
RouteHandler = Callable[["RequestContext"], dict[str, Any] | None]


class Route:
    """A single route definition."""

    def __init__(
        self,
        method: str,
        pattern: str,
        handler: RouteHandler,
        *,
        permission: str | None = None,
        auth_required: bool = True,
    ) -> None:
        self.method = method.upper()
        self.pattern = pattern
        self.handler = handler
        self.permission = permission
        self.auth_required = auth_required
        # Convert path pattern to regex (supports {param} syntax)
        regex_pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern)
        self.regex = re.compile(f"^{regex_pattern}$")

    def match(self, method: str, path: str) -> dict[str, str] | None:
        """Try to match a request method and path. Returns params dict or None."""
        if method != self.method:
            return None
        m = self.regex.match(path)
        if m:
            return m.groupdict()
        return None


class RequestContext:
    """Context object passed to route handlers."""

    def __init__(
        self,
        method: str,
        path: str,
        params: dict[str, str],
        query: dict[str, list[str]],
        body: dict[str, Any],
        user: dict[str, Any] | None,
        client_ip: str,
        session_token: str | None,
        user_agent: str | None,
    ) -> None:
        self.method = method
        self.path = path
        self.params = params
        self.query = query
        self.body = body
        self.user = user
        self.client_ip = client_ip
        self.session_token = session_token
        self.user_agent = user_agent

    def get_param(self, name: str) -> str:
        """Get a URL path parameter."""
        return self.params.get(name, "")

    def get_query(self, name: str, default: str = "") -> str:
        """Get a query string parameter."""
        values = self.query.get(name, [])
        return values[0] if values else default

    def get_query_int(self, name: str, default: int = 0) -> int:
        """Get a query string parameter as integer."""
        try:
            return int(self.get_query(name, str(default)))
        except (ValueError, TypeError):
            return default


class Router:
    """API router that manages route registration and dispatch."""

    def __init__(self) -> None:
        self.routes: list[Route] = []

    def add(
        self,
        method: str,
        pattern: str,
        handler: RouteHandler,
        *,
        permission: str | None = None,
        auth_required: bool = True,
    ) -> None:
        """Register a route."""
        self.routes.append(Route(method, pattern, handler, permission=permission, auth_required=auth_required))

    def get(self, pattern: str, handler: RouteHandler, **kwargs: Any) -> None:
        """Register a GET route."""
        self.add("GET", pattern, handler, **kwargs)

    def post(self, pattern: str, handler: RouteHandler, **kwargs: Any) -> None:
        """Register a POST route."""
        self.add("POST", pattern, handler, **kwargs)

    def put(self, pattern: str, handler: RouteHandler, **kwargs: Any) -> None:
        """Register a PUT route."""
        self.add("PUT", pattern, handler, **kwargs)

    def delete(self, pattern: str, handler: RouteHandler, **kwargs: Any) -> None:
        """Register a DELETE route."""
        self.add("DELETE", pattern, handler, **kwargs)

    def resolve(self, method: str, path: str) -> tuple[Route, dict[str, str]] | None:
        """Find a matching route for the given method and path."""
        for route in self.routes:
            params = route.match(method, path)
            if params is not None:
                return route, params
        return None
