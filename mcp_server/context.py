from __future__ import annotations

import contextvars

from .errors import UnauthenticatedError

current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "current_user_id", default=None
)


def get_current_user_id_or_raise() -> int:
    uid = current_user_id.get()
    if uid is None:
        raise UnauthenticatedError(401, "unauthenticated", "no authenticated user in context")
    return uid
