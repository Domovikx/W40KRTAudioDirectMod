#!/usr/bin/env python3
"""Narrow 30k source candidates down to ~2-4k likely env_desc.

Filters records by length band and excludes everything obviously not
environment descriptions (encyclopedia, UI, credits, draft, dialog_mf).
The has_other_tag branch is split into its own pending file because
dialog_mf needs a separate speaker resolution later.

Usage:
    python tools/narrow_candidates.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "catalog_2" / "raw"
SOURCE = OUT_DIR / "source.yaml"
NARROW_PATH = OUT_DIR / "narrow_v2.yaml"
DIALOG_MF_PATH = OUT_DIR / "dialog_mf_pending.yaml"

LENGTH_MIN = 80
LENGTH_MAX = 400

EXCLUDE_FLAGS = {
    "has_g_tag",
    "has_bind",
    "has_icon",
    "has_pfwiki",
    "has_draft",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(NARROW_PATH))
    parser.add_argument("--dialog-mf", default=str(DIALOG_MF_PATH))
    parser.add_argument("--len-min", type=int, default=LENGTH_MIN)
    parser.add_argument("--len-max", type=int, default=LENGTH_MAX)
    args = parser.parse_args()

    with open(SOURCE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    records = data["records"]

    narrow: list[dict] = []
    dialog_mf: list[dict] = []
    skipped: dict[str, int] = {}

    for r in records:
        flags = set(r.get("flags", []))
        text = r.get("text", "")
        length = r.get("length", len(text))

        if "has_other_tag" in flags:
            dialog_mf.append({
                "guid": r["guid"],
                "length": length,
                "text": text,
            })
            continue

        if length < args.len_min:
            skipped["too_short"] = skipped.get("too_short", 0) + 1
            continue
        if length > args.len_max:
            skipped["too_long"] = skipped.get("too_long", 0) + 1
            continue

        excluded = flags & EXCLUDE_FLAGS
        if excluded:
            key = ",".join(sorted(excluded))
            skipped[key] = skipped.get(key, 0) + 1
            continue

        narrow.append({
            "guid": r["guid"],
            "length": length,
            "text": text,
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "filter": (
                    f"len in [{args.len_min},{args.len_max}], "
                    "no g_tag/bind/icon/pfwiki/draft, "
                    "has_other_tag split to dialog_mf_pending"
                ),
                "total_in_source": len(records),
                "narrow": len(narrow),
                "dialog_mf": len(dialog_mf),
                "skipped": skipped,
                "records": narrow,
            },
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=10000,
        )

    dm_path = Path(args.dialog_mf)
    with open(dm_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "filter": "has_other_tag (mf) — диалоги без спикера, отложено",
                "total": len(dialog_mf),
                "records": dialog_mf,
            },
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=10000,
        )

    print(f"source: {len(records)}")
    print(f"  narrow candidates: {len(narrow)} -> {out_path}")
    print(f"  dialog_mf pending: {len(dialog_mf)} -> {dm_path}")
    print(f"  skipped:")
    for k, v in sorted(skipped.items(), key=lambda x: -x[1]):
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
