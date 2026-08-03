"""Tests for tools/dialog_roles.py — bbp node TYPE-BYTE classification.

The node name is NOT reliable (Answer_5 can be a cue); the type byte after
the 32-hex guid is the discriminator: 0x5B = answer, 0x45 = cue.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from dialog_roles import classify_bbp, role_of, is_answer_only  # noqa: E402

G1 = "aaaaaaaa-0000-0000-0000-000000000001"
G2 = "aaaaaaaa-0000-0000-0000-000000000002"
G3 = "aaaaaaaa-0000-0000-0000-000000000003"
G4 = "aaaaaaaa-0000-0000-0000-000000000004"


def node(name: str, type_byte: bytes, guid36: str) -> bytes:
    """<len><Name> <32hex><TYPE-BYTE> junk $<guid36>"""
    prefix = bytes([len(name)])
    guid32 = "b" * 32
    return prefix + name.encode() + b" " + guid32.encode() + type_byte + b"\x00\x01\x02" + b"$" + guid36.encode()


def test_answer_type_byte_5b():
    data = node("Answer_0001", b"[", G1)
    assert role_of(classify_bbp(data), G1) == "answer"
    assert is_answer_only(classify_bbp(data), G1)


def test_cue_type_byte_45():
    data = node("Cue_0001", b"E", G1)
    assert role_of(classify_bbp(data), G1) == "cue"


def test_answer_named_node_with_cue_type_byte():
    # The regression case: node named "Answer_5" but type byte 0x45 (cue)
    data = node("Answer_5", b"E", G1)
    assert role_of(classify_bbp(data), G1) == "cue"


def test_cue_named_node_with_answer_type_byte():
    data = node("Cue_0001", b"[", G1)
    assert role_of(classify_bbp(data), G1) == "answer"


def test_same_guid_answer_and_cue_is_cue():
    data = node("Answer_0001", b"[", G1) + node("Cue_0001", b"E", G1)
    roles = classify_bbp(data)
    assert role_of(roles, G1) == "cue"
    assert not is_answer_only(roles, G1)


def test_answer_plus_unknown_byte_is_answer():
    # {0x5b, 0x75}: player option + another node type -> still answer
    data = node("Answer_0001", b"[", G1) + node("Answer_0002", b"\x75", G1)
    assert role_of(classify_bbp(data), G1) == "answer"


def test_unknown_type_byte_only():
    # {0xfd} only -> unknown (narration scenes etc.)
    data = node("Answer_0017", b"\xfd", G1)
    assert role_of(classify_bbp(data), G1) == "unknown"


def test_two_guids_distinct():
    data = node("Answer_0001", b"[", G1) + node("Cue_0001", b"E", G2)
    roles = classify_bbp(data)
    assert role_of(roles, G1) == "answer"
    assert role_of(roles, G2) == "cue"


def test_no_node_is_unknown():
    data = b"garbage" + b"$" + G1.encode()
    roles = classify_bbp(data)
    assert G1 not in roles
    assert role_of(roles, G1) == "unknown"
    assert not is_answer_only(roles, G1)


def test_lookahead_window_respected():
    data = node("Answer_0001", b"[", G1) + b"\x00" * 4000 + b"$" + G2.encode()
    roles = classify_bbp(data)
    assert G1 in roles
    assert G2 not in roles
