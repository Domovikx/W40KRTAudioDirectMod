# -*- coding: utf-8 -*-
"""
Test ExtractGameSpeaker, ExtractGuidFromWav, and tracking logic.
Mirrors Main.cs regex patterns.
"""

import re
import json
import os
import tempfile

# Same regexes as Main.cs
re_game_speaker = re.compile(
    r"^([\w\-\u0400-\u04FF]+[\w\-\s\u0400-\u04FF]*):\s*"
)
re_guid_from_path = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def extract_game_speaker(raw_text: str) -> str | None:
    if not raw_text:
        return None
    m = re_game_speaker.match(raw_text)
    return m.group(1) if m else None


def extract_guid_from_wav(wav_rel_path: str) -> str | None:
    if not wav_rel_path:
        return None
    m = re_guid_from_path.search(wav_rel_path)
    return m.group(1) if m else None


# ── Tests ──

def test_extract_speaker():
    cases = [
        (None, None),
        ("", None),
        ("Просто текст", None),
        (
            '\u041a\u0443\u043d\u0440\u0430\u0434 \u0412\u043e\u0439\u0433\u0442\u0432\u0438\u0440: "\u041e\u0434\u043d\u0430 \u0438\u0437 \u0442\u0440\u043e\u0444\u0435\u0439\u043d\u044b\u0445..."',
            "\u041a\u0443\u043d\u0440\u0430\u0434 \u0412\u043e\u0439\u0433\u0442\u0432\u0438\u0440",
        ),
        (
            '\u0410\u0431\u0435\u043b\u044f\u0440: \u0414\u043e\u0431\u0440\u043e \u043f\u043e\u0436\u0430\u043b\u043e\u0432\u0430\u0442\u044c.',
            "\u0410\u0431\u0435\u043b\u044f\u0440",
        ),
        (
            '\u041a\u043b\u0435\u043c\u0435\u043d\u0446\u0438\u0430 \u0412\u0435\u0440\u0441\u0435\u0440\u0438\u0430\u043d: "\u041e\u0442\u0435\u0446!"',
            "\u041a\u043b\u0435\u043c\u0435\u043d\u0446\u0438\u0430 \u0412\u0435\u0440\u0441\u0435\u0440\u0438\u0430\u043d",
        ),
        ('Abelard: Welcome.', "Abelard"),
        ("No colon here", None),
        (":Missing name", None),
    ]
    for inp, expected in cases:
        result = extract_game_speaker(inp)
        assert result == expected, f"FAIL: {repr(inp)} -> {result} != {expected}"
    print("test_extract_speaker: OK")


def test_extract_guid():
    cases = [
        (None, None),
        ("", None),
        ("no-guid-here", None),
        (
            "Generic_Male_NPC/a4e42da5-445f-465c-a616-9d40d434f160.wav",
            "a4e42da5-445f-465c-a616-9d40d434f160",
        ),
        (
            "Kunrad_Voigtvir/cbf4e939-3f2b-417a-a237-0188dc9400e7.wav",
            "cbf4e939-3f2b-417a-a237-0188dc9400e7",
        ),
        (
            "a4e42da5-445f-465c-a616-9d40d434f160.wav",
            "a4e42da5-445f-465c-a616-9d40d434f160",
        ),
        (
            "output/full_icl/kunrad/ca2ef6c0-f159-447d-96d3-164e4ab8bb84__1.wav",
            "ca2ef6c0-f159-447d-96d3-164e4ab8bb84",
        ),
    ]
    for inp, expected in cases:
        result = extract_guid_from_wav(inp)
        assert result == expected, f"FAIL: {repr(inp)} -> {result} != {expected}"
    print("test_extract_guid: OK")


def test_tracking_format():
    """Simulate what Main.cs would write to speaker_stats.json and usage_stats.json."""
    # speaker_stats.json
    speaker_expected = {
        "version": "0.0.2",
        "mismatches": {
            "a4e42da5-445f-465c-a616-9d40d434f160": {
                "catalog": "Generic Male NPC",
                "game": "\u041a\u0443\u043d\u0440\u0430\u0434 \u0412\u043e\u0439\u0433\u0442\u0432\u0438\u0440",
                "text": "\u041e\u0434\u043d\u0430 \u0438\u0437 \u0442\u0440\u043e\u0444\u0435\u0439\u043d\u044b\u0445...",
                "count": 1,
            }
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(speaker_expected, f, indent=2, ensure_ascii=False)
        tmp_path = f.name

    with open(tmp_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert "mismatches" in loaded
    assert "a4e42da5-445f-465c-a616-9d40d434f160" in loaded["mismatches"]
    m = loaded["mismatches"]["a4e42da5-445f-465c-a616-9d40d434f160"]
    assert m["catalog"] == "Generic Male NPC"
    assert m["game"] == "\u041a\u0443\u043d\u0440\u0430\u0434 \u0412\u043e\u0439\u0433\u0442\u0432\u0438\u0440"
    assert m["count"] == 1
    os.unlink(tmp_path)
    print("test_tracking_format: OK")


def test_usage_stats_format():
    """Simulate usage_stats.json format."""
    expected = {
        "version": "0.0.2",
        "entries": {
            "a4e42da5-445f-465c-a616-9d40d434f160": {"plays": 5, "skips": 0, "cooldown": 2, "missing": 0},
            "f1a193b3-76cc-4e56-b0e9-5a63e7f94755": {"plays": 0, "skips": 3, "cooldown": 0, "missing": 1},
        },
    }

    # Verify count types
    for guid, stats in expected["entries"].items():
        assert "plays" in stats
        assert "skips" in stats
        assert "cooldown" in stats
        assert "missing" in stats
        assert all(isinstance(v, int) for v in stats.values())

    print("test_usage_stats_format: OK")


def test_deduplication():
    """Speaker mismatch should be recorded at most once per session per GUID."""
    mismatches = {}

    guid = "a4e42da5-445f-465c-a616-9d40d434f160"

    # First call: record
    if guid not in mismatches:
        mismatches[guid] = {"catalog": "Generic Male NPC", "game": "Kunrad", "count": 1}
    assert len(mismatches) == 1

    # Second call: skip (already tracked)
    if guid not in mismatches:
        mismatches[guid] = {"catalog": "Generic Male NPC", "game": "Kunrad", "count": 1}
    assert len(mismatches) == 1  # still 1

    print("test_deduplication: OK")


def test_settings_defaults():
    """All tracking flags should default to False."""
    # Simulate Settings.cs defaults
    defaults = {
        "VerboseDebugLog": False,
        "CollectSpeakerStats": False,
        "CollectUsageStats": False,
    }
    for key, val in defaults.items():
        assert val == False, f"{key} should be False by default"
    print("test_settings_defaults: OK")


if __name__ == "__main__":
    test_extract_speaker()
    test_extract_guid()
    test_tracking_format()
    test_usage_stats_format()
    test_deduplication()
    test_settings_defaults()
    print("\nAll tests passed!")
