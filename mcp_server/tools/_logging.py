from __future__ import annotations

import time

import structlog

log = structlog.get_logger(__name__)


def log_tool_call(
    tool_name: str,
    user_id: int,
    start: float,
    *,
    success: bool,
    error_type: str | None = None,
) -> None:
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    log.info(
        "tool_call",
        tool_name=tool_name,
        user_id=user_id,
        duration_ms=duration_ms,
        success=success,
        error_type=error_type,
    )
