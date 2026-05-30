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


# ---------------------------------------------------------------------------
# manage_preferences
# ---------------------------------------------------------------------------

def test_manage_preferences_prompt_shows_top_level_menu():
    from mcp_server.prompts.manage_preferences import build_manage_preferences_message
    msg = build_manage_preferences_message()
    # Must show both main options
    assert "activar" in msg.lower() or "desactivar" in msg.lower()
    assert "push" in msg.lower()


def test_manage_preferences_prompt_mentions_all_channels():
    from mcp_server.prompts.manage_preferences import build_manage_preferences_message
    msg = build_manage_preferences_message()
    assert "email" in msg.lower()
    assert "sms" in msg.lower()
    assert "push_ios" in msg.lower() or "push ios" in msg.lower()
    assert "push_android" in msg.lower() or "push android" in msg.lower()


def test_manage_preferences_prompt_mentions_tools():
    from mcp_server.prompts.manage_preferences import build_manage_preferences_message
    msg = build_manage_preferences_message()
    assert "update_user_setting_tool" in msg
    assert "register_device_tool" in msg


def test_manage_preferences_prompt_explains_device_token():
    from mcp_server.prompts.manage_preferences import build_manage_preferences_message
    msg = build_manage_preferences_message()
    # Should explain what a device token is in plain language
    assert "teléfono" in msg.lower() or "celular" in msg.lower() or "phone" in msg.lower()


def test_manage_preferences_prompt_returns_nonempty_string():
    from mcp_server.prompts.manage_preferences import build_manage_preferences_message
    msg = build_manage_preferences_message()
    assert isinstance(msg, str)
    assert len(msg) > 100


# ---------------------------------------------------------------------------
# onboarding
# ---------------------------------------------------------------------------

def test_onboarding_prompt_includes_welcome():
    from mcp_server.prompts.onboarding import build_onboarding_message
    msg = build_onboarding_message()
    assert "bienvenid" in msg.lower() or "salud" in msg.lower()


def test_onboarding_prompt_covers_push_device_registration():
    from mcp_server.prompts.onboarding import build_onboarding_message
    msg = build_onboarding_message()
    assert "register_device_tool" in msg
    assert "push" in msg.lower()


def test_onboarding_prompt_covers_channel_preferences():
    from mcp_server.prompts.onboarding import build_onboarding_message
    msg = build_onboarding_message()
    assert "update_user_setting_tool" in msg
    assert "email" in msg.lower()
    assert "sms" in msg.lower()


def test_onboarding_prompt_offers_next_steps():
    from mcp_server.prompts.onboarding import build_onboarding_message
    msg = build_onboarding_message()
    assert "submit_notification_tool" in msg or "notificación de prueba" in msg.lower()
    assert "template" in msg.lower()


def test_onboarding_prompt_explains_system_in_plain_language():
    from mcp_server.prompts.onboarding import build_onboarding_message
    msg = build_onboarding_message()
    assert "email" in msg.lower()
    assert "sms" in msg.lower()
    assert "push" in msg.lower()


def test_onboarding_prompt_returns_nonempty_string():
    from mcp_server.prompts.onboarding import build_onboarding_message
    msg = build_onboarding_message()
    assert isinstance(msg, str)
    assert len(msg) > 100


# ---------------------------------------------------------------------------
# create_template — social channels
# ---------------------------------------------------------------------------

def test_create_template_prompt_includes_telegram():
    from mcp_server.prompts.create_template import build_create_template_message
    msg = build_create_template_message()
    assert "telegram" in msg.lower()


def test_create_template_prompt_includes_whatsapp():
    from mcp_server.prompts.create_template import build_create_template_message
    msg = build_create_template_message()
    assert "whatsapp" in msg.lower()


def test_create_template_prompt_includes_line():
    from mcp_server.prompts.create_template import build_create_template_message
    msg = build_create_template_message()
    assert "line" in msg.lower()


def test_create_template_prompt_includes_facebook_messenger():
    from mcp_server.prompts.create_template import build_create_template_message
    msg = build_create_template_message()
    assert "facebook" in msg.lower() or "messenger" in msg.lower()


# ---------------------------------------------------------------------------
# update_template — delete option
# ---------------------------------------------------------------------------

def test_update_template_prompt_includes_delete_option():
    from mcp_server.prompts.update_template import build_update_template_message
    msg = build_update_template_message()
    assert "eliminar" in msg.lower() or "delete" in msg.lower()


def test_update_template_prompt_delete_requires_confirmation():
    from mcp_server.prompts.update_template import build_update_template_message
    msg = build_update_template_message()
    assert "confirmar" in msg.lower() or "CONFIRMAR" in msg


# ---------------------------------------------------------------------------
# manage_preferences — social channels
# ---------------------------------------------------------------------------

def test_manage_preferences_prompt_includes_telegram():
    from mcp_server.prompts.manage_preferences import build_manage_preferences_message
    msg = build_manage_preferences_message()
    assert "telegram" in msg.lower()


def test_manage_preferences_prompt_includes_whatsapp():
    from mcp_server.prompts.manage_preferences import build_manage_preferences_message
    msg = build_manage_preferences_message()
    assert "whatsapp" in msg.lower()


def test_manage_preferences_prompt_includes_all_8_channels():
    from mcp_server.prompts.manage_preferences import build_manage_preferences_message
    msg = build_manage_preferences_message().lower()
    for channel in ["email", "sms", "push ios", "push android", "telegram", "whatsapp", "line"]:
        assert channel in msg, f"missing channel: {channel}"


# ---------------------------------------------------------------------------
# onboarding — social channels
# ---------------------------------------------------------------------------

def test_onboarding_prompt_mentions_social_channels():
    from mcp_server.prompts.onboarding import build_onboarding_message
    msg = build_onboarding_message().lower()
    assert "telegram" in msg or "whatsapp" in msg or "social" in msg
