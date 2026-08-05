"""Tests for the gender-review pipeline (М/Ж checks) and its YAML invariants.

Run:  python -m pytest tools/test_gender_review.py -v
"""

import os, sys
import yaml
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_VOICES = ROOT / "config" / "voices.yaml"
CATALOG_DIR = ROOT / "catalog" / "people"


@pytest.fixture(scope="session")
def voices_config():
    with open(CONFIG_VOICES, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def catalog():
    data = {}
    for yaml_path in sorted(CATALOG_DIR.glob("*.yaml")):
        if yaml_path.name == "index.yaml":
            continue
        with open(yaml_path, encoding="utf-8") as f:
            data[yaml_path.stem] = yaml.safe_load(f)
    return data


def normalize_name(name: str) -> str:
    return name.lower().replace("_", " ").replace("-", " ").strip()


def resolve_speaker(speaker, voices_config):
    """Mirrors qwen3_full_icl.resolve_speaker_to_voice logic."""
    norm = normalize_name(speaker)
    if norm == "narrator":
        for vn, ref in voices_config.get("references", {}).items():
            for c in ref.get("characters", []):
                if normalize_name(c) == "narrator":
                    return vn
        return None
    for vn, ref in voices_config.get("references", {}).items():
        for c in ref.get("characters", []):
            nc = normalize_name(c)
            if norm == nc or norm in nc or nc in norm:
                return vn
    return None


def voice_gender(voice, voices_config):
    return voices_config.get("references", {}).get(voice, {}).get("gender")


# ── voices.yaml invariants ────────────────────────────────────────────────

def test_every_voice_has_gender(voices_config):
    missing = []
    for vname, ref in voices_config.get("references", {}).items():
        g = ref.get("gender")
        if g not in ("male", "female"):
            missing.append(f"{vname}: gender={g!r}")
    assert not missing, f"Voices without proper gender:\n" + "\n".join(missing)


def test_voice_gender_spot_checks(voices_config):
    expect = {
        "wh40k_narrator": "male",  # Narrator.wav — мужской голос
        "kunrad": "male",
        "teodora": "female",
        "jae": "female",
        "default_male": "male",
        "default_female": "female",
    }
    for vname, want in expect.items():
        got = voice_gender(vname, voices_config)
        assert got == want, f"{vname}: expected {want}, got {got}"


# ── catalog invariants ────────────────────────────────────────────────────

def test_speaker_overrides_resolve(voices_config, catalog):
    """Every speaker_override must resolve to a voice with a known gender."""
    bad = []
    for char_name, char_data in catalog.items():
        for phrase in char_data.get("phrases", []):
            for part in phrase.get("parts", []):
                ov = part.get("speaker_override", "")
                if not ov:
                    continue
                voice = resolve_speaker(ov, voices_config)
                if voice is None:
                    bad.append(f"{char_name}: override '{ov}' -> no voice")
                elif voice_gender(voice, voices_config) is None:
                    bad.append(f"{char_name}: override '{ov}' -> voice {voice} has no gender")
    assert not bad, f"Bad speaker_overrides:\n" + "\n".join(bad)


def test_review_flags_wellformed(catalog):
    """review_gender must be REVIEW|OK; REVIEW must carry a review_note."""
    bad = []
    for char_name, char_data in catalog.items():
        for phrase in char_data.get("phrases", []):
            rg = phrase.get("review_gender")
            if rg is None:
                continue
            if rg not in ("REVIEW", "OK"):
                bad.append(f"{char_name}/{phrase.get('guid')}: review_gender={rg!r}")
            elif rg == "REVIEW" and not phrase.get("review_note"):
                bad.append(f"{char_name}/{phrase.get('guid')}: REVIEW без review_note")
    assert not bad, f"Malformed review flags:\n" + "\n".join(bad)


def test_need_regen_wellformed(catalog):
    """need_regen: true on a phrase implies it is NOT skip_voicing."""
    bad = []
    for char_name, char_data in catalog.items():
        for phrase in char_data.get("phrases", []):
            nr = phrase.get("need_regen")
            if nr is None:
                continue
            if nr is not True:
                bad.append(f"{char_name}/{phrase.get('guid')}: need_regen={nr!r}")
            elif char_data.get("skip_voicing"):
                bad.append(f"{char_name}/{phrase.get('guid')}: need_regen на skip_voicing-файле")
    assert not bad, f"Malformed need_regen:\n" + "\n".join(bad)


# ── Smuggler.yaml regression (известный баг: женские реплики Джай под мужским голосом) ──

SMUGGLER_FIXED = {
    "0d772691-09ef-493f-8719-7755d9761e8f": {"Jae Heydari"},
    "ceaceb13-bd02-4cc4-b6dd-465ba5ed15ac": {"Jae Heydari"},
    "cf017f15-9ba5-4611-8619-d24907285cac": {"Jae Heydari"},
}


def test_smuggler_jae_fix(catalog):
    """Все Smuggler-части в этих фразах должны иметь speaker_override: Jae Heydari."""
    smug = catalog.get("Smuggler")
    assert smug is not None, "Smuggler.yaml отсутствует"
    by_guid = {p["guid"]: p for p in smug.get("phrases", [])}
    for guid, want_ov in SMUGGLER_FIXED.items():
        phrase = by_guid.get(guid)
        assert phrase is not None, f"{guid} не найден в Smuggler.yaml"
        smug_parts = [pp for pp in phrase.get("parts", [])
                      if (pp.get("speaker") or "").lower().strip() == "smuggler"]
        assert smug_parts, f"{guid}: нет частей со speaker=Smuggler"
        for pp in smug_parts:
            assert pp.get("speaker_override") in want_ov, \
                f"{guid}: часть без правильного speaker_override: {pp.get('speaker_override')}"


def test_smuggler_no_pending_flags(catalog):
    """Smuggler.yaml решён: ни REVIEW, ни need_regen не должно остаться."""
    smug = catalog.get("Smuggler")
    leftover = []
    for phrase in smug.get("phrases", []):
        if phrase.get("review_gender") or phrase.get("need_regen"):
            leftover.append(f"{phrase['guid']}: {phrase.get('review_gender')} {phrase.get('need_regen')}")
    assert not leftover, f"Незакрытые флаги в Smuggler.yaml:\n" + "\n".join(leftover)
