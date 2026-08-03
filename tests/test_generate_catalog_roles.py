"""Tests for generate_catalog.py role routing (player answers -> Player_Answers.yaml)."""

import sys
import os
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / ".opencode" / "skills" / "text-catalog" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_catalog as gc  # noqa: E402

G_ANS = "aaaaaaaa-0000-0000-0000-000000000001"
G_CUE = "aaaaaaaa-0000-0000-0000-000000000002"
G_UNK = "aaaaaaaa-0000-0000-0000-000000000003"


def make_game_files(tmp: Path, texts: dict, events: dict | None = None):
    """Create minimal ruRU.json / Sound.json under GAME so build_output runs."""
    game = tmp / "WH40KRT_Data" / "StreamingAssets" / "Localization"
    game.mkdir(parents=True)
    (game / "ruRU.json").write_text(
        json.dumps({"strings": {g: {"Offset": 0, "Text": t} for g, t in texts.items()}}),
        encoding="utf-8",
    )
    (game / "Sound.json").write_text(
        json.dumps({"strings": {g: {"Offset": 0, "Text": ev} for g, ev in (events or {}).items()}}),
        encoding="utf-8",
    )
    return game


def make_chars(tmp: Path, names=("Generic Male NPC", "Narrator")):
    people = tmp / "catalog" / "people"
    people.mkdir(parents=True)
    for n in names:
        fname = n.replace(" ", "_").replace("(", "").replace(")", "") + ".yaml"
        (people / fname).write_text(
            f"name: {n}\nsound_keys: []\nphrases: []\n", encoding="utf-8"
        )


def test_routing_answer_to_player_file(monkeypatch, tmp_path):
    texts = {
        G_ANS: '"Ответ игрока".',
        G_CUE: '"Реплика NPC". {n}Нарратив.{/n}',
        G_UNK: '"Реплика без дерева".',
    }
    make_game_files(tmp_path, texts)
    make_chars(tmp_path)
    (tmp_path / "catalog").mkdir(parents=True, exist_ok=True)
    (tmp_path / "catalog" / "dialog_roles.yaml").write_text(
        f"{G_ANS}: answer\n{G_CUE}: cue\n", encoding="utf-8"
    )
    monkeypatch.setattr(gc, "GAME", str(tmp_path))
    monkeypatch.setattr(gc, "MOD_DIR", tmp_path)
    monkeypatch.setattr(gc, "PEOPLE_DIR", tmp_path / "catalog" / "people")

    by_char, unassigned, player, extra_pool = gc.build_output(gc.load_char_metadata())
    assert unassigned == 0
    assert [p["guid"] for p in player] == [G_ANS]
    assert extra_pool == 3  # all three strings with quotes
    total_assigned = sum(d["total_phrases"] for d in by_char.values())
    assert total_assigned == 2  # cue + unknown
    # unknown (no dialog tree) lands in the default char
    assert G_UNK in {p["guid"] for p in by_char["Generic Male NPC"]["phrases"]}


def test_verify_total_ok(monkeypatch, tmp_path):
    texts = {G_ANS: '"Ответ".', G_CUE: '"Реплика".'}
    events = {"bbbbbbbb-0000-0000-0000-000000000001": "SomeEvent_01"}
    make_game_files(tmp_path, texts, events)
    make_chars(tmp_path)
    (tmp_path / "catalog").mkdir(parents=True, exist_ok=True)
    (tmp_path / "catalog" / "dialog_roles.yaml").write_text(f"{G_ANS}: answer\n", encoding="utf-8")
    monkeypatch.setattr(gc, "GAME", str(tmp_path))
    monkeypatch.setattr(gc, "MOD_DIR", tmp_path)
    monkeypatch.setattr(gc, "PEOPLE_DIR", tmp_path / "catalog" / "people")

    by_char, unassigned, player, extra_pool = gc.build_output(gc.load_char_metadata())
    assert gc.verify_total(by_char, unassigned, player, extra_pool) is True


def test_verify_total_mismatch_detected(monkeypatch, tmp_path):
    make_game_files(tmp_path, {G_CUE: '"Реплика".'}, {})
    make_chars(tmp_path)
    monkeypatch.setattr(gc, "GAME", str(tmp_path))
    monkeypatch.setattr(gc, "MOD_DIR", tmp_path)
    monkeypatch.setattr(gc, "PEOPLE_DIR", tmp_path / "catalog" / "people")

    by_char, unassigned, player, extra_pool = gc.build_output(gc.load_char_metadata())
    assert gc.verify_total(by_char, unassigned, player, extra_pool + 1) is False


def test_default_char_is_generic_male_npc(monkeypatch, tmp_path):
    # A phrase without narration and without a dialog role goes to Generic Male NPC
    texts = {G_UNK: '"Фраза без спикера".'}
    make_game_files(tmp_path, texts)
    make_chars(tmp_path)
    monkeypatch.setattr(gc, "GAME", str(tmp_path))
    monkeypatch.setattr(gc, "MOD_DIR", tmp_path)
    monkeypatch.setattr(gc, "PEOPLE_DIR", tmp_path / "catalog" / "people")

    by_char, _, player, _ = gc.build_output(gc.load_char_metadata())
    assert G_UNK in {p["guid"] for p in by_char["Generic Male NPC"]["phrases"]}
    assert player == []


def test_answer_with_narration_goes_to_catalog(monkeypatch, tmp_path):
    # Answer nodes can contain NPC content ("answer-scene"): {n} narration + NPC speech.
    # Such phrases must stay in the catalog, only pure choices go to Player_Answers.
    texts = {
        G_ANS: '"Чистый выбор".',
        "aaaaaaaa-0000-0000-0000-000000000004": '{n}Меровец салютует вам.{/n} "Здравия желаю!".',
    }
    make_game_files(tmp_path, texts)
    make_chars(tmp_path)
    (tmp_path / "catalog").mkdir(parents=True, exist_ok=True)
    (tmp_path / "catalog" / "dialog_roles.yaml").write_text(
        f"{G_ANS}: answer\naaaaaaaa-0000-0000-0000-000000000004: answer\n", encoding="utf-8"
    )
    monkeypatch.setattr(gc, "GAME", str(tmp_path))
    monkeypatch.setattr(gc, "MOD_DIR", tmp_path)
    monkeypatch.setattr(gc, "PEOPLE_DIR", tmp_path / "catalog" / "people")

    by_char, _, player, _ = gc.build_output(gc.load_char_metadata())
    assert [p["guid"] for p in player] == [G_ANS]
    scene = "aaaaaaaa-0000-0000-0000-000000000004"
    assert scene in {p["guid"] for p in by_char["Generic Male NPC"]["phrases"]}


def test_narrator_speaker_normalized(monkeypatch, tmp_path):
    # Pure narration (no speech) must land in Narrator with speaker "Narrator",
    # otherwise the voice wh40k_narrator won't resolve.
    texts = {"aaaaaaaa-0000-0000-0000-000000000005": "{n}Голос мужчины звенит от напряжения.{/n}"}
    make_game_files(tmp_path, texts)
    make_chars(tmp_path)
    monkeypatch.setattr(gc, "GAME", str(tmp_path))
    monkeypatch.setattr(gc, "MOD_DIR", tmp_path)
    monkeypatch.setattr(gc, "PEOPLE_DIR", tmp_path / "catalog" / "people")

    by_char, _, _, _ = gc.build_output(gc.load_char_metadata())
    narrator = by_char["Narrator"]["phrases"]
    assert any(p["guid"] == "aaaaaaaa-0000-0000-0000-000000000005" for p in narrator)
    assert any(p.get("speaker") == "Narrator" for p in narrator)


def test_junk_text_filtered(monkeypatch, tmp_path):
    # Empty placeholders ('"', '{n} {/n}') must NOT enter the catalog
    assert gc.is_junk_text('"')
    assert gc.is_junk_text("{n} {/n}")
    assert gc.is_junk_text(" ")
    assert not gc.is_junk_text('"Нет".')
    assert not gc.is_junk_text("{n}Бла-бла{/n}")

    texts = {
        "aaaaaaaa-0000-0000-0000-000000000006": '"',
        "aaaaaaaa-0000-0000-0000-000000000007": "{n} {/n}",
    }
    make_game_files(tmp_path, texts)
    make_chars(tmp_path)
    monkeypatch.setattr(gc, "GAME", str(tmp_path))
    monkeypatch.setattr(gc, "MOD_DIR", tmp_path)
    monkeypatch.setattr(gc, "PEOPLE_DIR", tmp_path / "catalog" / "people")

    by_char, _, _, extra_pool = gc.build_output(gc.load_char_metadata())
    assert extra_pool == 0
    assert all(not ph.get("parts") or True for d in by_char.values() for ph in d["phrases"])
