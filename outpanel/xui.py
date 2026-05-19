from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any


class XUIError(RuntimeError):
    """Custom exception for x-ui panel errors."""
    pass


class XUIClient:
    """Client for interacting with x-ui panel APIs."""

    def __init__(
        self,
        panel_url: str,
        username: str,
        password: str,
        *,
        verify_tls: bool = True,
        timeout: float = 8,
        api_token: str = "",
    ) -> None:
        self.base_url = normalize_panel_url(panel_url)
        self.username = username
        self.password = password
        self.api_token = api_token.strip()
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        handlers: list[Any] = [urllib.request.HTTPCookieProcessor(self.cookie_jar)]
        if not verify_tls:
            handlers.append(
                urllib.request.HTTPSHandler(context=ssl._create_unverified_context())
            )
        self.opener = urllib.request.build_opener(*handlers)

    def login(self) -> None:
        """Authenticate with the x-ui panel."""
        if not self.base_url:
            raise XUIError("x-ui panel URL is missing.")

        # If using API token, skip login — token is sent with each request
        if self.api_token:
            return

        if not self.username or not self.password:
            raise XUIError("x-ui panel username or password is missing.")

        payload = {"username": self.username, "password": self.password}
        try:
            data = self._request_json(
                "POST",
                "/login",
                payload,
                headers={"Content-Type": "application/json"},
            )
        except XUIError:
            # fallback to form-encoded login
            form = urllib.parse.urlencode(payload).encode("utf-8")
            data = self._request_json(
                "POST",
                "/login",
                form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if isinstance(data, dict) and data.get("success") is False:
            message = data.get("msg") or "x-ui panel login failed."
            raise XUIError(str(message))

    def get_status(self) -> dict[str, Any]:
        """Retrieve server status from x-ui."""
        return self._api_get("/panel/api/server/status")

    def list_inbounds(self) -> list[dict[str, Any]]:
        """Retrieve the list of inbounds from x-ui."""
        data = self._api_get("/panel/api/inbounds/list")
        obj = data.get("obj", data) if isinstance(data, dict) else data
        if isinstance(obj, list):
            return [item for item in obj if isinstance(item, dict)]
        raise XUIError("x-ui inbounds/list response is unreadable.")

    def _api_get(self, path: str) -> dict[str, Any]:
        """Internal GET request for x-ui API."""
        data = self._request_json("GET", path)
        if isinstance(data, dict) and data.get("success") is False:
            message = data.get("msg") or f"Request {path} failed."
            raise XUIError(str(message))
        if not isinstance(data, dict):
            raise XUIError(f"Response from {path} is not a JSON object.")
        return data

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | bytes | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Internal request helper that returns parsed JSON."""
        data: bytes | None
        request_headers = {"Accept": "application/json", **(headers or {})}

        # Add API token to all requests if configured
        if self.api_token:
            request_headers["Authorization"] = f"Bearer {self.api_token}"

        if isinstance(payload, dict):
            data = json.dumps(payload).encode("utf-8")
        else:
            data = payload

        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers=request_headers,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise XUIError(f"HTTP error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise XUIError(f"Failed to connect to x-ui: {exc.reason}") from exc
        except TimeoutError as exc:
            raise XUIError("x-ui connection timed out.") from exc

        if not body.strip():
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise XUIError("x-ui response is not valid JSON.") from exc


def normalize_panel_url(panel_url: str) -> str:
    """Normalize x-ui panel URL, removing trailing /panel or /panel/api suffix."""
    raw = (panel_url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urllib.parse.urlsplit(raw)
    path = parsed.path.rstrip("/")
    for suffix in ("/panel/api", "/panel"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
    normalized = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, path.rstrip("/"), "", "")
    )
    return normalized.rstrip("/")
