"""Smart-home configuration iterator.

Deterministic helper that filters ``smart_home_configuration.json`` by
``room_name`` and ``type_device`` keywords and returns a small focused YAML
subtree (the architecture's ``dataset_tmp.yaml``).

The JSON is the source of truth for the device registry — it is **never**
embedded into FAISS. Instead, agents extract keywords (room + device type)
and call this helper to get only the relevant slice, which is then handed
to the next agent (Retriever Agent) as inline context in YAML format to save tokens.

Typical usage
-------------
    from app.agent_system.tools.yaml_iterator import (
        iterate_smart_home_yaml,
        iterate_smart_home_yaml_tool,
    )

    subtree = iterate_smart_home_yaml("living_room", "smart_light")
"""

from __future__ import annotations

import functools
import logging
import os
from typing import Any

import yaml
from smolagents import Tool

logger = logging.getLogger(__name__)

DEFAULT_JSON_PATH: str = os.environ.get(
    "SMART_HOME_CONFIG_PATH",
    "knowledge_base/iot_knowledge/smart_home_configuration.json",
)


# ---------------------------------------------------------------------------
# JSON loading (cached)
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=4)
def _load_json(path: str) -> dict[str, Any]:
    """Parse the smart-home JSON once per path and cache the result."""
    import json
    with open(path, encoding="utf-8") as f:
        data = json.load(f) or {}
    if not isinstance(data, dict) or "rooms" not in data:
        raise ValueError(
            f"Smart home configuration at '{path}' is missing the top-level 'rooms' key."
        )
    return data


def reload_config_cache() -> None:
    """Drop the cached config so the next call re-reads from disk."""
    _load_json.cache_clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(value: str | list[str] | None) -> list[str]:
    """Convert ``None`` / ``str`` / ``list[str]`` into a lower-cased ``list[str]``."""
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    else:
        items = list(value)
    return [str(item).strip().lower() for item in items if str(item).strip()]


def _filter_rooms(
    data: dict[str, Any],
    rooms_filter: list[str],
    types_filter: list[str],
) -> dict[str, Any]:
    """Return a deep-copied subtree containing only matching rooms / type_device."""
    matched_rooms: list[dict[str, Any]] = []
    for room in data.get("rooms", []):
        room_name = str(room.get("name", "")).lower()
        if rooms_filter and room_name not in rooms_filter:
            continue

        type_devices = room.get("type_device", []) or []
        if types_filter:
            type_devices = [
                td
                for td in type_devices
                if str(td.get("name_type", "")).lower() in types_filter
            ]
            if not type_devices:
                continue

        matched_rooms.append({"name": room.get("name"), "type_device": type_devices})

    return {"rooms": matched_rooms}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def iterate_smart_home_yaml(
    room_name: str | list[str] | None = None,
    type_device: str | list[str] | None = None,
    json_path: str = DEFAULT_JSON_PATH,
) -> str:
    """Filter the smart-home JSON and return the matching subtree as a YAML string.

    Parameters
    ----------
    room_name:
        One or more room names to keep (e.g. ``"living_room"`` or
        ``["living_room", "kitchen"]``). ``None`` keeps every room.
    type_device:
        One or more ``name_type`` values to keep (e.g. ``"smart_light"``).
        ``None`` keeps every device type within each matched room.
    json_path:
        Path to ``smart_home_configuration.json``. Defaults to the project's
        canonical location.

    Returns
    -------
    str
        A small YAML document of the form::

            rooms:
              - name: living_room
                type_device:
                  - name_type: smart_light
                    devices:
                      - name: Đèn trần
                        device_token: xdF2nW4aR9SAdqqPiym0
                        ...

        If nothing matches the filter, returns ``"rooms: []\\n"``.
    """
    data = _load_json(json_path)

    rooms_filter = _normalise(room_name)
    types_filter = _normalise(type_device)

    subtree = _filter_rooms(data, rooms_filter, types_filter)
    return yaml.safe_dump(subtree, sort_keys=False, allow_unicode=True)


def list_available_rooms(json_path: str = DEFAULT_JSON_PATH) -> list[str]:
    """Return every ``rooms[].name`` defined in the config."""
    data = _load_json(json_path)
    return [str(room.get("name")) for room in data.get("rooms", []) if room.get("name")]


def list_available_type_devices(
    room_name: str | None = None,
    json_path: str = DEFAULT_JSON_PATH,
) -> list[str]:
    """Return every distinct ``name_type`` (optionally restricted to ``room_name``)."""
    data = _load_json(json_path)
    types: list[str] = []
    for room in data.get("rooms", []):
        if room_name and str(room.get("name", "")).lower() != room_name.lower():
            continue
        for td in room.get("type_device", []) or []:
            name_type = td.get("name_type")
            if name_type and name_type not in types:
                types.append(str(name_type))
    return types


def get_room_and_device_types(json_path: str = DEFAULT_JSON_PATH) -> dict[str, list[str]]:
    """Return a mapping of room name to its list of name_type values."""
    data = _load_json(json_path)
    mapping: dict[str, list[str]] = {}
    for room in data.get("rooms", []):
        r_name = str(room.get("name", ""))
        if not r_name:
            continue
        mapping[r_name] = []
        for td in room.get("type_device", []) or []:
            name_type = td.get("name_type")
            if name_type and str(name_type) not in mapping[r_name]:
                mapping[r_name].append(str(name_type))
    return mapping


def get_device_summary(json_path: str = DEFAULT_JSON_PATH) -> str:
    """Return a YAML string summarizing rooms, device types, names, and descriptions."""
    data = _load_json(json_path)
    summary_rooms = []
    
    for room in data.get("rooms", []):
        r_name = str(room.get("name", "unknown"))
        room_types = []
        for td in room.get("type_device", []) or []:
            t_name = str(td.get("name_type", "unknown"))
            dev_list = []
            for dev in td.get("devices", []) or []:
                d_name = str(dev.get("name", "unknown"))
                d_desc = str(dev.get("description_location", ""))
                dev_dict = {"name": d_name}
                if d_desc:
                    dev_dict["description"] = d_desc
                dev_list.append(dev_dict)
            if dev_list:
                room_types.append({"type": t_name, "devices": dev_list})
        if room_types:
            summary_rooms.append({"room": r_name, "types": room_types})
            
    return yaml.safe_dump({"device_summary": summary_rooms}, sort_keys=False, allow_unicode=True)


def get_device_keyword_mapping(json_path: str = DEFAULT_JSON_PATH) -> dict[str, str]:
    """Dynamically generate a mapping of device keywords to their type_device.
    E.g. 'đèn trần' -> 'smart_light', 'quạt' -> 'smart_fan'.
    """
    data = _load_json(json_path)
    mapping = {
        "tất cả thiết bị": "all",
        "các thiết bị": "all",
        "mọi thứ": "all",
        "tất cả": "all"
    }
    
    for room in data.get("rooms", []):
        for td in room.get("type_device", []) or []:
            name_type = td.get("name_type")
            if not name_type:
                continue
            name_type = str(name_type)
            mapping[name_type] = name_type  # map the exact type name to itself
            
            for dev in td.get("devices", []) or []:
                dev_name = str(dev.get("name", "")).lower().strip()
                if not dev_name:
                    continue
                mapping[dev_name] = name_type
                
                # Extract first word as a generic keyword (e.g. "đèn" from "đèn trần")
                first_word = dev_name.split()[0]
                if first_word not in mapping:
                    mapping[first_word] = name_type
                
                # If first word is "điều" (as in "điều hòa"), map the whole word
                if first_word == "điều" and "hòa" in dev_name:
                    mapping["điều hòa"] = name_type
                
                # English mappings for basics
                if "light" in name_type and "light" not in mapping:
                    mapping["light"] = name_type
                if "fan" in name_type and "fan" not in mapping:
                    mapping["fan"] = name_type

    return mapping


# ---------------------------------------------------------------------------
# smolagents Tool wrapper
# ---------------------------------------------------------------------------


class IterateSmartHomeYamlTool(Tool):
    name = "iterate_smart_home_yaml"
    description = (
        "Filter the smart_home_configuration.json by room_name and type_device "
        "and return only the matching subtree as a YAML string. "
        "Use this when you have already extracted the room and device-type "
        "keywords from the user's request and want to hand a small focused "
        "device list to the next agent. The YAML output contains every device's "
        "name, device_token, description_location and shared_attributes schema."
    )
    inputs = {
        "room_name": {
            "type": "string",
            "description": (
                "Room name to filter by, e.g. 'living_room', 'kitchen'. "
                "Pass null or empty string to include every room."
            ),
            "nullable": True,
        },
        "type_device": {
            "type": "string",
            "description": (
                "Device type to filter by, e.g. 'smart_light', 'smart_fan'. "
                "Pass null or empty string to include every device type within "
                "the matched rooms."
            ),
            "nullable": True,
        },
    }
    output_type = "string"

    def forward(
        self,
        room_name: str | None = None,
        type_device: str | None = None,
    ) -> str:
        try:
            return iterate_smart_home_yaml(
                room_name=room_name or None,
                type_device=type_device or None,
            )
        except FileNotFoundError as exc:
            return f"Error: smart_home_configuration.json not found ({exc})."
        except ValueError as exc:
            return f"Error: invalid JSON in smart_home_configuration.json ({exc})."
        except Exception as exc:  # noqa: BLE001
            logger.exception("iterate_smart_home_yaml failed")
            return f"Error iterating smart-home JSON: {exc}"


iterate_smart_home_yaml_tool = IterateSmartHomeYamlTool()


__all__ = [
    "iterate_smart_home_yaml",
    "list_available_rooms",
    "list_available_type_devices",
    "get_room_and_device_types",
    "get_device_summary",
    "get_device_keyword_mapping",
    "reload_config_cache",
    "IterateSmartHomeYamlTool",
    "iterate_smart_home_yaml_tool",
    "DEFAULT_JSON_PATH",
]
# EOF
