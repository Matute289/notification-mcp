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

# Run server (stdio, single-user local)
MCP_TRANSPORT=stdio MCP_STDIO_USER_ID=42 python main.py

# Generate SECRET_KEY
openssl rand -hex 32

# Manage API keys (requires DATABASE_URL + SECRET_KEY in env)
python -m mcp_server.scripts.keys create --user-id 42 --name "Claude Desktop"
python -m mcp_server.scripts.keys list
python -m mcp_server.scripts.keys revoke <key-id>

# MCP Inspector
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
# Add header: Authorization: Bearer nm_live_...
```

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
  app.py                FastAPI app + lifespan + /health + mount /mcp
  mcp_instance.py       FastMCP instance + 6 @mcp.tool registrations
  middleware/
    auth_middleware.py  Bearer → user_id → contextvar; 401 on failure
    rate_limit.py       slowapi 60/min keyed by user_id
    logging_middleware.py  access log (no params/body logged)
  tools/
    notifications.py    submit_notification, get_notification
    templates.py        create_template, get_template (TTL cache)
    users.py            register_device, update_user_setting
  services/
    service_api_client.py  httpx singleton + HMAC-signed requests
  scripts/
    keys.py             Cyclopts CLI for key management
```

## Auth model

- **Client → MCP**: `Authorization: Bearer nm_live_<token>`. Key is stored as `HMAC-SHA256(SECRET_KEY, key)` in Postgres — a DB leak without the SECRET_KEY is useless.
- **MCP → NotificationEngine**: HMAC-SHA256 with `X-On-Behalf-Of-User` header signed into the canonical string. Tools never trust user-supplied `user_id`; it always comes from the contextvar set by the auth middleware.
- 401 responses are always generic — never reveal whether a key exists or is revoked.

## Required env vars (fail-fast)

`SERVICE_API_URL`, `SERVICE_API_KEY`, `SERVICE_API_SECRET`, `DATABASE_URL`, `SECRET_KEY`

## Adding tools

```python
# mcp_server/mcp_instance.py
@mcp.tool
async def my_tool(param: str) -> dict[str, Any]:
    """Description for the AI."""
    user_id = get_current_user_id_or_raise()
    settings = get_settings()
    return await service_api_client.request(settings, "GET", f"/v1/resource/{param}")
```
