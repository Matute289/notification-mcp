from __future__ import annotations

from typing import Any
from uuid import UUID

from ..client import request
from ..config import get_settings
from ..models import (
    GetNotificationInput,
    NotificationView,
    RecipientInput,
    SubmitNotificationInput,
    SubmitResponse,
)


async def submit_notification(
    event_id: str,
    channel: str,
    recipient_user_id: int | None,
    recipient_email: str | None,
    recipient_phone_number: str | None,
    recipient_device_token: str | None,
    template_id: str | None,
    variables: dict[str, str] | None,
    subject: str | None,
    body: str | None,
) -> dict[str, Any]:
    """Submit a notification for delivery through the specified channel.

    Use recipient_user_id to identify a registered user (the system will look up
    their contact details). Alternatively supply the raw contact field for the
    channel: recipient_email for email, recipient_phone_number for sms,
    recipient_device_token for push_ios / push_android.

    Returns a dict with notification_id, status, and duplicate (bool).
    """
    settings = get_settings()

    inp = SubmitNotificationInput(
        event_id=event_id,
        channel=channel,  # type: ignore[arg-type]
        recipient=RecipientInput(
            user_id=recipient_user_id,
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
            k: v
            for k, v in {
                "user_id": inp.recipient.user_id,
                "email": inp.recipient.email,
                "phone_number": inp.recipient.phone_number,
                "device_token": inp.recipient.device_token,
            }.items()
            if v is not None
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

    result = await request(
        settings,
        "POST",
        "/v1/notifications",
        on_behalf_of_user_id=inp.recipient.user_id,
        json_body=payload,
    )
    return SubmitResponse(**result).model_dump()


async def get_notification(notification_id: str) -> dict[str, Any]:
    """Retrieve the current status and details of a notification by its UUID."""
    settings = get_settings()
    inp = GetNotificationInput(notification_id=UUID(notification_id))
    result = await request(settings, "GET", f"/v1/notifications/{inp.notification_id}")
    return NotificationView(**result).model_dump()
