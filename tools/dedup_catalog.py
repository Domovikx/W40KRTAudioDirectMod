#!/usr/bin/env python3
"""De-duplicate GUIDs across catalog/people/*.yaml.

Rule: every phrase GUID must live in EXACTLY ONE character file. When a GUID
is found in 2+ files, the canonical copy is kept in the per-character file
(any file other than the Generic dump), and the copy is removed from the
Generic dump file (configurable, default: Generic_Male_NPC.yaml).

Usage:
    python tools/dedup_catalog.py [--dry-run]
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEOPLE = os.path.join(ROOT, "catalog", "people")
GENERIC_FILE = "Generic_Male_NPC.yaml"


def load_all(catalog_dir: str = PEOPLE) -> dict[str, dict]:
    """path -> data for all per-character YAMLs (excluding index.yaml)."""
    result = {}
    for yaml_path in sorted(glob.glob(os.path.join(catalog_dir, "*.yaml"))):
        if yaml_path.endswith("index.yaml"):
            continue
        with open(yaml_path, encoding="utf-8") as f:
            result[yaml_path] = yaml.safe_load(f) or {}
    return result


def find_duplicate_guids(catalog_dir: str = PEOPLE) -> dict[str, list[str]]:
    """guid -> [file basenames] for GUIDs present in 2+ files."""
    by_guid: dict[str, list[str]] = {}
    for yaml_path, data in load_all(catalog_dir).items():
        for ph in data.get("phrases", []):
            g = ph.get("guid", "")
            if not g:
                continue
            by_guid.setdefault(g, []).append(os.path.basename(yaml_path))
    return {g: files for g, files in by_guid.items() if len(files) > 1}


def dedup(catalog_dir: str = PEOPLE, generic_file: str = GENERIC_FILE,
          dry_run: bool = False) -> tuple[int, list[str]]:
    """Remove duplicated phrases from the generic dump file.

    Returns (removed_count, warnings). Never drops data silently: if the
    per-character copy has no parts while the generic copy does, it is kept
    in the generic file and reported instead.
    """
    dups = find_duplicate_guids(catalog_dir)
    generic_path = os.path.join(catalog_dir, generic_file)
    if not os.path.exists(generic_path):
        print(f"WARN: {generic_file} not found — nothing to dedup")
        return 0, []

    with open(generic_path, encoding="utf-8") as f:
        generic_data = yaml.safe_load(f) or {}

    keep: dict[str, str] = {}
    for g, files in dups.items():
        others = [f for f in files if f != generic_file]
        if not others:
            keep[g] = generic_file
            continue
        keep[g] = sorted(others)[0]

    warnings: list[str] = []
    generic_phrases = generic_data.get("phrases", [])
    removed = 0
    kept_phrases = []
    for ph in generic_phrases:
        g = ph.get("guid", "")
        if g in keep and keep[g] != generic_file:
            other_path = os.path.join(catalog_dir, keep[g])
            with open(other_path, encoding="utf-8") as f:
                other_data = yaml.safe_load(f) or {}
            other_ph = next((p for p in other_data.get("phrases", [])
                             if p.get("guid") == g), None)
            if other_ph and not other_ph.get("parts") and ph.get("parts"):
                warnings.append(f"{g}: per-char copy has no parts, kept in {generic_file}")
                kept_phrases.append(ph)
                continue
            removed += 1
        else:
            kept_phrases.append(ph)

    generic_data["phrases"] = kept_phrases
    generic_data["total_phrases"] = len(kept_phrases)

    if not dry_run and removed:
        with open(generic_path, "w", encoding="utf-8") as f:
            yaml.dump(generic_data, f, allow_unicode=True, indent=2,
                      sort_keys=False, default_flow_style=False, width=65535)
    print(f"dedup: removed {removed} phrase(s) from {generic_file} "
          f"({'dry-run' if dry_run else 'written'})")
    for w in warnings:
        print(f"  WARN: {w}")
    return removed, warnings


def main() -> int:
    p = argparse.ArgumentParser(description="De-duplicate catalog GUIDs")
    p.add_argument("--dry-run", action="store_true",
                   help="Only report what would be removed")
    args = p.parse_args()
    removed, warnings = dedup(dry_run=args.dry_run)
    remaining = find_duplicate_guids()
    if remaining:
        print(f"ERROR: still {len(remaining)} duplicate GUIDs after dedup:")
        for g, files in sorted(remaining.items()):
            print(f"  {g} -> {files}")
        return 1
    print(f"OK: no duplicate GUIDs in catalog ({removed} removed, {len(warnings)} warnings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
