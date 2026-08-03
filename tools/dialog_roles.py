#!/usr/bin/env python3
"""Dialog role classification from blueprints-pack.bbp.

Dialog tree nodes are serialized as:

    <len><Name> <32hex><TYPE-BYTE><15 bytes>...$<text-guid36>

The node NAME (Answer_0001 / Cue_0001 / ...) is just an asset name and is NOT
reliable. The node TYPE is encoded by the byte right after the 32-hex GUID:

    0x5B '['  -> BlueprintAnswer (player option)
    0x45 'E'  -> BlueprintCue (NPC line)

Everything else (0xFD, 0xAA, 0xFE, ...) is a different node type with a text
field (narration scenes etc.) -> classified as "unknown" (kept in the catalog,
review decides).

Classification rule per text GUID:
    any 0x45 -> cue      (spoken by an NPC at least once)
    any 0x5B -> answer   (player option at least once, never a cue)
    otherwise -> unknown
"""

from __future__ import annotations

import re
from typing import Dict, Set

NODE_NAME_RE = re.compile(
    rb"[\x01-\x3f](Answer_\d+|Cue_\d+|NewBlueprintCue|NewBlueprintAnswer|BlueprintCue|BlueprintAnswer)"
    rb"\s+([0-9a-f]{32})(.)"
)
TEXT_REF_RE = re.compile(
    rb"[$]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)

# How far after a node we look for its text reference.
LOOKAHEAD = 2000

TYPE_BYTE_ANSWER = 0x5B  # '['
TYPE_BYTE_CUE = 0x45     # 'E'


def classify_bbp(data: bytes, lookahead: int = LOOKAHEAD) -> Dict[str, Set[int]]:
    """Map every referenced text GUID to the set of node type bytes it appears with."""
    types: Dict[str, Set[int]] = {}
    for m in NODE_NAME_RE.finditer(data):
        type_byte = m.group(3)[0]
        tm = TEXT_REF_RE.search(data, m.end(), min(len(data), m.end() + lookahead))
        if tm:
            guid = tm.group(1).decode("ascii")
            types.setdefault(guid, set()).add(type_byte)
    return types


def role_of(types: Dict[str, Set[int]], guid: str) -> str:
    """answer | cue | unknown."""
    s = types.get(guid)
    if not s:
        return "unknown"
    if TYPE_BYTE_CUE in s:
        return "cue"
    if TYPE_BYTE_ANSWER in s:
        return "answer"
    return "unknown"


def is_answer_only(types: Dict[str, Set[int]], guid: str) -> bool:
    return role_of(types, guid) == "answer"
