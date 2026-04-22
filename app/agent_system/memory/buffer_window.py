"""Per-session BufferWindowMemory.

Implements the architecture diagram's "Buffer Window Memory" node:

    action_list[max = 100] = [
        device: name,
        room: name,
        actionAPIs [api_swagger]
    ]

It is a per-session FIFO sliding window of the last *N* successful device
actions (reads or writes). The Slave Agent consults it before asking the
user for clarification, and the iot_action_agent appends to it after a
successful ``post_shared_attributes`` so the next turn can short-circuit if
the user references the same device or room.

The window lives entirely in process memory — it does NOT survive a server
restart. Long-term recall happens via ``app.vectore_store.conversation_memory``
which embeds chat turns into FAISS asynchronously. The buffer window is the
*hot* short-term cache; FAISS is the *cold* long-term recall.

Session id propagation
----------------------
smolagents tools have a fixed input schema (no per-call kwargs we can
inject), so the runner sets the *current* session id on a
``contextvars.ContextVar`` before each ``agent.run(...)`` call and the
buffer-window tools read it back via ``current_session_id.get()``. This
keeps the tool signature clean while letting one global tool serve every
session.
"""

from __future__ import annotations

import json
import os
import contextvars
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

logger = logging.getLogger(__name__)

DEFAULT_MAX_SIZE: int = 100
BUFFER_DIR = "memories/sessions"


# ---------------------------------------------------------------------------
# ActionRecord
# ---------------------------------------------------------------------------


@dataclass
class ActionRecord:
    """One entry in a session's action history."""

    device_name: str
    room: str
    token: str
    action: str  # "post" | "read"
    type_device: str = ""  # e.g. "smart_light", "smart_fan"
    shared_attributes: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_name": self.device_name,
            "room": self.room,
            "token": self.token,
            "action": self.action,
            "type_device": self.type_device,
            "shared_attributes": self.shared_attributes,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# BufferWindowMemory
# ---------------------------------------------------------------------------


class BufferWindowMemory:
    """A FIFO sliding window of ActionRecords for a single session."""

    def __init__(self, session_id: str, max_size: int = DEFAULT_MAX_SIZE) -> None:
        self.session_id = session_id
        self.max_size = max_size
        self._records: deque[ActionRecord] = deque(maxlen=max_size)
        self._load()

    def _get_file_path(self) -> str:
        os.makedirs(BUFFER_DIR, exist_ok=True)
        return os.path.join(BUFFER_DIR, f"{self.session_id}.jsonl")

    def _load(self) -> None:
        path = self._get_file_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        if "timestamp" in data:
                            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                        self._records.append(ActionRecord(**data))
            except Exception as e:
                logger.error(f"Failed to load buffer window for session {self.session_id}: {e}")

    def _append_to_file(self, record: ActionRecord) -> None:
        try:
            path = self._get_file_path()
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write buffer window for session {self.session_id}: {e}")

    # ----- mutation ------------------------------------------------------

    def append(self, record: ActionRecord) -> None:
        """Append a record. ``deque(maxlen=...)`` evicts the oldest entry on overflow."""
        self._records.append(record)
        self._append_to_file(record)

    def extend(self, records: Iterable[ActionRecord]) -> None:
        for record in records:
            self.append(record)

    def clear(self) -> None:
        self._records.clear()
        try:
            path = self._get_file_path()
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    # ----- query ---------------------------------------------------------

    def __len__(self) -> int:
        return len(self._records)

    def all(self) -> list[ActionRecord]:
        return list(self._records)

    def find(
        self,
        device_name: str | None = None,
        room: str | None = None,
        token: str | None = None,
    ) -> list[ActionRecord]:
        """Return matching records, newest first.

        Matches are case-insensitive substring matches on ``device_name`` and
        ``room`` and an exact match on ``token``. Any filter that is ``None``
        is ignored.
        """
        device_q = device_name.lower().strip() if device_name else None
        room_q = room.lower().strip() if room else None
        token_q = token.strip() if token else None

        matches: list[ActionRecord] = []
        for record in reversed(self._records):
            if device_q and device_q not in record.device_name.lower():
                continue
            if room_q and room_q not in record.room.lower():
                continue
            if token_q and record.token != token_q:
                continue
            matches.append(record)
        return matches

    def to_context_string(self, limit: int = 10) -> str:
        """Render the most recent ``limit`` records as plain text for an LLM prompt."""
        if not self._records:
            return "(empty)"
        recent = list(self._records)[-limit:]
        lines = []
        for record in reversed(recent):  # newest first
            ts = record.timestamp.strftime("%H:%M:%S")
            lines.append(
                f"- [{ts}] {record.action} {record.device_name} "
                f"(room={record.room}, token={record.token}, "
                f"attrs={record.shared_attributes})"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module-level session registry + ContextVar
# ---------------------------------------------------------------------------


_BUFFERS: dict[str, BufferWindowMemory] = {}

#: Set by the runner before each ``agent.run(...)`` call so tools can find
#: the right session's buffer without taking it as a parameter.
current_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_session_id", default=None
)


def set_current_session(session_id: str | None) -> contextvars.Token:
    """Bind the current session id and return a token for ``ContextVar.reset``."""
    return current_session_id.set(session_id)


def get_buffer(session_id: str) -> BufferWindowMemory:
    """Return the BufferWindowMemory for *session_id*, creating it on first use."""
    buffer = _BUFFERS.get(session_id)
    if buffer is None:
        buffer = BufferWindowMemory(session_id=session_id)
        _BUFFERS[session_id] = buffer
    return buffer


def get_current_buffer() -> BufferWindowMemory | None:
    """Return the buffer for the active session, or ``None`` if no session is set."""
    sid = current_session_id.get()
    if not sid:
        return None
    return get_buffer(sid)


def clear_buffer(session_id: str) -> None:
    """Drop a session's buffer entirely (call on session delete)."""
    _BUFFERS.pop(session_id, None)


__all__ = [
    "ActionRecord",
    "BufferWindowMemory",
    "DEFAULT_MAX_SIZE",
    "clear_buffer",
    "current_session_id",
    "get_buffer",
    "get_current_buffer",
    "set_current_session",
]
