"""NotificationEngine MCP server — FastMCP instance with all tools registered."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from .client import close_client, init_client
from .config import get_settings
from .tools.notifications import get_notification, submit_notification
from .tools.templates import create_template, get_template
from .tools.users import register_device, update_user_setting

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(server: FastMCP):  # type: ignore[type-arg]
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.mcp_log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info(
        "Starting NotificationEngineMCPServer — base_url=%s transport=%s host=%s port=%d",
        settings.notification_engine_base_url,
        settings.mcp_transport,
        settings.mcp_host,
        settings.mcp_port,
    )
    init_client(settings)
    try:
        yield
    finally:
        await close_client()
        logger.info("NotificationEngineMCPServer shut down.")


mcp = FastMCP("NotificationEngineMCPServer", lifespan=_lifespan)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool
async def submit_notification_tool(
    event_id: str,
    channel: str,
    recipient_user_id: int | None = None,
    recipient_email: str | None = None,
    recipient_phone_number: str | None = None,
    recipient_device_token: str | None = None,
    template_id: str | None = None,
    variables: dict[str, str] | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    """Submit a notification for delivery.

    event_id: caller-supplied idempotency key (1–256 chars). Duplicate submissions with the same event_id are deduplicated.
    channel: one of email, sms, push_ios, push_android.
    recipient_user_id: registered user ID — the system looks up their contact details automatically.
    recipient_email: required for channel=email when recipient_user_id is not provided.
    recipient_phone_number: required for channel=sms when recipient_user_id is not provided (E.164 format).
    recipient_device_token: required for push channels when recipient_user_id is not provided.
    template_id: UUID of a pre-created template to render the notification body.
    variables: key/value pairs for template variable substitution ({{variable_name}}).
    subject: overrides the template subject when template_id is provided.
    body: direct message body (use instead of template_id, or to override template body).
    """
    return await submit_notification(
        event_id=event_id,
        channel=channel,
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        recipient_phone_number=recipient_phone_number,
        recipient_device_token=recipient_device_token,
        template_id=template_id,
        variables=variables,
        subject=subject,
        body=body,
    )


@mcp.tool
async def get_notification_tool(notification_id: str) -> dict[str, Any]:
    """Get the current status and details of a notification by its UUID.

    notification_id: UUID returned when the notification was submitted.
    Returns id, event_id, channel, status, attempt count, subject, body, last_error, and recipient info.
    """
    return await get_notification(notification_id=notification_id)


@mcp.tool
async def create_template_tool(
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

    user_id: the user who owns this template (must be > 0). Enforced server-side.
    name: human-readable template name.
    channel: one of email, sms, push_ios, push_android.
    body: message body — supports {{variable_name}} interpolation.
    locale: BCP-47 locale tag (default: en).
    subject: email subject line (required for email channel).
    media_urls: optional list of media attachment URLs (MMS / rich push).
    version: template version number (default: 1).
    """
    return await create_template(
        user_id=user_id,
        name=name,
        channel=channel,
        body=body,
        locale=locale,
        subject=subject,
        media_urls=media_urls,
        version=version,
    )


@mcp.tool
async def get_template_tool(template_id: str) -> dict[str, Any]:
    """Retrieve a notification template by its UUID.

    Results are cached in-process for TEMPLATE_CACHE_TTL_S seconds (default 300).
    template_id: UUID of the template.
    """
    return await get_template(template_id=template_id)


@mcp.tool
async def register_device_tool(
    user_id: int,
    device_token: str,
    channel: str,
) -> dict[str, Any]:
    """Register or refresh a push notification device token for a user.

    user_id: the user who owns this device (must be > 0). The server enforces
    that only the authenticated owner can register their own devices.
    device_token: APNs or FCM device token provided by the mobile OS.
    channel: push_ios (APNs) or push_android (FCM).
    """
    return await register_device(
        user_id=user_id,
        device_token=device_token,
        channel=channel,
    )


@mcp.tool
async def update_user_setting_tool(
    user_id: int,
    channel: str,
    opt_in: bool,
) -> dict[str, Any]:
    """Update a user's notification opt-in/opt-out preference for a channel.

    user_id: the user whose setting is being updated (must be > 0). The server
    enforces that only the authenticated owner can change their own settings.
    channel: one of email, sms, push_ios, push_android.
    opt_in: true to enable notifications on this channel, false to opt out.
    """
    return await update_user_setting(
        user_id=user_id,
        channel=channel,
        opt_in=opt_in,
    )
