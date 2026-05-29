# Architecture Specifications

## System Overview

The NotificationEngine MCP Server is a production-ready Model Context Protocol gateway that securely proxies the NotificationEngine REST API. It provides per-user authentication, HMAC request signing, rate limiting, structured logging, and two transport modes (HTTP and stdio).

**Key technology decisions:**
- **MCP SDK**: official Anthropic package `mcp[cli]>=1.27` — **not** the third-party `fastmcp` package. Import: `from mcp.server.fastmcp import FastMCP, Context`
- **Transport layer**: Starlette (not FastAPI) — `mcp.streamable_http_app()` returns a Starlette sub-app
- **Development / testing tool**: `mcp dev server_dev.py` — included in `mcp[cli]`, starts the server and opens the built-in MCP Inspector UI

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Clients                             │
│  (Claude Desktop, MCP Inspector, Custom Clients, etc.)          │
└────────┬────────────────────────────────────────────────────────┘
         │
    HTTP │ (streamable-http) or
    Stdio│ (stdio)
         │
    ┌────▼────────────────────────────────────────────────────────┐
    │             Starlette Application (app.py)                  │
    │                                                             │
    │  Routes:                                                    │
    │    GET  /health  → 200 {"status": "ok"} (no auth)          │
    │    /*            → FastMCP sub-app (mcp_starlette)         │
    │                                                             │
    │  Middleware Stack (outermost → innermost):                  │
    │    1. LoggingMiddleware  — access logs (method/path/status) │
    │    2. RateLimitMiddleware — sliding window 60/min/user_id   │
    │    3. AuthMiddleware — Bearer token → user_id → contextvar  │
    │                                                             │
    │  FastMCP Instance:                                          │
    │    6 async tools (@mcp.tool, ctx: Context)                 │
    │    - submit_notification_tool                               │
    │    - get_notification_tool                                  │
    │    - create_template_tool                                   │
    │    - get_template_tool                                      │
    │    - register_device_tool                                   │
    │    - update_user_setting_tool                               │
    │                                                             │
    │  Lifespan Management:                                       │
    │    - asyncpg pool (min 2, max 10 connections)               │
    │    - httpx singleton (max 50 connections)                   │
    │    - MCP session manager (mcp.session_manager.run())        │
    └────┬────────────────────────────────────────────────────────┘
         │
         ├──────────────────┬──────────────────┐
         │                  │                  │
    ┌────▼─────┐      ┌─────▼─────────────────┐
    │ PostgreSQL│      │ NotificationEngine (Go)│
    │           │      │ HTTP API :8080         │
    │ api_keys  │      │ /v1/...               │
    │ (hashed)  │      │                       │
    └───────────┘      └───────────────────────┘
```

## Request Flow

### 1. Authentication & Authorization

```
Client Request with Bearer Token
         ↓
  AuthMiddleware (pure ASGI)
    ├─ Bypass: /health passes through
    ├─ Extract: Authorization: Bearer nm_live_<token>
    ├─ Prefix check: must start with "nm_live_"
    ├─ Compute: key_hash = HMAC-SHA256(SECRET_KEY, token).hexdigest()
    ├─ Query: SELECT user_id FROM api_keys
    │         WHERE key_hash = $1 AND revoked_at IS NULL
    ├─ Set: current_user_id (ContextVar) = user_id from DB
    ├─ On fail: return 401 {"error": "unauthorized"} — generic, never reveals existence
    └─ Continue: next middleware; reset ContextVar in finally block
```

**Key Design:**
- API keys stored as `HMAC-SHA256(SECRET_KEY, key)` hex-digest — DB compromise without SECRET_KEY is useless
- ContextVar ensures user_id is isolated per async context
- No user_id from client input is ever trusted
- Pure ASGI (not BaseHTTPMiddleware) to avoid buffering SSE streams

### 2. Rate Limiting

```
Request → RateLimitMiddleware (pure ASGI, custom sliding window)
  ├─ Bypass: /health passes through
  ├─ Get user_id from ContextVar (set by AuthMiddleware)
  ├─ Key: f"user:{uid}" or "anon" if uid is None
  ├─ Check: sliding window — evict timestamps older than 60s, count remaining
  │
  ├─ If over limit:
  │   ├─ Return 429 {"error": "rate_limit_exceeded"}
  │   ├─ Header: Retry-After: <seconds>
  │   └─ Log: rate_limit_exceeded
  │
  └─ If under limit:
      ├─ Append current monotonic timestamp to window
      └─ Continue to next middleware
```

**Notes:**
- Custom implementation (not slowapi) — slowapi requires `@limiter.limit()` decorators which cannot be applied to a mounted FastMCP sub-app
- In-memory `defaultdict(list)` per user_id — suitable for single-instance deployments
- Sliding window (not fixed window) for smoother throttling

### 3. Tool Execution Flow (Example: submit_notification)

```
Client → FastMCP /mcp endpoint
  ↓
FastMCP dispatch → submit_notification_tool(ctx: Context)
  ↓
ctx.report_progress(0, 3, "Validating request")
ctx.info(f"Submitting {channel} notification")
  ↓
mcp_server/tools/notifications.py:submit_notification()
  ├─ Get current user_id from ContextVar
  ├─ Validate input: SubmitNotificationInput (Pydantic v2, extra='forbid')
  ├─ Build payload dict (omit null fields; inject user_id into recipient)
  ├─ Call service_api_client.request()
  │   └─ (see Service API Signing below)
  ├─ Parse response: SubmitResponse(**result).model_dump()
  ├─ log_tool_call(tool_name, user_id, start, success=True)
  └─ Return: dict
ctx.report_progress(3, 3, "Done")
ctx.info(f"Notification accepted — status={status}")
```

**Error Handling:**
- Pydantic validation → ValidationError → MCP error response
- Service API error (4xx/5xx) → raises NotificationEngineError subclass → MCP error response
- All exceptions caught by tool, logged, then re-raised

### 4. Service API Signing (HMAC-SHA256)

```
service_api_client.request(settings, "POST", "/v1/notifications",
  on_behalf_of_user_id=42, json_body={...})

  ├─ Serialize body: json.dumps(json_body, separators=(",", ":")).encode()
  │
  ├─ Build canonical string:
  │   timestamp = str(int(time.time()))
  │   on_behalf_of = str(user_id) or ""
  │   canonical = f"{timestamp}\nPOST\n/v1/notifications\n{on_behalf_of}"
  │   msg = canonical.encode() + b"\n" + body_bytes
  │
  ├─ Sign:
  │   signature = HMAC-SHA256(SERVICE_API_SECRET, msg).hexdigest()
  │
  ├─ Headers:
  │   X-App-Key: SERVICE_API_KEY
  │   X-App-Signature: <hex-digest>
  │   X-App-Timestamp: <unix-seconds>
  │   X-On-Behalf-Of-User: "42"   (only when on_behalf_of_user_id is set)
  │   Content-Type: application/json
  │
  └─ POST to SERVICE_API_URL/v1/notifications
     ↓
  NotificationEngine (Go backend)
     ├─ Verify HMAC signature
     ├─ Check X-On-Behalf-Of-User authorization
     ├─ Process notification
     └─ Return JSON response
```

**Security Guarantees:**
- Signature covers: timestamp + method + path + on_behalf_of_user + body
- Replay attacks prevented by timestamp (server validates within ±5 min window)
- User impersonation impossible (user_id is signed, comes from ContextVar not client input)

**Response handling:**
- 200/201/202 → parse JSON, return dict
- 204 → return None
- 4xx/5xx → parse error body, raise NotificationEngineError subclass
- Body > 1 MB → RuntimeError guard

### 5. Logging & Observability

```
LoggingMiddleware (access logs):
  └─ After response: log "http_request" with method, path, status, duration_ms, user_id

Tool Execution → log_tool_call():
  └─ log "tool_call" with tool_name, user_id, duration_ms, success, error_type

Log Format:
  ├─ json  (production, default): structured, machine-parseable
  └─ console (development): human-readable with colors
```

## Module Architecture

### Core Modules

#### `config.py` — Configuration Management

```python
class Settings(BaseSettings):
    # ---- Required (fail-fast) ----
    service_api_url: str           # NotificationEngine endpoint (trailing slash stripped)
    service_api_key: str           # HMAC app key
    service_api_secret: str        # HMAC app secret
    database_url: str              # PostgreSQL (must start with postgresql://)
    secret_key: str                # API key hashing seed (≥32 bytes)

    # ---- Optional with secure defaults ----
    mcp_transport: Literal["streamable_http", "stdio"] = "streamable_http"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    mcp_stdio_user_id: int | None = None   # required when transport=stdio
    rate_limit_per_minute: int = 60
    http_timeout_s: float = 10.0
    http_max_connections: int = 50
    http_max_keepalive_connections: int = 20
    http_verify_tls: bool = True
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    template_cache_ttl_s: int = 300
```

**Design:**
- Pydantic v2 with `BaseSettings` for env var loading from `.env`
- Fail-fast: `SECRET_KEY` ≥32 bytes, `DATABASE_URL` must be PostgreSQL, `MCP_STDIO_USER_ID` required when transport=stdio
- Singleton (`get_settings()`) prevents reconfiguration at runtime

#### `auth.py` — API Key Management

```python
_KEY_PREFIX = "nm_live_"

def generate_api_key() -> str:
    return _KEY_PREFIX + secrets.token_urlsafe(32)  # ~256-bit entropy

def hash_key(key: str, *, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), key.encode(), hashlib.sha256).hexdigest()

async def resolve_user(api_key: str, settings: Settings) -> int | None:
    # 1. prefix check (short-circuit, no DB hit)
    # 2. compute hash
    # 3. lookup in DB (revoked_at IS NULL)
```

#### `db.py` — Database Connection Pool

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS api_keys (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,
    name        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ          -- NULL = active; non-NULL = revoked
);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
```

**Pool config:** min_size=2, max_size=10, command_timeout=30s

**Operations:**
- `connect(settings)` — create pool + apply schema (idempotent)
- `disconnect()` — close pool
- `lookup_user_by_key_hash(key_hash)` — returns user_id or None

#### `hmac_auth.py` — Request Signing

```python
_HEADER_APP_KEY       = "X-App-Key"
_HEADER_TIMESTAMP     = "X-App-Timestamp"
_HEADER_SIGNATURE     = "X-App-Signature"
_HEADER_ON_BEHALF_OF  = "X-On-Behalf-Of-User"

def build_auth_headers(app_key, app_secret, method, path, body, on_behalf_of_user_id=None):
    timestamp = str(int(time.time()))
    on_behalf_of = str(on_behalf_of_user_id) if on_behalf_of_user_id is not None else ""
    canonical = "\n".join([timestamp, method.upper(), path, on_behalf_of])
    msg = canonical.encode() + b"\n" + body
    signature = hmac.new(app_secret.encode(), msg, hashlib.sha256).hexdigest()
    headers = {X-App-Key: app_key, X-App-Timestamp: timestamp, X-App-Signature: signature}
    if on_behalf_of_user_id is not None:
        headers[X-On-Behalf-Of-User] = on_behalf_of
    return headers
```

**Canonical String Format:**
```
{timestamp}
{METHOD}
{path}
{on_behalf_of_user_id or ""}
```
Followed by `\n` + raw body bytes. Signature is HMAC-SHA256 hex-digest.

#### `context.py` — ContextVar Management

```python
current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)

def get_current_user_id_or_raise() -> int:
    uid = current_user_id.get()
    if uid is not None:
        return uid
    # Fallback for stdio transport (no auth middleware runs)
    stdio_uid = os.environ.get("MCP_STDIO_USER_ID")
    if stdio_uid:
        return int(stdio_uid)
    raise UnauthenticatedError(401, "unauthenticated", "no authenticated user in context")
```

**Why ContextVar?**
- Thread-safe across async contexts (each request gets its own context)
- Starlette/ASGI compatible
- Prevents user_id leakage between concurrent requests

#### `models.py` — Pydantic Input/Response Models

```python
# Input models (from MCP clients)
class SubmitNotificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    event_id: Annotated[str, Field(min_length=1, max_length=256)]
    channel: Literal["email", "sms", "push_ios", "push_android"]
    recipient: RecipientInput
    template_id: UUID | None = None
    variables: Annotated[dict[str, str], Field(max_length=50)] | None = None
    subject: str | None = Field(None, max_length=998)
    body: str | None = Field(None, max_length=160_000)

# Response models (from NotificationEngine)
class SubmitResponse(BaseModel):
    notification_id: UUID
    status: NotificationStatus
    duplicate: bool = False
```

**Design:**
- `extra="forbid"` — reject unknown fields
- Comprehensive bounds validation (min/max length, field constraints)
- Type coercion: string UUIDs → UUID objects

#### `middleware/auth_middleware.py` — Bearer Token Verification

```python
class AuthMiddleware:
    async def __call__(self, scope, receive, send):
        # Bypass /health
        # Extract Bearer token from Authorization header
        # Compute key_hash = HMAC-SHA256(SECRET_KEY, token).hexdigest()
        # Query DB: SELECT user_id WHERE key_hash=$1 AND revoked_at IS NULL
        # Set ContextVar; reset in finally block
        # On any failure: send 401 {"error": "unauthorized"}
```

**Security:**
- 401 response is always generic — never reveals if key exists or is revoked
- ContextVar reset in finally block ensures no leakage between requests

#### `middleware/rate_limit.py` — Request Throttling

```python
class RateLimitMiddleware:
    def __init__(self, app):
        self._windows: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, scope, receive, send):
        # Get user_id from ContextVar (set by AuthMiddleware)
        # Key: f"user:{uid}" or "anon"
        # Evict timestamps older than 60s
        # If len >= limit: send 429 with Retry-After header
        # Else: append timestamp, continue
```

#### `middleware/logging_middleware.py` — Access Logging

```python
class LoggingMiddleware:
    async def __call__(self, scope, receive, send):
        # Intercept response.start to capture status_code
        # After response: log method, path, status, duration_ms, user_id
        # No body/params logged (security)
```

### Tool Modules

#### `tools/notifications.py`

```python
async def submit_notification(event_id, channel, recipient_*, template_id, variables, subject, body):
    # 1. get_current_user_id_or_raise()
    # 2. SubmitNotificationInput validation (Pydantic)
    # 3. Build payload (inject user_id into recipient, omit nulls)
    # 4. service_api_client.request("POST", "/v1/notifications", on_behalf_of_user_id=user_id)
    # 5. SubmitResponse(**result).model_dump()
    # 6. log_tool_call(...)
    # 7. return response dict

async def get_notification(notification_id: str):
    # GET /v1/notifications/{uuid}
    # → NotificationView(**result).model_dump()
```

#### `tools/templates.py`

```python
_template_cache: dict[str, tuple[float, dict]] = {}  # template_id → (monotonic, data)

async def create_template(name, channel, body, locale, subject, media_urls, version):
    # POST /v1/templates  (on_behalf_of_user_id=user_id)
    # → TemplateView(**result).model_dump()

async def get_template(template_id: str):
    # Check in-memory TTL cache first
    # Cache miss: GET /v1/templates/{uuid}
    # Cache result; TTL from settings.template_cache_ttl_s (default 300s)
```

#### `tools/users.py`

```python
async def register_device(device_token: str, channel: str):
    # POST /v1/users/{user_id}/devices  (on_behalf_of_user_id=user_id)

async def update_user_setting(channel: str, opt_in: bool):
    # PUT /v1/users/{user_id}/settings  (on_behalf_of_user_id=user_id)
```

### Service Module

#### `services/service_api_client.py` — HTTP Client

```python
_client: httpx.AsyncClient | None = None
_MAX_RESPONSE_BYTES = 1 * 1024 * 1024  # 1 MB guard

async def init(settings):
    _client = httpx.AsyncClient(
        base_url=settings.service_api_url,
        timeout=httpx.Timeout(settings.http_timeout_s),
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        verify=settings.http_verify_tls,
        follow_redirects=False,
    )

async def request(settings, method, path, *, on_behalf_of_user_id=None, json_body=None):
    # 1. Serialize body (compact JSON)
    # 2. build_auth_headers(...)
    # 3. Execute request
    # 4. Guard: len(content) > 1 MB → RuntimeError
    # 5. 200/201/202 → parse JSON; 204 → return None
    # 6. 4xx/5xx → raise_for_response(status, body, retry_after)
```

## Deployment Modes

### 1. HTTP Server (Production / Claude Desktop)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Transport:** streamable-http (MCP over HTTP with streaming)

**Architecture:**
- Pure Starlette ASGI app (`app.py`)
- FastMCP sub-app mounted at `Mount("/")` (preserves `/mcp` path internally)
- `mcp.session_manager.run()` called from outermost lifespan
- uvloop installed automatically if available (improves throughput on Linux/macOS)

### 2. `mcp dev` (Development / Testing)

```bash
mcp dev server_dev.py
```

`mcp dev` is part of the official `mcp[cli]` SDK. It starts the server and opens the built-in MCP Inspector UI automatically — no need to run a separate inspector command.

`server_dev.py` exists at the project root because `mcp dev` loads files without package context, so `mcp_server`'s relative imports would fail. The file simply re-exports the FastMCP instance as an absolute import:

```python
from mcp_server.mcp_instance import mcp  # noqa: F401
```

### 3. Stdio Transport (Single-User Local)

```bash
MCP_TRANSPORT=stdio MCP_STDIO_USER_ID=42 python main.py
```

- Skips FastAPI/uvicorn entirely; runs `mcp.run(transport="stdio")` directly
- `get_current_user_id_or_raise()` reads `MCP_STDIO_USER_ID` from env (no auth middleware)

## Error Handling

### Error Hierarchy (`errors.py`)

```python
NotificationEngineError (base)
  ├─ NotFoundError          (not_found → 404)
  ├─ AlreadyExistsError     (already_exists → 409)
  ├─ InvalidInputError      (invalid_input, invalid_json, invalid_channel → 400)
  ├─ OptedOutError          (opted_out → 403)
  ├─ RateLimitedError       (rate_limited → 429; has retry_after attr)
  ├─ ForbiddenError         (forbidden → 403)
  ├─ UnauthenticatedError   (unauthenticated, invalid_on_behalf_of → 401)
  └─ UpstreamError          (catch-all for unknown codes)
```

### Auth Failure

```
Request with invalid/missing Bearer → AuthMiddleware → 401 {"error": "unauthorized"}
```

### Rate Limit Exceeded

```
61st request/min → RateLimitMiddleware → 429 {"error": "rate_limit_exceeded"}
                                         Retry-After: <seconds>
```

### Upstream API Error

```
service_api_client.request() → response.status_code >= 400
  → raise_for_response(status, body)
  → raises appropriate NotificationEngineError subclass
  → bubbles through tool → FastMCP → MCP error response to client
```

## Security Checklist

- [x] **User_id Isolation**: Always from ContextVar (auth middleware), never from client input
- [x] **API Key Storage**: `HMAC-SHA256(SECRET_KEY, key)` hex-digest; DB leak without SECRET_KEY is useless
- [x] **HMAC Signing**: All outgoing requests signed (X-App-Key, X-App-Signature, X-App-Timestamp)
- [x] **Canonical String**: Covers timestamp + method + path + on_behalf_of_user + body
- [x] **Rate Limiting**: Per-user_id, not per-IP (works behind NAT)
- [x] **Generic 401**: Never reveals if a key exists or is revoked
- [x] **No Sensitive Logging**: Body/params never logged (no credential leaks)
- [x] **TLS Verification**: Enabled by default (`HTTP_VERIFY_TLS=true`)
- [x] **Response Size Guard**: 1 MB cap on service API responses
- [x] **Input Validation**: Pydantic `extra="forbid"` + field bounds on all inputs
- [x] **ContextVar Reset**: AuthMiddleware resets ContextVar in finally block (no leakage)

## Testing Strategy

### Unit Tests (test_auth.py, test_config.py, test_hmac.py)
- API key generation, hashing, resolve_user (with mocked DB)
- Configuration validation (fail-fast checks)
- HMAC signing (cross-language test vectors)
- No external dependencies

### Integration Tests (test_http_app.py, test_tools.py)
- HTTP endpoints: /health, /mcp
- Auth middleware: Bearer token extraction, database lookup
- Tool execution: input validation, service API mocking (respx)
- Error propagation: Pydantic errors, upstream API errors

### Test Coverage
- 38/38 passing (pytest-asyncio in auto mode)
- No external services required (all mocked via monkeypatch + respx)

## Future Improvements

1. **Distributed Rate Limiting**: Replace in-memory window with Redis backend
2. **Template Cache Invalidation**: Webhook or event-based invalidation
3. **API Key Expiration**: Auto-expire old keys, implement rotation
4. **Metrics & Observability**: Prometheus metrics (requests/sec, latency, error rates)
5. **Batch Operations**: `submit_notifications` (plural) for bulk delivery
6. **Audit Logging**: Track all API key mutations, tool invocations
