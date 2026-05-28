"""Per-user rate limiting — pure ASGI sliding window.

slowapi requires @limiter.limit() decorators on route functions, which cannot
be applied to the mounted FastMCP sub-app. This middleware implements a simple
in-memory sliding window keyed by user_id (set by AuthMiddleware via contextvar).
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Any

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

from ..config import get_settings
from ..context import current_user_id

log = structlog.get_logger(__name__)

_429_HEADERS_BASE = [(b"content-type", b"application/json")]
_BYPASS_PATHS = {"/health"}


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        # keyed by user_id string → list of request timestamps (monotonic)
        self._windows: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _BYPASS_PATHS:
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        limit = settings.rate_limit_per_minute
        window_s = 60.0

        uid = current_user_id.get()
        key = f"user:{uid}" if uid is not None else "anon"

        now = time.monotonic()
        window_start = now - window_s
        timestamps = self._windows[key]

        # Evict expired entries
        self._windows[key] = [t for t in timestamps if t > window_start]

        if len(self._windows[key]) >= limit:
            retry_after = int(self._windows[key][0] + window_s - now) + 1
            ip = _client_ip(scope)
            log.warning("rate_limit_exceeded", user_id=uid, ip=ip, path=path,
                        limit=limit, retry_after=retry_after)
            body = json.dumps({"error": "rate_limit_exceeded"}).encode()
            headers = _429_HEADERS_BASE + [
                (b"content-length", str(len(body)).encode()),
                (b"retry-after", str(retry_after).encode()),
            ]
            await send({"type": "http.response.start", "status": 429, "headers": headers})
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        self._windows[key].append(now)
        await self.app(scope, receive, send)


def _client_ip(scope: Scope) -> str:
    forwarded = dict(scope.get("headers", [])).get(b"x-forwarded-for", b"")
    if forwarded:
        return forwarded.decode().split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"
