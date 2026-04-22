"""
Clarification Agent — resolves missing room/device context.

Leverages thinking_model to logically connect recent Buffer Window Memory
acts to the current incomplete user message.
"""

from __future__ import annotations

import json
import logging

from app.agent_system.model import thinking_model
from app.agent_system.tools.buffer_window_tools import check_buffer_window_tool
from app.agent_system.memory.buffer_window import get_current_buffer
from app.agent_system.tools.yaml_iterator import list_available_rooms, get_room_and_device_types

logger = logging.getLogger("ClarificationAgent")


class ClarificationAgent:
    """Clarification leveraging LLM to infer the missing context from history."""

    def run(self, user_message: str, extracted_intent=None) -> str:
        buf = get_current_buffer()
        recent_context = buf.to_context_string(limit=5) if buf else "(empty)"
        
        has_room = False
        device_type = None
        if extracted_intent:
            has_room = bool(extracted_intent.room_name)
            device_type = extracted_intent.type_device

        available_rooms = ", ".join(list_available_rooms())
        
        room_to_types = get_room_and_device_types()
        details = []
        for r, t_list in room_to_types.items():
            types_str = ", ".join(t_list)
            details.append(f"{r} ({types_str})")
        available_devices = "; ".join(details) if details else "unknown"

        prompt = f"""\
You are a smart home clarification assistant. The user wants to control a device but didn't provide enough information.
Determine what is missing (room or specific device type) and ask the user a brief clarifying question.

Recent Context (last actions): 
{recent_context}

Available Rooms: {available_rooms}
Available Devices per Room: {available_devices}

User's Incomplete Message: "{user_message}"
Extracted Intent So Far: Room={extracted_intent.room_name if extracted_intent else None}, DeviceType={device_type}

Task: Use the Recent Context and Available info to figure out what they most likely meant.
If you can infer the missing context from Recent Context (e.g., they said "đổi cái quạt", and the recent context shows they just interacted with a fan in the living room), ask them if they mean that specific one. Otherwise, list the available options for the missing piece.
Keep the question short, natural, and directly address the user. You can answer in the user's language.
"""
        messages = [{"role": "system", "content": [{"type": "text", "text": prompt}]}]
        
        try:
            response = thinking_model(messages=messages)
            logger.info(f"AI RESPONSE: ClarificationAgent: {response.content}")
            return response.content
        except Exception as e:
            logger.warning(f"Clarification generation failed: {str(e)}")
            return "Please provide more specific information about the device or room."

clarification_agent = ClarificationAgent()
