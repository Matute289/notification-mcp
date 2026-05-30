# NotificationEngine MCP Server

A production-ready [Model Context Protocol](https://modelcontextprotocol.io/) server that proxies the NotificationEngine REST API with per-user authentication, rate limiting, structured logging, and both HTTP and stdio transports.

## Overview

This MCP server exposes 12 notification delivery tools via Model Context Protocol, allowing Claude and other LLM clients to:

- Submit notifications across 8 channels (email, SMS, iOS push, Android push, Telegram, WhatsApp, LINE, Facebook Messenger)
- Create, retrieve, update, and delete notification templates
- Register and delete device tokens for push notifications
- Manage user notification preferences and list notifications

Each request is authenticated with a per-user Bearer API key and signed with HMAC-SHA256 when proxying to NotificationEngine. The server enforces strict input validation, rate limiting (60 requests/min per user), and structured logging.

## Quick Start

### Prerequisites

- Python ≥ 3.12
- PostgreSQL ≥ 12
- NotificationEngine running (see `SERVICE_API_URL` in environment setup)

> **Note:** This project uses the **official Anthropic MCP SDK** (`mcp[cli]>=1.27`, package `mcp`) — not the third-party `fastmcp` package. FastMCP is accessed via `from mcp.server.fastmcp import FastMCP, Context`.

### Installation

```bash
# Clone the repository
git clone <repo>
cd notification-mcp

# Install dependencies (using uv or pip)
pip install -e .

# Generate a secret key
openssl rand -hex 32
```

### Configuration

Create a `.env` file with required variables:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Required
SERVICE_API_URL=http://localhost:8080           # NotificationEngine endpoint
SERVICE_API_KEY=your-hmac-app-key
SERVICE_API_SECRET=your-hmac-app-secret
DATABASE_URL=postgresql://user:password@localhost:5432/notification_mcp
SECRET_KEY=<output-of-openssl-rand-hex-32>

# Optional (defaults shown)
MCP_TRANSPORT=streamable_http                    # streamable_http | stdio
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_STDIO_USER_ID=                               # required when MCP_TRANSPORT=stdio
RATE_LIMIT_PER_MINUTE=60
HTTP_TIMEOUT_S=10
HTTP_MAX_CONNECTIONS=50
HTTP_VERIFY_TLS=true
LOG_LEVEL=INFO
LOG_FORMAT=json                                  # json | console
TEMPLATE_CACHE_TTL_S=300
```

## Usage

### HTTP Server (Recommended for Claude Desktop)

```bash
# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000
```

The server exposes:
- `POST /mcp` — MCP endpoint (streamable-http protocol)
- `GET /health` — health check (no auth required)

**Claude Desktop Configuration** (save to `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "notification-engine": {
      "command": "uvicorn",
      "args": [
        "main:app",
        "--host", "0.0.0.0",
        "--port", "8000"
      ],
      "env": {
        "SERVICE_API_URL": "http://localhost:8080",
        "SERVICE_API_KEY": "your-key",
        "SERVICE_API_SECRET": "your-secret",
        "DATABASE_URL": "postgresql://...",
        "SECRET_KEY": "..."
      }
    }
  }
}
```

**MCP Inspector** (for testing and debugging):

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp

# Add Authorization header when prompted:
# Authorization: Bearer nm_live_<your-api-key>
```

### Development Mode (`mcp dev`)

`mcp dev` is the official testing tool included in `mcp[cli]`. It starts the server and opens the built-in MCP Inspector UI automatically in the browser.

```bash
mcp dev server_dev.py
```

`server_dev.py` exists at the project root because `mcp dev` loads files without package context (relative imports would fail inside `mcp_server/`). It simply re-exports the FastMCP instance:

```python
# server_dev.py
from mcp_server.mcp_instance import mcp  # noqa: F401
```

The Inspector UI lets you call tools interactively, inspect schemas, and see raw MCP messages — no separate `npx @modelcontextprotocol/inspector` needed when using `mcp dev`.

### Stdio Transport (Single-User Local)

For local testing or embedded use:

```bash
MCP_TRANSPORT=stdio MCP_STDIO_USER_ID=42 python main.py
```

The server runs as a single-user stdio server. No auth middleware runs — `user_id` comes from `MCP_STDIO_USER_ID`. Use with:
- Claude Code (local integration)
- Custom MCP clients
- Local automation scripts

## API Keys & Authentication

### Generate an API Key

```bash
python -m mcp_server.scripts.keys create --user-id 42 --name "Claude Desktop"
```

Output:
```
API Key created (shown once — store it securely):

  nm_live_xxx...

Key ID: 1  |  User: 42  |  Name: Claude Desktop
```

### List Keys

```bash
python -m mcp_server.scripts.keys list           # all keys
python -m mcp_server.scripts.keys list --user-id 42  # filter by user
```

### Revoke a Key

```bash
python -m mcp_server.scripts.keys revoke <key-id>
```

Revoked keys are marked with `revoked_at = now()`. They immediately fail auth (401).

### Authentication Flow

1. **Client → MCP Server**: Include `Authorization: Bearer nm_live_<token>` header
2. **MCP Server**: Computes `HMAC-SHA256(SECRET_KEY, token)` hex-digest and looks it up in PostgreSQL (`key_hash` column, `revoked_at IS NULL`)
3. **MCP Server → NotificationEngine**: Signs request with HMAC-SHA256, includes `X-App-Key`, `X-App-Signature`, `X-App-Timestamp`, and `X-On-Behalf-Of-User` headers
4. All requests are tagged with the authenticated user's `user_id` (from ContextVar)

**Security Notes:**
- API keys stored as `HMAC-SHA256(SECRET_KEY, key)` hex-digest — a DB leak without `SECRET_KEY` is useless
- `user_id` is never trusted from client input; it always comes from the auth middleware
- 401 responses are always generic ("unauthorized") — never reveal if a key exists or is revoked

## Tools

All tools are authenticated — they operate on behalf of the authenticated user. Each tool emits progress events via the MCP Context.

### submit_notification

Submit a notification for delivery.

**Parameters:**
- `event_id` (str, required): Idempotency key (1–256 chars). Duplicate event_ids are deduplicated server-side.
- `channel` (str, required): `email` | `sms` | `push_ios` | `push_android`
- `recipient_email` (str, optional): Direct email address (channel=email)
- `recipient_phone_number` (str, optional): E.164 phone number (channel=sms)
- `recipient_device_token` (str, optional): Push token (channel=push_ios/android)
- `template_id` (str, optional): UUID of a pre-created template
- `variables` (dict, optional): Key/value pairs for `{{variable_name}}` substitution (max 50 keys)
- `subject` (str, optional): Message subject (overrides template)
- `body` (str, optional): Message body (use instead of template or to override)

**Response:**
```json
{
  "notification_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "enqueued",
  "duplicate": false
}
```

**Status Values:**
- `received` — Notification stored, awaiting processing
- `enqueued` — In delivery queue
- `in_flight` — Being delivered
- `sent` — Successfully delivered
- `retrying` — Failed attempt, queued for retry
- `dead_letter` — Exhausted retries, final failure
- `failed` — Immediate failure (invalid recipient, etc.)

### get_notification

Retrieve notification status and metadata.

**Parameters:**
- `notification_id` (str, required): UUID of the notification

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "event_id": "order_123_receipt",
  "channel": "email",
  "status": "sent",
  "attempt": 1,
  "subject": "Order Receipt",
  "body": "Your order #123 is confirmed",
  "last_error": null,
  "recipient": {
    "user_id": 42,
    "email": "user@example.com",
    "phone_number": null,
    "device_token": null
  },
  "variables": null,
  "template_id": null
}
```

### create_template

Create a reusable notification template.

**Parameters:**
- `name` (str, required): Template name (1–128 chars)
- `channel` (str, required): `email` | `sms` | `push_ios` | `push_android`
- `body` (str, required): Template body with optional `{{variable_name}}` placeholders (1–160,000 chars)
- `locale` (str, optional): Locale code (default: `"en"`, 2–10 chars)
- `subject` (str, optional): Email subject (max 998 chars, channel=email)
- `media_urls` (list, optional): URLs to media attachments (max 10)
- `version` (int, optional): Template version (default: 1, range: 1–9999)

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Order Receipt",
  "channel": "email",
  "locale": "en",
  "subject": "Order Receipt",
  "body": "Thank you for your order {{order_id}}! Total: {{total}}",
  "media_urls": null,
  "version": 1,
  "owner_user_id": 42
}
```

### get_template

Retrieve a template by ID. **Cached** (default 5-minute TTL, configurable via `TEMPLATE_CACHE_TTL_S`).

**Parameters:**
- `template_id` (str, required): UUID of the template

**Response:** Same schema as `create_template` response

### register_device

Register a device token for push notifications.

**Parameters:**
- `device_token` (str, required): Push token from APNs/FCM (1–512 chars)
- `channel` (str, required): `push_ios` | `push_android`

**Response:**
```json
{
  "success": true
}
```

### update_user_setting

Set user notification preferences (opt-in/opt-out per channel).

**Parameters:**
- `channel` (str, required): `email` | `sms` | `push_ios` | `push_android` | `telegram` | `whatsapp` | `line` | `facebook_messenger`
- `opt_in` (bool, required): true to enable, false to disable

**Response:**
```json
{
  "success": true
}
```

### list_notifications

List recent notifications with cursor pagination and optional filters.

**Parameters:**
- `limit` (int, optional): Max 100, default 20
- `cursor` (str, optional): Pagination cursor (opaque string from previous response)
- `status` (str, optional): Filter by status (enqueued, sent, failed, etc.)
- `channel` (str, optional): Filter by channel

**Response:**
```json
{
  "notifications": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "event_id": "order_123_receipt",
      "channel": "email",
      "status": "sent"
    }
  ],
  "cursor": "eyJpZCI6IDEyMzQ1Njc4OTAsICJ0YXJnZXQiOiAiZGlyIn0="
}
```

### delete_template

Permanently delete a notification template.

**Parameters:**
- `template_id` (str, required): UUID of the template to delete

**Response:**
```json
{
  "success": true
}
```

### delete_device

Unregister a mobile device push token.

**Parameters:**
- `device_token` (str, required): The push token to unregister

**Response:**
```json
{
  "success": true
}
```

### get_user_settings

Retrieve all user notification preferences across all 8 channels.

**Parameters:** None

**Response:**
```json
{
  "settings": [
    {"channel": "email", "opt_in": true},
    {"channel": "sms", "opt_in": false},
    {"channel": "push_ios", "opt_in": true},
    {"channel": "push_android", "opt_in": true},
    {"channel": "telegram", "opt_in": false},
    {"channel": "whatsapp", "opt_in": true},
    {"channel": "line", "opt_in": true},
    {"channel": "facebook_messenger", "opt_in": false}
  ]
}
```

## MCP Resources

The server exposes 3 read-only resources clients can subscribe to:

| URI | Description |
|-----|-------------|
| `notification://templates` | All user templates grouped by channel |
| `notification://history` | 20 most recent notifications |
| `notification://settings` | All 8 channel preferences |

## Errors

### Error Response Schema

Tool errors are surfaced as MCP error responses. Errors from NotificationEngine include:

```json
{
  "code": "error_code_string",
  "message": "Human-readable message",
  "status_code": 400
}
```

### Common Error Codes

| Code | HTTP | Cause |
|------|------|-------|
| `unauthorized` | 401 | Invalid or missing Bearer token |
| `not_found` | 404 | Resource (template, notification) doesn't exist |
| `already_exists` | 409 | Template or resource already exists |
| `invalid_input` | 400 | Input validation failed |
| `invalid_channel` | 400 | Unknown channel value |
| `opted_out` | 403 | User has opted out of this channel |
| `rate_limited` | 429 | Rate limit exceeded. Includes `Retry-After` header |
| `forbidden` | 403 | User lacks permission |
| `unauthenticated` | 401 | Invalid HMAC signature when proxying to NotificationEngine |

### Rate Limiting

- **Limit:** 60 requests per minute per user (sliding window)
- **Header:** `Retry-After: <seconds>`
- **Error body:** `{"error": "rate_limit_exceeded"}`

## Testing

### Run Unit & Integration Tests

```bash
python -m pytest tests/ -v
```

**Test Coverage:**
- `test_auth.py` — API key generation, hashing, resolve_user (mocked DB)
- `test_config.py` — Configuration validation, fail-fast checks
- `test_hmac.py` — HMAC signing, cross-language vectors
- `test_http_app.py` — HTTP endpoints, auth middleware, 401 responses
- `test_tools.py` — Tool execution, service API mocking (respx)

**Status:** 107/107 passing

### Local Testing with MCP Inspector

1. Start the server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. Create a test API key:
   ```bash
   python -m mcp_server.scripts.keys create --user-id 42 --name "test"
   ```

3. Open MCP Inspector:
   ```bash
   npx @modelcontextprotocol/inspector http://localhost:8000/mcp
   ```

4. Add the Authorization header:
   ```
   Authorization: Bearer nm_live_<your-key>
   ```

### Example: Python MCP Client (stdio)

```python
import asyncio
from mcp import ClientSession
from mcp.client.stdio import stdio_client

async def test():
    async with stdio_client("python main.py") as (read, write):
        async with ClientSession(read, write) as session:
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"- {tool.name}: {tool.description}")

asyncio.run(test())
```

## Project Structure

```
notification-mcp/
├── README.md                      # This file
├── architecture-specifications.md # Detailed architecture reference
├── CLAUDE.md                      # Claude Code project guidance
├── .claude/
│   └── CLAUDE_CONTEXT.md          # Internal context (non-shared)
├── .env.example                   # Environment variables template
├── .env                           # Local env (git-ignored)
├── main.py                        # Entry point (HTTP & stdio)
├── server_dev.py                  # Thin re-export for `mcp dev server_dev.py`
├── pyproject.toml                 # Project metadata and dependencies
├── uv.lock                        # Locked dependencies (uv)
├── mcp_server/
│   ├── __init__.py
│   ├── app.py                     # Starlette app + lifespan + /health
│   ├── config.py                  # Pydantic Settings (fail-fast validation)
│   ├── auth.py                    # API key generation & HMAC hashing
│   ├── db.py                      # asyncpg pool + schema bootstrap
│   ├── context.py                 # current_user_id ContextVar
│   ├── hmac_auth.py               # HMAC-SHA256 signing (X-App-* headers)
│   ├── errors.py                  # NotificationEngineError hierarchy
│   ├── models.py                  # Pydantic v2 input/response models
│   ├── logging_setup.py           # structlog JSON/console config
│   ├── mcp_instance.py            # FastMCP + 12 @mcp.tool, 4 @mcp.prompt, 3 @mcp.resource
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth_middleware.py     # Bearer → user_id → contextvar (pure ASGI)
│   │   ├── rate_limit.py          # Sliding window 60/min per user_id (pure ASGI)
│   │   └── logging_middleware.py  # Access log (pure ASGI)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── _logging.py            # log_tool_call() helper
│   │   ├── notifications.py       # submit, get, list_notifications
│   │   ├── templates.py           # create, get, update (immutable channel/locale/version), delete
│   │   └── users.py               # register/delete device, update/get user_settings
│   ├── resources/
│   │   ├── __init__.py
│   │   ├── templates.py           # notification://templates
│   │   ├── history.py             # notification://history
│   │   └── settings.py            # notification://settings
│   ├── services/
│   │   ├── __init__.py
│   │   └── service_api_client.py  # httpx singleton + HMAC signing
│   └── scripts/
│       ├── __init__.py
│       └── keys.py                # Cyclopts CLI for key management
└── tests/
    ├── __init__.py
    ├── test_auth.py               # Auth & key tests
    ├── test_config.py             # Config validation tests
    ├── test_hmac.py               # HMAC signing tests
    ├── test_http_app.py           # HTTP app tests
    ├── test_tools.py              # Tool execution tests
    └── test_resources.py          # MCP resources tests
```

## Development

### Running the Development Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Debugging

```bash
LOG_LEVEL=DEBUG LOG_FORMAT=console uvicorn main:app --host 0.0.0.0 --port 8000
```

Logs include:
- `http_request`: method, path, status, duration_ms, user_id
- `tool_call`: tool_name, user_id, duration_ms, success, error_type
- `auth_failed`: reason (missing_token, empty_token, invalid_token), ip, path
- `rate_limit_exceeded`: user_id, ip, path, limit, retry_after

### Managing Database Schema

The server automatically creates the `api_keys` table on startup (idempotent). To reset:

```bash
psql -U user -h localhost -d notification_mcp -c "DROP TABLE IF EXISTS api_keys;"
# Restart the server to recreate
```

## Related Projects

- **NotificationEngine** (`/Users/mgrinberg/Workspace/GolandProjects/NotificationEngine`) — Backend API in Go (chi router)
  - Endpoints: `/v1/notifications`, `/v1/templates`, `/v1/users/{user_id}/devices`, `/v1/users/{user_id}/settings`
  - HMAC auth: `X-App-Key`, `X-App-Signature`, `X-App-Timestamp`, `X-On-Behalf-Of-User`

## License

See LICENSE file in repository.
