"""Singleton async HTTP client for NotificationEngine with HMAC signing.

A single AsyncClient instance is shared across all requests. This is safe
in async code: httpx manages per-request state internally and the connection
pool is correctly isolated between concurrent coroutines.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from ..config import Settings
from ..errors import raise_for_response
from ..hmac_auth import build_auth_headers

log = structlog.get_logger(__name__)

_MAX_RESPONSE_BYTES = 1 * 1024 * 1024  # 1 MB guard

_client: httpx.AsyncClient | None = None


async def init(settings: Settings) -> None:
    global _client
    _client = httpx.AsyncClient(
        base_url=settings.service_api_url,
        timeout=httpx.Timeout(settings.http_timeout_s),
        limits=httpx.Limits(
            max_connections=settings.http_max_connections,
            max_keepalive_connections=settings.http_max_keepalive_connections,
        ),
        verify=settings.http_verify_tls,
        follow_redirects=False,
    )


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("Service API client not initialized. Call service_api_client.init() first.")
    return _client


async def request(
    settings: Settings,
    method: str,
    path: str,
    *,
    on_behalf_of_user_id: int | None = None,
    json_body: Any = None,
    params: dict[str, str] | None = None,
) -> Any:
    """Sign and execute a request to the Service API (NotificationEngine).

    Returns parsed JSON on 2xx. Raises NotificationEngineError subclass on 4xx/5xx.

    params: optional query parameters — appended by httpx to the URL but NOT
        included in the HMAC signature path (backend verifier strips query params).
    """
    raw_body = b""
    if json_body is not None:
        raw_body = json.dumps(json_body, separators=(",", ":")).encode()

    auth_headers = build_auth_headers(
        app_key=settings.service_api_key,
        app_secret=settings.service_api_secret,
        method=method,
        path=path,
        body=raw_body,
        on_behalf_of_user_id=on_behalf_of_user_id,
    )

    headers = {**auth_headers, "Content-Type": "application/json"}
    response = await _get_client().request(
        method, path, content=raw_body if raw_body else None, headers=headers,
        params=params,
    )

    content = response.content
    if len(content) > _MAX_RESPONSE_BYTES:
        raise RuntimeError(f"Response body too large: {len(content)} bytes from {method} {path}")

    if response.status_code in (200, 201, 202):
        if not content:
            raise RuntimeError(
                f"Unexpected empty body for {response.status_code} {method} {path}"
            )
        return response.json()
    if response.status_code == 204:
        return None

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
