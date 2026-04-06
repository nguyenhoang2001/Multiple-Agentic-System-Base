"""
SensorLogsTool — Live sensor data via the smart home hub API.

Makes HTTP GET requests to the hub to fetch current/recent sensor readings
instead of reading from local CSV files.

API endpoints used:
    GET {SMART_HOME_API_BASE}/api/devices/{device_id}/sensors
        Returns the latest readings for a specific device.

    GET {SMART_HOME_API_BASE}/api/sensors
        Returns readings for all devices, with optional ?sensor_type= filter.

The base URL is configured via the SMART_HOME_API_BASE environment variable
(defaults to http://localhost:8123).
"""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx
from smolagents import Tool

from app.agent_system.tools.device_resolver import resolve_device
from app.agent_system.tools.device_registry import lookup


class SensorLogsTool(Tool):
    name = "sensor_logs_reader"
    description = """
            Retrieves and queries sensor logs from smart home devices.
            Use this tool when you need to:
            - Check the current state of a sensor (temperature, humidity, light brightness)
            - Detect anomalies or unusual patterns in sensor data
            - Verify if a device action was successfully executed by checking state changes
            - Answer user questions about their home environment

            You can pass an exact device_id (e.g. 'thermostat_01') OR a natural-language
            description (e.g. 'bedroom thermostat', 'living room light').
            The tool will resolve it automatically.

            Returns structured sensor data including device_id, timestamp, reading_type, and value.
        """
    inputs = {
        "device_id": {
            "type": "string",
            "description": (
                "The device to query. Can be an exact device ID like 'thermostat_01' "
                "OR a natural-language reference like 'bedroom thermostat', "
                "'living room light', 'bedroom light'. "
                "Leave empty to retrieve readings for all devices."
            ),
            "nullable": True,
        },
        "sensor_type": {
            "type": "string",
            "description": (
                "Filter readings by sensor type (e.g. 'temperature', 'humidity', "
                "'brightness', 'temperature_setpoint'). Leave empty for all sensor types."
            ),
            "nullable": True,
        },
    }
    output_type = "string"

    def forward(
        self,
        device_id: Optional[str] = None,
        sensor_type: Optional[str] = None,
    ) -> str:
        base_url = os.getenv("SMART_HOME_API_BASE", "http://localhost:8123").rstrip("/")

        # Resolve natural-language device references
        if device_id and not lookup(device_id):
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

        try:
            if device_id:
                url = f"{base_url}/api/devices/{device_id}/sensors"
                params = {}
                if sensor_type:
                    params["sensor_type"] = sensor_type
            else:
                url = f"{base_url}/api/sensors"
                params = {}
                if sensor_type:
                    params["sensor_type"] = sensor_type

            response = httpx.get(url, params=params, timeout=10.0)
            response.raise_for_status()

            data = response.json()
            if not data:
                return "No sensor readings found for the given filters."

            # If the response has task_outcome_short, return it directly
            if isinstance(data, dict) and "task_outcome_short" in data:
                return data["task_outcome_short"]

            # Format the response as readable text
            lines = []
            readings = data if isinstance(data, list) else [data]
            for reading in readings:
                parts = []
                for key in (
                    "device_id",
                    "sensor_type",
                    "value",
                    "unit",
                    "timestamp",
                    "status",
                ):
                    if key in reading:
                        parts.append(f"{key}: {reading[key]}")
                lines.append(" | ".join(parts))
            return "\n".join(lines)

        except httpx.HTTPStatusError as exc:
            return (
                f"Sensor API error for device '{device_id or 'all'}': "
                f"HTTP {exc.response.status_code} — {exc.response.text}"
            )
        except httpx.RequestError as exc:
            return (
                f"Could not reach the smart home hub at {base_url}. "
                f"Check that SMART_HOME_API_BASE is set correctly. Details: {exc}"
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return f"Unexpected response format from hub: {exc}"


sensor_logs_tool = SensorLogsTool()
