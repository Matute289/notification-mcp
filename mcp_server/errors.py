"""Map NotificationEngine HTTP error responses to Python exceptions."""
from __future__ import annotations

from typing import Any


class NotificationEngineError(Exception):
    """Base for all errors returned by NotificationEngine."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} (HTTP {self.status_code})"


class NotFoundError(NotificationEngineError):
    pass


class AlreadyExistsError(NotificationEngineError):
    pass


class InvalidInputError(NotificationEngineError):
    pass


class OptedOutError(NotificationEngineError):
    pass


class RateLimitedError(NotificationEngineError):
    def __init__(self, status_code: int, code: str, message: str, retry_after: int | None = None) -> None:
        super().__init__(status_code, code, message)
        self.retry_after = retry_after


class ForbiddenError(NotificationEngineError):
    pass


class UnauthenticatedError(NotificationEngineError):
    pass


class UpstreamError(NotificationEngineError):
    """Unexpected / unclassified upstream error."""
    pass


class ConflictError(NotificationEngineError):
    """409 — resource already exists (e.g. duplicate event_id in rapid succession)."""


class InvalidEmailError(NotificationEngineError):
    """400 — email address format rejected by NotificationEngine."""


class InvalidPhoneError(NotificationEngineError):
    """400 — phone number format rejected by NotificationEngine."""


_CODE_MAP: dict[str, type[NotificationEngineError]] = {
    "not_found": NotFoundError,
    "already_exists": AlreadyExistsError,
    "invalid_input": InvalidInputError,
    "invalid_json": InvalidInputError,
    "invalid_channel": InvalidInputError,
    "opted_out": OptedOutError,
    "rate_limited": RateLimitedError,
    "forbidden": ForbiddenError,
    "unauthenticated": UnauthenticatedError,
    "invalid_on_behalf_of": UnauthenticatedError,
    "conflict": ConflictError,
    "invalid_email": InvalidEmailError,
    "invalid_phone": InvalidPhoneError,
    "invalid_request": InvalidInputError,
    "invalid_id": InvalidInputError,
    "internal_error": UpstreamError,
}


def raise_for_response(status_code: int, body: dict[str, Any], retry_after: int | None = None) -> None:
    """Raise the appropriate exception based on the API error response body."""
    code = body.get("code", "unknown")
    message = body.get("message", "unknown error")
    exc_class = _CODE_MAP.get(code, UpstreamError)
    if exc_class is RateLimitedError:
        raise RateLimitedError(status_code, code, message, retry_after=retry_after)
    raise exc_class(status_code, code, message)
