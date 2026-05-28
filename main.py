"""Entry point for the NotificationEngine MCP server.

Usage:
    python main.py                   # stdio transport (default for MCP clients)
    MCP_TRANSPORT=sse python main.py # HTTP/SSE transport
"""
from __future__ import annotations

try:
    import uvloop as _uvloop
    _uvloop.install()
except ImportError:
    _uvloop = None  # type: ignore[assignment]

from src.notification_mcp.config import get_settings
from src.notification_mcp.server import mcp

if __name__ == "__main__":
    settings = get_settings()
    transport = settings.mcp_transport

    if transport == "sse":
        mcp.run(
            transport="sse",
            host=settings.mcp_host,
            port=settings.mcp_port,
        )
    else:
        mcp.run(transport="http")
