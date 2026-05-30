from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from ..config import get_settings
from ..context import get_current_user_id_or_raise
from ._logging import log_tool_call
from ..models import (
    GetNotificationInput,
    NotificationListResponse,
    NotificationView,
    RecipientInput,
    SubmitNotificationInput,
    SubmitResponse,
)
from ..services import service_api_client


async def submit_notification(
    event_id: str,
    channel: str,
    recipient_email: str | None,
    recipient_phone_number: str | None,
    recipient_device_token: str | None,
    template_id: str | None,
    variables: dict[str, str] | None,
    subject: str | None,
    body: str | None,
) -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "submit_notification"
    try:
        inp = SubmitNotificationInput(
            event_id=event_id,
            channel=channel,  # type: ignore[arg-type]
            recipient=RecipientInput(
                email=recipient_email,
                phone_number=recipient_phone_number,
                device_token=recipient_device_token,
            ),
            template_id=UUID(template_id) if template_id else None,
            variables=variables,
            subject=subject,
            body=body,
        )

        payload: dict[str, Any] = {
            "event_id": inp.event_id,
            "channel": inp.channel,
            "recipient": {
                k: v for k, v in {
                    "user_id": user_id,
                    "email": inp.recipient.email,
                    "phone_number": inp.recipient.phone_number,
                    "device_token": inp.recipient.device_token,
                }.items() if v is not None
            },
        }
        if inp.template_id:
            payload["template_id"] = str(inp.template_id)
        if inp.variables:
            payload["variables"] = inp.variables
        if inp.subject:
            payload["subject"] = inp.subject
        if inp.body:
            payload["body"] = inp.body

        result = await service_api_client.request(
            settings, "POST", "/v1/notifications",
            on_behalf_of_user_id=user_id, json_body=payload,
        )
        response = SubmitResponse(**result).model_dump()
        log_tool_call(tool_name, user_id, start, success=True)
        return response
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise


async def get_notification(notification_id: str) -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "get_notification"
    try:
        inp = GetNotificationInput(notification_id=UUID(notification_id))
        result = await service_api_client.request(
            settings, "GET", f"/v1/notifications/{inp.notification_id}",
            on_behalf_of_user_id=user_id,
        )
        response = NotificationView(**result).model_dump()
        log_tool_call(tool_name, user_id, start, success=True)
        return response
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise


async def list_notifications(
    limit: int = 20,
    cursor: str | None = None,
    channel: str | None = None,
    status: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "list_notifications"
    try:
        params: dict[str, str] = {"limit": str(limit)}
        if cursor:
            params["cursor"] = cursor
        if channel:
            params["channel"] = channel
        if status:
            params["status"] = status
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        result = await service_api_client.request(
            settings, "GET", "/v1/notifications",
            on_behalf_of_user_id=user_id, params=params,
        )
        response = NotificationListResponse(**result).model_dump()
        log_tool_call(tool_name, user_id, start, success=True)
        return response
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise


