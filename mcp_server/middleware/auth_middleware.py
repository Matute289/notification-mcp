from __future__ import annotations

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from ..auth import resolve_user
from ..config import get_settings
from ..context import current_user_id

log = structlog.get_logger(__name__)

_UNAUTHENTICATED = JSONResponse({"error": "unauthorized"}, status_code=401)
_BYPASS_PATHS = {"/health"}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _BYPASS_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            log.warning("auth_failed", reason="missing_token", ip=_client_ip(request), path=request.url.path)
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        token = auth_header[7:].strip()
        if not token:
            log.warning("auth_failed", reason="empty_token", ip=_client_ip(request), path=request.url.path)
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        settings = get_settings()
        user_id = await resolve_user(token, settings)
        if user_id is None:
            log.warning("auth_failed", reason="invalid_token", ip=_client_ip(request), path=request.url.path)
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        token_ctx = current_user_id.set(user_id)
        try:
            return await call_next(request)
        finally:
            current_user_id.reset(token_ctx)
