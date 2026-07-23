"""Regenerate text_clean and parts for all YAML files in catalog/people/.

Reads text_original from each phrase, runs clean_text / split_into_parts,
and updates the YAML with fresh parts/speaker/text_clean.

Dry-run mode: --dry-run to preview changes without writing.

Usage:
    python .opencode/skills/text-cleaner/scripts/regenerate_text_clean.py
    python .opencode/skills/text-cleaner/scripts/regenerate_text_clean.py --dry-run
    python .opencode/skills/text-cleaner/scripts/regenerate_text_clean.py --char "Кунрад"
"""

import argparse
import glob
import os
import sys
from typing import Dict

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from clean_text import split_into_parts

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
CATALOG_DIR = os.path.join(ROOT, "catalog", "people")
VOICES_CONFIG_PATH = os.path.join(ROOT, "config", "voices.yaml")


def _load_voices_config():
    if not os.path.exists(VOICES_CONFIG_PATH):
        return None
    with open(VOICES_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, width=9999)


def _normalize_name(name: str) -> str:
    return name.lower().replace("_", " ").replace("-", " ").strip()


def _resolve_to_voice(name: str, voices_config: dict) -> str | None:
    norm = _normalize_name(name)
    for vname, ref in voices_config.get("references", {}).items():
        for c in ref.get("characters", []):
            nc = _normalize_name(c)
            if norm == nc or norm in nc or nc in norm:
                return vname
    return None


def _normalize_speaker_to_char(speaker: str, char_name: str, voices_config: dict = None, filename_stem: str = None) -> str:
    if speaker.lower().strip() == char_name.lower().strip():
        return char_name
    if voices_config:
        sv = _resolve_to_voice(speaker, voices_config)
        # Use filename stem (English) to find the character's voice, not char_name (Russian)
        cv = _resolve_to_voice(filename_stem, voices_config) if filename_stem else _resolve_to_voice(char_name, voices_config)
        if sv and cv and sv == cv:
            return char_name
    return speaker


def regenerate_file(path: str, dry_run: bool = False, voices_config: dict = None) -> Dict[str, int]:
    data = load_yaml(path)
    stats = {"total": 0, "updated": 0, "skipped": 0, "errors": 0}

    char_name = data.get("name", os.path.basename(path))
    filename_stem = os.path.splitext(os.path.basename(path))[0]

    for phrase in data.get("phrases", []):
        stats["total"] += 1
        raw = phrase.get("text_original") or phrase.get("text", "")
        if not raw:
            stats["skipped"] += 1
            continue

        orig_speaker = phrase.get("speaker")
        default_speaker = _normalize_speaker_to_char(orig_speaker, char_name, voices_config, filename_stem) if orig_speaker else char_name
        try:
            parts = split_into_parts(raw, default_speaker=default_speaker, name_replacement="КЭП")
        except Exception as e:
            print(f"  ERROR {phrase.get('guid', '?')[:12]}: {e}")
            stats["errors"] += 1
            continue

        if not parts:
            stats["skipped"] += 1
            continue

        phrase["parts"] = parts
        stats["updated"] += 1

    if not dry_run and stats["updated"] > 0:
        save_yaml(data, path)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Regenerate text_clean for catalog YAML files")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--char", type=str, help="Process only character (substring match on filename)")
    args = parser.parse_args()

    voices_config = _load_voices_config()
    yaml_files = sorted(glob.glob(os.path.join(CATALOG_DIR, "*.yaml")))

    if args.char:
        yaml_files = [f for f in yaml_files if args.char.lower() in os.path.basename(f).lower()]

    total_updated = 0
    total_errors = 0

    for path in yaml_files:
        filename = os.path.basename(path)
        print(f"{'[DRY RUN]' if args.dry_run else '[UPDATE]'} {filename}...", end=" ")

        stats = regenerate_file(path, dry_run=args.dry_run, voices_config=voices_config)
        total_updated += stats["updated"]
        total_errors += stats["errors"]
        print(f"{stats['updated']} phrases updated, {stats['errors']} errors")

    print(f"\nDone. Total updated: {total_updated}, errors: {total_errors}")
    if args.dry_run:
        print("Dry-run mode — no files were modified.")


if __name__ == "__main__":
    main()
