"""Tests for TTS generation pipeline integrity.

Run:  python -m pytest tools/test_pipeline.py -v
"""

import os, sys
import yaml
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_VOICES = ROOT / "config" / "voices.yaml"
CATALOG_DIR = ROOT / "catalog" / "people"
PARTS_DIR = ROOT / "output" / "full_icl"
LOCALIZATION_DIR = ROOT / "Localization"


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


def load_name_map() -> dict:
    """Load Russian aliases + title aliases from config."""
    path = ROOT / "config" / "name_map.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    result = {}
    for section in ("ru_aliases", "title_aliases", "ru_full_names"):
        result.update(data.get(section, {}))
    return result


NAME_MAP = load_name_map()


def resolve_speaker(speaker, voices_config):
    """Mirrors qwen3_full_icl.resolve_speaker_to_voice logic."""
    # Resolve Russian/title aliases to English names
    if speaker in NAME_MAP:
        speaker = NAME_MAP[speaker]
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


def test_all_ref_wavs_exist(voices_config):
    missing = []
    for vname, ref in voices_config.get("references", {}).items():
        wav_path = ROOT / ref["wav"]
        if not wav_path.exists():
            missing.append(f"{vname}: {ref['wav']}")
    assert not missing, f"Missing ref WAVs:\n" + "\n".join(missing)


def test_all_speakers_resolve(voices_config, catalog):
    unmapped = set()
    for char_name, char_data in catalog.items():
        for phrase in char_data.get("phrases", []):
            for part in phrase.get("parts", []):
                speaker = part.get("speaker_override") or part.get("speaker", "")
                if not speaker:
                    continue
                voice = resolve_speaker(speaker, voices_config)
                if voice is None:
                    unmapped.add(f"{char_name}: speaker '{speaker}'")
    assert not unmapped, f"Unmapped speakers:\n" + "\n".join(sorted(unmapped))


def test_no_ambiguous_speakers(voices_config, catalog):
    all_speakers = set()
    for _, char_data in catalog.items():
        for phrase in char_data.get("phrases", []):
            for part in phrase.get("parts", []):
                s = part.get("speaker", "")
                if s:
                    all_speakers.add(s)
    ambiguous = []
    for speaker in sorted(all_speakers):
        matches = []
        for vn, ref in voices_config.get("references", {}).items():
            for c in ref.get("characters", []):
                if normalize_name(speaker) == normalize_name(c):
                    matches.append(vn)
        unique = list(set(matches))
        if len(unique) > 1:
            ambiguous.append(f"'{speaker}' -> {unique}")
    assert not ambiguous, f"Ambiguous speakers:\n" + "\n".join(ambiguous)


def test_no_stale_cached_parts(voices_config):
    voices_mtime = os.path.getmtime(CONFIG_VOICES)
    stale = []
    for vname, ref in voices_config.get("references", {}).items():
        voice_dir = PARTS_DIR / vname
        if not voice_dir.is_dir():
            continue
        ref_wav = ROOT / ref["wav"]
        ref_mtime = os.path.getmtime(ref_wav) if ref_wav.exists() else 0
        for wav_file in sorted(voice_dir.glob("*.wav")):
            part_mtime = os.path.getmtime(wav_file)
            if part_mtime < ref_mtime or part_mtime < voices_mtime:
                stale.append(f"{vname}/{wav_file.name}")
    assert not stale, (
        f"{len(stale)} stale cached parts:\n" + "\n".join(stale)
    )


def test_no_duplicate_guids(catalog):
    seen = {}
    dups = []
    for char_name, char_data in catalog.items():
        for phrase in char_data.get("phrases", []):
            guid = phrase.get("guid", "")
            if not guid:
                continue
            if guid in seen:
                dups.append(f"{guid} in {seen[guid]} AND {char_name}")
            else:
                seen[guid] = char_name
    assert not dups, f"Duplicate GUIDs:\n" + "\n".join(dups)


def test_final_wavs_have_parts(catalog):
    """Every merged WAV's GUID must exist in the catalog with parts defined.

    Part WAVs on disk are a transient cache (cleaned after concat) — the real
    integrity check is: merged wav GUID -> catalog phrase with non-empty parts.
    """
    guids = {}
    for char_name, char_data in catalog.items():
        for phrase in char_data.get("phrases", []):
            g = phrase.get("guid", "")
            if g and phrase.get("parts"):
                guids.setdefault(g, []).append(char_name)
    missing = []
    for lang_dir in LOCALIZATION_DIR.iterdir():
        if not lang_dir.is_dir():
            continue
        for char_dir in lang_dir.iterdir():
            if not char_dir.is_dir():
                continue
            for wav in char_dir.glob("*.wav"):
                guid = wav.stem
                if guid not in guids:
                    missing.append(f"{wav} — GUID not in catalog (or no parts)")
    assert not missing, "Orphan/stale merged WAVs:\n" + "\n".join(missing[:20])


def test_no_en_suffix_voices(voices_config):
    en_entries = [vn for vn in voices_config.get("references", {}) if vn.endswith("_en")]
    assert not en_entries, f"Remove legacy _en entries: {en_entries}"


def test_yaml_no_line_wrapping():
    """Verify all YAML text values are on single lines."""
    for yaml_path in sorted(CATALOG_DIR.glob("*.yaml")):
        if yaml_path.name == "index.yaml":
            continue
        with open(yaml_path, "r", encoding="utf-8") as f:
            content = f.read()
        lines = content.split("\n")
        problems = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("text:"):
                continue
            # Check if this line ends with quote (single or double)
            if stripped.endswith("'") or stripped.endswith('"'):
                continue
            # For unquoted scalars: check that next line isn't a continuation
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                # If next line starts with space+tilda or space+text (unquoted continuation)
                if next_line and next_line[0] in (' ', '\t') and not next_line.strip().startswith(('-', 'guid:', 'event:', 'speaker:', 'text:', 'text_clean:', 'parts:')):
                    problems.append(f"{yaml_path.name}:{i+1}")
        assert not problems, f"Text wrapping in:\n" + "\n".join(problems[:10])


def test_text_clean_no_formatting(catalog):
    """Verify text_clean has no newlines, double spaces, or leading/trailing whitespace."""
    problems = []
    for char_name, char_data in catalog.items():
        for phrase in char_data.get("phrases", []):
            guid = phrase.get("guid", "")
            for part in phrase.get("parts", []):
                tc = part.get("text_clean", "")
                if not tc:
                    continue
                if "\n" in tc:
                    problems.append(f"{char_name}/{guid}: newline")
                if "  " in tc:
                    problems.append(f"{char_name}/{guid}: double space")
                if tc != tc.strip():
                    problems.append(f"{char_name}/{guid}: whitespace")
    assert not problems, f"text_clean issues:\n" + "\n".join(problems[:20])


def test_no_gender_candidates():
    """Regression guard: feminine self-referential grammar must not sit on a male voice.

    Runs tools/scan_speaker_candidates.py over the whole catalog and fails if any
    GENDER candidate appears (e.g. a new female line added with default_male voice).
    """
    import sys
    from pathlib import Path
    tools_dir = str(ROOT / "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    from scan_speaker_candidates import scan_file, load_yaml, load_names

    voices = load_yaml(CONFIG_VOICES)
    names = load_names()
    issues = []
    for yaml_path in sorted(CATALOG_DIR.glob("*.yaml")):
        if yaml_path.name in ("index.yaml", "Player_Answers.yaml"):
            continue
        res = scan_file(str(yaml_path), names, voices)
        for c in res["candidates"]:
            if "GENDER" in c["flags"]:
                issues.append(f"{yaml_path.name}: {c['guid'][:8]} p{c['part']} "
                              f"{c['reason']} | {c['text'][:60]}")
    assert not issues, "GENDER candidates found:\n" + "\n".join(issues[:20])


def test_skill_frontmatter_valid():
    """Every .opencode/skills/*/SKILL.md must have parseable YAML frontmatter."""
    skills_dir = ROOT / ".opencode" / "skills"
    if not skills_dir.is_dir():
        return
    bad = []
    for md in sorted(skills_dir.glob("*/SKILL.md")):
        txt = md.read_text(encoding="utf-8")
        if not txt.startswith("---"):
            bad.append(f"{md.name}: no frontmatter")
            continue
        end = txt.find("\n---", 4)
        fm = txt[4:end] if end > 0 else txt[4:]
        try:
            import yaml as _yaml
            _yaml.safe_load(fm)
        except Exception as e:
            bad.append(f"{md.parent.name}: {e}")
    assert not bad, "Broken skill frontmatter:\n" + "\n".join(bad)
