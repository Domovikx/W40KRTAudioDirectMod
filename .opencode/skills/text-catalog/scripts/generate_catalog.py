#!/usr/bin/env python3
"""
Generate per-character YAML phrase catalogs.

Reads Sound.json + ruRU.json + config/characters.yaml (or existing
Localization/ruRU/people/*.yaml for metadata if characters.yaml is absent).

Outputs:
    Localization/ruRU/people/  -- one YAML per character (metadata + phrases)
    Localization/ruRU/people/index.yaml -- summary table

Speaker auto-detection (two-stage):
    1. Parse Wwise event name (Sound.json) — extract character segment per
       prefix pattern (BNTRS, Companions, PRL, CH1-3, etc.). Covers ~95%.
    2. Fallback: parse {n}...{/n} narration blocks in dialog text — if a known
       character's name appears at the start of any narration block, that
       character is identified as the speaker.
    If neither method finds a speaker, it defaults to the file's character name.

Usage:
    python generate_catalog.py
    python generate_catalog.py --verify-only
"""

from __future__ import annotations
import argparse, json, re, sys, yaml
from collections import defaultdict
from pathlib import Path
from datetime import date

GAME = "C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40,000 Rogue Trader"
MOD_DIR = Path(__file__).parent.parent.parent.parent.parent
CHAR_YAML = MOD_DIR / "config" / "characters.yaml"
PEOPLE_DIR = MOD_DIR / "catalog" / "people"
INDEX_PATH = PEOPLE_DIR / "index.yaml"


def load_sound_json() -> dict[str, str]:
    path = Path(GAME) / "WH40KRT_Data" / "StreamingAssets" / "Localization" / "Sound.json"
    with open(path, encoding="utf-8") as f:
        return {guid: e["Text"] for guid, e in json.load(f)["strings"].items()}


def load_texts(lang: str = "ruRU") -> dict[str, str]:
    path = Path(GAME) / "WH40KRT_Data" / "StreamingAssets" / "Localization" / f"{lang}.json"
    with open(path, encoding="utf-8") as f:
        return {guid: e["Text"] for guid, e in json.load(f)["strings"].items()}


def load_char_metadata() -> list[dict]:
    """Load character metadata: prefer characters.yaml, fallback to Localization/ruRU/people/."""
    if CHAR_YAML.exists():
        with open(CHAR_YAML, encoding="utf-8") as f:
            return yaml.safe_load(f)["characters"]
    if PEOPLE_DIR.exists():
        chars = []
        for path in sorted(PEOPLE_DIR.glob("*.yaml")):
            if path.stem in ("index", "catalog_index"):
                continue
            with open(path, encoding="utf-8") as f:
                chars.append(yaml.safe_load(f))
        return chars
    return []


def build_char_map(chars: list[dict]) -> dict[str, str]:
    m = {}
    for c in chars:
        for key in c.get("sound_keys", []):
            if key:
                m[key] = c["name"]
    return m


def build_speaker_aliases(chars: list[dict]) -> dict[str, str]:
    aliases = {}
    for c in chars:
        for key in c.get("sound_keys", []):
            if key:
                aliases[key.lower()] = c["name"]
    aliases["smugler"] = "Джаэ Хейдари"
    aliases["psyker"] = "Идира Тласс"
    aliases["sororitasq1"] = "Сестра Арджента"
    if "pasqal" in aliases and "pascal" in aliases:
        aliases["pasqal"] = aliases["pascal"]
    return aliases


def extract_speaker_from_event(event_name: str, aliases: dict[str, str]) -> str | None:
    parts = event_name.split("_")
    if not parts:
        return None

    prefix = parts[0]

    if prefix in ("NARR", "speaker", "DeathCultIntroduction"):
        return None

    def _try(segment: str) -> str | None:
        return aliases.get(segment.lower())

    candidates: list[str] = []

    if prefix == "BNTRS":
        if len(parts) >= 5 and parts[1] in ("Companion", "Reactivity") and parts[2] == "DLC3":
            candidates.append(parts[3])
        elif len(parts) >= 4:
            candidates.append(parts[2])

    elif prefix == "Companions":
        if len(parts) >= 2:
            candidates.append(parts[1])

    elif prefix == "CompanionDialogue":
        if len(parts) >= 2:
            candidates.append(parts[1])

    elif prefix in ("PRL", "CH1", "CH2", "CH3"):
        if len(parts) >= 2:
            for seg in parts[1:]:
                if _try(seg):
                    candidates.append(seg)
                    break

    elif prefix == "RMNC":
        for seg in parts[1:]:
            if _try(seg):
                candidates.append(seg)
                break
        else:
            for seg in parts[1:]:
                seg_lower = seg.lower()
                for key in aliases:
                    if key in seg_lower:
                        candidates.append(seg)
                        break
                if candidates:
                    break

    elif prefix in ("BS", "RM"):
        if len(parts) >= 3:
            candidates.append(parts[2])

    elif prefix in ("OfficialPropos", "ManipulusFirstMeet",
                     "TrazynOffer", "TrazynFirstMeet", "TrazynInYourRoom",
                     "TrazynShowdown", "TrazynAfterOffer", "ArbitesAfterSex"):
        if len(parts) >= 2:
            candidates.append(parts[1])

    elif prefix == "Solomorn":
        r = _try("solomorne") or _try("solomorn")
        if r:
            return r

    for c in candidates:
        r = _try(c)
        if r:
            return r

    return None


def build_name_to_char(chars: list[dict]) -> dict[str, str]:
    """Build {first_name → full_name} + {last_name → full_name} lookup."""
    m = {}
    for c in chars:
        name = c["name"]
        parts = name.split()
        if parts:
            m[parts[0]] = name          # first name
        if len(parts) > 1:
            m[parts[-1]] = name         # last name
        # Also add full name as-is
        m[name] = name
    # Hardcoded aliases for generic NPC roles
    m["Архмилитант"] = "__NPC__"
    m["Морт"] = "__NPC__"
    m["Мастер шепотов"] = "__NPC__"
    # Role → specific character mappings (specific chars only, not generic NPCs)
    role_map: dict[str, str] = {}
    for c in chars:
        name = c["name"]
        role = c.get("role", "")
        if "NPC" in name:
            continue
        rl = role.lower()
        if "сенешаль" in rl:
            role_map["Сенешаль"] = name
            role_map["сенешаль"] = name
            role_map["сенешаля"] = name
        if "интеррогатор" in rl:
            role_map["дознаватель"] = name
            role_map["Дознаватель"] = name
            role_map["Интеррогатор"] = name
            role_map["интеррогатор"] = name
    m.update(role_map)
    return m


def _split_segments(raw: str) -> list[tuple[str, bool]]:
    """Split text into (segment, is_narrator) pairs."""
    results: list[tuple[str, bool]] = []
    pattern = re.compile(r"\{n\}(.*?)\{/n\}", re.DOTALL)
    pos = 0
    for m in pattern.finditer(raw):
        before = raw[pos : m.start()]
        if before.strip():
            results.append((before, False))
        results.append((m.group(1), True))
        pos = m.end()
    after = raw[pos:]
    if after.strip():
        results.append((after, False))
    if not results:
        results.append((raw, False))
    return results


def detect_speaker(text: str, name_map: dict[str, str], char_name: str = "") -> str | None:
    """Detect speaker from {n}...{/n} narration blocks.

    1. If a narration block starts with a known name → that's the speaker.
    2. If non-narrator text addresses the YAML owner (\"Леди {name}\", \"{name}, ...\")
       → search narrator blocks for any known character name; return first found.
    """
    segments = _split_segments(text)
    narrator_blocks = [s for s, is_narr in segments if is_narr]
    non_narrator_parts = [s for s, is_narr in segments if not is_narr]

    if not narrator_blocks:
        return None

    # Step 1: narrator starts with a character name
    counts: dict[str, int] = {}
    for block in narrator_blocks:
        stripped = block.strip()
        for token, cn in name_map.items():
            if stripped.startswith(token):
                counts[cn] = counts.get(cn, 0) + 1
                break
    if counts:
        best = max(counts, key=counts.get)
        return best

    if not char_name:
        return None

    # Step 2: check if non-narrator text addresses the YAML owner
    char_first = char_name.split()[0]

    def _text_addresses_owner(seg: str) -> bool:
        clean = seg.strip().strip("\"").strip("\u201d").strip("\u201c").strip("\u00ab").strip("\u00bb")
        if f"Леди {char_first}" in clean:
            return True
        if clean.startswith(char_first) and len(clean) > len(char_first) and not clean.startswith(char_first + " " + char_first.split()[-1] if len(char_name.split()) > 1 else ""):
            return True
        return False

    addressed = any(_text_addresses_owner(np) for np in non_narrator_parts)
    if not addressed:
        return None

    # Guard: if narrator mentions YAML owner speaking, it's self-reference (Ulfar case)
    for block in narrator_blocks:
        bl = block.lower()
        for token, cn in name_map.items():
            if cn == char_name and len(token) > 2 and token.lower() in bl:
                return None

    # Search all narrator blocks for ANY other character name
    for block in narrator_blocks:
        bl = block.lower()
        for token, cn in name_map.items():
            if cn == char_name:
                continue
            if len(token) > 2 and token.lower() in bl:
                return cn

    # Keyword fallback: unique character descriptors in narrator blocks
    keyword_map = {
        "синт-кож": "Сенешаль",
        "синт кож": "Сенешаль",
    }
    for block in narrator_blocks:
        bl = block.lower()
        for kw, role in keyword_map.items():
            if kw in bl and role in name_map:
                cn = name_map[role]
                if cn != char_name:
                    return cn

    return None


def resolve_character(
    event_name: str, char_map: dict[str, str], chars: list[dict]
) -> tuple[str | None, dict | None]:
    candidates = []
    for key, name in char_map.items():
        if key in event_name:
            candidates.append((len(key), -event_name.find(key), key, name))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    if candidates:
        name = candidates[0][3]
        for c in chars:
            if c["name"] == name:
                return name, c
        return name, None
    for c in chars:
        if c["name"] == "NPC (по умолчанию)":
            return c["name"], c
    return None, None


def build_output(chars: list[dict]) -> tuple[dict[str, dict], int]:
    events = load_sound_json()
    texts = load_texts()
    char_map = build_char_map(chars)

    name_map = build_name_to_char(chars)
    speaker_aliases = build_speaker_aliases(chars)
    by_char = {}
    for c in chars:
        name = c["name"]
        safe = name.replace(" ", "_").replace("(", "").replace(")", "")
        by_char[name] = {
            "name": name,
            "sound_keys": c.get("sound_keys", []),
            "doc": f"docs/characters/{safe}.md",
            "total_phrases": 0,
            "phrases": [],
        }

    unassigned = 0

    for guid, event_name in sorted(events.items(), key=lambda x: x[1]):
        if guid not in texts:
            continue
        text = texts[guid]
        if len(text) < 3:
            continue

        name, _ = resolve_character(event_name, char_map, chars)
        if name:
            speaker = extract_speaker_from_event(event_name, speaker_aliases)
            if not speaker:
                speaker = detect_speaker(text, name_map, char_name=name)
            if not speaker or speaker == "__NPC__":
                speaker = name  # default to file owner

            if speaker == "__NPC__":
                speaker = None
            phrase = {
                "guid": guid,
                "event": event_name,
                "text": text,
                "speaker": speaker,
            }
            by_char[name]["phrases"].append(phrase)
            by_char[name]["total_phrases"] += 1
        else:
            unassigned += 1

    return by_char, unassigned


def write_people(by_char: dict[str, dict]):
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(by_char.items()):
        safe = name.replace(" ", "_").replace("(", "").replace(")", "")
        path = PEOPLE_DIR / f"{safe}.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, indent=2,
                      sort_keys=False, default_flow_style=False, width=120)
    print(f"Written {len(by_char)} files to {PEOPLE_DIR}/")


def write_index(by_char: dict[str, dict], unassigned: int):
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    total = 0
    for name, data in sorted(by_char.items()):
        entries.append({
            "name": name,
            "doc": data.get("doc", ""),
            "total_phrases": data["total_phrases"],
        })
        total += data["total_phrases"]
    index_data = {
        "generated": str(date.today()),
        "total_characters": len(by_char),
        "total_phrases": total + unassigned,
        "unassigned": unassigned,
        "characters": entries,
    }
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        yaml.dump(index_data, f, allow_unicode=True, indent=2,
                  sort_keys=False, default_flow_style=False)
    print(f"Index: {INDEX_PATH}")


def verify_total(by_char: dict[str, dict], unassigned: int) -> bool:
    events = load_sound_json()
    total_in_events = len(events)
    total_assigned = sum(d["total_phrases"] for d in by_char.values())
    grand = total_assigned + unassigned
    print(f"\nSound.json: {total_in_events} entries")
    print(f"Assigned:   {total_assigned}")
    print(f"Unassigned: {unassigned}")
    print(f"Total:      {grand}")
    if grand != total_in_events:
        print(f"!! MISMATCH: expected {total_in_events}, got {grand}")
        return False
    print("OK - All good -- every event is assigned to a character")
    return True


def main():
    p = argparse.ArgumentParser(description="Generate per-character YAML catalogs")
    p.add_argument("--verify-only", action="store_true",
                   help="Just verify counts against Sound.json, don't write")
    args = p.parse_args()

    chars = load_char_metadata()
    if not chars:
        print("ERROR: No character metadata found (missing characters.yaml and Localization/ruRU/people/)")
        sys.exit(1)

    by_char, unassigned = build_output(chars)

    if args.verify_only:
        ok = verify_total(by_char, unassigned)
        sys.exit(0 if ok else 1)

    write_people(by_char)
    write_index(by_char, unassigned)
    verify_total(by_char, unassigned)


if __name__ == "__main__":
    main()
