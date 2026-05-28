from __future__ import annotations

import time
from typing import Any

from ..config import get_settings
from ..context import get_current_user_id_or_raise
from ..models import RegisterDeviceInput, UpdateUserSettingInput
from ..services import service_api_client
from ._logging import log_tool_call


async def register_device(device_token: str, channel: str) -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "register_device"
    try:
        inp = RegisterDeviceInput(device_token=device_token, channel=channel)  # type: ignore[arg-type]
        await service_api_client.request(
            settings, "POST", f"/v1/users/{user_id}/devices",
            on_behalf_of_user_id=user_id,
            json_body={"device_token": inp.device_token, "channel": inp.channel},
        )
        log_tool_call(tool_name, user_id, start, success=True)
        return {"success": True}
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise


async def update_user_setting(channel: str, opt_in: bool) -> dict[str, Any]:
    settings = get_settings()
    user_id = get_current_user_id_or_raise()
    start = time.perf_counter()
    tool_name = "update_user_setting"
    try:
        inp = UpdateUserSettingInput(channel=channel, opt_in=opt_in)  # type: ignore[arg-type]
        await service_api_client.request(
            settings, "PUT", f"/v1/users/{user_id}/settings",
            on_behalf_of_user_id=user_id,
            json_body={"channel": inp.channel, "opt_in": inp.opt_in},
        )
        log_tool_call(tool_name, user_id, start, success=True)
        return {"success": True}
    except Exception as exc:
        log_tool_call(tool_name, user_id, start, success=False, error_type=type(exc).__name__)
        raise
