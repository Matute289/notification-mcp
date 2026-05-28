"""Entry point for the NotificationEngine MCP server.

HTTP/streamable-http (default):
    uvicorn main:app --host 0.0.0.0 --port 8000

stdio (single-user local):
    MCP_TRANSPORT=stdio MCP_STDIO_USER_ID=42 python main.py
"""
from __future__ import annotations

try:
    import uvloop as _uvloop
    _uvloop.install()
except ImportError:
    _uvloop = None  # type: ignore[assignment]

from mcp_server.app import app  # noqa: F401 — exported for uvicorn main:app

if __name__ == "__main__":
    from mcp_server.config import get_settings
    settings = get_settings()

    if settings.mcp_transport == "stdio":
        from mcp_server.context import current_user_id
        from mcp_server.mcp_instance import mcp
        if settings.mcp_stdio_user_id is not None:
            current_user_id.set(settings.mcp_stdio_user_id)
        mcp.run(transport="stdio")
    else:
        import uvicorn
        uvicorn.run(app, host=settings.mcp_host, port=settings.mcp_port)
