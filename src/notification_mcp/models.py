"""Pydantic v2 models for tool inputs and API responses."""
from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

Channel = Literal["email", "sms", "push_ios", "push_android"]
PushChannel = Literal["push_ios", "push_android"]

NotificationStatus = Literal[
    "received", "enqueued", "in_flight", "sent", "retrying", "dead_letter", "failed"
]


# ---------------------------------------------------------------------------
# Tool inputs
# ---------------------------------------------------------------------------

class RecipientInput(BaseModel):
    model_config = _STRICT

    user_id: int | None = None
    email: str | None = None
    phone_number: str | None = None
    device_token: str | None = None


class SubmitNotificationInput(BaseModel):
    model_config = _STRICT

    event_id: Annotated[str, Field(min_length=1, max_length=256)]
    channel: Channel
    recipient: RecipientInput
    template_id: UUID | None = None
    variables: dict[str, str] | None = None
    subject: str | None = None
    body: str | None = None


class GetNotificationInput(BaseModel):
    model_config = _STRICT

    notification_id: UUID


class CreateTemplateInput(BaseModel):
    model_config = _STRICT

    user_id: Annotated[int, Field(gt=0)]
    name: Annotated[str, Field(min_length=1)]
    channel: Channel
    locale: str = "en"
    subject: str | None = None
    body: Annotated[str, Field(min_length=1)]
    media_urls: list[str] | None = None
    version: int = 1


class GetTemplateInput(BaseModel):
    model_config = _STRICT

    template_id: UUID


class RegisterDeviceInput(BaseModel):
    model_config = _STRICT

    user_id: Annotated[int, Field(gt=0)]
    device_token: Annotated[str, Field(min_length=1)]
    channel: PushChannel


class UpdateUserSettingInput(BaseModel):
    model_config = _STRICT

    user_id: Annotated[int, Field(gt=0)]
    channel: Channel
    opt_in: bool


# ---------------------------------------------------------------------------
# API response shapes (for documentation / type-safety in tools)
# ---------------------------------------------------------------------------

class RecipientView(BaseModel):
    user_id: int | None = None
    email: str | None = None
    phone_number: str | None = None
    device_token: str | None = None


class NotificationView(BaseModel):
    id: UUID
    event_id: str
    channel: str
    status: NotificationStatus
    attempt: int
    subject: str | None = None
    body: str | None = None
    last_error: str | None = None
    recipient: RecipientView
    variables: dict[str, str] | None = None
    template_id: UUID | None = None


class SubmitResponse(BaseModel):
    notification_id: UUID
    status: NotificationStatus
    duplicate: bool


class TemplateView(BaseModel):
    id: UUID
    name: str
    channel: str
    locale: str
    subject: str | None = None
    body: str
    media_urls: list[str] | None = None
    version: int
    owner_user_id: int | None = None
