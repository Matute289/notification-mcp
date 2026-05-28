from __future__ import annotations

import functools
import time
from typing import Any
from uuid import UUID

from ..client import request
from ..config import get_settings
from ..models import CreateTemplateInput, GetTemplateInput, TemplateView


# Simple TTL cache: maps template_id (str) → (fetched_at, data)
_template_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _cache_get(template_id: str, ttl_s: int) -> dict[str, Any] | None:
    if ttl_s <= 0:
        return None
    entry = _template_cache.get(template_id)
    if entry and (time.monotonic() - entry[0]) < ttl_s:
        return entry[1]
    return None


def _cache_set(template_id: str, data: dict[str, Any]) -> None:
    _template_cache[template_id] = (time.monotonic(), data)


async def create_template(
    user_id: int,
    name: str,
    channel: str,
    body: str,
    locale: str = "en",
    subject: str | None = None,
    media_urls: list[str] | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create a reusable notification template owned by the specified user.

    Templates support variable interpolation using {{variable_name}} syntax in
    subject and body fields. The owner (user_id) is enforced server-side via
    the X-On-Behalf-Of-User header.

    Returns the created template including its id and owner_user_id.
    """
    settings = get_settings()
    inp = CreateTemplateInput(
        user_id=user_id,
        name=name,
        channel=channel,  # type: ignore[arg-type]
        locale=locale,
        subject=subject,
        body=body,
        media_urls=media_urls,
        version=version,
    )

    payload: dict[str, Any] = {
        "name": inp.name,
        "channel": inp.channel,
        "locale": inp.locale,
        "body": inp.body,
        "version": inp.version,
    }
    if inp.subject:
        payload["subject"] = inp.subject
    if inp.media_urls:
        payload["media_urls"] = inp.media_urls

    result = await request(
        settings,
        "POST",
        "/v1/templates",
        on_behalf_of_user_id=inp.user_id,
        json_body=payload,
    )
    return TemplateView(**result).model_dump()


async def get_template(template_id: str) -> dict[str, Any]:
    """Retrieve a template by its UUID. Results are cached in-process for
    template_cache_ttl_s seconds (default 300 s; 0 disables caching).
    """
    settings = get_settings()
    inp = GetTemplateInput(template_id=UUID(template_id))
    tid = str(inp.template_id)

    cached = _cache_get(tid, settings.template_cache_ttl_s)
    if cached is not None:
        return cached

    result = await request(settings, "GET", f"/v1/templates/{tid}")
    view = TemplateView(**result).model_dump()
    _cache_set(tid, view)
    return view
