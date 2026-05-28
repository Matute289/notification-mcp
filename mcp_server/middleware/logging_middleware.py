"""HTTP access logging middleware — pure ASGI to avoid buffering SSE streams."""
from __future__ import annotations

import time

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

from ..context import current_user_id

log = structlog.get_logger(__name__)


class LoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 0

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        log.info(
            "http_request",
            method=scope.get("method", ""),
            path=scope.get("path", ""),
            status=status_code,
            duration_ms=duration_ms,
            user_id=current_user_id.get(),
        )
