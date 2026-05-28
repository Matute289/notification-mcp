from __future__ import annotations

from typing import Any

from ..client import request
from ..config import get_settings
from ..models import RegisterDeviceInput, UpdateUserSettingInput


async def register_device(
    user_id: int,
    device_token: str,
    channel: str,
) -> dict[str, Any]:
    """Register or refresh a push notification device token for a user.

    channel must be push_ios or push_android. The server enforces that the
    caller can only register devices for the user identified in user_id
    (via X-On-Behalf-Of-User). Returns an empty dict on success (204).
    """
    settings = get_settings()
    inp = RegisterDeviceInput(
        user_id=user_id,
        device_token=device_token,
        channel=channel,  # type: ignore[arg-type]
    )

    await request(
        settings,
        "POST",
        f"/v1/users/{inp.user_id}/devices",
        on_behalf_of_user_id=inp.user_id,
        json_body={
            "device_token": inp.device_token,
            "channel": inp.channel,
        },
    )
    return {"success": True}


async def update_user_setting(
    user_id: int,
    channel: str,
    opt_in: bool,
) -> dict[str, Any]:
    """Update a user's notification opt-in preference for a channel.

    The server enforces that the caller can only modify settings for the user
    identified in user_id (via X-On-Behalf-Of-User). Returns an empty dict on
    success (204).
    """
    settings = get_settings()
    inp = UpdateUserSettingInput(
        user_id=user_id,
        channel=channel,  # type: ignore[arg-type]
        opt_in=opt_in,
    )

    await request(
        settings,
        "PUT",
        f"/v1/users/{inp.user_id}/settings",
        on_behalf_of_user_id=inp.user_id,
        json_body={
            "channel": inp.channel,
            "opt_in": inp.opt_in,
        },
    )
    return {"success": True}
