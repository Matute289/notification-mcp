"""MCP resource: notification://templates"""
from __future__ import annotations

import json

from ..tools.templates import list_templates


async def build_templates_resource() -> str:
    """Return all user templates grouped by channel as JSON."""
    result = await list_templates()
    return json.dumps(result, default=str)
