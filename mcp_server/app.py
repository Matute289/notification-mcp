"""FastAPI application — mounts the FastMCP streamable-http app and adds middleware."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from . import db
from .config import get_settings
from .errors import NotificationEngineError
from .logging_setup import setup_logging
from .middleware.auth_middleware import AuthMiddleware
from .middleware.logging_middleware import LoggingMiddleware
from .middleware.rate_limit import limiter, rate_limit_exceeded_handler
from .services import service_api_client

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings)
    log.info("startup", transport=settings.mcp_transport, host=settings.mcp_host, port=settings.mcp_port)
    await db.connect(settings)
    await service_api_client.init(settings)
    try:
        yield
    finally:
        await service_api_client.close()
        await db.disconnect()
        log.info("shutdown")


async def _generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, NotificationEngineError):
        log.warning("upstream_error", code=exc.code, status=exc.status_code, path=str(request.url.path))
        return JSONResponse({"error": exc.code}, status_code=exc.status_code)
    log.exception("unhandled_exception", path=str(request.url.path))
    return JSONResponse({"error": "internal_server_error"}, status_code=500)


def create_app() -> FastAPI:
    from .mcp_instance import mcp  # imported here to avoid circular import at module level

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

    # Rate limiter state on the app
    app.state.limiter = limiter

    # Exception handlers
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_exception_handler(Exception, _generic_error_handler)

    # Middleware — FastAPI applies in reverse order, so last added runs first.
    # We want: Auth → RateLimit → Logging (outermost first).
    # Add in reverse: Logging first, RateLimit second, Auth last (runs first).
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(AuthMiddleware)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok"}

    # Mount FastMCP streamable-http at /mcp
    mcp_asgi = mcp.http_app(transport="streamable-http")
    app.mount("/mcp", mcp_asgi)

    return app


app = create_app()
