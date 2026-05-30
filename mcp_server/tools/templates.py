from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from ..config import get_settings
from ..context import get_current_user_id_or_raise
from ..models import CreateTemplateInput, GetTemplateInput, TemplateView, UpdateTemplateInput
from ..services import service_api_client
from ._logging import log_tool_call

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
    name: str,
    channel: str,
    body: str,
    locale: str = "en",
    subject: str | None = None,
    media_urls: list[str] | None = None,
    version: int = 1,
) -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "create_template"
    try:
        inp = CreateTemplateInput(
            name=name, channel=channel, locale=locale,  # type: ignore[arg-type]
            subject=subject, body=body, media_urls=media_urls, version=version,
        )
        payload: dict[str, Any] = {
            "name": inp.name, "channel": inp.channel, "locale": inp.locale,
            "body": inp.body, "version": inp.version,
        }
        if inp.subject:
            payload["subject"] = inp.subject
        if inp.media_urls:
            payload["media_urls"] = inp.media_urls

        result = await service_api_client.request(
            settings, "POST", "/v1/templates",
            on_behalf_of_user_id=user_id, json_body=payload,
        )
        response = TemplateView(**result).model_dump()
        log_tool_call(tool_name, user_id, start, success=True)
        return response
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise


async def get_template(template_id: str) -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "get_template"
    try:
        inp = GetTemplateInput(template_id=UUID(template_id))
        tid = str(inp.template_id)
        cached = _cache_get(tid, settings.template_cache_ttl_s)
        if cached is not None:
            log_tool_call(tool_name, user_id, start, success=True)
            return cached
        result = await service_api_client.request(settings, "GET", f"/v1/templates/{tid}", on_behalf_of_user_id=user_id)
        view = TemplateView(**result).model_dump()
        _cache_set(tid, view)
        log_tool_call(tool_name, user_id, start, success=True)
        return view
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise


async def list_templates() -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "list_templates"
    try:
        result = await service_api_client.request(settings, "GET", "/v1/templates", on_behalf_of_user_id=user_id)
        validated: dict[str, Any] = {
            channel: [TemplateView(**t).model_dump() for t in templates]
            for channel, templates in result.items()
            if isinstance(templates, list)
        }
        log_tool_call(tool_name, user_id, start, success=True)
        return validated
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise


async def update_template(
    template_id: str,
    name: str,
    body: str,
    subject: str | None = None,
    media_urls: list[str] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "update_template"
    try:
        inp = UpdateTemplateInput(
            template_id=UUID(template_id),
            name=name, subject=subject, body=body, media_urls=media_urls,
        )
        payload: dict[str, Any] = {
            "name": inp.name, "body": inp.body,
        }
        if inp.subject:
            payload["subject"] = inp.subject
        if inp.media_urls:
            payload["media_urls"] = inp.media_urls

        result = await service_api_client.request(
            settings, "PUT", f"/v1/templates/{inp.template_id}",
            on_behalf_of_user_id=user_id, json_body=payload,
        )
        response = TemplateView(**result).model_dump()
        log_tool_call(tool_name, user_id, start, success=True)
        return response
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise
