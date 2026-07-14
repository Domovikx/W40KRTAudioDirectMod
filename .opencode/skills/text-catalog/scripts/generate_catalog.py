#!/usr/bin/env python3
"""
Generate per-character YAML phrase catalogs.

Reads Sound.json + ruRU.json + config/characters.yaml (or existing catalog/people/*.yaml
for metadata if characters.yaml is absent).

Outputs:
    catalog/people/  -- one YAML per character (metadata + phrases)
    catalog/index.yaml -- summary table

Usage:
    python generate_catalog.py
    python generate_catalog.py --verify-only
"""

from __future__ import annotations
import argparse, json, sys, yaml
from collections import defaultdict
from pathlib import Path
from datetime import date

GAME = "C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40,000 Rogue Trader"
MOD_DIR = Path(__file__).parent.parent.parent.parent.parent
CHAR_YAML = MOD_DIR / "config" / "characters.yaml"
PEOPLE_DIR = MOD_DIR / "catalog" / "people"
INDEX_PATH = MOD_DIR / "catalog" / "index.yaml"


def load_sound_json() -> dict[str, str]:
    path = Path(GAME) / "WH40KRT_Data" / "StreamingAssets" / "Localization" / "Sound.json"
    with open(path, encoding="utf-8") as f:
        return {guid: e["Text"] for guid, e in json.load(f)["strings"].items()}


def load_texts(lang: str = "ruRU") -> dict[str, str]:
    path = Path(GAME) / "WH40KRT_Data" / "StreamingAssets" / "Localization" / f"{lang}.json"
    with open(path, encoding="utf-8") as f:
        return {guid: e["Text"] for guid, e in json.load(f)["strings"].items()}


def load_char_metadata() -> list[dict]:
    """Load character metadata: prefer characters.yaml, fallback to catalog/people/."""
    if CHAR_YAML.exists():
        with open(CHAR_YAML, encoding="utf-8") as f:
            return yaml.safe_load(f)["characters"]
    if PEOPLE_DIR.exists():
        chars = []
        for path in sorted(PEOPLE_DIR.glob("*.yaml")):
            if path.stem == "catalog_index":
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


def key_position(key: str, event_name: str) -> int:
    idx = event_name.find(key)
    return idx if idx >= 0 else 999999


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

    by_char = {}
    for c in chars:
        name = c["name"]
        by_char[name] = {
            "name": name,
            "gender": c.get("gender", "?"),
            "role": c.get("role", ""),
            "age": c.get("age", ""),
            "personality": c.get("personality", ""),
            "voice": c.get("voice", "aidar"),
            "gemini_voice": c.get("gemini_voice", "Charon"),
            "sound_keys": c.get("sound_keys", []),
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
            by_char[name]["phrases"].append({"guid": guid, "event": event_name, "text": text})
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
            "gender": data["gender"],
            "role": data["role"],
            "voice": data["voice"],
            "gemini_voice": data["gemini_voice"],
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
        print("ERROR: No character metadata found (missing characters.yaml and catalog/people/)")
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
