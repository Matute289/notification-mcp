"""HMAC-SHA256 request signing — mirrors NotificationEngine's canonical string.

Canonical string (all parts joined with newline, no trailing newline):
    timestamp \\n method \\n path \\n on_behalf_of \\n body

- timestamp    : Unix seconds as decimal string
- method       : HTTP method in UPPERCASE
- path         : URL path (no query string)
- on_behalf_of : value of X-On-Behalf-Of-User header, or "" if absent
- body         : raw request body bytes decoded as UTF-8 (empty string if no body)
"""
from __future__ import annotations

import hashlib
import hmac
import time


_HEADER_APP_KEY = "X-App-Key"
_HEADER_TIMESTAMP = "X-App-Timestamp"
_HEADER_SIGNATURE = "X-App-Signature"
_HEADER_ON_BEHALF_OF = "X-On-Behalf-Of-User"


def _sign(secret: str, timestamp: str, method: str, path: str, on_behalf_of: str, body: bytes) -> str:
    canonical = "\n".join([timestamp, method.upper(), path, on_behalf_of])
    msg = canonical.encode() + b"\n" + body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def build_auth_headers(
    app_key: str,
    app_secret: str,
    method: str,
    path: str,
    body: bytes,
    on_behalf_of_user_id: int | None = None,
) -> dict[str, str]:
    """Return the set of HMAC auth headers to attach to a request.

    on_behalf_of_user_id: when provided, sets X-On-Behalf-Of-User and
    includes it in the signed payload.
    """
    timestamp = str(int(time.time()))
    on_behalf_of = str(on_behalf_of_user_id) if on_behalf_of_user_id is not None else ""

    signature = _sign(app_secret, timestamp, method, path, on_behalf_of, body)

    headers: dict[str, str] = {
        _HEADER_APP_KEY: app_key,
        _HEADER_TIMESTAMP: timestamp,
        _HEADER_SIGNATURE: signature,
    }
    if on_behalf_of_user_id is not None:
        headers[_HEADER_ON_BEHALF_OF] = on_behalf_of
    return headers
