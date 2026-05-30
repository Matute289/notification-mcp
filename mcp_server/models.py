"""Pydantic v2 models for tool inputs and API responses."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)

Channel = Literal[
    "email", "sms", "push_ios", "push_android",
    "telegram", "whatsapp", "line", "facebook_messenger",
]
PushChannel = Literal["push_ios", "push_android"]
NotificationStatus = Literal[
    "received", "enqueued", "in_flight", "sent", "retrying", "dead_letter", "failed"
]


# ---------------------------------------------------------------------------
# Tool inputs — user_id removed from user-scoped tools (comes from contextvar)
# ---------------------------------------------------------------------------

class RecipientInput(BaseModel):
    model_config = _STRICT
    email: str | None = Field(None, max_length=320)
    phone_number: str | None = Field(None, max_length=20)
    device_token: str | None = Field(None, max_length=512)
    messaging_id: str | None = Field(None, max_length=512)


class SubmitNotificationInput(BaseModel):
    model_config = _STRICT
    event_id: Annotated[str, Field(min_length=1, max_length=256)]
    channel: Channel
    recipient: RecipientInput
    template_id: UUID | None = None
    variables: Annotated[dict[str, str], Field(max_length=50)] | None = None
    subject: str | None = Field(None, max_length=998)
    body: str | None = Field(None, max_length=160_000)


class GetNotificationInput(BaseModel):
    model_config = _STRICT
    notification_id: UUID


class CreateTemplateInput(BaseModel):
    model_config = _STRICT
    name: Annotated[str, Field(min_length=1, max_length=128)]
    channel: Channel
    locale: Annotated[str, Field(min_length=2, max_length=10)] = "en"
    subject: str | None = Field(None, max_length=998)
    body: Annotated[str, Field(min_length=1, max_length=160_000)]
    media_urls: Annotated[list[str], Field(max_length=10)] | None = None
    version: Annotated[int, Field(ge=1, le=9999)] = 1


class UpdateTemplateInput(BaseModel):
    """Input for PUT /v1/templates/{id}. Channel, locale and version are
    immutable after creation — only name, subject, body and media_urls can change."""
    model_config = _STRICT
    template_id: UUID
    name: Annotated[str, Field(min_length=1, max_length=128)]
    subject: str | None = Field(None, max_length=998)
    body: Annotated[str, Field(min_length=1, max_length=160_000)]
    media_urls: Annotated[list[str], Field(max_length=10)] | None = None


class GetTemplateInput(BaseModel):
    model_config = _STRICT
    template_id: UUID


class RegisterDeviceInput(BaseModel):
    model_config = _STRICT
    device_token: Annotated[str, Field(min_length=1, max_length=512)]
    channel: PushChannel


class UpdateUserSettingInput(BaseModel):
    model_config = _STRICT
    channel: Channel
    opt_in: bool


# ---------------------------------------------------------------------------
# API response shapes
# ---------------------------------------------------------------------------

class RecipientView(BaseModel):
    user_id: int | None = None
    email: str | None = None
    phone_number: str | None = None
    device_token: str | None = None
    messaging_id: str | None = None


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
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SubmitResponse(BaseModel):
    notification_id: UUID
    status: NotificationStatus
    duplicate: bool = False  # some server versions omit this field on non-duplicates


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
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SettingView(BaseModel):
    channel: str
    opt_in: bool
    updated_at: datetime | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationView]
    next_cursor: str
    limit: int
