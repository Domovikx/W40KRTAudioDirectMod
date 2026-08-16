#!/usr/bin/env python3
"""Extract non-dialog strings from ruRU.json.

Builds catalog_2/raw/source.yaml from ruRU.json
minus all GUIDs already used in catalog/people/*.yaml. Strings containing
dialogue markers (") or narration markers ({n}) are skipped. Each candidate
carries auto-detected flags for downstream neural classification.

Usage:
    python tools/extract_non_dialog.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "catalog_2" / "raw"
GAME = ROOT / "WH40KRT_Data"
GAME_FALLBACK = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common"
    r"\Warhammer 40,000 Rogue Trader\WH40KRT_Data"
)
PEOPLE_DIR = ROOT / "catalog" / "people"
OUT_PATH = OUT_DIR / "source.yaml"


def load_texts() -> dict[str, str]:
    candidates = [
        GAME / "StreamingAssets" / "Localization" / "ruRU.json",
        GAME_FALLBACK / "StreamingAssets" / "Localization" / "ruRU.json",
    ]
    for path in candidates:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return {guid: info["Text"] for guid, info in data["strings"].items()}
    sys.exit(f"ERROR: ruRU.json not found in {candidates}")


def load_catalog_guids() -> set[str]:
    guids: set[str] = set()
    for yaml_path in sorted(PEOPLE_DIR.glob("*.yaml")):
        if yaml_path.name == "index.yaml":
            continue
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for phrase in data.get("phrases", []) or []:
            guid = phrase.get("guid")
            if guid:
                guids.add(guid)
    return guids


def compute_flags(text: str) -> list[str]:
    flags: list[str] = []
    if "{g|" in text:
        flags.append("has_g_tag")
    if "[{bind|" in text or "{bind|" in text:
        flags.append("has_bind")
    if "mouse_icon" in text or "{icon|" in text:
        flags.append("has_icon")
    if len(text.strip()) < 30:
        flags.append("is_short")
    if text.lstrip().startswith("[draft]") or text.lstrip().startswith("[Draft]"):
        flags.append("has_draft")
    if "pathfinderwiki" in text.lower():
        flags.append("has_pfwiki")
    if "\n" in text:
        flags.append("has_newline")
    if re.search(r"\{d\||\{mf\||\{rt_mf\||\{c\||\{font|\\n", text):
        flags.append("has_other_tag")
    if re.search(r"\[[^\[\]]{1,40}\]", text.strip()):
        flags.append("has_bracket")
    return flags


def is_candidate(text: str) -> bool:
    s = text.strip()
    if len(s) < 2:
        return False
    if '"' in text:
        return False
    if "{n}" in text:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT_PATH))
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    texts = load_texts()
    catalog_guids = load_catalog_guids()

    skipped_catalog = 0
    skipped_dialog = 0
    skipped_junk = 0

    records: list[dict] = []
    for guid, text in sorted(texts.items()):
        if guid in catalog_guids:
            skipped_catalog += 1
            continue
        if not is_candidate(text):
            if '"' in text or "{n}" in text:
                skipped_dialog += 1
            else:
                skipped_junk += 1
            continue
        records.append({
            "guid": guid,
            "length": len(text),
            "flags": compute_flags(text),
            "text": text,
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "source": "ruRU.json",
                "filter": "no-double-quote, no-n-tag, len>=2, not in catalog",
                "total_in_source": len(texts),
                "skipped_in_catalog": skipped_catalog,
                "skipped_dialog": skipped_dialog,
                "skipped_junk": skipped_junk,
                "written": len(records),
                "records": records,
            },
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=10000,
        )

    print(f"ruRU.json total:                {len(texts)}")
    print(f"  skipped (already in catalog): {skipped_catalog}")
    print(f"  skipped (dialog/quotes):      {skipped_dialog}")
    print(f"  skipped (junk):               {skipped_junk}")
    print(f"  written to {out_path}: {len(records)}")


if __name__ == "__main__":
    main()
