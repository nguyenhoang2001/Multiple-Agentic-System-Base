"""
Device Registry — in-memory store of all IoT device ID mappings.

Parsed once from ``knowledge_base/iot_knowledge/device_registry.txt`` and
kept as a flat list of ``DeviceEntry`` dataclasses for O(1)-style lookups
by device_id, and cheap iteration for searches by type / location / name.

Typical usage
-------------
    from app.agent_system.tools.device_registry import get_registry, lookup

    entry = lookup("light_bedroom_01")          # exact ID
    entries = get_registry()                     # full list
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

_REGISTRY_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "knowledge_base",
    "iot_knowledge",
    "device_registry.txt",
)


@dataclass(frozen=True)
class DeviceEntry:
    device_id: str
    name: str
    device_type: str
    location: str
    capabilities: List[str] = field(default_factory=list)
    status: str = "online"

    # Convenience aliases derived from name / type for fuzzy matching
    @property
    def aliases(self) -> List[str]:
        """Return lowercase search terms: type words, name words, location."""
        parts = set()
        parts.add(self.device_type.replace("_", " "))
        for word in self.name.lower().split():
            parts.add(word)
        parts.add(self.location.replace("_", " "))
        return list(parts)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_KV_RE = re.compile(r"^(\w+):\s*(.+)$")


def _parse_registry(path: str) -> List[DeviceEntry]:
    entries: List[DeviceEntry] = []
    current: dict[str, str] = {}

    with open(os.path.normpath(path), encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                # Blank line or comment → flush current block if complete
                if "device_id" in current:
                    entries.append(_build_entry(current))
                    current = {}
                continue
            m = _KV_RE.match(line)
            if m:
                key, value = m.group(1), m.group(2).strip()
                current[key] = value

    # Flush last block
    if "device_id" in current:
        entries.append(_build_entry(current))

    return entries


def _build_entry(d: dict[str, str]) -> DeviceEntry:
    caps_raw = d.get("capabilities", "")
    caps = [c.strip() for c in caps_raw.split(",") if c.strip()]
    return DeviceEntry(
        device_id=d["device_id"],
        name=d.get("name", ""),
        device_type=d.get("type", ""),
        location=d.get("location", ""),
        capabilities=caps,
        status=d.get("status", "online"),
    )


# ---------------------------------------------------------------------------
# Singleton + public API
# ---------------------------------------------------------------------------

_registry: Optional[List[DeviceEntry]] = None
_by_id: Optional[dict[str, DeviceEntry]] = None


def get_registry() -> List[DeviceEntry]:
    """Return the full list of device entries (lazy-loaded, cached)."""
    global _registry
    if _registry is None:
        _registry = _parse_registry(_REGISTRY_PATH)
    return _registry


def _id_index() -> dict[str, DeviceEntry]:
    global _by_id
    if _by_id is None:
        _by_id = {e.device_id: e for e in get_registry()}
    return _by_id


def lookup(device_id: str) -> Optional[DeviceEntry]:
    """Look up a device by exact ID. Returns ``None`` if not found."""
    return _id_index().get(device_id)


def find_by_type(device_type: str) -> List[DeviceEntry]:
    """Return all devices matching the given type (e.g. 'smart_light')."""
    return [e for e in get_registry() if e.device_type == device_type]


def find_by_location(location: str) -> List[DeviceEntry]:
    """Return all devices in a given location (e.g. 'bedroom')."""
    return [e for e in get_registry() if e.location == location]
