"""Tests for tools/qwen3_full_icl.py skip_voicing support."""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import qwen3_full_icl as q  # noqa: E402


def test_should_skip_file_level():
    char_data = {"skip_voicing": True, "phrases": [{"guid": "x", "parts": [{}]}]}
    assert q.should_skip(char_data, char_data["phrases"][0])


def test_should_skip_phrase_level():
    char_data = {"phrases": [{"guid": "x", "skip_voicing": True, "parts": [{}]}]}
    assert q.should_skip(char_data, char_data["phrases"][0])


def test_should_not_skip_normal():
    char_data = {"phrases": [{"guid": "x", "parts": [{"speaker": "Npc", "text_clean": "фраза"}]}]}
    assert not q.should_skip(char_data, char_data["phrases"][0])
