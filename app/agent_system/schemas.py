"""
Pydantic schemas for structured LLM output throughout the IoT pipeline.

These schemas force the LLM to output valid JSON instead of generating Python code,
which is far more reliable for small local models like gemma4:e2b.

Pipeline:
  UserIntent    → Master Agent  (intent extraction from user message)
  DeviceAction  → Retriever     (device selection from YAML subset)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserIntent(BaseModel):
    """
    Structured output from the Master Agent's intent extraction step.

    The LLM is asked to extract room_name and type_device from the user's
    natural-language message. Both fields are Optional — None signals that
    the information was not present in the message and further clarification
    is needed.
    """

    room_name: Any = Field(
        default=None,
        description=(
            "The room name in snake_case English, e.g. 'living_room', 'kitchen', "
            "'bedroom'. None if the user did not mention a room."
        ),
    )
    type_device: Any = Field(
        default=None,
        description=(
            "The device category, e.g. 'smart_light' or 'smart_fan'. "
            "None if the user did not mention a device type."
        ),
    )
    device_name: Any = Field(
        default=None,
        description=(
            "The specific device name mentioned by the user. "
            "None if the user did not mention a specific device name."
        ),
    )


class UserIntentList(BaseModel):
    """List of intents extracted from the user message to support multi-device/multi-room."""
    intents: List[UserIntent]


class SensorAction(BaseModel):
    """One sensor function within a device, containing multiple attributes."""
    sensor_name: str
    shared_attributes: Dict[str, Any]

    def __init__(self, **data):
        if "shared_attribute" in data and "shared_attributes" not in data:
            data["shared_attributes"] = data.pop("shared_attribute")
        
        shared_attrs = data.get("shared_attributes")
        if isinstance(shared_attrs, list):
            new_attrs = {}
            for item in shared_attrs:
                if isinstance(item, dict) and "name_key" in item and "value" in item:
                    new_attrs[item["name_key"]] = item["value"]
                elif isinstance(item, dict) and len(item) == 1:
                    new_attrs.update(item)
            data["shared_attributes"] = new_attrs

        super().__init__(**data)

class DeviceAction(BaseModel):
    """
    One device to act on, as selected by the Retriever step.

    Matches the output contract expected by iot_action_agent:
        name_device   — human-readable device name from YAML
        token         — CoreIoT device token (NEVER invented — copied from YAML)
        room          — room name from YAML
        sensors       — List of sensors and their requested shared_attributes
    """

    name_device: str
    token: str
    device_id: Optional[str] = Field(
        default=None,
        description="CoreIoT device UUID — required for Server-Side RPC control.",
    )
    room: str
    type_device: Any = Field(
        default=None,
        description="Device category from YAML e.g. 'smart_light', 'smart_fan'.",
    )
    sensors: List[SensorAction] = Field(
        description=(
            "List of sensors (e.g. led_celling, fan) and their shared_attributes to act on. "
            "All attributes for a chosen sensor should be included."
        )
    )


class DeviceActionList(BaseModel):
    """Wrapper so the LLM can output a JSON object instead of a bare array."""

    devices: List[DeviceAction]
