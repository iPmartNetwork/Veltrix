"""Veltrix OutPanel — Main HTTP application server.

Serves the API and static web dashboard using Python's built-in HTTP server.
Integrates rate limiting, request logging, and the router-based API dispatch.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .auth import get_user_by_session, has_permission, service_user
from .db import PROJECT_ROOT, init_db, seed_demo_if_empty
from .logger import get_request_logger
from .migrations import run_pending_migrations
from .monitor import monitor_loop
from .ratelimit import check_rate_limit
from .router import RequestContext
from .routes import build_router
from .sse import get_sse_broker
from .worker import enhanced_monitor_loop

WEB_ROOT = PROJECT_ROOT / "web"
API_TOKEN = os.getenv("OUTPANEL_API_TOKEN", "").strip()

# Build the router once at module level
_router = build_router()


class OutPanelHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Veltrix OutPanel."""

    server_version = f"Veltrix/{__version__}"

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self.handle_api("GET")
            return
        self.serve_static()

    def do_POST(self) -> None:
        self.handle_api("POST")

    def do_PUT(self) -> None:
        self.handle_api("PUT")

    def do_DELETE(self) -> None:
        self.handle_api("DELETE")

    def handle_api(self, method: str) -> None:
        """Dispatch API requests through the router."""
        start_time = time.perf_counter()
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        client_ip = self.client_ip()
        status_code = 200
        error_msg: str | None = None

        try:
            # Rate limiting
            allowed, rate_info = check_rate_limit(client_ip)
            if not allowed:
                self.json_response(
                    {"error": "Too many requests. Please slow down."},
                    HTTPStatus.TOO_MANY_REQUESTS,
                    rate_headers=rate_info,
                )
                status_code = 429
                return

            # Route resolution
            match = _router.resolve(method, path)
            if not match:
                self.json_response({"error": "not found"}, HTTPStatus.NOT_FOUND)
                status_code = 404
                return

            route, params = match

            # Authentication
            current_user: dict[str, Any] | None = None
            if route.auth_required:
                current_user = self.authenticate_request()
                if not current_user:
                    self.json_response({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                    status_code = 401
                    return

                # Permission check
                if route.permission and not has_permission(current_user, route.permission):
                    self.json_response(
                        {"error": "You do not have permission to access this resource."},
                        HTTPStatus.FORBIDDEN,
                    )
                    status_code = 403
                    return

            # Build request context
            body = self.read_json() if method in ("POST", "PUT", "PATCH") else {}
            ctx = RequestContext(
                method=method,
                path=path,
                params=params,
                query=query,
                body=body,
                user=current_user,
                client_ip=client_ip,
                session_token=self.session_token(),
                user_agent=self.headers.get("User-Agent"),
            )

            # Execute handler
            result = route.handler(ctx)
            if result is None:
                result = {"ok": True}

            # Handle SSE stream
            if result.get("__sse_stream"):
                self._serve_sse_stream()
                return

            # Handle session cookie directives
            if result.get("__set_session"):
                self.set_session_cookie(result.pop("__set_session"))
            if result.pop("__clear_session", None):
                self.clear_session_cookie()

            # Determine response status
            response_status = HTTPStatus.OK
            if method == "POST" and result.get("ok") and "id" in result:
                response_status = HTTPStatus.CREATED

            self.json_response(result, response_status, rate_headers=rate_info)
            status_code = response_status.value

        except PermissionError as exc:
            error_msg = str(exc)
            self.json_response({"error": error_msg}, HTTPStatus.FORBIDDEN)
            status_code = 403
        except ValueError as exc:
            error_msg = str(exc)
            self.json_response({"error": error_msg}, HTTPStatus.BAD_REQUEST)
            status_code = 400
        except Exception as exc:
            error_msg = str(exc)
            self.json_response({"error": error_msg}, HTTPStatus.INTERNAL_SERVER_ERROR)
            status_code = 500
        finally:
            # Log the request
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger = get_request_logger()
            logger.log_request(
                method=method,
                path=path,
                client_ip=client_ip,
                status_code=status_code,
                duration_ms=duration_ms,
                user_agent=self.headers.get("User-Agent"),
                error=error_msg,
            )

    # --- Utility methods ---

    def authenticate_request(self) -> dict[str, Any] | None:
        """Authenticate the request via Bearer token, API token, or session cookie."""
        auth = self.headers.get("Authorization", "")
        header_token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
        api_token = self.headers.get("X-OutPanel-Token", "").strip()
        if API_TOKEN and (header_token == API_TOKEN or api_token == API_TOKEN):
            return service_user()
        return get_user_by_session(self.session_token())

    def session_token(self) -> str | None:
        """Extract session token from Authorization header or cookie."""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and (not API_TOKEN or auth.removeprefix("Bearer ").strip() != API_TOKEN):
            return auth.removeprefix("Bearer ").strip()
        cookie_header = self.headers.get("Cookie", "")
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        morsel = cookie.get("veltrix_session")
        return morsel.value if morsel else None

    def set_session_cookie(self, token: str) -> None:
        self._session_cookie = f"veltrix_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800"

    def clear_session_cookie(self) -> None:
        self._session_cookie = "veltrix_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

    def client_ip(self) -> str:
        """Get client IP, respecting X-Forwarded-For header."""
        forwarded = self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        return forwarded or str(self.client_address[0])

    def read_json(self) -> dict[str, Any]:
        """Read and parse JSON request body."""
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def json_response(
        self,
        data: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        *,
        rate_headers: dict[str, Any] | None = None,
    ) -> None:
        """Send a JSON response with appropriate headers."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))

        # Rate limit headers
        if rate_headers:
            self.send_header("X-RateLimit-Limit", str(rate_headers.get("limit", "")))
            self.send_header("X-RateLimit-Remaining", str(rate_headers.get("remaining", "")))

        # Session cookie
        if getattr(self, "_session_cookie", None):
            self.send_header("Set-Cookie", self._session_cookie)
            self._session_cookie = None

        self.end_headers()
        self.wfile.write(body)

    def serve_static(self) -> None:
        """Serve static files from the web directory."""
        parsed = urlparse(self.path)
        requested = parsed.path if parsed.path != "/" else "/index.html"
        target = (WEB_ROOT / requested.lstrip("/")).resolve()
        if not str(target).startswith(str(WEB_ROOT.resolve())) or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND.value)
            return
        content = target.read_bytes()
        mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", mime_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_sse_stream(self) -> None:
        """Serve a Server-Sent Events stream to the client."""
        broker = get_sse_broker()
        client_queue = broker.subscribe()

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        try:
            # Send initial connection event
            self.wfile.write(b"event: connected\ndata: {\"ok\":true}\n\n")
            self.wfile.flush()

            while True:
                try:
                    message = client_queue.get(timeout=30)
                    if not message:
                        break  # Empty message = close signal
                    self.wfile.write(message.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            broker.unsubscribe(client_queue)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP server logging (handled by our logger)."""
        if os.getenv("OUTPANEL_QUIET", "") == "1":
            return
        # Use our structured logger instead of default stderr output
        pass


def main() -> None:
    """Entry point for the Veltrix OutPanel server."""
    parser = argparse.ArgumentParser(description="Veltrix OutPanel Server")
    parser.add_argument("--host", default=os.getenv("OUTPANEL_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("OUTPANEL_PORT", "8000")))
    args = parser.parse_args()

    # Initialize database
    init_db()
    seed_demo_if_empty()

    # Run pending migrations
    migration_results = run_pending_migrations()
    if migration_results:
        for m in migration_results:
            print(f"  Migration {m['version']}: {m['status']}")

    # Start background monitor (enhanced with SSE and auto-disable)
    stop_event = threading.Event()
    monitor_interval = int(os.getenv("OUTPANEL_MONITOR_INTERVAL", "30"))
    if os.getenv("OUTPANEL_DISABLE_MONITOR", "") != "1":
        monitor_thread = threading.Thread(
            target=enhanced_monitor_loop,
            args=(stop_event, monitor_interval),
            daemon=True,
            name="veltrix-worker",
        )
        monitor_thread.start()

    # Start HTTP server
    logger = get_request_logger()
    logger.log_startup(args.host, args.port, __version__)

    server = ThreadingHTTPServer((args.host, args.port), OutPanelHandler)
    print(f"Veltrix {__version__} running on http://{args.host}:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.shutdown()
        print("\nVeltrix stopped.")


if __name__ == "__main__":
    main()
