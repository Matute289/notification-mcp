"""Auth middleware — pure ASGI (no BaseHTTPMiddleware) to avoid buffering SSE streams."""
from __future__ import annotations

import json

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

from ..auth import resolve_user
from ..config import get_settings
from ..context import current_user_id

log = structlog.get_logger(__name__)

_401_BODY = json.dumps({"error": "unauthorized"}).encode()
_401_HEADERS = [
    (b"content-type", b"application/json"),
    (b"content-length", str(len(_401_BODY)).encode()),
]
_BYPASS_PATHS = {"/health"}


def _get_client_ip(scope: Scope) -> str:
    forwarded = dict(scope.get("headers", [])).get(b"x-forwarded-for", b"")
    if forwarded:
        return forwarded.decode().split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


async def _send_401(send: Send) -> None:
    await send({"type": "http.response.start", "status": 401, "headers": _401_HEADERS})
    await send({"type": "http.response.body", "body": _401_BODY, "more_body": False})


class AuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _BYPASS_PATHS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        ip = _get_client_ip(scope)

        if not auth_header.lower().startswith("bearer "):
            log.warning("auth_failed", reason="missing_token", ip=ip, path=path)
            await _send_401(send)
            return

        token = auth_header[7:].strip()
        if not token:
            log.warning("auth_failed", reason="empty_token", ip=ip, path=path)
            await _send_401(send)
            return

        settings = get_settings()
        user_id = await resolve_user(token, settings)
        if user_id is None:
            log.warning("auth_failed", reason="invalid_token", ip=ip, path=path)
            await _send_401(send)
            return

        token_ctx = current_user_id.set(user_id)
        try:
            await self.app(scope, receive, send)
        finally:
            current_user_id.reset(token_ctx)
