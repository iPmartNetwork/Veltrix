"""Auto-generated API documentation for Veltrix.

Generates OpenAPI/Swagger-compatible documentation from the router.
Accessible at /api/docs for developer customers.
"""
from __future__ import annotations

from typing import Any

from . import __version__


def generate_api_docs(routes: list[Any]) -> dict[str, Any]:
    """Generate OpenAPI 3.0 documentation from registered routes."""
    paths: dict[str, Any] = {}

    for route in routes:
        # Convert {param} to OpenAPI {param} format (already compatible)
        path = route.pattern
        method = route.method.lower()

        if path not in paths:
            paths[path] = {}

        operation: dict[str, Any] = {
            "summary": _generate_summary(path, method),
            "tags": [_extract_tag(path)],
            "responses": {
                "200": {"description": "Successful response"},
                "400": {"description": "Bad request"},
                "401": {"description": "Unauthorized"},
                "403": {"description": "Forbidden"},
                "404": {"description": "Not found"},
                "429": {"description": "Rate limited"},
            },
        }

        if route.auth_required:
            operation["security"] = [{"bearerAuth": []}, {"cookieAuth": []}]

        if route.permission:
            operation["description"] = f"Required permission: `{route.permission}`"

        # Add path parameters
        params = _extract_path_params(path)
        if params:
            operation["parameters"] = params

        if method in ("post", "put"):
            operation["requestBody"] = {
                "content": {
                    "application/json": {
                        "schema": {"type": "object"}
                    }
                }
            }

        paths[path][method] = operation

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Veltrix API",
            "description": "Intelligent Network Control — REST API Documentation",
            "version": __version__,
            "contact": {
                "name": "iPmartNetwork",
                "url": "https://github.com/iPmartNetwork/Veltrix",
            },
        },
        "servers": [
            {"url": "/", "description": "Current server"},
        ],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "API Token or session token",
                },
                "cookieAuth": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "veltrix_session",
                },
            },
        },
        "tags": [
            {"name": "auth", "description": "Authentication & sessions"},
            {"name": "servers", "description": "Server management"},
            {"name": "outbounds", "description": "Outbound monitoring"},
            {"name": "alerts", "description": "Alert management"},
            {"name": "incidents", "description": "Incident lifecycle"},
            {"name": "notifications", "description": "Notification channels"},
            {"name": "reports", "description": "Reporting & export"},
            {"name": "license", "description": "License management"},
            {"name": "settings", "description": "Application settings"},
            {"name": "monitor", "description": "Monitoring operations"},
            {"name": "users", "description": "User & manager management"},
            {"name": "backups", "description": "Backup & restore"},
            {"name": "system", "description": "System endpoints"},
        ],
    }


def _generate_summary(path: str, method: str) -> str:
    """Generate a human-readable summary from path and method."""
    parts = [p for p in path.split("/") if p and p != "api" and not p.startswith("{")]
    action = {
        "get": "Get",
        "post": "Create/Execute",
        "put": "Update",
        "delete": "Delete",
    }.get(method, method.upper())

    resource = " ".join(parts[-2:]) if len(parts) >= 2 else " ".join(parts)
    return f"{action} {resource}"


def _extract_tag(path: str) -> str:
    """Extract the API tag from the path."""
    parts = [p for p in path.split("/") if p and p != "api" and not p.startswith("{")]
    if not parts:
        return "system"

    tag_map = {
        "auth": "auth",
        "servers": "servers",
        "outbounds": "outbounds",
        "alerts": "alerts",
        "incidents": "incidents",
        "notifications": "notifications",
        "notification-channels": "notifications",
        "reports": "reports",
        "export": "reports",
        "license": "license",
        "settings": "settings",
        "branding": "settings",
        "i18n": "settings",
        "monitor": "monitor",
        "users": "users",
        "backups": "backups",
        "audit": "users",
        "audit-logs": "users",
        "health": "system",
        "events": "system",
        "overview": "system",
        "badge": "system",
        "docs": "system",
        "demo": "system",
        "bulk": "servers",
        "tags": "servers",
    }

    return tag_map.get(parts[0], parts[0])


def _extract_path_params(path: str) -> list[dict[str, Any]]:
    """Extract path parameters from a route pattern."""
    params = []
    for part in path.split("/"):
        if part.startswith("{") and part.endswith("}"):
            name = part[1:-1]
            params.append({
                "name": name,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            })
    return params
