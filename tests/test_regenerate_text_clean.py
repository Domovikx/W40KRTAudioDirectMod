"""Tests for regenerate_text_clean.py — parts regeneration for new phrases."""

import sys
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / ".opencode" / "skills" / "text-cleaner" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import regenerate_text_clean as rt  # noqa: E402

G = "11111111-1111-1111-1111-111111111111"


def make_yaml(tmp: Path, name: str, phrases, skip=False):
    p = tmp / f"{name}.yaml"
    data = {"name": name, "phrases": phrases}
    if skip:
        data["skip_voicing"] = True
    p.write_text(
        "name: %s\n%sphrases:\n" % (name, "skip_voicing: true\n" if skip else "")
        + "\n".join(
            f"  - guid: {ph['guid']}\n    text: '{ph['text']}'\n    speaker: {ph['speaker']}"
            for ph in phrases
        ),
        encoding="utf-8",
    )
    return p


def test_skip_voicing_file_untouched(tmp_path):
    path = make_yaml(tmp_path, "Player_Answers", [
        {"guid": G, "text": '"Ответ".', "speaker": "Player"},
    ], skip=True)
    stats = rt.regenerate_file(str(path), dry_run=False)
    assert stats["updated"] == 0
    assert stats["skipped"] == 1
    data = rt.load_yaml(str(path))
    assert data["phrases"][0].get("parts") is None  # untouched


def test_phrase_without_parts_gets_them(tmp_path):
    path = make_yaml(tmp_path, "Abelard_Werserian", [
        {"guid": G, "text": '{n}Абеляр одобрительно кивает.{/n} "Подходяще".', "speaker": "Abelard Werserian"},
    ])
    stats = rt.regenerate_file(str(path), dry_run=False)
    assert stats["updated"] == 1
    data = rt.load_yaml(str(path))
    parts = data["phrases"][0]["parts"]
    speakers = [p["speaker"] for p in parts]
    assert "narrator" in speakers  # narration split out
    assert any(s == "Abelard Werserian" for s in speakers)
    assert all(p["text_clean"] for p in parts)


def test_dry_run_writes_nothing(tmp_path):
    path = make_yaml(tmp_path, "Abelard_Werserian", [
        {"guid": G, "text": '"Подходяще".', "speaker": "Abelard Werserian"},
    ])
    before = path.read_text(encoding="utf-8")
    stats = rt.regenerate_file(str(path), dry_run=True)
    assert stats["updated"] == 1
    assert path.read_text(encoding="utf-8") == before


def test_speaker_override_preserved(tmp_path):
    # A part with speaker_override must survive parts regeneration
    yaml_text = (
        "name: Abelard_Werserian\n"
        "phrases:\n"
        "  - guid: " + G + "\n"
        "    text: '{n}Сервочереп разражается статикой.{/n} \"...верные сыны и дочери Бога-Императора, к оружию!\"'\n"
        "    speaker: Abelard Werserian\n"
        "    parts:\n"
        "    - speaker: narrator\n"
        "      text_clean: Сервочереп разражается статикой.\n"
        "    - speaker: Abelard Werserian\n"
        "      text_clean: '...верные сыны и дочери Бога-Императора, к оружию!'\n"
        "      speaker_override: Theodora von Valancius\n"
    )
    path = tmp_path / "Abelard_Werserian.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    stats = rt.regenerate_file(str(path), dry_run=False)
    assert stats["updated"] == 1
    data = rt.load_yaml(str(path))
    parts = data["phrases"][0]["parts"]
    overrides = [p.get("speaker_override") for p in parts if p.get("speaker_override")]
    assert "Theodora von Valancius" in overrides
