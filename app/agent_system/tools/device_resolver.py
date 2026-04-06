"""
Device Resolver — fuzzy matching + ambiguity handling for natural-language
device references.

Given a free-text phrase like ``"bedroom light"``, ``"the thermostat"``, or
``"living room light"``, this module finds the best-matching ``DeviceEntry``
from the in-memory registry.

Resolution flow
-----------------
1. **Exact ID** — if the query is already a valid ``device_id``, return it.
2. **Type + location** — extract a device type keyword and a location keyword,
   then intersect.
3. **Token overlap** — score every device by how many of its aliases overlap
   with the query tokens (fuzzy fallback).
4. **Ambiguity** — if multiple devices tie, return them all and let the caller
   decide (e.g. ask for clarification).

Typical usage
-------------
    from app.agent_system.tools.device_resolver import resolve_device

    result = resolve_device("bedroom light")
    # ResolveResult(matches=[DeviceEntry(...)], ambiguous=False)

    result = resolve_device("the thermostat")
    # ResolveResult(matches=[DeviceEntry(...)], ambiguous=False)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.agent_system.tools.device_registry import (
    DeviceEntry,
    get_registry,
    lookup,
)


# ---------------------------------------------------------------------------
# Keyword → registry field mappings
# ---------------------------------------------------------------------------

# Map natural-language type words to registry device_type values
_TYPE_KEYWORDS: dict[str, str] = {
    "light": "smart_light",
    "lights": "smart_light",
    "lamp": "smart_light",
    "bulb": "smart_light",
    "thermostat": "thermostat",
    "temperature": "thermostat",
    "heating": "thermostat",
    "cooling": "thermostat",
}

# Map natural-language location words to registry location values
_LOCATION_KEYWORDS: dict[str, str] = {
    "living room": "living_room",
    "livingroom": "living_room",
    "living": "living_room",
    "lounge": "living_room",
    "bedroom": "bedroom",
    "bed room": "bedroom",
}

# Devices that are unique in the home (only one exists) — no location needed
_UNIQUE_TYPES = {"thermostat"}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ResolveResult:
    """Outcome of a device resolution attempt."""

    matches: List[DeviceEntry] = field(default_factory=list)
    ambiguous: bool = False

    @property
    def found(self) -> bool:
        return len(self.matches) > 0

    @property
    def unique(self) -> bool:
        return len(self.matches) == 1

    @property
    def device(self) -> Optional[DeviceEntry]:
        """Return the single match, or ``None`` if ambiguous / not found."""
        return self.matches[0] if self.unique else None

    @property
    def device_id(self) -> Optional[str]:
        d = self.device
        return d.device_id if d else None


# ---------------------------------------------------------------------------
# Core resolver
# ---------------------------------------------------------------------------

_STRIP_RE = re.compile(r"\b(?:the|my|a|an|please|can you|could you)\b", re.IGNORECASE)


def _normalise(text: str) -> str:
    """Lowercase, strip filler words, collapse whitespace."""
    text = _STRIP_RE.sub("", text.lower())
    return " ".join(text.split())


def _extract_type(text: str) -> Optional[str]:
    """Return the registry device_type if a type keyword is found in *text*."""
    # Check multi-word keys first (e.g. "motion sensor" before "motion")
    for kw in sorted(_TYPE_KEYWORDS, key=len, reverse=True):
        if kw in text:
            return _TYPE_KEYWORDS[kw]
    return None


def _extract_location(text: str) -> Optional[str]:
    """Return the registry location if a location keyword is found in *text*."""
    for kw in sorted(_LOCATION_KEYWORDS, key=len, reverse=True):
        if kw in text:
            return _LOCATION_KEYWORDS[kw]
    return None


def resolve_device(query: str) -> ResolveResult:
    """
    Resolve a natural-language device reference to one or more ``DeviceEntry`` objects.

    Parameters
    ----------
    query : str
        Free-text such as ``"bedroom light"``, ``"thermostat"``,
        ``"the thermostat"``, or an exact device ID.

    Returns
    -------
    ResolveResult
        ``.unique`` is ``True`` when exactly one device matched.
        ``.ambiguous`` is ``True`` when multiple devices matched equally well.
        ``.matches`` contains the candidate(s).
    """
    registry = get_registry()
    text = _normalise(query)

    # 1. Exact device_id match
    exact = lookup(text.replace(" ", "_"))
    if exact:
        return ResolveResult(matches=[exact])

    # 2. Type + location intersection
    dev_type = _extract_type(text)
    location = _extract_location(text)

    if dev_type:
        type_matches = [e for e in registry if e.device_type == dev_type]

        # Unique device type (only one in the home) → return immediately
        if dev_type in _UNIQUE_TYPES and type_matches:
            return ResolveResult(matches=type_matches[:1])

        if location:
            loc_matches = [e for e in type_matches if e.location == location]
            if loc_matches:
                return ResolveResult(
                    matches=loc_matches,
                    ambiguous=len(loc_matches) > 1,
                )

        # Type found but no location → ambiguous if >1 device of that type
        if len(type_matches) == 1:
            return ResolveResult(matches=type_matches)
        if type_matches:
            return ResolveResult(matches=type_matches, ambiguous=True)

    # 3. Location-only (no type keyword recognised)
    if location:
        loc_matches = [e for e in registry if e.location == location]
        if loc_matches:
            return ResolveResult(matches=loc_matches, ambiguous=len(loc_matches) > 1)

    # 4. Token-overlap fallback
    tokens = set(text.split())
    scored: list[tuple[int, DeviceEntry]] = []
    for entry in registry:
        alias_tokens = set()
        for a in entry.aliases:
            alias_tokens.update(a.split())
        overlap = len(tokens & alias_tokens)
        if overlap:
            scored.append((overlap, entry))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score = scored[0][0]
        top = [e for s, e in scored if s == best_score]
        return ResolveResult(matches=top, ambiguous=len(top) > 1)

    # 5. Nothing found
    return ResolveResult()
