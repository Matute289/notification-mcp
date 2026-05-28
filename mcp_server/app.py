"""ASGI app — FastMCP's http_app as the root with our middleware and /health route.

FastMCP's streamable-http transport uses anyio task groups initialized in its
own lifespan. It must be the ASGI root — mounting it inside FastAPI breaks that
lifespan. Instead we use create_streamable_http_app() directly, passing our
middleware and a /health route as Starlette primitives.
"""
from __future__ import annotations

from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .middleware.auth_middleware import AuthMiddleware
from .middleware.logging_middleware import LoggingMiddleware


async def _health(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


def create_app():
    from .mcp_instance import mcp
    from fastmcp.server.http import create_streamable_http_app

    return create_streamable_http_app(
        server=mcp,
        streamable_http_path="/mcp",
        middleware=[
            Middleware(AuthMiddleware),
            Middleware(LoggingMiddleware),
        ],
        routes=[
            Route("/health", _health, methods=["GET"]),
        ],
    )


app = create_app()
