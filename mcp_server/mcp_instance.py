"""FastMCP instance with all 6 tools registered."""
from __future__ import annotations

from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP, Context

from .tools.notifications import get_notification, submit_notification
from .tools.templates import create_template, get_template, list_templates, update_template
from .tools.users import register_device, update_user_setting
from .prompts.create_template import build_create_template_message
from .prompts.update_template import build_update_template_message
from .prompts.manage_preferences import build_manage_preferences_message
from .prompts.onboarding import build_onboarding_message

log = structlog.get_logger(__name__)

mcp = FastMCP("NotificationEngineMCPServer")


@mcp.tool()
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
    """Send a notification to a recipient via email, SMS, or push notification.

    Always gather all required information before calling this tool.
    For email: suggest a subject based on the message body and wait for the user
    to confirm it before proceeding. If the recipient's contact details are missing
    (email address, phone number, or device token), ask the user for them first.

    event_id: a unique identifier for this send (letters, numbers, or dashes, 1–256 chars).
        Re-submitting the same event_id is safe — duplicates are automatically ignored.
        Example: "welcome-user-42" or "order-1234-confirmation".
    channel: the delivery method — email | sms | push_ios | push_android.
    recipient_email: (email only) destination address. Example: "user@example.com".
    recipient_phone_number: (sms only) international format. Example: "+5491112345678".
    recipient_device_token: (push_ios / push_android only) the device push token.
    template_id: UUID of a pre-saved template. Use instead of body to send a
        designed message. Example: "550e8400-e29b-41d4-a716-446655440000".
    variables: values to fill {{placeholder}} fields in the template.
        Example: {"name": "Ana", "amount": "1500"}.
    subject: email subject line. Example: "Your order has been confirmed".
    body: message text. Use this instead of a template, or to override the template body.
        Example: "Hello {{name}}, how are you?".
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


@mcp.tool()
async def get_notification_tool(notification_id: str, ctx: Context) -> dict[str, Any]:
    """Retrieve the current status and full details of a previously sent notification.

    Use this to check whether a notification was delivered, is still in transit,
    or failed. The status field shows the current state of the delivery.

    notification_id: the UUID returned by submit_notification_tool when the notification
        was created. Example: "550e8400-e29b-41d4-a716-446655440000".
    """
    await ctx.report_progress(0, 2, "Fetching notification")
    result = await get_notification(notification_id=notification_id)
    await ctx.report_progress(2, 2, "Done")
    await ctx.info(f"Notification status: {result.get('status', 'unknown')}")
    return result


@mcp.tool()
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
    """Create a reusable notification template that can be sent to any user later.

    Templates save time when you send the same type of message often. Use
    {{variable_name}} placeholders in the body (and subject) to insert
    personalized data at send time.

    name: a human-readable label for this template (max 128 chars).
        Example: "Welcome Email".
    channel: the delivery channel for this template — email | sms | push_ios | push_android.
    body: the message content (max 160 000 chars). Use {{name}} syntax for dynamic values.
        Example: "Hi {{name}}, your order {{order_id}} has been confirmed!".
    locale: the BCP-47 language code of the template text (default: en).
        Examples: "es" for Spanish, "pt" for Portuguese, "fr" for French.
    subject: the email subject line (only used when channel=email).
        Example: "Order Confirmed".
    media_urls: list of image or video URLs to attach (MMS or rich push), max 10 URLs.
    version: template revision number (default: 1). Increment when updating a template.
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


@mcp.tool()
async def get_template_tool(template_id: str, ctx: Context) -> dict[str, Any]:
    """Retrieve a saved notification template by its UUID. Results are cached.

    Use list_templates_tool first if you need to find the template's ID by name.

    template_id: UUID of the template to retrieve.
        Example: "550e8400-e29b-41d4-a716-446655440000".
    """
    await ctx.report_progress(0, 2, "Looking up template")
    result = await get_template(template_id=template_id)
    await ctx.report_progress(2, 2, "Done")
    await ctx.info(f"Template '{result.get('name')}' (channel={result.get('channel')})")
    return result


@mcp.tool()
async def register_device_tool(device_token: str, channel: str, ctx: Context) -> dict[str, Any]:
    """Register or refresh a mobile device to receive push notifications.

    Call this when a user first installs the app, or when the mobile OS issues a
    new push token. The device token is generated automatically by the phone —
    the mobile app provides it; the user does not type it manually.

    device_token: the APNs (iOS) or FCM (Android) token from the mobile OS (max 512 chars).
    channel: the push platform — push_ios (iPhone/iPad) | push_android (Android).
    """
    await ctx.report_progress(0, 2, "Registering device")
    await ctx.info(f"Registering device for channel={channel}")
    result = await register_device(device_token=device_token, channel=channel)
    await ctx.report_progress(2, 2, "Done")
    return result


@mcp.tool()
async def update_user_setting_tool(channel: str, opt_in: bool, ctx: Context) -> dict[str, Any]:
    """Turn a notification channel on or off for the current user.

    Use this when the user wants to start or stop receiving notifications
    on a specific channel.

    channel: the channel to update — email | sms | push_ios | push_android.
    opt_in: true to enable notifications on this channel, false to disable them.
    """
    await ctx.report_progress(0, 2, "Updating preference")
    action = "opted in to" if opt_in else "opted out of"
    await ctx.info(f"User {action} {channel} notifications")
    result = await update_user_setting(channel=channel, opt_in=opt_in)
    await ctx.report_progress(2, 2, "Done")
    return result


@mcp.tool()
async def list_templates_tool(ctx: Context) -> dict[str, Any]:
    """Show all notification templates you have saved, grouped by channel.

    Returns a dictionary where each key is a channel name (email, sms, push_ios,
    push_android) and each value is a list of your templates for that channel.
    Use this to browse your templates before editing or reusing them.

    Each template entry includes: id, name, channel, locale, body, and version.
    The id is the UUID you need to pass to get_template_tool or update_template_tool.
    """
    await ctx.report_progress(0, 2, "Fetching your templates")
    result = await list_templates()
    await ctx.report_progress(2, 2, "Done")
    total = sum(len(v) for v in result.values() if isinstance(v, list))
    await ctx.info(f"Found {total} template(s)")
    return result


@mcp.tool()
async def update_template_tool(
    template_id: str,
    name: str,
    channel: str,
    body: str,
    ctx: Context,
    locale: str = "en",
    subject: str | None = None,
    media_urls: list[str] | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Replace an existing notification template with new content (full update).

    This replaces every field of the template — supply all fields, not just the ones
    you want to change. To keep an existing field unchanged, copy its current value
    from get_template_tool and include it here.

    template_id: UUID of the template to update. Get this from list_templates_tool.
        Example: "550e8400-e29b-41d4-a716-446655440000".
    name: new human-readable label for this template (max 128 chars).
        Example: "Welcome Email v2".
    channel: the delivery channel — email | sms | push_ios | push_android.
        Must match the original template's channel.
    body: new message text (max 160 000 chars). Use {{variable_name}} for dynamic values.
        Example: "Hola {{nombre}}, tu pedido {{numero}} fue confirmado.".
    locale: BCP-47 language code of the template text (default: en).
        Examples: "es" for Spanish, "pt" for Portuguese, "fr" for French.
    subject: new email subject line (only for channel=email).
        Example: "Tu pedido fue confirmado".
    media_urls: new media attachment URLs for MMS or rich push (max 10 URLs).
    version: increment this number to signal a new revision. Example: if current is 1, pass 2.
    """
    await ctx.report_progress(0, 3, "Validating update")
    await ctx.info(f"Updating template {template_id}")
    result = await update_template(
        template_id=template_id, name=name, channel=channel, body=body,
        locale=locale, subject=subject, media_urls=media_urls, version=version,
    )
    await ctx.report_progress(3, 3, "Done")
    await ctx.info(f"Template updated — name='{result.get('name')}', version={result.get('version')}")
    return result


@mcp.prompt(
    name="create_template",
    description="Asistente guiado para crear templates de notificación en uno o varios canales.",
)
def create_template_prompt(
    channel: str | None = None,
    purpose: str | None = None,
) -> str:
    return build_create_template_message(channel=channel, purpose=purpose)


@mcp.prompt(
    name="update_template",
    description="Asistente guiado para modificar un template de notificación existente.",
)
def update_template_prompt(channel: str | None = None) -> str:
    return build_update_template_message(channel=channel)


@mcp.prompt(
    name="manage_preferences",
    description="Asistente para activar/desactivar canales y registrar dispositivos push.",
)
def manage_preferences_prompt() -> str:
    return build_manage_preferences_message()


@mcp.prompt(
    name="onboarding",
    description="Configuración inicial: registrá tu dispositivo y establecé tus preferencias de notificación.",
)
def onboarding_prompt() -> str:
    return build_onboarding_message()
