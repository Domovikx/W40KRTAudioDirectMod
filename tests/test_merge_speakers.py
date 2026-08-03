"""Tests for tools/merge_speakers.py — union merge and player-answer removal."""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import merge_speakers as ms  # noqa: E402

G_OLD = "11111111-1111-1111-1111-111111111111"
G_NEW = "22222222-2222-2222-2222-222222222222"
G_ANS = "33333333-3333-3333-3333-333333333333"

ROLES = {G_ANS: "answer", G_OLD: "cue", G_NEW: "cue"}


def old_phrases():
    return [
        {"guid": G_OLD, "text": '"Старая фраза".', "speaker": "Generic Male NPC",
         "parts": [{"speaker": "Generic Male NPC", "text_clean": "Старая фраза."}]},
        {"guid": G_ANS, "text": '"Ответ игрока".', "speaker": "Generic Male NPC",
         "parts": [{"speaker": "Generic Male NPC", "text_clean": "Ответ игрока."}]},
    ]


def new_phrases():
    return [
        {"guid": G_OLD, "event": "", "text": '"Старая фраза".', "speaker": "Kunrad Voigtvir"},
        {"guid": G_NEW, "event": "", "text": '"Новая фраза".', "speaker": "Generic Male NPC"},
    ]


def test_merge_keeps_old_with_parts_and_preserves_speaker():
    # Existing phrases keep their speaker (manual review result).
    merged = ms.merge_phrases(old_phrases(), new_phrases(), lambda g: ROLES.get(g) == "answer")
    by_guid = {p["guid"]: p for p in merged}
    assert G_OLD in by_guid
    assert by_guid[G_OLD]["speaker"] == "Generic Male NPC"  # old speaker preserved
    assert by_guid[G_OLD]["parts"][0]["speaker"] == "Generic Male NPC"  # parts untouched
    assert by_guid[G_OLD]["parts"][0]["text_clean"] == "Старая фраза."  # parts preserved
    assert G_NEW in by_guid  # new phrase added with the machine speaker
    assert by_guid[G_NEW]["speaker"] == "Generic Male NPC"


def test_merge_does_not_overwrite_review_speaker():
    old = [
        {"guid": G_OLD, "text": '"Леди Теодора".', "speaker": "Seneschal (NPC)",
         "parts": [{"speaker": "Seneschal (NPC)", "text_clean": "Леди Теодора."}]},
    ]
    new = [{"guid": G_OLD, "text": '"Леди Теодора".', "speaker": "Theodora von Valancius"}]
    merged = ms.merge_phrases(old, new, lambda g: False)
    assert merged[0]["speaker"] == "Seneschal (NPC)"
    assert merged[0]["parts"][0]["speaker"] == "Seneschal (NPC)"


def test_merge_keeps_answer_with_event():
    # Voiced NPC lines can sit in Answer nodes (0x5B) — they are NOT player answers.
    old = [{"guid": G_ANS, "event": "TrazynOffer_Trazyn_01", "text": '"Нужно отдать тебе должное".',
            "speaker": "Trazyn", "parts": [{"speaker": "Trazyn", "text_clean": "Нужно отдать тебе должное."}]}]
    new = [{"guid": G_ANS, "event": "TrazynOffer_Trazyn_01", "text": '"Нужно отдать тебе должное".',
            "speaker": "Trazyn"}]
    merged = ms.merge_phrases(old, new, lambda g: ROLES.get(g) == "answer")
    assert any(p["guid"] == G_ANS for p in merged)
    assert merged[0]["parts"][0]["text_clean"] == "Нужно отдать тебе должное."


def test_merge_removes_answer_without_event():
    old = [{"guid": G_ANS, "event": "", "text": '"Ответ игрока".', "speaker": "Generic Male NPC",
            "parts": [{"speaker": "Generic Male NPC", "text_clean": "Ответ игрока."}]}]
    new = [{"guid": G_ANS, "event": "", "text": '"Ответ игрока".', "speaker": "Player"}]
    merged = ms.merge_phrases(old, new, lambda g: ROLES.get(g) == "answer")
    assert all(p["guid"] != G_ANS for p in merged)


def test_build_player_answers_skips_event_phrases():
    old_by_file = {
        "Trazyn.yaml": {"phrases": [
            {"guid": G_ANS, "event": "TrazynOffer_Trazyn_01", "text": '"Реплика".', "speaker": "Trazyn",
             "parts": [{"speaker": "Trazyn", "text_clean": "Реплика."}]},
        ]}
    }
    new_player = [{"guid": G_ANS, "event": "", "text": '"Реплика".', "speaker": "Player"}]
    result = ms.build_player_answers(new_player, old_by_file, lambda g: ROLES.get(g) == "answer")
    # the event phrase must NOT be carried into Player_Answers with its parts
    assert result[0].get("parts") is None


def test_merge_removes_player_answers():
    merged = ms.merge_phrases(old_phrases(), new_phrases(), lambda g: ROLES.get(g) == "answer")
    guids = [p["guid"] for p in merged]
    assert G_ANS not in guids


def test_build_player_answers_prefers_old_with_parts():
    new_player = [
        {"guid": G_ANS, "event": "", "text": '"Ответ игрока".', "speaker": "Player"},
        {"guid": "44444444-4444-4444-4444-444444444444", "event": "", "text": '"Ещё ответ".', "speaker": "Player"},
    ]
    old_by_file = {
        "Generic_Male_NPC.yaml": {"phrases": [
            {"guid": G_ANS, "text": '"Ответ игрока".', "speaker": "Generic Male NPC",
             "parts": [{"speaker": "Generic Male NPC", "text_clean": "Ответ игрока."}]},
        ]}
    }
    result = ms.build_player_answers(new_player, old_by_file, lambda g: ROLES.get(g) == "answer")
    by_guid = {p["guid"]: p for p in result}
    assert by_guid[G_ANS]["parts"]  # parts carried over
    assert not by_guid["44444444-4444-4444-4444-444444444444"].get("parts")  # fresh, no parts


def test_safe_filename_and_file_key():
    assert ms.safe_filename("Smuggler") == "Smuggler"
    assert ms.safe_filename("Psyker (NPC)") == "Psyker_NPC"
    assert ms.file_key({"name": "Smuggler"}) == "Smuggler"
    assert ms.file_key({"phrases": []}) == ""


def test_load_old_people_excludes_player_answers(tmp_path):
    (tmp_path / "Generic_Male_NPC.yaml").write_text(
        "name: Generic Male NPC\nphrases:\n  - guid: x\n", encoding="utf-8"
    )
    (tmp_path / "Player_Answers.yaml").write_text(
        "name: Player Answers\nphrases:\n  - guid: y\n", encoding="utf-8"
    )
    (tmp_path / "index.yaml").write_text("index: yes\n", encoding="utf-8")
    by_name, by_file, orphans = ms.load_old_people(str(tmp_path))
    assert "Generic Male NPC" in by_name
    assert "Player Answers" not in by_name
    assert by_file["Generic Male NPC"] == "Generic_Male_NPC.yaml"
    assert orphans == []


def test_load_old_people_duplicate_name_picks_canonical(tmp_path):
    # Both Smuggler.yaml and Smuggler_NPC.yaml carry name: Smuggler
    (tmp_path / "Smuggler.yaml").write_text(
        "name: Smuggler\nphrases:\n  - guid: a\n", encoding="utf-8"
    )
    (tmp_path / "Smuggler_NPC.yaml").write_text(
        "name: Smuggler\nphrases:\n  - guid: b\n", encoding="utf-8"
    )
    by_name, by_file, orphans = ms.load_old_people(str(tmp_path))
    assert by_file["Smuggler"] == "Smuggler.yaml"  # canonical wins
    assert "Smuggler_NPC.yaml" in orphans
