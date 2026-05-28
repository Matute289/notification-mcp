"""Entry point for `mcp dev server_dev.py`.

mcp dev loads files without package context, so relative imports fail.
This file sits at the project root where `mcp_server` is importable as
an absolute package, then re-exports the FastMCP instance.
"""
from mcp_server.mcp_instance import mcp  # noqa: F401
