from __future__ import annotations

import contextvars

from .errors import UnauthenticatedError

current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "current_user_id", default=None
)


def get_current_user_id_or_raise() -> int:
    uid = current_user_id.get()
    if uid is not None:
        return uid
    # Fallback for stdio transport (mcp dev / Claude Desktop):
    # no auth middleware runs, so we read from env var set by the operator.
    import os
    stdio_uid = os.environ.get("MCP_STDIO_USER_ID")
    if stdio_uid:
        try:
            return int(stdio_uid)
        except ValueError:
            raise UnauthenticatedError(
                401, "unauthenticated",
                f"MCP_STDIO_USER_ID must be an integer, got: {stdio_uid!r}",
            )
    raise UnauthenticatedError(401, "unauthenticated", "no authenticated user in context")
