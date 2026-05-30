# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Production-ready MCP server wrapping the **NotificationEngine** REST API. Clients authenticate with a per-user Bearer API key; the server resolves that key to a `user_id` and proxies signed HMAC requests to NotificationEngine on behalf of that user.

## Commands

```bash
# Run tests
python -m pytest tests/ -v

# Run server (streamable-http, default)
cp .env.example .env   # fill in required vars
uvicorn main:app --host 0.0.0.0 --port 8000

# Run server with mcp dev (uses server_dev.py at project root)
mcp dev server_dev.py

# Run server (stdio, single-user local)
MCP_TRANSPORT=stdio MCP_STDIO_USER_ID=42 python main.py

# Generate SECRET_KEY
openssl rand -hex 32

# Manage API keys (requires DATABASE_URL + SECRET_KEY in env)
python -m mcp_server.scripts.keys create --user-id 42 --name "Claude Desktop"
python -m mcp_server.scripts.keys list [--user-id 42]
python -m mcp_server.scripts.keys revoke <key-id>

# MCP Inspector
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
# Add header: Authorization: Bearer nm_live_...
```

## SDK & Framework

- **MCP**: official Anthropic SDK — `mcp[cli]>=1.27` (package `mcp`, **not** the third-party `fastmcp`)
- **FastMCP**: `from mcp.server.fastmcp import FastMCP, Context`
- **Transport layer**: Starlette (not FastAPI)
- **Testing tool**: `mcp dev server_dev.py` (included in `mcp[cli]`, starts server + MCP Inspector)

## Architecture

```
mcp_server/
  config.py             pydantic-settings — fails fast if required vars missing
  auth.py               API key generation + HMAC-SHA256 hashing + user lookup
  db.py                 asyncpg pool + schema bootstrap (api_keys table)
  context.py            current_user_id ContextVar (injected by auth middleware)
  hmac_auth.py          HMAC signing for outgoing NotificationEngine requests
  errors.py             NotificationEngineError hierarchy
  models.py             Pydantic v2 input models (extra='forbid', bounds)
  logging_setup.py      structlog JSON (prod) / console (dev) config
  app.py                Starlette app + lifespan + /health + mount /mcp
  mcp_instance.py       FastMCP instance + 12 @mcp.tool registrations, 4 @mcp.prompt, 3 @mcp.resource (with ctx: Context)
  middleware/
    auth_middleware.py  Bearer → user_id → contextvar; 401 on failure (pure ASGI)
    rate_limit.py       custom sliding-window 60/min keyed by user_id (pure ASGI)
    logging_middleware.py  access log (no params/body logged) (pure ASGI)
  tools/
    notifications.py    submit_notification, get_notification, list_notifications
    templates.py        create_template, get_template (TTL cache), update_template (bug fix: channel/locale/version immutable), delete_template
    users.py            register_device, delete_device, update_user_setting, get_user_settings
    _logging.py         log_tool_call() helper
  resources/
    templates.py        notification://templates (user's templates grouped by channel)
    history.py          notification://history (20 most recent notifications)
    settings.py         notification://settings (channel preferences)
  services/
    service_api_client.py  httpx singleton + HMAC-signed requests
  scripts/
    keys.py             Cyclopts CLI for key management
server_dev.py           thin re-export for `mcp dev server_dev.py`
```

## Auth model

- **Client → MCP**: `Authorization: Bearer nm_live_<token>`. Key stored as `HMAC-SHA256(SECRET_KEY, key)` in `api_keys.key_hash` — a DB leak without the SECRET_KEY is useless.
- **MCP → NotificationEngine**: HMAC-SHA256 with headers `X-App-Key`, `X-App-Signature`, `X-App-Timestamp`, and `X-On-Behalf-Of-User` (user_id signed into canonical string). Tools never trust user-supplied `user_id`; it always comes from the contextvar set by the auth middleware.
- Keys are revoked by setting `revoked_at`; the lookup query filters `revoked_at IS NULL`.
- 401 responses are always generic — never reveal whether a key exists or is revoked.

## DB schema

```sql
CREATE TABLE api_keys (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,
    name        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ          -- NULL = active, non-NULL = revoked
);
```

## Required env vars (fail-fast)

`SERVICE_API_URL`, `SERVICE_API_KEY`, `SERVICE_API_SECRET`, `DATABASE_URL`, `SECRET_KEY`

## Adding tools

```python
# mcp_server/mcp_instance.py
from mcp.server.fastmcp import FastMCP, Context  # official SDK — NOT the third-party `fastmcp`

@mcp.tool()
async def my_tool(param: str, ctx: Context) -> dict[str, Any]:
    """Description for the AI."""
    await ctx.report_progress(0, 1, "Working")
    user_id = get_current_user_id_or_raise()
    settings = get_settings()
    result = await service_api_client.request(settings, "GET", f"/v1/resource/{param}")
    await ctx.report_progress(1, 1, "Done")
    return result
```

## Key implementation notes

- All middleware is pure ASGI (`__call__(scope, receive, send)`) — not `BaseHTTPMiddleware` — to avoid buffering SSE/streaming responses.
- Rate limiter is a custom in-memory sliding window (not slowapi), because slowapi requires decorators that can't be applied to a mounted FastMCP sub-app.
- HMAC signature is **hex** (`hmac.hexdigest()`), not base64.
- `context.py` falls back to `MCP_STDIO_USER_ID` env var if the ContextVar is unset (stdio transport).
- `uvloop` is installed automatically if present (optional dependency).
