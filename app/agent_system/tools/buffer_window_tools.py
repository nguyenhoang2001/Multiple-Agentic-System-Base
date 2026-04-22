"""Buffer Window Memory tool.

Exposes the per-session ``BufferWindowMemory`` to agents as a named tool so
the Slave Agent can quickly check whether the user already interacted with a
device/room in the current session before asking a clarifying question.

This is a pure in-memory lookup — no LLM call, no network request.
"""

from __future__ import annotations

import json

from smolagents import Tool

from app.agent_system.memory.buffer_window import get_current_buffer


class CheckBufferWindowTool(Tool):
    name = "check_buffer_window"
    description = (
        "Look up recent device actions in the current session's Buffer Window Memory. "
        "Returns a JSON list of matching ActionRecords (device_name, room, token, "
        "action, shared_attributes, timestamp). Returns '[]' on a cache miss. "
        "Use this FIRST when the user's request is ambiguous about room or device — "
        "if a hit is found, the missing context can be inferred without asking the user."
    )
    inputs = {
        "query": {
            "type": "string",
            "description": (
                "Free-text query describing the device or room to look up, "
                "e.g. 'đèn trần phòng khách' or 'kitchen fan'. "
                "The search is a case-insensitive substring match on device_name and room."
            ),
        }
    }
    output_type = "string"

    def forward(self, query: str) -> str:
        buffer = get_current_buffer()
        if buffer is None:
            return "[]"

        # Tokenise the query into words and match against device_name + room
        words = [w.strip().lower() for w in query.split() if w.strip()]

        matches = []
        for record in reversed(buffer.all()):  # newest first
            haystack = f"{record.device_name} {record.room}".lower()
            if any(word in haystack for word in words):
                matches.append(record.to_dict())

        # FALLBACK: If no explicit keyword matched, we return the most recent 
        # interacted devices. This avoids language-specific hardcoded phrases
        # (like "hồi nãy", "earlier", "刚才") while giving the LLM context to infer.
        if not matches:
            recent_records = buffer.all()[-2:] # take up to 2 most recent
            matches = [r.to_dict() for r in recent_records]

        return json.dumps(matches, ensure_ascii=False, default=str)


check_buffer_window_tool = CheckBufferWindowTool()

__all__ = [
    "CheckBufferWindowTool",
    "check_buffer_window_tool",
]
