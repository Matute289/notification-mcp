"""Tool integration tests using respx to mock the Service API."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
import respx
import httpx

import mcp_server.config as _config_module
import mcp_server.services.service_api_client as _client_module
from mcp_server.context import current_user_id

BASE_URL = "http://localhost:8080"
_TEST_USER_ID = 42

_ENV = {
    "SERVICE_API_URL": BASE_URL,
    "SERVICE_API_KEY": "testkey",
    "SERVICE_API_SECRET": "testsecret",
    "DATABASE_URL": "postgresql://user:pass@localhost:5432/test",
    "SECRET_KEY": "a" * 32,
    "MCP_TRANSPORT": "streamable_http",
    "TEMPLATE_CACHE_TTL_S": "0",
}


@pytest.fixture(autouse=True)
def reset_singletons():
    _config_module._settings = None
    _client_module._client = None
    yield
    _config_module._settings = None
    _client_module._client = None


@pytest.fixture(autouse=True)
def set_user_context():
    """Inject authenticated user into contextvar for all tool tests."""
    token = current_user_id.set(_TEST_USER_ID)
    yield
    current_user_id.reset(token)


@pytest.fixture(autouse=True)
def apply_env():
    with patch.dict(os.environ, _ENV, clear=True):
        yield


async def _make_client():
    from mcp_server.config import get_settings
    from mcp_server.services.service_api_client import init
    await init(get_settings())


# ---------------------------------------------------------------------------
# submit_notification
# ---------------------------------------------------------------------------

@respx.mock
async def test_submit_notification_success():
    await _make_client()
    route = respx.post(f"{BASE_URL}/v1/notifications").mock(
        return_value=httpx.Response(202, json={
            "notification_id": "00000000-0000-0000-0000-000000000001",
            "status": "received", "duplicate": False,
        })
    )
    from mcp_server.tools.notifications import submit_notification
    result = await submit_notification(
        event_id="evt-001", channel="email",
        recipient_email="user@example.com",
        recipient_phone_number=None, recipient_device_token=None,
        template_id=None, variables=None, subject="Hi", body="Hello",
    )
    assert route.called
    assert result["status"] == "received"


@respx.mock
async def test_submit_notification_sends_obo_header():
    await _make_client()
    route = respx.post(f"{BASE_URL}/v1/notifications").mock(
        return_value=httpx.Response(202, json={
            "notification_id": "00000000-0000-0000-0000-000000000002",
            "status": "received", "duplicate": False,
        })
    )
    from mcp_server.tools.notifications import submit_notification
    await submit_notification(
        event_id="evt-002", channel="sms",
        recipient_email=None, recipient_phone_number=None, recipient_device_token=None,
        template_id=None, variables=None, subject=None, body="hi",
    )
    assert route.called
    assert route.calls[0].request.headers["X-On-Behalf-Of-User"] == str(_TEST_USER_ID)


@respx.mock
async def test_submit_notification_forbidden():
    await _make_client()
    respx.post(f"{BASE_URL}/v1/notifications").mock(
        return_value=httpx.Response(403, json={"code": "forbidden", "message": "forbidden"})
    )
    from mcp_server.tools.notifications import submit_notification
    from mcp_server.errors import ForbiddenError
    with pytest.raises(ForbiddenError):
        await submit_notification(
            event_id="evt-003", channel="sms",
            recipient_email=None, recipient_phone_number=None, recipient_device_token=None,
            template_id=None, variables=None, subject=None, body="test",
        )


# ---------------------------------------------------------------------------
# get_notification
# ---------------------------------------------------------------------------

@respx.mock
async def test_get_notification():
    await _make_client()
    nid = "00000000-0000-0000-0000-000000000003"
    respx.get(f"{BASE_URL}/v1/notifications/{nid}").mock(
        return_value=httpx.Response(200, json={
            "id": nid, "event_id": "evt-x", "channel": "email",
            "status": "sent", "attempt": 1, "recipient": {"email": "a@b.com"},
        })
    )
    from mcp_server.tools.notifications import get_notification
    result = await get_notification(nid)
    assert result["status"] == "sent"


@respx.mock
async def test_get_notification_not_found():
    await _make_client()
    nid = "00000000-0000-0000-0000-000000000099"
    respx.get(f"{BASE_URL}/v1/notifications/{nid}").mock(
        return_value=httpx.Response(404, json={"code": "not_found", "message": "not found"})
    )
    from mcp_server.tools.notifications import get_notification
    from mcp_server.errors import NotFoundError
    with pytest.raises(NotFoundError):
        await get_notification(nid)


# ---------------------------------------------------------------------------
# create_template
# ---------------------------------------------------------------------------

@respx.mock
async def test_create_template_sends_obo_header():
    await _make_client()
    route = respx.post(f"{BASE_URL}/v1/templates").mock(
        return_value=httpx.Response(201, json={
            "id": "00000000-0000-0000-0000-000000000010",
            "name": "welcome", "channel": "email", "locale": "en",
            "body": "Hello {{name}}", "version": 1, "owner_user_id": _TEST_USER_ID,
        })
    )
    from mcp_server.tools.templates import create_template
    result = await create_template(name="welcome", channel="email", body="Hello {{name}}")
    assert route.called
    assert route.calls[0].request.headers["X-On-Behalf-Of-User"] == str(_TEST_USER_ID)
    assert result["owner_user_id"] == _TEST_USER_ID


# ---------------------------------------------------------------------------
# register_device
# ---------------------------------------------------------------------------

@respx.mock
async def test_register_device_sends_obo_header():
    await _make_client()
    route = respx.post(f"{BASE_URL}/v1/users/{_TEST_USER_ID}/devices").mock(
        return_value=httpx.Response(204)
    )
    from mcp_server.tools.users import register_device
    result = await register_device(device_token="tok123", channel="push_ios")
    assert route.called
    assert route.calls[0].request.headers["X-On-Behalf-Of-User"] == str(_TEST_USER_ID)
    assert result["success"] is True


# ---------------------------------------------------------------------------
# update_user_setting
# ---------------------------------------------------------------------------

@respx.mock
async def test_update_user_setting():
    await _make_client()
    route = respx.put(f"{BASE_URL}/v1/users/{_TEST_USER_ID}/settings").mock(
        return_value=httpx.Response(204)
    )
    from mcp_server.tools.users import update_user_setting
    result = await update_user_setting(channel="email", opt_in=False)
    assert route.called
    assert route.calls[0].request.headers["X-On-Behalf-Of-User"] == str(_TEST_USER_ID)
    assert result["success"] is True


# ---------------------------------------------------------------------------
# list_templates
# ---------------------------------------------------------------------------

@respx.mock
async def test_list_templates_returns_grouped_by_channel():
    await _make_client()
    tid = "00000000-0000-0000-0000-000000000010"
    respx.get(f"{BASE_URL}/v1/templates").mock(
        return_value=httpx.Response(200, json={
            "email": [
                {"id": tid, "name": "Welcome Email", "channel": "email",
                 "locale": "en", "body": "Hi {{name}}", "version": 1}
            ],
            "sms": [],
            "push_ios": [],
            "push_android": [],
        })
    )
    from mcp_server.tools.templates import list_templates
    result = await list_templates()
    assert "email" in result
    assert len(result["email"]) == 1
    assert result["email"][0]["name"] == "Welcome Email"
    assert result["sms"] == []


@respx.mock
async def test_list_templates_makes_get_request():
    await _make_client()
    route = respx.get(f"{BASE_URL}/v1/templates").mock(
        return_value=httpx.Response(200, json={"email": [], "sms": [], "push_ios": [], "push_android": []})
    )
    from mcp_server.tools.templates import list_templates
    result = await list_templates()
    assert route.called
    assert result == {"email": [], "sms": [], "push_ios": [], "push_android": []}
