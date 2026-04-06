"""
SmartHomeControlTool — Send control commands to smart home devices.

Makes HTTP POST requests to the smart home hub API to control actuators
such as lights and the thermostat.

API format (from demonstration knowledge):
    POST {SMART_HOME_API_BASE}/api/devices/{device_id}/control
    Body: {"action": "<action>", ...extra_params}

The base URL is configured via the SMART_HOME_API_BASE environment variable
(defaults to http://localhost:8123).

Supported device IDs and their actions come from the IoT device registry:
  - light_living_01 (Living Room Light)
      actions: turn_on, turn_off, set
      params:  brightness (0-100), color_temperature (2700-6500)

  - light_bedroom_01 (Bedroom Light)
      actions: turn_on, turn_off, set
      params:  brightness (0-100)

  - thermostat_01 (Bedroom Thermostat)
      actions: set_temperature, set_mode
      params:  setpoint (16-30), mode (heat/cool/auto/off)
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from smolagents import Tool

from app.agent_system.tools.device_resolver import resolve_device
from app.agent_system.tools.device_registry import lookup


class SmartHomeControlTool(Tool):
    name = "smart_home_control"
    description = (
        "Sends a control command to a smart home device via the hub API. "
        "Use this when the user wants to control a device — turn lights on/off, "
        "adjust brightness or colour temperature, or set the thermostat temperature or mode. "
        "You can pass an exact device_id (e.g. 'light_living_01') OR a natural-language "
        "description (e.g. 'bedroom light', 'the thermostat'). The tool will resolve it "
        "automatically."
    )
    inputs = {
        "device_id": {
            "type": "string",
            "description": (
                "The device to control. Can be an exact device ID like 'light_living_01' "
                "OR a natural-language reference like 'bedroom light', 'the thermostat'."
            ),
        },
        "action": {
            "type": "string",
            "description": (
                "The action to perform on the device. Examples: "
                "'turn_on', 'turn_off', 'set', 'set_temperature', 'set_mode'."
            ),
        },
        "parameters": {
            "type": "object",
            "description": (
                "Optional dictionary of extra parameters for the action. Examples: "
                '{"brightness": 80} for lights, '
                '{"brightness": 80, "color_temperature": 3000} for living room light, '
                '{"setpoint": 22, "mode": "heat"} for the thermostat. '
                "Pass null or omit if the action needs no extra parameters."
            ),
            "nullable": True,
        },
    }
    output_type = "string"

    def forward(
        self,
        device_id: str,
        action: str,
        parameters: Optional[dict[str, Any]] = None,
    ) -> str:
        # Resolve natural-language device references
        if not lookup(device_id):
            result = resolve_device(device_id)
            if not result.found:
                return f"Error: could not find a device matching '{device_id}'."
            if result.ambiguous:
                options = ", ".join(f"{m.name} ({m.device_id})" for m in result.matches)
                return (
                    f"Ambiguous device reference '{device_id}'. "
                    f"Multiple devices match: {options}. "
                    f"Please specify which one."
                )
            device_id = result.device_id

        base_url = os.getenv("SMART_HOME_API_BASE", "http://localhost:8123").rstrip("/")
        url = f"{base_url}/api/devices/{device_id}/control"

        payload: dict[str, Any] = {"action": action}

        if parameters:
            if not isinstance(parameters, dict):
                return f"Error: parameters must be a dictionary, got: {parameters!r}"
            payload.update(parameters)

        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            try:
                data = response.json()
                if "task_outcome_short" in data:
                    return data["task_outcome_short"]
            except Exception:
                pass
            return response.text
        except httpx.HTTPStatusError as exc:
            return (
                f"Device API error for '{device_id}': "
                f"HTTP {exc.response.status_code} — {exc.response.text}"
            )
        except httpx.RequestError as exc:
            return (
                f"Could not reach the smart home hub at {base_url}. "
                f"Check that SMART_HOME_API_BASE is set correctly. Details: {exc}"
            )


smart_home_control_tool = SmartHomeControlTool()

__all__ = ["SmartHomeControlTool", "smart_home_control_tool"]
