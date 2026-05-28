"""Per-user rate limiting via slowapi."""
from __future__ import annotations

import structlog
from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse

from ..context import current_user_id

log = structlog.get_logger(__name__)


def _user_id_key(request: Request) -> str:
    """Key function: rate-limit by authenticated user_id, not by IP."""
    uid = current_user_id.get()
    if uid is not None:
        return f"user:{uid}"
    # Unauthenticated requests are already blocked by AuthMiddleware before
    # reaching rate-limited endpoints, but fall back to IP just in case.
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_user_id_key, headers_enabled=True)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    uid = current_user_id.get()
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    log.warning("rate_limit_exceeded", user_id=uid, ip=ip, path=str(request.url.path))
    retry_after = getattr(exc, "retry_after", None) or 60
    return JSONResponse(
        {"error": "rate_limit_exceeded"},
        status_code=429,
        headers={"Retry-After": str(retry_after)},
    )
