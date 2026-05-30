"""Pydantic model validation tests."""
from __future__ import annotations

import uuid

import pytest


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------

def test_channel_includes_social_channels():
    from mcp_server.models import Channel
    import typing
    args = typing.get_args(Channel)
    assert "telegram" in args
    assert "whatsapp" in args
    assert "line" in args
    assert "facebook_messenger" in args


# ---------------------------------------------------------------------------
# RecipientInput
# ---------------------------------------------------------------------------

def test_recipient_input_accepts_messaging_id():
    from mcp_server.models import RecipientInput
    inp = RecipientInput(messaging_id="12345678")
    assert inp.messaging_id == "12345678"


def test_recipient_input_messaging_id_is_optional():
    from mcp_server.models import RecipientInput
    inp = RecipientInput()
    assert inp.messaging_id is None


# ---------------------------------------------------------------------------
# UpdateTemplateInput — bug fix: channel/locale/version removed
# ---------------------------------------------------------------------------

def test_update_template_input_minimal():
    from mcp_server.models import UpdateTemplateInput
    tid = uuid.uuid4()
    inp = UpdateTemplateInput(template_id=tid, name="Welcome", body="Hello")
    assert inp.template_id == tid
    assert inp.name == "Welcome"
    assert inp.body == "Hello"
    assert inp.subject is None
    assert inp.media_urls is None


def test_update_template_input_with_subject_and_media():
    from mcp_server.models import UpdateTemplateInput
    inp = UpdateTemplateInput(
        template_id=uuid.uuid4(),
        name="Promo",
        body="Body text",
        subject="Subject here",
        media_urls=["https://example.com/img.jpg"],
    )
    assert inp.subject == "Subject here"
    assert inp.media_urls == ["https://example.com/img.jpg"]


def test_update_template_input_rejects_channel():
    from mcp_server.models import UpdateTemplateInput
    with pytest.raises(Exception):
        UpdateTemplateInput(
            template_id=uuid.uuid4(), name="Bad", body="Body",
            channel="email",
        )


def test_update_template_input_rejects_locale():
    from mcp_server.models import UpdateTemplateInput
    with pytest.raises(Exception):
        UpdateTemplateInput(
            template_id=uuid.uuid4(), name="Bad", body="Body",
            locale="es",
        )


def test_update_template_input_rejects_version():
    from mcp_server.models import UpdateTemplateInput
    with pytest.raises(Exception):
        UpdateTemplateInput(
            template_id=uuid.uuid4(), name="Bad", body="Body",
            version=2,
        )


def test_update_template_input_strips_whitespace():
    from mcp_server.models import UpdateTemplateInput
    inp = UpdateTemplateInput(
        template_id=uuid.uuid4(), name="  Welcome  ", body="Hello",
    )
    assert inp.name == "Welcome"


# ---------------------------------------------------------------------------
# TemplateView — timestamps
# ---------------------------------------------------------------------------

def test_template_view_accepts_timestamps():
    from mcp_server.models import TemplateView
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    view = TemplateView(
        id=uuid.uuid4(), name="T", channel="email", locale="en",
        body="Hi", version=1, created_at=now, updated_at=now,
    )
    assert view.created_at == now
    assert view.updated_at == now


def test_template_view_timestamps_optional():
    from mcp_server.models import TemplateView
    view = TemplateView(
        id=uuid.uuid4(), name="T", channel="email", locale="en",
        body="Hi", version=1,
    )
    assert view.created_at is None
    assert view.updated_at is None


# ---------------------------------------------------------------------------
# SettingView (new)
# ---------------------------------------------------------------------------

def test_setting_view_with_opt_in():
    from mcp_server.models import SettingView
    sv = SettingView(channel="email", opt_in=True)
    assert sv.channel == "email"
    assert sv.opt_in is True
    assert sv.updated_at is None


def test_setting_view_with_updated_at():
    from mcp_server.models import SettingView
    from datetime import datetime, timezone
    ts = datetime(2025, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
    sv = SettingView(channel="sms", opt_in=False, updated_at=ts)
    assert sv.opt_in is False
    assert sv.updated_at == ts


# ---------------------------------------------------------------------------
# NotificationListResponse (new)
# ---------------------------------------------------------------------------

def test_notification_list_response_empty():
    from mcp_server.models import NotificationListResponse
    resp = NotificationListResponse(items=[], next_cursor="", limit=20)
    assert resp.items == []
    assert resp.next_cursor == ""
    assert resp.limit == 20
