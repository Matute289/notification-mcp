"""Singleton async HTTP client with HMAC signing and connection pooling."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .config import Settings
from .errors import raise_for_response
from .hmac_auth import build_auth_headers

logger = logging.getLogger(__name__)

_MAX_RESPONSE_BYTES = 1 * 1024 * 1024  # 1 MB guard against unexpectedly large bodies

_client: httpx.AsyncClient | None = None


def _make_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.notification_engine_base_url,
        timeout=httpx.Timeout(settings.http_timeout_s),
        limits=httpx.Limits(
            max_connections=settings.http_max_connections,
            max_keepalive_connections=settings.http_max_keepalive_connections,
        ),
        verify=settings.http_verify_tls,
        follow_redirects=False,
    )


def init_client(settings: Settings) -> None:
    global _client
    _client = _make_client(settings)


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client is not initialized. Call init_client() first.")
    return _client


async def request(
    settings: Settings,
    method: str,
    path: str,
    *,
    on_behalf_of_user_id: int | None = None,
    json_body: Any = None,
) -> Any:
    """Sign and execute an HTTP request against NotificationEngine.

    Returns the parsed JSON body on success (2xx).
    Raises a NotificationEngineError subclass on 4xx/5xx.
    """
    raw_body = b""
    if json_body is not None:
        raw_body = json.dumps(json_body, separators=(",", ":")).encode()

    auth_headers = build_auth_headers(
        app_key=settings.notification_engine_app_key,
        app_secret=settings.notification_engine_app_secret,
        method=method,
        path=path,
        body=raw_body,
        on_behalf_of_user_id=on_behalf_of_user_id,
    )

    headers = {**auth_headers, "Content-Type": "application/json"}

    client = _get_client()
    response = await client.request(
        method,
        path,
        content=raw_body if raw_body else None,
        headers=headers,
    )

    # Guard against huge response bodies
    content = response.content
    if len(content) > _MAX_RESPONSE_BYTES:
        raise RuntimeError(f"Response body too large: {len(content)} bytes from {method} {path}")

    if response.status_code in (200, 201, 202):
        if content:
            return response.json()
        return None

    if response.status_code == 204:
        return None

    # Error path
    try:
        error_body: dict[str, Any] = response.json()
    except Exception:
        error_body = {"code": "upstream_error", "message": response.text[:500]}

    retry_after: int | None = None
    if response.status_code == 429:
        try:
            retry_after = int(response.headers.get("Retry-After", "0")) or None
        except ValueError:
            pass

    raise_for_response(response.status_code, error_body, retry_after=retry_after)
