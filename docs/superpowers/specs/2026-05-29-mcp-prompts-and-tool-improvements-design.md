# MCP Prompts & Tool Improvements — Design Spec

**Date:** 2026-05-29
**Status:** Approved

---

## Overview

Add 4 MCP prompts and 2 new tools to make the NotificationEngine MCP server intuitive for users of all ages and technical levels. The guiding principle is that every operation can be completed through a guided conversation — users never need to know UUIDs, field names, or API conventions.

---

## Scope

### New tools (2)
- `list_templates_tool` — lists the user's templates grouped by channel
- `update_template_tool` — fully replaces an existing template

### New prompts (4)
- `create_template` — guided creation for one or more channels
- `update_template` — guided editing of an existing template
- `manage_preferences` — menu-driven opt-in/out and device registration
- `onboarding` — first-time user setup

### Tool docstring improvements (8 tools)
All existing and new tools get clear, plain-language docstrings with concrete examples — readable by users of all ages.

### Out of scope
- No new API endpoints beyond what NotificationEngine already exposes
- No changes to auth, middleware, rate limiting, or HMAC logic
- The `submit_notification_tool` conversational flow (asking for missing info, suggesting email subject, waiting for confirmation) is handled by the AI's natural language understanding aided by an improved docstring — no new prompt or wrapper tool needed

---

## Architecture

### File structure

```
mcp_server/
  prompts/
    __init__.py          re-exports all prompt functions for import
    create_template.py
    update_template.py
    manage_preferences.py
    onboarding.py
  tools/
    templates.py         add list_templates() and update_template() here
  models.py              add UpdateTemplateInput, TemplateListView
  mcp_instance.py        register new tools + import and register prompts
```

Prompts follow the same pattern as tools: logic lives in `mcp_server/prompts/<name>.py`, registered via `@mcp.prompt()` in `mcp_instance.py`.

---

## New Tools

### `list_templates_tool`

**Endpoint:** `GET /v1/templates`

**Purpose:** Returns the user's templates grouped by channel. Used internally by the `update_template` prompt so users can select a template by name rather than UUID.

**Tool function signature:**
```python
@mcp.tool()
async def list_templates_tool(ctx: Context) -> dict[str, Any]:
```

**Response shape** (from API):
```json
{
  "email": [{"id": "...", "name": "...", "subject": "...", "locale": "...", "version": 1}],
  "sms": [...],
  "push_ios": [...],
  "push_android": [...]
}
```

**Model:** `TemplateListView` — a dict mapping channel name to list of `TemplateView`.

**Docstring goal:** Explain that this shows all the user's saved templates, organized by the channel they belong to.

---

### `update_template_tool`

**Endpoint:** `PUT /v1/templates/{id}`  (full replacement)

**Purpose:** Replaces all fields of an existing template. The caller must supply the complete new state (PUT semantics).

**Tool function signature:**
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
```

**Model:** `UpdateTemplateInput` — identical fields to `CreateTemplateInput` plus `template_id: UUID`. Added to `models.py`.

**Docstring goal:** Clarify that this replaces the full template (not a partial update), and that the version should be incremented to signal a new revision.

---

## New Prompts

Prompts return `list[Message]` (role `"user"`) using FastMCP's `@mcp.prompt()` decorator. Each prompt message is written in plain, friendly language in Spanish (the primary user language), instructing the AI on how to guide the user step by step.

All prompt functions are pure Python (no async, no I/O). They compose the instruction message from their optional parameters and return it.

---

### `create_template`

**File:** `mcp_server/prompts/create_template.py`

**Parameters:**
```python
def create_template_prompt(
    channel: str | None = None,   # pre-fill if already known from context
    purpose: str | None = None,   # e.g. "mensaje de bienvenida"
) -> list[Message]:
```

**Guided flow the AI must follow:**

1. **Channel selection** — If `channel` is not pre-filled, ask the user which channels they want (email, sms, push_ios, push_android). They can choose one, several, or all. Use a lettered list.

2. **Content gathering** — Ask for the purpose/content of the template (if not supplied via `purpose`). One question at a time.

3. **Per-channel details** — For each selected channel:
   - Template name (human-readable, e.g. "Bienvenida Email")
   - Body text — explain that `{{variable_name}}` syntax inserts dynamic values, give an example
   - Subject (only for email)
   - Media URLs (optional, only for sms and push)
   - **Locale** — suggest common options: Español (`es`), English (`en`), Português (`pt`), Français (`fr`), and allow free-text BCP-47 input

4. **Create** — Call `create_template_tool` for each channel.

5. **Summary** — Show a confirmation with each template's name and ID. Offer to create more or send a notification.

---

### `update_template`

**File:** `mcp_server/prompts/update_template.py`

**Parameters:**
```python
def update_template_prompt(
    channel: str | None = None,   # narrow the list if already known
) -> list[Message]:
```

**Guided flow the AI must follow:**

1. **List templates** — Call `list_templates_tool`. Display results grouped by channel, numbered for easy selection. If `channel` is pre-filled, show only that channel's templates.

2. **Template selection** — Ask the user to pick a template by number or name (not UUID).

3. **Show current values** — Display the current name, channel, locale, subject (if email), and body so the user sees what they're changing.

4. **What to change** — Ask which fields to modify. Present as a lettered menu:
   - a) Nombre
   - b) Cuerpo del mensaje
   - c) Asunto (solo email)
   - d) Idioma (sugiere opciones BCP-47 igual que en create)
   - e) URLs de medios (sms / push)
   - f) Versión
   - g) Varios de los anteriores

5. **Gather new values** — Collect only the fields the user wants to change; keep existing values for the rest.

6. **Update** — Call `update_template_tool` with the full merged field set (existing + changes).

7. **Confirm** — Show a summary of what changed.

---

### `manage_preferences`

**File:** `mcp_server/prompts/manage_preferences.py`

**Parameters:**
```python
def manage_preferences_prompt() -> list[Message]:
```

**Guided flow the AI must follow:**

Present a top-level menu:
```
"¿Qué preferencias deseás actualizar?"
a) Activar o desactivar canales de notificación
b) Registrar o actualizar un dispositivo push
```

**Option a — Activar/Desactivar canales:**
1. Ask which channels (can be multiple): email, sms, push_ios, push_android, or all.
2. Ask whether to activate or deactivate.
3. Call `update_user_setting_tool` for each channel.
4. Show confirmation of all changes made.

**Option b — Registrar dispositivo push:**
1. Ask which platform: iOS (push_ios) or Android (push_android).
2. Ask for the device token — explain what it is in plain language (it's a code provided by the phone to receive notifications).
3. Call `register_device_tool`.
4. Confirm registration.

After completing either option, ask if the user wants to make additional changes before finishing.

---

### `onboarding`

**File:** `mcp_server/prompts/onboarding.py`

**Parameters:**
```python
def onboarding_prompt() -> list[Message]:
```

**Guided flow the AI must follow:**

1. **Welcome** — Greet the user and explain in simple terms what the system does: send notifications via email, SMS, or push; use templates to reuse messages; manage preferences to control which channels are active.

2. **Push device** — Ask if they want to receive push notifications on a mobile device.
   - If yes: ask iOS or Android, then ask for the device token (explain what it is), call `register_device_tool`.

3. **Channel preferences** — Walk through each channel (email, sms, push) one at a time and ask if they want it active. Call `update_user_setting_tool` for each.

4. **Next steps** — Offer two options:
   - a) Crear un template de notificación (→ invoke `create_template` prompt logic or suggest typing `/create_template`)
   - b) Enviar una notificación de prueba (→ guide them to describe what they want to send; the AI will use `submit_notification_tool`)
   - c) Listo por ahora

---

## Docstring Improvements

All 8 tools (6 existing + 2 new) get rewritten docstrings in English following this pattern:

- **First line:** one sentence saying what the tool does in plain language
- **Parameters section:** each param explained in plain language with a concrete example
- **Notes:** any important constraint (e.g. "event_id must be unique per notification to avoid duplicates")

**Target:** a non-technical user reading the tool's description in an AI chat should understand what each parameter means without needing documentation.

The `submit_notification_tool` docstring (already drafted in the design session) is the reference for tone and style.

---

## Data Flow

```
User: "Crear template de bienvenida para email y SMS"
  → AI invokes create_template prompt
  → AI guides conversation (channel, name, body, subject, locale)
  → AI calls create_template_tool (email)
  → AI calls create_template_tool (sms)
  → AI shows summary

User: "Quiero cambiar mi template de bienvenida"
  → AI invokes update_template prompt
  → AI calls list_templates_tool → shows numbered list
  → User picks "1 - Bienvenida Email"
  → AI shows current values
  → User says "cambia el asunto"
  → AI calls update_template_tool with merged fields
  → AI confirms changes

User: "Activar notificaciones de email"
  → AI invokes manage_preferences prompt (or handles naturally)
  → AI calls update_user_setting_tool(channel="email", opt_in=True)
  → AI confirms

User: "Configurar todo" (new user)
  → AI invokes onboarding prompt
  → Guided setup: push device, channel preferences, first template or test notification
```

---

## Testing

- Unit tests for each prompt function: verify the returned message contains the expected instructions for each scenario (channel pre-filled vs. not, etc.)
- Unit tests for `list_templates` and `update_template` tool functions: mock `service_api_client.request`, verify correct HTTP method/path/payload
- Unit test for `UpdateTemplateInput` model: valid input, invalid channel, missing required fields
- Existing tests must continue to pass

---

## Open Questions

None — all constraints confirmed during design:
- NotificationEngine supports `PUT /v1/templates/{id}` and `GET /v1/templates`
- User always provides contact info (email, phone, device token) — no user directory lookup
- Email subject is always suggested by AI and confirmed by user before sending
- Locale is suggested with common BCP-47 options during template creation and update
