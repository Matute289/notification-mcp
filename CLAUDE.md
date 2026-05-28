# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP (Model Context Protocol) server that wraps the **NotificationEngine** REST API (`/Users/mgrinberg/Workspace/GolandProjects/NotificationEngine`). Exposes 6 tools for AI agents: submit/query notifications, manage templates, register devices, and update user notification settings.

## Environment

- Python 3.14 with a local `.venv` virtualenv
- FastMCP 3.3.1, httpx 0.28, Pydantic v2, pydantic-settings

Activate the virtualenv before running anything:
```
source .venv/bin/activate
```

## Commands

```bash
# Run tests
python -m pytest tests/ -v

# Run server (SSE transport on 127.0.0.1:8765)
cp .env.example .env   # fill in APP_KEY + APP_SECRET
MCP_TRANSPORT=sse python main.py

# Run server (stdio transport for MCP clients like Claude Desktop)
python main.py

# Test via MCP inspector
npx @modelcontextprotocol/inspector http://127.0.0.1:8765/sse
```

## Architecture

```
main.py                          # entry point (uvloop + run)
src/notification_mcp/
  config.py                      # pydantic-settings, validates env vars
  hmac_auth.py                   # HMAC-SHA256 signing (mirrors NotificationEngine Go impl)
  client.py                      # httpx.AsyncClient singleton — all HTTP goes through here
  models.py                      # Pydantic v2 input/output models
  errors.py                      # maps API error codes to Python exceptions
  server.py                      # FastMCP instance + lifespan + 6 @mcp.tool registrations
  tools/
    notifications.py             # submit_notification, get_notification
    templates.py                 # create_template, get_template (with TTL cache)
    users.py                     # register_device, update_user_setting
tests/
  test_hmac.py                   # HMAC vector tests (cross-language parity with Go)
  test_tools.py                  # tool tests with respx HTTP mocks
  test_config.py                 # pydantic-settings validation
```

## Key Design Points

**Authentication**: HMAC-SHA256 service-to-service. Canonical string: `timestamp\nmethod\npath\non_behalf_of\nbody`. The `on_behalf_of` field is `""` for non-user-scoped calls, or the user ID string for user-scoped tools.

**User ownership**: User-scoped tools (`register_device`, `update_user_setting`, `create_template`, `submit_notification` with recipient.user_id) set `X-On-Behalf-Of-User: {user_id}` header. NotificationEngine validates server-side that the signed header matches the target user.

**Transport**: Default is `stdio` (for MCP clients). Set `MCP_TRANSPORT=sse` for HTTP/SSE; defaults to `127.0.0.1` for security.

**Template cache**: `get_template` uses a simple in-process TTL dict. Set `TEMPLATE_CACHE_TTL_S=0` to disable (e.g., in tests).

## Adding Tools

```python
# server.py
@mcp.tool
async def my_tool_name(param: str) -> dict[str, Any]:
    """Description shown to the AI."""
    settings = get_settings()
    return await request(settings, "GET", f"/v1/resource/{param}")
```
