"""Tool integration tests using respx to mock the NotificationEngine HTTP API."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
import respx
import httpx

from notification_mcp import config as _config_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8080"

_ENV = {
    "NOTIFICATION_ENGINE_APP_KEY": "testkey",
    "NOTIFICATION_ENGINE_APP_SECRET": "testsecret",
    "NOTIFICATION_ENGINE_BASE_URL": BASE_URL,
    "TEMPLATE_CACHE_TTL_S": "0",  # disable cache for tests
}


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset the settings singleton between tests."""
    _config_module._settings = None
    with patch.dict(os.environ, _ENV, clear=True):
        yield
    _config_module._settings = None


@pytest.fixture(autouse=True)
def reset_client():
    """Reset the HTTP client singleton between tests."""
    import notification_mcp.client as _client_module
    _client_module._client = None
    yield
    _client_module._client = None


def _make_client():
    from notification_mcp.config import get_settings
    from notification_mcp.client import init_client, _get_client
    init_client(get_settings())
    return _get_client()


# ---------------------------------------------------------------------------
# submit_notification
# ---------------------------------------------------------------------------

@respx.mock
async def test_submit_notification_success():
    _make_client()
    route = respx.post(f"{BASE_URL}/v1/notifications").mock(
        return_value=httpx.Response(
            202,
            json={
                "notification_id": "00000000-0000-0000-0000-000000000001",
                "status": "received",
                "duplicate": False,
            },
        )
    )

    from notification_mcp.tools.notifications import submit_notification
    result = await submit_notification(
        event_id="evt-001",
        channel="email",
        recipient_user_id=None,
        recipient_email="user@example.com",
        recipient_phone_number=None,
        recipient_device_token=None,
        template_id=None,
        variables=None,
        subject="Hello",
        body="World",
    )

    assert route.called
    assert result["status"] == "received"
    assert result["duplicate"] is False


@respx.mock
async def test_submit_notification_sends_obo_header_when_user_id():
    _make_client()
    route = respx.post(f"{BASE_URL}/v1/notifications").mock(
        return_value=httpx.Response(
            202,
            json={
                "notification_id": "00000000-0000-0000-0000-000000000002",
                "status": "received",
                "duplicate": False,
            },
        )
    )

    from notification_mcp.tools.notifications import submit_notification
    await submit_notification(
        event_id="evt-002",
        channel="sms",
        recipient_user_id=42,
        recipient_email=None,
        recipient_phone_number=None,
        recipient_device_token=None,
        template_id=None,
        variables=None,
        subject=None,
        body="hi",
    )

    assert route.called
    sent_request = route.calls[0].request
    assert sent_request.headers["X-On-Behalf-Of-User"] == "42"


@respx.mock
async def test_submit_notification_forbidden():
    _make_client()
    respx.post(f"{BASE_URL}/v1/notifications").mock(
        return_value=httpx.Response(403, json={"code": "forbidden", "message": "forbidden"})
    )

    from notification_mcp.tools.notifications import submit_notification
    from notification_mcp.errors import ForbiddenError
    with pytest.raises(ForbiddenError):
        await submit_notification(
            event_id="evt-003",
            channel="sms",
            recipient_user_id=99,
            recipient_email=None,
            recipient_phone_number=None,
            recipient_device_token=None,
            template_id=None,
            variables=None,
            subject=None,
            body="test",
        )


# ---------------------------------------------------------------------------
# get_notification
# ---------------------------------------------------------------------------

@respx.mock
async def test_get_notification():
    _make_client()
    nid = "00000000-0000-0000-0000-000000000003"
    respx.get(f"{BASE_URL}/v1/notifications/{nid}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": nid,
                "event_id": "evt-x",
                "channel": "email",
                "status": "sent",
                "attempt": 1,
                "recipient": {"email": "a@b.com"},
            },
        )
    )

    from notification_mcp.tools.notifications import get_notification
    result = await get_notification(nid)
    assert result["status"] == "sent"
    assert result["channel"] == "email"


@respx.mock
async def test_get_notification_not_found():
    _make_client()
    nid = "00000000-0000-0000-0000-000000000099"
    respx.get(f"{BASE_URL}/v1/notifications/{nid}").mock(
        return_value=httpx.Response(404, json={"code": "not_found", "message": "not found"})
    )

    from notification_mcp.tools.notifications import get_notification
    from notification_mcp.errors import NotFoundError
    with pytest.raises(NotFoundError):
        await get_notification(nid)


# ---------------------------------------------------------------------------
# create_template
# ---------------------------------------------------------------------------

@respx.mock
async def test_create_template_sends_obo_header():
    _make_client()
    route = respx.post(f"{BASE_URL}/v1/templates").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "00000000-0000-0000-0000-000000000010",
                "name": "welcome",
                "channel": "email",
                "locale": "en",
                "body": "Hello {{name}}",
                "version": 1,
                "owner_user_id": 42,
            },
        )
    )

    from notification_mcp.tools.templates import create_template
    result = await create_template(user_id=42, name="welcome", channel="email", body="Hello {{name}}")

    assert route.called
    sent_request = route.calls[0].request
    assert sent_request.headers["X-On-Behalf-Of-User"] == "42"
    assert result["owner_user_id"] == 42


# ---------------------------------------------------------------------------
# register_device
# ---------------------------------------------------------------------------

@respx.mock
async def test_register_device_sends_obo_header():
    _make_client()
    route = respx.post(f"{BASE_URL}/v1/users/42/devices").mock(
        return_value=httpx.Response(204)
    )

    from notification_mcp.tools.users import register_device
    result = await register_device(user_id=42, device_token="tok123", channel="push_ios")

    assert route.called
    sent_request = route.calls[0].request
    assert sent_request.headers["X-On-Behalf-Of-User"] == "42"
    assert result["success"] is True


@respx.mock
async def test_register_device_forbidden():
    _make_client()
    respx.post(f"{BASE_URL}/v1/users/99/devices").mock(
        return_value=httpx.Response(403, json={"code": "forbidden", "message": "forbidden"})
    )

    from notification_mcp.tools.users import register_device
    from notification_mcp.errors import ForbiddenError
    # The MCP would call this with user_id=99 but the server sees OBO=42 mismatch
    with pytest.raises(ForbiddenError):
        await register_device(user_id=99, device_token="tok123", channel="push_ios")


# ---------------------------------------------------------------------------
# update_user_setting
# ---------------------------------------------------------------------------

@respx.mock
async def test_update_user_setting():
    _make_client()
    route = respx.put(f"{BASE_URL}/v1/users/7/settings").mock(
        return_value=httpx.Response(204)
    )

    from notification_mcp.tools.users import update_user_setting
    result = await update_user_setting(user_id=7, channel="email", opt_in=False)

    assert route.called
    sent_request = route.calls[0].request
    assert sent_request.headers["X-On-Behalf-Of-User"] == "7"
    assert result["success"] is True
