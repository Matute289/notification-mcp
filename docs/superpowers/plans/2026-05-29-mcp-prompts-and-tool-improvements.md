# MCP Prompts & Tool Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 2 new tools (list_templates, update_template), 4 guided MCP prompts (create_template, update_template, manage_preferences, onboarding), and improve docstrings across all 8 tools for clarity and accessibility.

**Architecture:** New tools follow the existing pattern in `tools/templates.py`; prompts live in a new `mcp_server/prompts/` package with pure-Python message-builder functions; all tools and prompts are registered in `mcp_instance.py` via `@mcp.tool()` / `@mcp.prompt()` decorators.

**Tech Stack:** Python 3.12+, FastMCP (`mcp[cli]>=1.27`), Pydantic v2, `respx` + `pytest-asyncio` for tests.

**Spec:** `docs/superpowers/specs/2026-05-29-mcp-prompts-and-tool-improvements-design.md`

---

## File Map

### Created
| Path | Purpose |
|------|---------|
| `mcp_server/prompts/__init__.py` | Package marker |
| `mcp_server/prompts/create_template.py` | Message builder for create_template prompt |
| `mcp_server/prompts/update_template.py` | Message builder for update_template prompt |
| `mcp_server/prompts/manage_preferences.py` | Message builder for manage_preferences prompt |
| `mcp_server/prompts/onboarding.py` | Message builder for onboarding prompt |
| `tests/test_models.py` | Model validation tests |
| `tests/test_prompts.py` | Prompt message content tests |

### Modified
| Path | Change |
|------|--------|
| `mcp_server/models.py` | Add `UpdateTemplateInput` |
| `mcp_server/tools/templates.py` | Add `list_templates()`, `update_template()` |
| `mcp_server/mcp_instance.py` | Register 2 new tools + 4 prompts; rewrite all 8 docstrings |
| `tests/test_tools.py` | Add tests for `list_templates` and `update_template` |

---

## Task 1: Add UpdateTemplateInput to models

**Files:**
- Modify: `mcp_server/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_models.py -v
```

Expected: `ImportError` or similar — `UpdateTemplateInput` doesn't exist yet.

- [ ] **Step 3: Add UpdateTemplateInput to models.py**

Open `mcp_server/models.py` and add after `CreateTemplateInput`:

```python
class UpdateTemplateInput(BaseModel):
    model_config = _STRICT
    template_id: UUID
    name: Annotated[str, Field(min_length=1, max_length=128)]
    channel: Channel
    locale: Annotated[str, Field(min_length=2, max_length=10)] = "en"
    subject: str | None = Field(None, max_length=998)
    body: Annotated[str, Field(min_length=1, max_length=160_000)]
    media_urls: Annotated[list[str], Field(max_length=10)] | None = None
    version: Annotated[int, Field(ge=1, le=9999)] = 1
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_models.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/models.py tests/test_models.py
git commit -m "feat: add UpdateTemplateInput model"
```

---

## Task 2: Add list_templates() tool function

**Files:**
- Modify: `mcp_server/tools/templates.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tools.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_tools.py::test_list_templates_returns_grouped_by_channel -v
```

Expected: `ImportError` — `list_templates` not defined yet.

- [ ] **Step 3: Add list_templates() to tools/templates.py**

Add the import at the top of `mcp_server/tools/templates.py` (the `UpdateTemplateInput` isn't needed here, just `TemplateView`). Then append the function:

```python
async def list_templates() -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "list_templates"
    try:
        result = await service_api_client.request(settings, "GET", "/v1/templates")
        validated: dict[str, Any] = {
            channel: [TemplateView(**t).model_dump() for t in templates]
            for channel, templates in result.items()
            if isinstance(templates, list)
        }
        log_tool_call(tool_name, user_id, start, success=True)
        return validated
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_tools.py::test_list_templates_returns_grouped_by_channel tests/test_tools.py::test_list_templates_sends_no_obo_header -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/tools/templates.py tests/test_tools.py
git commit -m "feat: add list_templates tool function"
```

---

## Task 3: Add update_template() tool function

**Files:**
- Modify: `mcp_server/tools/templates.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tools.py`:

```python
# ---------------------------------------------------------------------------
# update_template
# ---------------------------------------------------------------------------

@respx.mock
async def test_update_template_success():
    await _make_client()
    tid = "00000000-0000-0000-0000-000000000011"
    route = respx.put(f"{BASE_URL}/v1/templates/{tid}").mock(
        return_value=httpx.Response(200, json={
            "id": tid, "name": "Welcome v2", "channel": "email",
            "locale": "es", "body": "Hola {{nombre}}", "version": 2,
            "owner_user_id": _TEST_USER_ID,
        })
    )
    from mcp_server.tools.templates import update_template
    result = await update_template(
        template_id=tid,
        name="Welcome v2",
        channel="email",
        body="Hola {{nombre}}",
        locale="es",
        version=2,
    )
    assert route.called
    assert result["name"] == "Welcome v2"
    assert result["version"] == 2
    assert result["locale"] == "es"


@respx.mock
async def test_update_template_sends_obo_header():
    await _make_client()
    tid = "00000000-0000-0000-0000-000000000012"
    route = respx.put(f"{BASE_URL}/v1/templates/{tid}").mock(
        return_value=httpx.Response(200, json={
            "id": tid, "name": "T", "channel": "sms", "locale": "en",
            "body": "Hi", "version": 1, "owner_user_id": _TEST_USER_ID,
        })
    )
    from mcp_server.tools.templates import update_template
    await update_template(template_id=tid, name="T", channel="sms", body="Hi")
    assert route.called
    assert route.calls[0].request.headers["X-On-Behalf-Of-User"] == str(_TEST_USER_ID)


@respx.mock
async def test_update_template_sends_subject_when_provided():
    await _make_client()
    tid = "00000000-0000-0000-0000-000000000013"
    route = respx.put(f"{BASE_URL}/v1/templates/{tid}").mock(
        return_value=httpx.Response(200, json={
            "id": tid, "name": "T", "channel": "email", "locale": "en",
            "subject": "Hello!", "body": "Hi", "version": 1,
        })
    )
    from mcp_server.tools.templates import update_template
    import json as _json
    await update_template(
        template_id=tid, name="T", channel="email", body="Hi", subject="Hello!",
    )
    sent_body = _json.loads(route.calls[0].request.content)
    assert sent_body["subject"] == "Hello!"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_tools.py::test_update_template_success -v
```

Expected: `ImportError` — `update_template` not defined yet.

- [ ] **Step 3: Add update_template() to tools/templates.py**

First, add `UpdateTemplateInput` to the import from `..models` at the top of `mcp_server/tools/templates.py`:

```python
from ..models import CreateTemplateInput, GetTemplateInput, TemplateView, UpdateTemplateInput
```

Then append the function:

```python
async def update_template(
    template_id: str,
    name: str,
    channel: str,
    body: str,
    locale: str = "en",
    subject: str | None = None,
    media_urls: list[str] | None = None,
    version: int = 1,
) -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "update_template"
    try:
        from uuid import UUID as _UUID
        inp = UpdateTemplateInput(
            template_id=_UUID(template_id),
            name=name, channel=channel, locale=locale,  # type: ignore[arg-type]
            subject=subject, body=body, media_urls=media_urls, version=version,
        )
        payload: dict[str, Any] = {
            "name": inp.name, "channel": inp.channel, "locale": inp.locale,
            "body": inp.body, "version": inp.version,
        }
        if inp.subject:
            payload["subject"] = inp.subject
        if inp.media_urls:
            payload["media_urls"] = inp.media_urls

        result = await service_api_client.request(
            settings, "PUT", f"/v1/templates/{inp.template_id}",
            on_behalf_of_user_id=user_id, json_body=payload,
        )
        response = TemplateView(**result).model_dump()
        log_tool_call(tool_name, user_id, start, success=True)
        return response
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_tools.py::test_update_template_success tests/test_tools.py::test_update_template_sends_obo_header tests/test_tools.py::test_update_template_sends_subject_when_provided -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp_server/tools/templates.py mcp_server/models.py tests/test_tools.py
git commit -m "feat: add update_template tool function"
```

---

## Task 4: Register new tools in mcp_instance.py

**Files:**
- Modify: `mcp_server/mcp_instance.py`

- [ ] **Step 1: Update the import line for templates**

In `mcp_server/mcp_instance.py`, change:

```python
from .tools.templates import create_template, get_template
```

to:

```python
from .tools.templates import create_template, get_template, list_templates, update_template
```

- [ ] **Step 2: Add list_templates_tool**

Append after `update_user_setting_tool` in `mcp_instance.py`:

```python
@mcp.tool()
async def list_templates_tool(ctx: Context) -> dict[str, Any]:
    """Show all notification templates you have saved, grouped by channel.

    Returns a dictionary where each key is a channel name (email, sms, push_ios,
    push_android) and each value is a list of your templates for that channel.
    Use this to browse your templates before editing or reusing them.

    Each template entry includes: id, name, channel, locale, body, and version.
    The id is the UUID you need to pass to get_template_tool or update_template_tool.
    """
    await ctx.report_progress(0, 2, "Fetching your templates")
    result = await list_templates()
    await ctx.report_progress(2, 2, "Done")
    total = sum(len(v) for v in result.values() if isinstance(v, list))
    await ctx.info(f"Found {total} template(s)")
    return result
```

- [ ] **Step 3: Add update_template_tool**

Append after `list_templates_tool`:

```python
@mcp.tool()
async def update_template_tool(
    template_id: str,
    name: str,
    channel: str,
    body: str,
    ctx: Context,
    locale: str = "en",
    subject: str | None = None,
    media_urls: list[str] | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Replace an existing notification template with new content (full update).

    This replaces every field of the template — supply all fields, not just the ones
    you want to change. To keep an existing field unchanged, copy its current value
    from get_template_tool and include it here.

    template_id: UUID of the template to update. Get this from list_templates_tool.
        Example: "550e8400-e29b-41d4-a716-446655440000".
    name: new human-readable label for this template (max 128 chars).
        Example: "Welcome Email v2".
    channel: the delivery channel — email | sms | push_ios | push_android.
        Must match the original template's channel.
    body: new message text (max 160 000 chars). Use {{variable_name}} for dynamic values.
        Example: "Hola {{nombre}}, tu pedido {{numero}} fue confirmado.".
    locale: BCP-47 language code of the template text (default: en).
        Examples: "es" for Spanish, "pt" for Portuguese, "fr" for French.
    subject: new email subject line (only for channel=email).
        Example: "Tu pedido fue confirmado".
    media_urls: new media attachment URLs for MMS or rich push (max 10 URLs).
    version: increment this number to signal a new revision. Example: if current is 1, pass 2.
    """
    await ctx.report_progress(0, 3, "Validating update")
    await ctx.info(f"Updating template {template_id}")
    result = await update_template(
        template_id=template_id, name=name, channel=channel, body=body,
        locale=locale, subject=subject, media_urls=media_urls, version=version,
    )
    await ctx.report_progress(3, 3, "Done")
    await ctx.info(f"Template updated — name='{result.get('name')}', version={result.get('version')}")
    return result
```

- [ ] **Step 4: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/mcp_instance.py
git commit -m "feat: register list_templates_tool and update_template_tool"
```

---

## Task 5: Improve docstrings on all 6 existing tools

**Files:**
- Modify: `mcp_server/mcp_instance.py`

Replace the docstring of each existing tool with the text below. Only change the docstring — leave the function body, decorator, and signature untouched.

- [ ] **Step 1: Replace submit_notification_tool docstring**

New docstring:

```python
    """Send a notification to a recipient via email, SMS, or push notification.

    Always gather all required information before calling this tool.
    For email: suggest a subject based on the message body and wait for the user
    to confirm it before proceeding. If the recipient's contact details are missing
    (email address, phone number, or device token), ask the user for them first.

    event_id: a unique identifier for this send (letters, numbers, or dashes, 1–256 chars).
        Re-submitting the same event_id is safe — duplicates are automatically ignored.
        Example: "welcome-user-42" or "order-1234-confirmation".
    channel: the delivery method — email | sms | push_ios | push_android.
    recipient_email: (email only) destination address. Example: "user@example.com".
    recipient_phone_number: (sms only) international format. Example: "+5491112345678".
    recipient_device_token: (push_ios / push_android only) the device push token.
    template_id: UUID of a pre-saved template. Use instead of body to send a
        designed message. Example: "550e8400-e29b-41d4-a716-446655440000".
    variables: values to fill {{placeholder}} fields in the template.
        Example: {"name": "Ana", "amount": "1500"}.
    subject: email subject line. Example: "Your order has been confirmed".
    body: message text. Use this instead of a template, or to override the template body.
        Example: "Hello {{name}}, how are you?".
    """
```

- [ ] **Step 2: Replace get_notification_tool docstring**

New docstring:

```python
    """Retrieve the current status and full details of a previously sent notification.

    Use this to check whether a notification was delivered, is still in transit,
    or failed. The status field shows the current state of the delivery.

    notification_id: the UUID returned by submit_notification_tool when the notification
        was created. Example: "550e8400-e29b-41d4-a716-446655440000".
    """
```

- [ ] **Step 3: Replace create_template_tool docstring**

New docstring:

```python
    """Create a reusable notification template that can be sent to any user later.

    Templates save time when you send the same type of message often. Use
    {{variable_name}} placeholders in the body (and subject) to insert
    personalized data at send time.

    name: a human-readable label for this template (max 128 chars).
        Example: "Welcome Email".
    channel: the delivery channel for this template — email | sms | push_ios | push_android.
    body: the message content (max 160 000 chars). Use {{name}} syntax for dynamic values.
        Example: "Hi {{name}}, your order {{order_id}} has been confirmed!".
    locale: the BCP-47 language code of the template text (default: en).
        Examples: "es" for Spanish, "pt" for Portuguese, "fr" for French.
    subject: the email subject line (only used when channel=email).
        Example: "Order Confirmed".
    media_urls: list of image or video URLs to attach (MMS or rich push), max 10 URLs.
    version: template revision number (default: 1). Increment when updating a template.
    """
```

- [ ] **Step 4: Replace get_template_tool docstring**

New docstring:

```python
    """Retrieve a saved notification template by its UUID. Results are cached.

    Use list_templates_tool first if you need to find the template's ID by name.

    template_id: UUID of the template to retrieve.
        Example: "550e8400-e29b-41d4-a716-446655440000".
    """
```

- [ ] **Step 5: Replace register_device_tool docstring**

New docstring:

```python
    """Register or refresh a mobile device to receive push notifications.

    Call this when a user first installs the app, or when the mobile OS issues a
    new push token. The device token is generated automatically by the phone —
    the mobile app provides it; the user does not type it manually.

    device_token: the APNs (iOS) or FCM (Android) token from the mobile OS (max 512 chars).
    channel: the push platform — push_ios (iPhone/iPad) | push_android (Android).
    """
```

- [ ] **Step 6: Replace update_user_setting_tool docstring**

New docstring:

```python
    """Turn a notification channel on or off for the current user.

    Use this when the user wants to start or stop receiving notifications
    on a specific channel.

    channel: the channel to update — email | sms | push_ios | push_android.
    opt_in: true to enable notifications on this channel, false to disable them.
    """
```

- [ ] **Step 7: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS (docstring changes don't affect test results).

- [ ] **Step 8: Commit**

```bash
git add mcp_server/mcp_instance.py
git commit -m "docs: rewrite all tool docstrings for accessibility and clarity"
```

---

## Task 6: Create prompts module and create_template prompt

**Files:**
- Create: `mcp_server/prompts/__init__.py`
- Create: `mcp_server/prompts/create_template.py`
- Create: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_prompts.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_prompts.py -v
```

Expected: `ModuleNotFoundError` — prompts package doesn't exist yet.

- [ ] **Step 3: Create the prompts package**

Create `mcp_server/prompts/__init__.py` (empty):

```python
```

- [ ] **Step 4: Create create_template.py**

Create `mcp_server/prompts/create_template.py`:

```python
from __future__ import annotations


def build_create_template_message(
    channel: str | None = None,
    purpose: str | None = None,
) -> str:
    parts: list[str] = [
        "Sos un asistente amigable para la creación de templates de notificación. "
        "Seguí este flujo exacto, una pregunta a la vez:\n\n"
    ]

    if channel:
        parts.append(
            f"El usuario ya indicó que quiere crear un template para el canal: **{channel}**. "
            "Saltá el paso de selección de canales y pasá directo al contenido.\n\n"
        )
    else:
        parts.append(
            "1. CANALES: Preguntá para qué canales quiere crear el template. "
            "Presentá las opciones:\n"
            "   a) Email (correo electrónico)\n"
            "   b) SMS (mensaje de texto)\n"
            "   c) Push iOS (iPhone/iPad)\n"
            "   d) Push Android\n"
            "   e) Todos los anteriores\n"
            "   El usuario puede elegir uno o varios combinando letras (ej: \"a, b\").\n\n"
        )

    if purpose:
        parts.append(
            f"El usuario ya indicó que el propósito del template es: **{purpose}**. "
            "Usá eso como guía para el contenido.\n\n"
        )
    else:
        parts.append(
            "2. CONTENIDO: Preguntá para qué se va a usar el template "
            "(ej: bienvenida, confirmación de pedido, alerta de pago).\n\n"
        )

    parts.append(
        "3. POR CANAL: Para cada canal seleccionado, pedí de a un campo a la vez:\n"
        "   - Nombre del template (ej: \"Bienvenida Email\")\n"
        "   - Cuerpo del mensaje. Explicá que {{nombre_variable}} inserta datos dinámicos. "
        "Ejemplo: \"Hola {{nombre}}, tu pedido {{numero}} fue confirmado.\"\n"
        "   - Asunto del correo (solo para email)\n"
        "   - URLs de medios adjuntos, opcional (solo para sms y push)\n"
        "   - Idioma del template. Sugerí estas opciones:\n"
        "     a) Español (es)\n"
        "     b) English (en)\n"
        "     c) Português (pt)\n"
        "     d) Français (fr)\n"
        "     e) Otro — el usuario puede escribir el código BCP-47 directamente\n\n"
        "4. CREACIÓN: Llamá a create_template_tool para cada canal seleccionado.\n\n"
        "5. RESUMEN: Mostrá el nombre e ID de cada template creado. "
        "Ofrecé crear más templates o enviar una notificación de prueba.\n\n"
        "Empezá saludando brevemente y luego hacé la primera pregunta."
    )

    return "".join(parts)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_prompts.py -k "create_template" -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp_server/prompts/__init__.py mcp_server/prompts/create_template.py tests/test_prompts.py
git commit -m "feat: add create_template prompt"
```

---

## Task 7: update_template prompt

**Files:**
- Create: `mcp_server/prompts/update_template.py`
- Modify: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_prompts.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_prompts.py -k "update_template" -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create update_template.py**

Create `mcp_server/prompts/update_template.py`:

```python
from __future__ import annotations


def build_update_template_message(channel: str | None = None) -> str:
    filter_note = f" Solo mostrá los templates del canal **{channel}**." if channel else ""

    return (
        "Sos un asistente amigable para modificar templates de notificación existentes. "
        "Seguí este flujo exacto:\n\n"
        f"1. LISTAR: Llamá a list_templates_tool para obtener los templates del usuario.{filter_note} "
        "Mostrá los resultados agrupados por canal, numerados, con su nombre. "
        "Si no hay templates, informá al usuario y ofrecé crear uno con create_template_tool.\n\n"
        "2. SELECCIÓN: Pedí al usuario que elija un template por número o nombre "
        "(no por ID).\n\n"
        "3. VALORES ACTUALES: Mostrá los valores actuales del template elegido: "
        "nombre, canal, idioma, asunto (si es email), y cuerpo del mensaje.\n\n"
        "4. QUÉ CAMBIAR: Preguntá qué campos quiere modificar. Presentá como menú:\n"
        "   a) Nombre\n"
        "   b) Cuerpo del mensaje\n"
        "   c) Asunto (solo para email)\n"
        "   d) Idioma — sugerí: Español (es), English (en), Português (pt), "
        "Français (fr), u otro código BCP-47\n"
        "   e) URLs de medios (para sms y push)\n"
        "   f) Versión\n"
        "   g) Varios de los anteriores\n\n"
        "5. NUEVOS VALORES: Recopilá solo los campos que el usuario quiere cambiar. "
        "Para el resto, conservá los valores actuales del template.\n\n"
        "6. ACTUALIZAR: Llamá a update_template_tool con el conjunto completo de campos "
        "(valores actuales + cambios del usuario). Usá el ID del template seleccionado.\n\n"
        "7. CONFIRMAR: Mostrá un resumen de los cambios realizados.\n\n"
        "Empezá llamando a list_templates_tool de inmediato (paso 1)."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_prompts.py -k "update_template" -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/prompts/update_template.py tests/test_prompts.py
git commit -m "feat: add update_template prompt"
```

---

## Task 8: manage_preferences prompt

**Files:**
- Create: `mcp_server/prompts/manage_preferences.py`
- Modify: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_prompts.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_prompts.py -k "manage_preferences" -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create manage_preferences.py**

Create `mcp_server/prompts/manage_preferences.py`:

```python
from __future__ import annotations


def build_manage_preferences_message() -> str:
    return (
        "Sos un asistente amigable para gestionar las preferencias de notificación. "
        "Empezá presentando este menú:\n\n"
        "\"¿Qué preferencias deseás actualizar?\"\n"
        "a) Activar o desactivar canales de notificación\n"
        "b) Registrar o actualizar un dispositivo push\n\n"
        "Para la opción (a) — Activar/Desactivar canales:\n"
        "1. Preguntá qué canales quiere modificar. Presentá las opciones:\n"
        "   a) Email\n"
        "   b) SMS\n"
        "   c) Push iOS\n"
        "   d) Push Android\n"
        "   e) Todos\n"
        "   El usuario puede elegir varios combinando letras.\n"
        "2. Preguntá si quiere activarlos o desactivarlos.\n"
        "3. Llamá a update_user_setting_tool para cada canal seleccionado.\n"
        "4. Confirmá todos los cambios realizados.\n\n"
        "Para la opción (b) — Registrar dispositivo push:\n"
        "1. Preguntá qué plataforma: iOS (push_ios) o Android (push_android).\n"
        "2. Pedí el token del dispositivo. Explicá en términos simples: "
        "\"Es un código que tu teléfono genera automáticamente para poder recibir "
        "notificaciones. Lo encontrás en la configuración de la app móvil.\"\n"
        "3. Llamá a register_device_tool con el token y el canal.\n"
        "4. Confirmá el registro.\n\n"
        "Después de completar cualquier opción, preguntá si el usuario desea realizar "
        "algún cambio adicional antes de terminar."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_prompts.py -k "manage_preferences" -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/prompts/manage_preferences.py tests/test_prompts.py
git commit -m "feat: add manage_preferences prompt"
```

---

## Task 9: onboarding prompt

**Files:**
- Create: `mcp_server/prompts/onboarding.py`
- Modify: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_prompts.py`:

```python
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
    # Should explain what the system does without technical jargon
    assert "email" in msg.lower()
    assert "sms" in msg.lower()
    assert "push" in msg.lower()


def test_onboarding_prompt_returns_nonempty_string():
    from mcp_server.prompts.onboarding import build_onboarding_message
    msg = build_onboarding_message()
    assert isinstance(msg, str)
    assert len(msg) > 100
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_prompts.py -k "onboarding" -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create onboarding.py**

Create `mcp_server/prompts/onboarding.py`:

```python
from __future__ import annotations


def build_onboarding_message() -> str:
    return (
        "Sos un asistente amigable para configurar por primera vez las notificaciones "
        "del usuario. Seguí este flujo, una pregunta a la vez:\n\n"
        "1. BIENVENIDA: Saludá al usuario y explicá en términos simples qué puede hacer "
        "el sistema:\n"
        "   - Enviar notificaciones por email, SMS o notificación push en el celular\n"
        "   - Crear templates para reutilizar mensajes\n"
        "   - Controlar qué tipos de notificaciones desea recibir\n\n"
        "2. DISPOSITIVO PUSH: Preguntá si quiere recibir notificaciones push en un celular.\n"
        "   Si sí:\n"
        "   a) Preguntá si es iPhone/iPad (push_ios) o Android (push_android).\n"
        "   b) Pedí el token del dispositivo. Explicá: \"Es un código que genera tu teléfono "
        "automáticamente. Lo encontrás en la configuración de la app.\"\n"
        "   c) Llamá a register_device_tool con el token y el canal.\n"
        "   d) Confirmá el registro.\n\n"
        "3. PREFERENCIAS POR CANAL: Para cada canal (email, sms, push), preguntá al usuario "
        "si desea tenerlo activo. Hacé una pregunta a la vez. "
        "Llamá a update_user_setting_tool para cada canal según la respuesta.\n\n"
        "4. PRÓXIMOS PASOS: Al terminar la configuración, ofrecé estas opciones:\n"
        "   a) Crear un template de notificación — indicale que puede escribir "
        "\"crear template\" para comenzar\n"
        "   b) Enviar una notificación de prueba — pedile que describa qué quiere enviar "
        "y a quién; usá submit_notification_tool para enviarlo\n"
        "   c) Listo por ahora — agradecé y despedite\n\n"
        "Empezá con la bienvenida (paso 1) y luego avanzá de a una pregunta."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_prompts.py -k "onboarding" -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Run the full prompt test suite**

```bash
python -m pytest tests/test_prompts.py -v
```

Expected: all 29 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp_server/prompts/onboarding.py tests/test_prompts.py
git commit -m "feat: add onboarding prompt"
```

---

## Task 10: Register all 4 prompts in mcp_instance.py

**Files:**
- Modify: `mcp_server/mcp_instance.py`

- [ ] **Step 1: Add prompt imports**

In `mcp_server/mcp_instance.py`, add after the existing tool imports:

```python
from .prompts.create_template import build_create_template_message
from .prompts.update_template import build_update_template_message
from .prompts.manage_preferences import build_manage_preferences_message
from .prompts.onboarding import build_onboarding_message
```

- [ ] **Step 2: Register all 4 prompts**

Append to the end of `mcp_server/mcp_instance.py`:

```python
@mcp.prompt(
    name="create_template",
    description="Asistente guiado para crear templates de notificación en uno o varios canales.",
)
def create_template_prompt(
    channel: str | None = None,
    purpose: str | None = None,
) -> str:
    return build_create_template_message(channel=channel, purpose=purpose)


@mcp.prompt(
    name="update_template",
    description="Asistente guiado para modificar un template de notificación existente.",
)
def update_template_prompt(channel: str | None = None) -> str:
    return build_update_template_message(channel=channel)


@mcp.prompt(
    name="manage_preferences",
    description="Asistente para activar/desactivar canales y registrar dispositivos push.",
)
def manage_preferences_prompt() -> str:
    return build_manage_preferences_message()


@mcp.prompt(
    name="onboarding",
    description="Configuración inicial: registrá tu dispositivo y establecé tus preferencias de notificación.",
)
def onboarding_prompt() -> str:
    return build_onboarding_message()
```

- [ ] **Step 3: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Smoke-test with mcp dev**

```bash
mcp dev server_dev.py
```

Open the MCP Inspector at the URL shown. Verify:
- 8 tools are listed (submit_notification, get_notification, create_template, get_template, register_device, update_user_setting, list_templates, update_template)
- 4 prompts are listed (create_template, update_template, manage_preferences, onboarding)
- Each prompt's description appears correctly

- [ ] **Step 5: Commit**

```bash
git add mcp_server/mcp_instance.py
git commit -m "feat: register all 4 MCP prompts"
```
