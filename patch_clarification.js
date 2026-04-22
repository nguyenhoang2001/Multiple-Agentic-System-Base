const fs = require('fs');
let code = fs.readFileSync('app/agent_system/agents/clarification_agent.py', 'utf8');

const newCode = `"""
Clarification Agent — resolves missing room/device context.

No LLM, no code generation — fully deterministic:
  1. Check Buffer Window Memory for cached device/room this session.
  2. If still missing → asks specifically for the missing info (room or device type).
"""

from __future__ import annotations

import json
import re

from app.agent_system.tools.buffer_window_tools import check_buffer_window_tool
from app.agent_system.tools.yaml_iterator import iterate_smart_home_yaml_tool


_DEVICE_TYPE_MAP = {
    "đèn": "smart_light",
    "bóng đèn": "smart_light",
    "đèn trần": "smart_light",
    "đèn ngủ": "smart_light",
    "đèn bếp": "smart_light",
    "quạt": "smart_fan",
    "quạt trần": "smart_fan",
    "light": "smart_light",
    "fan": "smart_fan",
    "tất cả thiết bị": "all",
    "các thiết bị": "all",
    "mọi thứ": "all",
    "tất cả": "all"
}


def _infer_device_type(user_message: str) -> str | None:
    msg = user_message.lower()
    for keyword, dtype in _DEVICE_TYPE_MAP.items():
        if keyword in msg:
            return dtype
    return None


class ClarificationAgent:
    """Deterministic clarification — no LLM, no code generation."""

    def run(self, user_message: str, extracted_intent=None) -> str:
        # Step 1 — Check Buffer Window Memory
        cached = check_buffer_window_tool.forward(user_message)
        if cached != "[]":
            try:
                hit = json.loads(cached)[0]
                return (
                    f"CACHED: device_name={hit.get('device_name')}, "
                    f"room={hit.get('room')}, token={hit.get('token')}"
                )
            except (json.JSONDecodeError, IndexError, KeyError):
                pass
                
        # Try inferring device type from user message explicitly
        device_type = _infer_device_type(user_message)
        
        # Merge with extracted intent if passed
        has_room = False
        if extracted_intent:
            has_room = bool(extracted_intent.room_name)
            if not device_type:
                device_type = extracted_intent.type_device

        # If LLM failed but we know from regex it's "all"
        if device_type == "all" and has_room:
            # We magically caught it. Tell Orchestrator to proceed (we shouldn't be here, but just in case)
            pass

        # Step 2 — Missing Room
        if not has_room:
            yaml_result = iterate_smart_home_yaml_tool.forward(
                room_name="", type_device=device_type or ""
            )
            rooms = re.findall(r"name:\\s*(\\S+)", yaml_result)
            room_names = [r for r in rooms if "_" in r or r in ("kitchen", "bedroom")]
            if not room_names:
                room_names = list(dict.fromkeys(rooms))
            room_list = ", ".join(room_names) if room_names else "không rõ"
            return f"Bạn muốn điều khiển ở phòng nào? Các phòng hiện có: {room_list}."
            
        # Step 3 - Missing Device
        if not device_type:
            return "Bạn muốn điều khiển thiết bị nào? (ví dụ: đèn, quạt, hoặc 'tất cả thiết bị')"
            
        return "Bạn hãy cung cấp rõ hơn thông tin thiết bị hoặc phòng nhé."


clarification_agent = ClarificationAgent()
`;

fs.writeFileSync('app/agent_system/agents/clarification_agent.py', newCode);
console.log("Patched clarification_agent!");
