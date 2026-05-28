"""FastMCP instance with all 6 tools registered."""
from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

from .tools.notifications import get_notification, submit_notification
from .tools.templates import create_template, get_template
from .tools.users import register_device, update_user_setting

mcp = FastMCP("NotificationEngineMCPServer")


@mcp.tool
async def submit_notification_tool(
    event_id: str,
    channel: str,
    ctx: Context,
    recipient_email: str | None = None,
    recipient_phone_number: str | None = None,
    recipient_device_token: str | None = None,
    template_id: str | None = None,
    variables: dict[str, str] | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    """Submit a notification for delivery on behalf of the authenticated user.

    The notification is sent to the authenticated user's own account unless
    a specific recipient contact is provided.

    event_id: idempotency key (1–256 chars). Duplicate event_ids are deduplicated.
    channel: email | sms | push_ios | push_android.
    recipient_email: direct email address (channel=email, overrides user's registered email).
    recipient_phone_number: E.164 phone number (channel=sms, overrides user's registered phone).
    recipient_device_token: push token (channel=push_ios/android, overrides registered device).
    template_id: UUID of a pre-created template.
    variables: key/value pairs for {{variable_name}} template substitution.
    subject: message subject (overrides template subject).
    body: message body (use instead of template_id, or to override template body).
    """
    await ctx.report_progress(0, 3, "Validating request")
    await ctx.info(f"Submitting {channel} notification (event_id={event_id})")
    result = await submit_notification(
        event_id=event_id, channel=channel,
        recipient_email=recipient_email,
        recipient_phone_number=recipient_phone_number,
        recipient_device_token=recipient_device_token,
        template_id=template_id, variables=variables,
        subject=subject, body=body,
    )
    await ctx.report_progress(3, 3, "Done")
    status = result.get("status", "unknown")
    duplicate = result.get("duplicate", False)
    await ctx.info(f"Notification accepted — status={status}" + (" (duplicate)" if duplicate else ""))
    return result


@mcp.tool
async def get_notification_tool(notification_id: str, ctx: Context) -> dict[str, Any]:
    """Get the current status and details of a notification by its UUID.

    notification_id: UUID returned when the notification was submitted.
    """
    await ctx.report_progress(0, 2, "Fetching notification")
    result = await get_notification(notification_id=notification_id)
    await ctx.report_progress(2, 2, "Done")
    await ctx.info(f"Notification status: {result.get('status', 'unknown')}")
    return result


@mcp.tool
async def create_template_tool(
    name: str,
    channel: str,
    body: str,
    ctx: Context,
    locale: str = "en",
    subject: str | None = None,
    media_urls: list[str] | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create a reusable notification template owned by the authenticated user.

    name: human-readable template name (max 128 chars).
    channel: email | sms | push_ios | push_android.
    body: message body — supports {{variable_name}} interpolation (max 160 000 chars).
    locale: BCP-47 locale tag (default: en).
    subject: email subject line.
    media_urls: media attachment URLs (MMS / rich push), max 10.
    version: template version number (default: 1).
    """
    await ctx.report_progress(0, 3, "Validating template")
    await ctx.info(f"Creating template '{name}' for channel={channel}")
    result = await create_template(
        name=name, channel=channel, body=body, locale=locale,
        subject=subject, media_urls=media_urls, version=version,
    )
    await ctx.report_progress(3, 3, "Done")
    await ctx.info(f"Template created — id={result.get('id')}")
    return result


@mcp.tool
async def get_template_tool(template_id: str, ctx: Context) -> dict[str, Any]:
    """Retrieve a notification template by its UUID. Results are cached in-process.

    template_id: UUID of the template.
    """
    await ctx.report_progress(0, 2, "Looking up template")
    result = await get_template(template_id=template_id)
    await ctx.report_progress(2, 2, "Done")
    await ctx.info(f"Template '{result.get('name')}' (channel={result.get('channel')})")
    return result


@mcp.tool
async def register_device_tool(device_token: str, channel: str, ctx: Context) -> dict[str, Any]:
    """Register or refresh a push notification device token for the authenticated user.

    device_token: APNs or FCM device token provided by the mobile OS (max 512 chars).
    channel: push_ios (APNs) | push_android (FCM).
    """
    await ctx.report_progress(0, 2, "Registering device")
    await ctx.info(f"Registering device for channel={channel}")
    result = await register_device(device_token=device_token, channel=channel)
    await ctx.report_progress(2, 2, "Done")
    return result


@mcp.tool
async def update_user_setting_tool(channel: str, opt_in: bool, ctx: Context) -> dict[str, Any]:
    """Update the authenticated user's notification opt-in/opt-out preference.

    channel: email | sms | push_ios | push_android.
    opt_in: true to enable notifications on this channel, false to opt out.
    """
    await ctx.report_progress(0, 2, "Updating preference")
    action = "opted in to" if opt_in else "opted out of"
    await ctx.info(f"User {action} {channel} notifications")
    result = await update_user_setting(channel=channel, opt_in=opt_in)
    await ctx.report_progress(2, 2, "Done")
    return result
