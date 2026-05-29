"""Pydantic model validation tests."""
from __future__ import annotations

import uuid

import pytest


def test_update_template_input_valid_minimal():
    from mcp_server.models import UpdateTemplateInput
    tid = uuid.uuid4()
    inp = UpdateTemplateInput(
        template_id=tid,
        name="Welcome",
        channel="email",
        body="Hello {{name}}",
    )
    assert inp.template_id == tid
    assert inp.locale == "en"
    assert inp.version == 1
    assert inp.subject is None
    assert inp.media_urls is None


def test_update_template_input_valid_full():
    from mcp_server.models import UpdateTemplateInput
    inp = UpdateTemplateInput(
        template_id=uuid.uuid4(),
        name="Promo SMS",
        channel="sms",
        body="Oferta especial: {{descuento}}%",
        locale="es",
        version=3,
        media_urls=["https://example.com/img.jpg"],
    )
    assert inp.locale == "es"
    assert inp.version == 3
    assert inp.media_urls == ["https://example.com/img.jpg"]


def test_update_template_input_invalid_channel():
    from mcp_server.models import UpdateTemplateInput
    with pytest.raises(Exception):
        UpdateTemplateInput(
            template_id=uuid.uuid4(),
            name="Bad",
            channel="fax",
            body="Hello",
        )


def test_update_template_input_rejects_extra_field():
    from mcp_server.models import UpdateTemplateInput
    with pytest.raises(Exception):
        UpdateTemplateInput(
            template_id=uuid.uuid4(),
            name="Bad",
            channel="email",
            body="Hello",
            unknown_field="oops",
        )


def test_update_template_input_strips_whitespace():
    from mcp_server.models import UpdateTemplateInput
    inp = UpdateTemplateInput(
        template_id=uuid.uuid4(),
        name="  Welcome  ",
        channel="email",
        body="Hello",
    )
    assert inp.name == "Welcome"
