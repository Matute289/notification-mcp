"""ASGI app — official MCP SDK integration with custom middleware and /health route.

The official SDK's streamable_http_app() returns a Starlette app with /mcp
defined internally. We mount it inside a parent Starlette app that:
  - Owns the process lifespan (DB pool, service client, session_manager.run())
  - Applies our pure-ASGI middleware (auth, logging)
  - Exposes /health without authentication

Key constraint: session_manager.run() must be called exactly once, from the
outermost lifespan. Mounting mcp_starlette as a sub-app suppresses its inner
lifespan, so we call mcp.session_manager.run() ourselves here.
"""
from __future__ import annotations

import contextlib

import structlog
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from . import db
from .config import get_settings
from .logging_setup import setup_logging
from .middleware.auth_middleware import AuthMiddleware
from .middleware.logging_middleware import LoggingMiddleware
from .services import service_api_client

log = structlog.get_logger(__name__)


async def _health(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


def create_app() -> Starlette:
    from .mcp_instance import mcp

    # streamable_http_app() must be called before mcp.session_manager is accessed
    mcp_starlette = mcp.streamable_http_app()

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        settings = get_settings()
        setup_logging(settings)
        log.info("startup", transport=settings.mcp_transport,
                 host=settings.mcp_host, port=settings.mcp_port)
        await db.connect(settings)
        await service_api_client.init(settings)
        async with mcp.session_manager.run():
            yield
        await service_api_client.close()
        await db.disconnect()
        log.info("shutdown")

    return Starlette(
        routes=[
            Route("/health", _health, methods=["GET"]),
            # mcp_starlette has /mcp defined internally; Mount("/") preserves
            # the full path so /mcp reaches it correctly (Mount("/mcp") would
            # cause Starlette to strip the prefix and the sub-app would look
            # for /mcp within itself → 404).
            Mount("/", app=mcp_starlette),
        ],
        middleware=[
            Middleware(AuthMiddleware),
            Middleware(LoggingMiddleware),
        ],
        lifespan=lifespan,
    )


app = create_app()
