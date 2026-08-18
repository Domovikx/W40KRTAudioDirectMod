#!/usr/bin/env python3
"""Regenerate catalog_2/raw/guid_map_stats.yaml from guid_map.json.

The map is built by build_guid_map.py (P1/P3/P4/P5) and enriched by
build_trees.py (L1b) + enrich_sound.py (L2/L3). This script recomputes the
stats snapshot — run it after any enrichment.

Usage:
    python catalog_2/tools/update_map_stats.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import yaml

RAW = Path(__file__).resolve().parent.parent / "raw"
MAP = RAW / "guid_map.json"
OUT = RAW / "guid_map_stats.yaml"


def top(counter: Counter, n: int = 20) -> dict:
    return {k: v for k, v in counter.most_common(n)}


def main() -> None:
    with open(MAP, encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    n_blueprint = n_bbp = n_scenes = n_any = n_multi = 0
    n_tree = n_dialog_tree = 0
    n_sound = n_speaker = n_hint = 0
    roles: Counter = Counter()
    cats: Counter = Counter()
    classes: Counter = Counter()
    fields: Counter = Counter()
    flags: Counter = Counter()
    scene_counter: Counter = Counter()

    for rec in data.values():
        if rec.get("blueprint"):
            n_blueprint += 1
            bp = rec["blueprint"]
            classes[bp.get("class") or ""] += 1
            fields[bp.get("field") or ""] += 1
        bb = rec.get("bbp") or {}
        if bb:
            n_bbp += 1
            roles[bb.get("role") or "-"] += 1
            cats[bb.get("category") or ""] += 1
            if bb.get("tree_id"):
                n_tree += 1
                n_dialog_tree += 1
        if rec.get("scenes"):
            n_scenes += 1
            for s in rec["scenes"]:
                scene_counter[s] += 1
        if rec.get("sound"):
            n_sound += 1
            if rec["sound"].get("speaker"):
                n_speaker += 1
        if rec.get("owner_hint"):
            n_hint += 1
        if rec.get("blueprint") or (rec.get("bbp") or {}) or rec.get("scenes"):
            n_any += 1
        for f in rec.get("flags") or []:
            flags[f] += 1
    n_multi = n_any - n_blueprint - n_bbp - n_scenes + 0  # placeholder; computed below
    n_multi = sum(
        1 for r in data.values()
        if (1 if r.get("blueprint") else 0)
        + (1 if r.get("bbp") else 0)
        + (1 if r.get("scenes") else 0) > 1)

    stats = {
        "total": total,
        "coverage": {
            "blueprint": n_blueprint,
            "blueprint_pct": round(100 * n_blueprint / total, 1),
            "bbp": n_bbp,
            "bbp_pct": round(100 * n_bbp / total, 1),
            "scenes": n_scenes,
            "scenes_pct": round(100 * n_scenes / total, 1),
            "any_source": n_any,
            "multi_source": n_multi,
            "tree_attributed": n_tree,
            "dialog_trees": n_dialog_tree,
            "sound": n_sound,
            "sound_speaker": n_speaker,
            "owner_hint": n_hint,
        },
        "roles": {k: v for k, v in sorted(roles.items())},
        "bbp_categories": top(cats),
        "blueprint_classes": top(classes),
        "blueprint_fields": top(fields),
        "flags": dict(flags),
        "top_scenes": top(scene_counter),
        "extracted_by": [
            "catalog_2/tools/build_guid_map.py",
            "catalog_2/tools/build_trees.py (L1b)",
            "catalog_2/tools/enrich_sound.py (L2/L3)",
            "catalog_2/tools/update_map_stats.py (этот снапшот)",
        ],
        "sources": {
            "P1": "WH40KRT_Data/StreamingAssets/Localization/ruRU.json",
            "P3": "Bundles/blueprint.assets",
            "P4": "Bundles/blueprints-pack.bbp",
            "P5": "Bundles/*.scenes + *.res (без static/forart/ui)",
            "L2": "WH40KRT_Data/StreamingAssets/Localization/Sound.json",
        },
    }
    OUT.write_text(yaml.dump(stats, allow_unicode=True, indent=2,
                             sort_keys=False, width=65535),
                   encoding="utf-8")
    print(f"stats -> {OUT}")
    print(f"  coverage: bp={n_blueprint} bbp={n_bbp} scenes={n_scenes} "
          f"any={n_any} tree={n_tree} sound={n_sound}({n_speaker}) hint={n_hint}")
    print(f"  roles: {dict(roles)}")


if __name__ == "__main__":
    main()