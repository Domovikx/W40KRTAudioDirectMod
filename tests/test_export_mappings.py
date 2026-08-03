"""Tests for tools/export_mappings.py — mappings.json generation."""

import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import export_mappings  # noqa: E402

G1 = "11111111-1111-1111-1111-111111111111"
G2 = "22222222-2222-2222-2222-222222222222"
G3 = "33333333-3333-3333-3333-333333333333"


def make_catalog(tmp: Path):
    people = tmp / "catalog" / "people"
    people.mkdir(parents=True)
    (people / "Npc.yaml").write_text(
        f"""
name: Npc
phrases:
  - guid: {G1}
    text: '"Первая фраза". {{n}}Нарратив.{{/n}}'
    parts:
      - speaker: Npc
        text_clean: 'Первая фраза.'
      - speaker: narrator
        text_clean: 'Нарратив.'
  - guid: {G2}
    text: '"Вторая фраза".'
    parts:
      - speaker: Npc
        text_clean: 'Вторая фраза.'
""",
        encoding="utf-8",
    )
    (people / "Player_Answers.yaml").write_text(
        f"""
name: Player Answers
skip_voicing: true
phrases:
  - guid: {G3}
    text: '"Ответ игрока".'
    parts:
      - speaker: Player
        text_clean: 'Ответ игрока.'
""",
        encoding="utf-8",
    )
    # phrase-level skip in a normal file
    (people / "Skipped.yaml").write_text(
        """
name: Skipped
phrases:
  - guid: 44444444-4444-4444-4444-444444444444
    text: '"Скипнутая фраза".'
    skip_voicing: true
    parts:
      - speaker: Npc
        text_clean: 'Скипнутая фраза.'
""",
        encoding="utf-8",
    )


def make_wavs(tmp: Path):
    lang = tmp / "Localization" / "ruRU"
    (lang / "Npc").mkdir(parents=True)
    (lang / "Npc" / f"{G1}.wav").write_bytes(b"RIFF")
    (lang / "Npc" / f"{G2}.wav").write_bytes(b"RIFF")
    (lang / "Npc" / f"{G3}.wav").write_bytes(b"RIFF")  # player answer wav exists but must be excluded
    (lang / "Npc" / "44444444-4444-4444-4444-444444444444.wav").write_bytes(b"RIFF")  # phrase-level skip


def load_entries(tmp: Path) -> list[dict]:
    with open(tmp / "Localization" / "ruRU" / "mappings.json", encoding="utf-8") as f:
        return json.load(f)["entries"]


def test_export_parts_and_whole(monkeypatch, tmp_path):
    make_catalog(tmp_path)
    make_wavs(tmp_path)
    monkeypatch.setattr(export_mappings, "ROOT", tmp_path)

    n, skipped = export_mappings.export()
    entries = load_entries(tmp_path)

    texts = [e["t"] for e in entries]
    # per-part entries
    assert "Первая фраза." in texts
    assert "Нарратив." in texts
    assert "Вторая фраза." in texts
    # whole-phrase entry (parts joined)
    assert "Первая фраза. Нарратив." in texts
    # player answer excluded by file-level skip
    assert "Ответ игрока." not in texts
    # phrase-level skip excluded
    assert "Скипнутая фраза." not in texts
    assert skipped == 2


def test_export_dedupe_by_text(monkeypatch, tmp_path):
    make_catalog(tmp_path)
    make_wavs(tmp_path)
    monkeypatch.setattr(export_mappings, "ROOT", tmp_path)
    export_mappings.export()
    entries = load_entries(tmp_path)
    texts = [e["t"] for e in entries]
    assert len(texts) == len(set(texts))


def test_export_missing_phrase_ignored(monkeypatch, tmp_path):
    make_catalog(tmp_path)
    make_wavs(tmp_path)
    (tmp_path / "Localization" / "ruRU" / "Npc" / "99999999-9999-9999-9999-999999999999.wav").write_bytes(b"RIFF")
    monkeypatch.setattr(export_mappings, "ROOT", tmp_path)
    n, _ = export_mappings.export()
    entries = load_entries(tmp_path)
    assert len(entries) == n
