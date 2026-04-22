"""smolagents Tool wrappers around the CoreIoT helpers in ``thingsboard_api``.

These wrappers let an agent call ``read_shared_attributes`` and
``post_shared_attributes`` as named tools (e.g. from a ToolCallingAgent's JSON
tool call). The CodeAgent can also import the underlying functions directly
from ``app.agent_system.tools.thingsboard_api`` and use them inside generated
Python code without going through the tool wrapper — both paths are
supported on purpose.

Tool input format
-----------------
Both tools take a single ``devices`` parameter that is a JSON string encoding
a list of device dicts. The JSON-string indirection is required because
smolagents tool inputs are scalar (string / integer / boolean / object) and
``object`` is rendered as a single dict, not a list. Encoding the list as a
JSON string keeps the schema simple and lets the agent build the payload in
its own working memory.

Example payload (passed as a JSON string)::

    [
        {
            "name_device": "Đèn trần",
            "token":       "xdF2nW4aR9SAdqqPiym0",
            "room":        "living_room",
            "shared_attributes": {"led": true}
        }
    ]

The wrappers always return a JSON-encoded string of the result list so the
agent can json.loads it back into a Python list when needed.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from smolagents import Tool

from app.agent_system.tools.thingsboard_api import (
    post_shared_attributes,
    read_shared_attributes,
)
from app.agent_system.memory.buffer_window import ActionRecord, get_current_buffer

logger = logging.getLogger(__name__)


def _parse_devices(devices_json: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Accept either a JSON string or an already-parsed list of device dicts."""
    if isinstance(devices_json, list):
        return devices_json
    if not isinstance(devices_json, str):
        raise ValueError(
            f"`devices` must be a JSON string or list, got {type(devices_json).__name__}"
        )
    try:
        parsed = json.loads(devices_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"`devices` is not valid JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValueError(
            f"`devices` must decode to a list, got {type(parsed).__name__}"
        )
    return parsed


# ---------------------------------------------------------------------------
# Read tool
# ---------------------------------------------------------------------------


class ReadSharedAttributeTool(Tool):
    name = "read_shared_attributes"
    description = (
        "Read the current CLIENT attributes for one or more CoreIoT devices "
        "via GET /api/v1/{deviceToken}/attributes?clientKeys=... "
        "Use this for STATUS queries (is the LED on? current brightness? fan speed?). "
        "The firmware publishes state as client attributes via sendAttributeData. "
        "The `devices` argument is a JSON string encoding a list of device dicts. "
        'Each dict must have at least {"token": "<deviceToken>"} and may include '
        '"name_device", "room", and "shared_attributes" (dict whose KEYS are the '
        'client attribute names to read, e.g. {"led": null}). '
        "Returns a JSON string with one entry per device containing the "
        "`shared` dict (current state), the HTTP `status`, and any `error`."
    )
    inputs = {
        "devices": {
            "type": "string",
            "description": (
                "JSON-encoded list of device dicts to read. Each entry needs a "
                '"token" plus an optional "shared_attributes" dict whose keys are '
                "the attributes to read."
            ),
        },
    }
    output_type = "string"

    def forward(self, devices: str) -> str:
        try:
            device_list = _parse_devices(devices)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
        results = read_shared_attributes(device_list)

        # Append successful reads to the per-session BufferWindowMemory.
        buffer = get_current_buffer()
        if buffer is not None:
            for device, result in zip(device_list, results):
                if not result.get("error"):
                    buffer.append(
                        ActionRecord(
                            device_name=device.get("name_device") or "",
                            room=device.get("room") or "",
                            token=device.get("token") or "",
                            action="read",
                            type_device=device.get("type_device") or "",
                            shared_attributes=result.get("shared", {}),
                        )
                    )

        return json.dumps(results, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Post tool
# ---------------------------------------------------------------------------


class PostSharedAttributeTool(Tool):
    name = "post_shared_attributes"
    description = (
        "Write shared attributes to CoreIoT to control devices. "
        "Use this for CONTROL COMMANDS (turn light on/off, set fan speed, etc.). "
        "Flow: GET current client attributes → diff → POST /api/v1/{token}/attributes if changed. "
        "CoreIoT pushes the new value to the device via MQTT. "
        "Calling twice with the same value is a no-op (diff check). "
        "The `devices` argument is a JSON string encoding a list of device dicts. "
        'Each dict must have {"token": "<deviceToken>", "shared_attributes": {"led": true/false}} '
        'and may include "name_device" and "room" for logging. '
        "Returns a JSON string with one entry per device containing `before`, `after`, "
        "`posted`, the HTTP `status`, and any `error`."
    )
    inputs = {
        "devices": {
            "type": "string",
            "description": (
                "JSON-encoded list of device dicts to update. Each entry needs a "
                '"token" and a "shared_attributes" dict mapping attribute names to '
                'their desired values, e.g. {"led": true, "brightness": 80}.'
            ),
        },
    }
    output_type = "string"

    def forward(self, devices: str) -> str:
        try:
            device_list = _parse_devices(devices)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
        results = post_shared_attributes(device_list)

        # Append successful POSTs to the per-session BufferWindowMemory.
        buffer = get_current_buffer()
        if buffer is not None:
            for device, result in zip(device_list, results):
                if not result.get("error"):
                    buffer.append(
                        ActionRecord(
                            device_name=device.get("name_device") or "",
                            room=device.get("room") or "",
                            token=device.get("token") or "",
                            action="post",
                            type_device=device.get("type_device") or "",
                            shared_attributes=device.get("shared_attributes") or {},
                        )
                    )

        return json.dumps(results, ensure_ascii=False, default=str)


read_shared_attributes_tool = ReadSharedAttributeTool()
post_shared_attributes_tool = PostSharedAttributeTool()


__all__ = [
    "ReadSharedAttributeTool",
    "PostSharedAttributeTool",
    "read_shared_attributes_tool",
    "post_shared_attributes_tool",
]
