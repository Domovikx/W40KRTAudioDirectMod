#!/usr/bin/env python3
"""Restore speaker_overrides from a reference catalog into the current one.

Regeneration tools (regenerate_text_clean.py) rewrite `parts` entirely and can
drop manual speaker_overrides. This script copies them back from a reference
source (default: catalog/people_orig) by GUID + text_clean match.

Usage:
    python tools/restore_overrides.py
    python tools/restore_overrides.py --source catalog/people_orig --target catalog/people
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_phrases(dirpath: str) -> dict[str, dict]:
    """guid -> phrase (with parts) for all files under dirpath."""
    out = {}
    for p in sorted(glob.glob(os.path.join(dirpath, "*.yaml"))):
        if p.endswith("index.yaml"):
            continue
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for ph in data.get("phrases", []):
            g = ph.get("guid", "")
            if g:
                out[g] = ph
    return out


def restore_phrase_overrides(target: dict, source: dict) -> int:
    """Apply source speaker/speaker_override to target parts (by text_clean). Returns count."""
    wanted = {}
    for pp in source.get("parts", []):
        tc = pp.get("text_clean")
        if not tc:
            continue
        wanted.setdefault(tc, pp)
    applied = 0
    for pp in target.get("parts", []):
        tc = pp.get("text_clean")
        sp = wanted.get(tc)
        if not sp:
            continue
        if sp.get("speaker") and sp.get("speaker") != pp.get("speaker"):
            pp["speaker"] = sp["speaker"]
            applied += 1
        if sp.get("speaker_override") and not pp.get("speaker_override"):
            pp["speaker_override"] = sp["speaker_override"]
            applied += 1
    return applied


def main() -> int:
    p = argparse.ArgumentParser(description="Restore speaker_overrides from a reference catalog")
    p.add_argument("--source", default=os.path.join(ROOT, "catalog", "people_orig"))
    p.add_argument("--target", default=os.path.join(ROOT, "catalog", "people"))
    args = p.parse_args()

    source_phrases = load_phrases(args.source)
    total = 0
    changed_files = set()

    for path in sorted(glob.glob(os.path.join(args.target, "*.yaml"))):
        if path.endswith("index.yaml"):
            continue
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        touched = False
        for ph in data.get("phrases", []):
            src = source_phrases.get(ph.get("guid", ""))
            if src and restore_phrase_overrides(ph, src):
                touched = True
                total += 1
        if touched:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, indent=2,
                          sort_keys=False, default_flow_style=False, width=65535)
            changed_files.add(os.path.basename(path))

    print(f"Restored {total} speaker_override(s) in {len(changed_files)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
