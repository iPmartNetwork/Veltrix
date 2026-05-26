"""Multi-panel support for Veltrix.

Supports multiple panel types beyond x-ui:
- x-ui (original, Alireza)
- 3x-ui (MHSanaei fork)
- Marzban

Each panel type has its own client adapter that normalizes
the API responses into Veltrix's internal format.
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any

from .xui import XUIClient, XUIError, normalize_panel_url


# Panel type constants
PANEL_XUI = "x-ui"
PANEL_3XUI = "3x-ui"
PANEL_MARZBAN = "marzban"

SUPPORTED_PANELS = {
    PANEL_XUI: "x-ui (Original)",
    PANEL_3XUI: "3x-ui (MHSanaei)",
    PANEL_MARZBAN: "Marzban",
}


def create_panel_client(
    panel_type: str,
    panel_url: str,
    username: str = "",
    password: str = "",
    api_token: str = "",
    verify_tls: bool = True,
    timeout: float = 8,
) -> "BasePanelClient":
    """Factory: create the appropriate panel client based on type."""
    panel_type = (panel_type or PANEL_XUI).lower().strip()

    if panel_type in (PANEL_XUI, PANEL_3XUI):
        return XUIPanelClient(
            panel_url=panel_url,
            username=username,
            password=password,
            api_token=api_token,
            verify_tls=verify_tls,
            timeout=timeout,
            is_3xui=(panel_type == PANEL_3XUI),
        )
    elif panel_type == PANEL_MARZBAN:
        return MarzbanPanelClient(
            panel_url=panel_url,
            username=username,
            password=password,
            api_token=api_token,
            verify_tls=verify_tls,
            timeout=timeout,
        )
    else:
        # Default to x-ui
        return XUIPanelClient(
            panel_url=panel_url,
            username=username,
            password=password,
            api_token=api_token,
            verify_tls=verify_tls,
            timeout=timeout,
        )


class BasePanelClient:
    """Base class for panel clients."""

    def login(self) -> None:
        raise NotImplementedError

    def get_status(self) -> dict[str, Any]:
        raise NotImplementedError

    def list_inbounds(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class XUIPanelClient(BasePanelClient):
    """Client for x-ui and 3x-ui panels (compatible API)."""

    def __init__(self, panel_url: str, username: str, password: str,
                 api_token: str = "", verify_tls: bool = True,
                 timeout: float = 8, is_3xui: bool = False) -> None:
        self.is_3xui = is_3xui
        self._client = XUIClient(
            panel_url=panel_url,
            username=username,
            password=password,
            api_token=api_token,
            verify_tls=verify_tls,
            timeout=timeout,
        )

    def login(self) -> None:
        self._client.login()

    def get_status(self) -> dict[str, Any]:
        return self._client.get_status()

    def list_inbounds(self) -> list[dict[str, Any]]:
        return self._client.list_inbounds()


class MarzbanPanelClient(BasePanelClient):
    """Client for Marzban panel API.

    Marzban uses a different API structure:
    - Auth: POST /api/admin/token (OAuth2 form)
    - Status: GET /api/system
    - Users/Proxies: GET /api/users
    """

    def __init__(self, panel_url: str, username: str, password: str,
                 api_token: str = "", verify_tls: bool = True,
                 timeout: float = 8) -> None:
        self.base_url = normalize_panel_url(panel_url)
        self.username = username
        self.password = password
        self.api_token = api_token.strip()
        self.timeout = timeout
        self.access_token = ""

        handlers: list[Any] = []
        if not verify_tls:
            handlers.append(
                urllib.request.HTTPSHandler(context=ssl._create_unverified_context())
            )
        self.opener = urllib.request.build_opener(*handlers)

    def login(self) -> None:
        """Authenticate with Marzban using OAuth2 or API token."""
        if self.api_token:
            self.access_token = self.api_token
            return

        if not self.username or not self.password:
            raise XUIError("Marzban username or password is missing.")

        # Marzban uses OAuth2 form-encoded login
        form_data = urllib.parse.urlencode({
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
        }).encode("utf-8")

        request = urllib.request.Request(
            self.base_url + "/api/admin/token",
            data=form_data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                self.access_token = data.get("access_token", "")
                if not self.access_token:
                    raise XUIError("Marzban login failed: no access token returned.")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise XUIError(f"Marzban login failed (HTTP {exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise XUIError(f"Cannot connect to Marzban: {exc.reason}") from exc

    def get_status(self) -> dict[str, Any]:
        """Get system status from Marzban."""
        data = self._api_get("/api/system")
        # Normalize to x-ui format
        return {
            "obj": {
                "cpu": data.get("cpu_usage"),
                "mem": {
                    "current": data.get("mem_used"),
                    "total": data.get("mem_total"),
                },
                "disk": {
                    "current": data.get("disk_used"),
                    "total": data.get("disk_total"),
                },
                "xray": {
                    "state": "running" if data.get("xray_version") else "unknown",
                    "version": data.get("xray_version"),
                },
                "uptime": data.get("uptime"),
            }
        }

    def list_inbounds(self) -> list[dict[str, Any]]:
        """Get inbounds from Marzban (mapped from users/proxies)."""
        # Marzban exposes inbounds differently — via /api/inbounds
        try:
            data = self._api_get("/api/inbounds")
            if isinstance(data, dict):
                # Marzban returns {protocol: [inbound_tags]}
                inbounds = []
                inbound_id = 1
                for protocol, tags in data.items():
                    if isinstance(tags, list):
                        for tag in tags:
                            inbounds.append({
                                "id": inbound_id,
                                "remark": tag if isinstance(tag, str) else str(tag),
                                "protocol": protocol,
                                "port": 0,
                                "enable": True,
                                "up": 0,
                                "down": 0,
                            })
                            inbound_id += 1
                return inbounds
            return []
        except XUIError:
            # Fallback: try to get from hosts
            return []

    def _api_get(self, path: str) -> Any:
        """Make an authenticated GET request to Marzban API."""
        request = urllib.request.Request(
            self.base_url + path,
            method="GET",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise XUIError(f"Marzban API error (HTTP {exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise XUIError(f"Cannot connect to Marzban: {exc.reason}") from exc
