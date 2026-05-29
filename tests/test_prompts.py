"""Tests for MCP prompt message builders."""
from __future__ import annotations


# ---------------------------------------------------------------------------
# create_template
# ---------------------------------------------------------------------------

def test_create_template_prompt_lists_all_channels_when_no_channel():
    from mcp_server.prompts.create_template import build_create_template_message
    msg = build_create_template_message()
    assert "email" in msg.lower()
    assert "sms" in msg.lower()
    assert "push_ios" in msg.lower() or "push ios" in msg.lower()
    assert "push_android" in msg.lower() or "push android" in msg.lower()


def test_create_template_prompt_suggests_locale_options():
    from mcp_server.prompts.create_template import build_create_template_message
    msg = build_create_template_message()
    assert '"es"' in msg or "(es)" in msg
    assert '"en"' in msg or "(en)" in msg
    assert '"pt"' in msg or "(pt)" in msg


def test_create_template_prompt_injects_prefilled_channel():
    from mcp_server.prompts.create_template import build_create_template_message
    msg = build_create_template_message(channel="email")
    assert "email" in msg.lower()
    # When channel is pre-filled, should skip asking for channel
    assert "saltá" in msg.lower() or "skip" in msg.lower() or "ya indicó" in msg.lower()


def test_create_template_prompt_injects_prefilled_purpose():
    from mcp_server.prompts.create_template import build_create_template_message
    msg = build_create_template_message(purpose="confirmación de pedido")
    assert "confirmación de pedido" in msg


def test_create_template_prompt_mentions_variable_syntax():
    from mcp_server.prompts.create_template import build_create_template_message
    msg = build_create_template_message()
    assert "{{" in msg and "}}" in msg


def test_create_template_prompt_returns_nonempty_string():
    from mcp_server.prompts.create_template import build_create_template_message
    msg = build_create_template_message()
    assert isinstance(msg, str)
    assert len(msg) > 100


# ---------------------------------------------------------------------------
# update_template
# ---------------------------------------------------------------------------

def test_update_template_prompt_instructs_list_first():
    from mcp_server.prompts.update_template import build_update_template_message
    msg = build_update_template_message()
    assert "list_templates_tool" in msg


def test_update_template_prompt_shows_field_menu():
    from mcp_server.prompts.update_template import build_update_template_message
    msg = build_update_template_message()
    # Must show all editable fields
    assert "nombre" in msg.lower() or "name" in msg.lower()
    assert "cuerpo" in msg.lower() or "body" in msg.lower()
    assert "asunto" in msg.lower() or "subject" in msg.lower()
    assert "idioma" in msg.lower() or "locale" in msg.lower()
    assert "versión" in msg.lower() or "version" in msg.lower()


def test_update_template_prompt_suggests_locale_options():
    from mcp_server.prompts.update_template import build_update_template_message
    msg = build_update_template_message()
    assert "(es)" in msg or '"es"' in msg
    assert "(en)" in msg or '"en"' in msg


def test_update_template_prompt_filters_by_channel_when_provided():
    from mcp_server.prompts.update_template import build_update_template_message
    msg = build_update_template_message(channel="sms")
    assert "sms" in msg.lower()


def test_update_template_prompt_instructs_use_id_for_update():
    from mcp_server.prompts.update_template import build_update_template_message
    msg = build_update_template_message()
    assert "update_template_tool" in msg


def test_update_template_prompt_returns_nonempty_string():
    from mcp_server.prompts.update_template import build_update_template_message
    msg = build_update_template_message()
    assert isinstance(msg, str)
    assert len(msg) > 100
