#!/usr/bin/env python3
"""Build catalog_2/people/ — a full, lossless partition of ALL ruRU.json GUIDs.

Every GUID from ruRU.json lands in exactly ONE of the category files, so the
invariant holds:

    sum(files) == len(ruRU.json) == 77691

If the game is updated and ruRU.json changes, the sum breaks -> the tests
detect it. No filtering by deletion — grouping only.

Routing chain (deterministic, order matters; first match wins):
    1. voiced    — GUID has a Wwise event (Sound.json)
    2. answer    — bbp role 'answer' (player choices)
    3. cue       — bbp role 'cue' (NPC dialog lines)
    4. bark      — blueprint owner matches bark|banter|randomphrase
    5. env       — env_scan.classify() accepts (object/adjective start, no
                   journal/encyclopedia markers, no markup, ends with '.')
    6. ui        — blueprint class in UI set (UIStrings/UISettings/KeyBinding/
                   ReasonStrings/GlossaryStrings)
    7. enc       — blueprint class Encyclopedia*/BookPage
    8. gamelog   — blueprint class GameLog*
    9. objective — dialog_owner Objective*/Obj* (quest objective nodes)
   10. narration — text contains {n} narrator blocks
   11. short     — len(text) < 40 (no signals at all)
   12. other     — everything left (markup, noise)

Environment entries are enriched from guid_map.json (blueprint_owner, scenes)
and carry parts [{speaker: narrator, text_clean}] ready for future TTS.
All other files are lean: guid + text.

Usage:
    python catalog_2/tools/build_partition.py            # build + validate
    python catalog_2/tools/build_partition.py --no-map   # skip guid_map enrich

Validation (exit 1 on failure):
    - sum(files) == len(ruRU.json)
    - no GUID appears twice
    - every ruRU GUID is in exactly one file
    - no foreign GUIDs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from env_scan import (  # noqa: E402
    MIN_LEN, RU_JSON, SOUND_JSON, classify, load_json_strs, load_sound_guids,
)
from text_normalize import normalize  # noqa: E402

GUID_MAP = ROOT / "catalog_2" / "raw" / "guid_map.json"
OUT_DIR = ROOT / "catalog_2" / "people"

UI_CLASS_MARKERS = ("UIStrings", "UISettings", "KeyBinding",
                    "ReasonStrings", "GlossaryStrings")
ENC_CLASS_MARKERS = ("Encyclopedia", "BookPage")
BARK_OWNER_RE = re.compile(r"bark|banter|randomphrase", re.I)

FILES = [
    ("VoicedDialog.yaml", "voiced",
     "GUID has a Wwise event (Sound.json) — voiced dialog line"),
    ("DialogAnswer.yaml", "answer",
     "bbp role 'answer' — player dialogue choices"),
    ("DialogCue.yaml", "cue",
     "bbp role 'cue' — NPC dialog lines"),
    ("Barks.yaml", "bark",
     "blueprint owner matches bark|banter|randomphrase — NPC barks"),
    ("Environment_Descriptions.yaml", "env",
     "env_scan.classify() accepted — object/location descriptions"),
    ("UI.yaml", "ui",
     "blueprint class in UI set (UIStrings/UISettings/KeyBinding/ReasonStrings/GlossaryStrings)"),
    ("Encyclopedia.yaml", "enc",
     "blueprint class Encyclopedia*/BookPage — codex articles"),
    ("GameLog.yaml", "gamelog",
     "blueprint class GameLog* — journal event entries"),
    ("Objectives.yaml", "objective",
     "dialog_owner Objective*/Obj* — quest objective nodes"),
    ("Narration.yaml", "narration",
     "text contains {n} narrator blocks"),
    ("Short.yaml", "short",
     f"len(text) < {MIN_LEN} — no signals at all"),
    ("Other.yaml", "other",
     "remainder: markup, noise, unrecognized"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def blueprint_info(entry: dict) -> dict:
    """Extract owner + scenes from a guid_map entry."""
    bp = (entry or {}).get("blueprint") or {}
    owner = bp.get("owner") or ""
    scenes = (entry or {}).get("scenes") or []
    return {"owner": owner, "scenes": scenes}


def make_phrase(guid: str, text: str) -> dict:
    return {"guid": guid, "text": text}


def make_env_phrase(guid: str, text: str, cand: dict, map_entry: dict) -> dict:
    phrase = {"guid": guid, "text": text,
              "category": cand["cat"],
              "reasons": cand.get("reasons", [])}
    info = blueprint_info(map_entry)
    if info["owner"]:
        phrase["blueprint_owner"] = info["owner"]
    if info["scenes"]:
        phrase["scenes"] = info["scenes"]
    phrase["parts"] = [{"speaker": "narrator",
                        "text_clean": normalize(text)}]
    return phrase


def write_yaml(path: Path, data: dict) -> bool:
    text = yaml.dump(data, allow_unicode=True, indent=2, sort_keys=False,
                     default_flow_style=False, width=65535)
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if text == old:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-map", action="store_true",
                    help="skip guid_map.json enrichment (env entries lean)")
    args = ap.parse_args()

    ru = load_json_strs(RU_JSON)
    sound = load_sound_guids(SOUND_JSON)
    guid_map = {} if args.no_map else json.load(
        open(GUID_MAP, encoding="utf-8"))

    def role(g: str) -> str:
        e = guid_map.get(g) or {}
        return (e.get("bbp") or {}).get("role") or ""

    def cls(g: str) -> str:
        e = guid_map.get(g) or {}
        return (e.get("blueprint") or {}).get("class") or ""

    def owner(g: str) -> str:
        e = guid_map.get(g) or {}
        return (e.get("blueprint") or {}).get("owner") or ""

    def dialog_owner(g: str) -> str:
        e = guid_map.get(g) or {}
        return (e.get("bbp") or {}).get("dialog_owner") or ""

    buckets: dict[str, list[dict]] = {name: [] for _, name, _ in FILES}
    pool = list(ru.keys())
    seen = set()
    for pos, guid in enumerate(pool):
        if guid in seen:
            continue
        seen.add(guid)
        text = ru[guid]
        if guid in sound:
            bucket = "voiced"
        elif role(guid) == "answer":
            bucket = "answer"
        elif role(guid) == "cue":
            bucket = "cue"
        elif BARK_OWNER_RE.search(owner(guid)):
            bucket = "bark"
        else:
            c = classify(text, pos, sound, guid, {})
            if isinstance(c, dict):
                bucket = "env"
            elif any(k in cls(guid) for k in UI_CLASS_MARKERS):
                bucket = "ui"
            elif any(k in cls(guid) for k in ENC_CLASS_MARKERS):
                bucket = "enc"
            elif "GameLog" in cls(guid):
                bucket = "gamelog"
            elif (dialog_owner(guid).startswith(("Objectiv", "Obj"))
                  or "Objective" in cls(guid)):
                bucket = "objective"
            elif "{n}" in text:
                bucket = "narration"
            elif len(text) < MIN_LEN:
                bucket = "short"
            else:
                bucket = "other"
        if bucket == "env" and not args.no_map:
            phrase = make_env_phrase(guid, text, c, guid_map.get(guid))
        else:
            phrase = make_phrase(guid, text)
        buckets[bucket].append(phrase)

    for fname, bucket, rule in FILES:
        phrases = sorted(buckets[bucket], key=lambda p: p["guid"])
        data = {"name": fname[:-5], "description": rule,
                "total_phrases": len(phrases), "phrases": phrases}
        write_yaml(OUT_DIR / fname, data)

    counts = {b: len(buckets[b]) for _, b, _ in FILES}
    total = sum(counts.values())

    # ---- validation ----
    errors = []
    if total != len(ru):
        errors.append(f"SUM {total} != ruRU {len(ru)}")
    all_keys = [p["guid"] for bucket in buckets.values() for p in bucket]
    if len(all_keys) != len(set(all_keys)):
        dups = {g for g in all_keys if all_keys.count(g) > 1}
        errors.append(f"duplicates: {len(dups)} ({sorted(dups)[:5]}...)")
    if set(all_keys) != set(ru.keys()):
        missing = set(ru) - set(all_keys)
        foreign = set(all_keys) - set(ru)
        errors.append(f"missing={len(missing)} foreign={len(foreign)}")

    print("=== catalog_2/people partition ===")
    for fname, bucket, _ in FILES:
        print(f"  {fname:32s} {counts[bucket]:6d}")
    print(f"  {'TOTAL':32s} {total:6d}  (ruRU: {len(ru)})")
    print(f"  env: A={sum(1 for p in buckets['env'] if p['category']=='A')} "
          f"B={sum(1 for p in buckets['env'] if p['category']=='B')}")
    if errors:
        print("FAIL:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("VALIDATION OK")

    index = {
        "generated": "build_partition.py",
        "source_ruRU": str(RU_JSON),
        "source_ruRU_sha256": sha256(RU_JSON),
        "source_guid_map": str(GUID_MAP),
        "total_guids": total,
        "files": [
            {"name": fname[:-5], "rule": rule, "total": counts[bucket]}
            for fname, bucket, rule in FILES
        ],
    }
    write_yaml(OUT_DIR / "index.yaml", index)
    print(f"index: {OUT_DIR / 'index.yaml'}")


if __name__ == "__main__":
    main()