"""MCP resource: notification://history"""
from __future__ import annotations

import json

from ..tools.notifications import list_notifications


async def build_history_resource() -> str:
    """Return the 20 most recent notifications as JSON."""
    result = await list_notifications(limit=20)
    return json.dumps(result, default=str)
