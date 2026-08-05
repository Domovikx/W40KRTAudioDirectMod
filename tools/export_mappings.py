#!/usr/bin/env python3
"""Export playable mappings from the catalog to Localization/{lang}/mappings.json.

For every generated WAV in Localization/{lang}/**/*.wav the catalog is looked
up by GUID; each phrase contributes:

  - one entry per part:  normalized(parts[i].text_clean) -> wav
  - one entry per whole: normalized(concat of parts)     -> wav

Phrases in files with `skip_voicing: true` (e.g. Player_Answers.yaml) and
phrases with `skip_voicing: true` are NOT exported.

mappings.json:
    {"entries": [{"t": "<normalized text>", "w": "<relative wav path>"}, ...]}

The game mod loads this file instead of scanning ruRU.json, and matches with
EXACT equality (normalized) — no substring collisions possible.

Usage:
    python tools/export_mappings.py [--lang ruRU]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from text_normalize import normalize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def load_catalog() -> dict[str, dict]:
    """guid -> {text, parts, skip, file} for all phrases in catalog/people/."""
    catalog_dir = ROOT / "catalog" / "people"
    result = {}
    for yaml_path in sorted(glob.glob(str(catalog_dir / "*.yaml"))):
        if yaml_path.endswith("index.yaml"):
            continue
        import yaml

        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        file_skip = bool(data.get("skip_voicing"))
        for ph in data.get("phrases", []):
            guid = ph.get("guid", "")
            if not guid:
                continue
            result[guid] = {
                "text": ph.get("text", ""),
                "parts": ph.get("parts", []),
                "skip": file_skip or bool(ph.get("skip_voicing")),
                "file": os.path.basename(yaml_path),
            }
    return result


def collect_wavs(lang_dir: Path) -> dict[str, list[str]]:
    """guid -> [relative wav paths] (recursive scan)."""
    found: dict[str, list[str]] = {}
    if not lang_dir.exists():
        return found
    for wav in lang_dir.rglob("*.wav"):
        guid = wav.stem
        if len(guid) != 36:
            continue
        rel = wav.relative_to(lang_dir).as_posix()
        found.setdefault(guid, []).append(rel)
    return found


def phrase_mapping_entries(phrase: dict, wav_rel: str) -> list[dict]:
    """Per-part + whole-phrase normalized entries for one phrase."""
    entries = []
    parts = phrase.get("parts") or []
    part_texts = [p.get("text_clean", "").strip() for p in parts if p.get("text_clean", "").strip()]
    if part_texts:
        for pt in part_texts:
            entries.append({"t": normalize(pt), "w": wav_rel})
        entries.append({"t": normalize(" ".join(part_texts)), "w": wav_rel})
    elif phrase.get("text"):
        entries.append({"t": normalize(phrase["text"]), "w": wav_rel})
    return entries


def export(lang: str = "ruRU") -> tuple[int, int]:
    lang_dir = ROOT / "Localization" / lang
    maps_dir = lang_dir / "mappings"
    catalog = load_catalog()
    wavs = collect_wavs(lang_dir)

    # group -> entries, one file per character dir
    grouped: dict[str, list[dict]] = {}
    skipped = 0
    for guid, wav_list in wavs.items():
        phrase = catalog.get(guid)
        if phrase is None:
            continue
        if phrase["skip"]:
            skipped += 1
            continue
        wav_rel = wav_list[0]
        if len(wav_list) > 1:
            print(f"  WARNING: GUID {guid} has WAVs in {len(wav_list)} dirs: "
                  f"{wav_list} — duplicate GUIDs or stale wavs; using {wav_rel}")
        group = wav_rel.split("/", 1)[0] if "/" in wav_rel else "_root"
        for e in phrase_mapping_entries(phrase, wav_rel):
            grouped.setdefault(group, []).append(e)

    maps_dir.mkdir(exist_ok=True)
    total = 0
    for group in sorted(grouped):
        # Deterministic order (stable for identical texts) and dedupe by text.
        entries = grouped[group]
        entries.sort(key=lambda e: e["w"])
        seen: set[str] = set()
        unique = []
        for e in entries:
            if e["t"] in seen:
                continue
            seen.add(e["t"])
            unique.append(e)

        out = maps_dir / f"{group}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"entries": unique}, f, ensure_ascii=False, separators=(",", ":"))
        total += len(unique)
        print(f"  {out.name}: {len(unique)} entries")

    print(f"{maps_dir}: {total} entries, {skipped} skipped (skip_voicing)")
    return total, skipped


def main() -> int:
    p = argparse.ArgumentParser(description="Export mappings.json from catalog + WAVs")
    p.add_argument("--lang", default="ruRU")
    args = p.parse_args()
    export(args.lang)
    return 0


if __name__ == "__main__":
    sys.exit(main())
