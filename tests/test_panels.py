"""Unit tests for multi-panel support."""
import pytest
from outpanel.panels import (
    create_panel_client,
    PANEL_XUI,
    PANEL_3XUI,
    PANEL_MARZBAN,
    SUPPORTED_PANELS,
    XUIPanelClient,
    MarzbanPanelClient,
)


class TestPanelFactory:
    def test_supported_panels(self):
        assert PANEL_XUI in SUPPORTED_PANELS
        assert PANEL_3XUI in SUPPORTED_PANELS
        assert PANEL_MARZBAN in SUPPORTED_PANELS

    def test_create_xui_client(self):
        client = create_panel_client("x-ui", "http://test.com", "admin", "pass")
        assert isinstance(client, XUIPanelClient)

    def test_create_3xui_client(self):
        client = create_panel_client("3x-ui", "http://test.com", "admin", "pass")
        assert isinstance(client, XUIPanelClient)
        assert client.is_3xui is True

    def test_create_marzban_client(self):
        client = create_panel_client("marzban", "http://test.com", "admin", "pass")
        assert isinstance(client, MarzbanPanelClient)

    def test_unknown_panel_defaults_to_xui(self):
        client = create_panel_client("unknown_panel", "http://test.com", "admin", "pass")
        assert isinstance(client, XUIPanelClient)

    def test_api_token_support(self):
        client = create_panel_client("x-ui", "http://test.com", "", "", api_token="my_token")
        assert isinstance(client, XUIPanelClient)
