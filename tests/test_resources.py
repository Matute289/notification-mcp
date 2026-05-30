"""Tests for MCP resource builder functions."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch


async def test_templates_resource_calls_list_templates():
    with patch("mcp_server.resources.templates.list_templates", new_callable=AsyncMock) as mock:
        mock.return_value = {"email": [], "sms": []}
        from mcp_server.resources.templates import build_templates_resource
        result = await build_templates_resource()
        mock.assert_called_once()
        parsed = json.loads(result)
        assert parsed == {"email": [], "sms": []}


async def test_history_resource_calls_list_notifications_with_limit_20():
    with patch("mcp_server.resources.history.list_notifications", new_callable=AsyncMock) as mock:
        mock.return_value = {"items": [], "next_cursor": "", "limit": 20}
        from mcp_server.resources.history import build_history_resource
        result = await build_history_resource()
        mock.assert_called_once_with(limit=20)
        assert json.loads(result) == {"items": [], "next_cursor": "", "limit": 20}


async def test_settings_resource_calls_get_user_settings():
    with patch("mcp_server.resources.settings.get_user_settings", new_callable=AsyncMock) as mock:
        mock.return_value = [{"channel": "email", "opt_in": True, "updated_at": None}]
        from mcp_server.resources.settings import build_settings_resource
        result = await build_settings_resource()
        mock.assert_called_once()
        parsed = json.loads(result)
        assert parsed[0]["channel"] == "email"


async def test_templates_resource_returns_valid_json():
    with patch("mcp_server.resources.templates.list_templates", new_callable=AsyncMock, return_value={}):
        from mcp_server.resources.templates import build_templates_resource
        json.loads(await build_templates_resource())  # must not raise


async def test_history_resource_returns_valid_json():
    with patch("mcp_server.resources.history.list_notifications", new_callable=AsyncMock,
               return_value={"items": [], "next_cursor": "", "limit": 20}):
        from mcp_server.resources.history import build_history_resource
        json.loads(await build_history_resource())


async def test_settings_resource_returns_valid_json():
    with patch("mcp_server.resources.settings.get_user_settings", new_callable=AsyncMock, return_value=[]):
        from mcp_server.resources.settings import build_settings_resource
        json.loads(await build_settings_resource())
