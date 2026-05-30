"""MCP resource: notification://settings"""
from __future__ import annotations

import json

from ..tools.users import get_user_settings


async def build_settings_resource() -> str:
    """Return all channel preferences for the user as JSON."""
    result = await get_user_settings()
    return json.dumps(result, default=str)
