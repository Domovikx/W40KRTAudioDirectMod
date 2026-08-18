#!/usr/bin/env python3
"""L1b — dialog tree structure extraction from blueprints-pack.bbp.

Parses dialog node blocks from the bbp binary and:

1. Builds `catalog_2/raw/dialog_trees.json` — tree definitions:
   per tree: tree_id, node counts, ordered text GUIDs.
2. Enriches `catalog_2/raw/guid_map.json` bbp-layer with:
     tree_id   — tree id (root block asset GUID)
     node_seq  — position of the node inside its tree (file order)
     node_prev — last compact GUID of the node block (raw, semantics unresolved)
     node_aux  — second-to-last compact GUID of the node block (raw)
     node_lit  — literal strings found inside the node block (max 8)
   (fields are added only for GUIDs that are node texts)

Node format (verified by probing):
    Cue_N [32hex assetGUID] 0x45='E' ... $[textGUID] ... [32hex] [32hex]
    Answer_N [32hex assetGUID] 0x5B='[' ... $[textGUID] ... [32hex] [32hex]

Text references are bare "$<hyphenated-guid>"; "$FieldName$<guid>" pairs are
field references (e.g. $EtudeStatus$...) and are excluded. A text GUID is
considered a node text only if it exists in ruRU (guid_map keys); other bare
refs are asset links and counted as `foreign_refs` stats.

Tree grouping: contiguous runs of text-bearing node blocks in file order
(a dialog blueprint is serialized contiguously). Probe-verified: Cue_34..39
adjacent = one run. Empirical: 4538 runs, sizes 1..20+.

Validation (exit 1 on failure):
    - unique(text_guids over trees) == unique(bare textGUIDs in node blocks
      that exist in guid_map) — deterministic sum (own anchor, != 77691)
    - every tree text GUID exists in guid_map.json
    - per tree: nodes == len(node_order)
    - cross-check vs existing guid_map bbp layer (two parsers of one binary):
      dialog_owner/bp_guid match rate reported in stats

Usage:
    python catalog_2/tools/build_trees.py          # parse + enrich + validate
    python catalog_2/tools/build_trees.py --no-map # skip guid_map enrichment
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BBP = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40,000 Rogue Trader\Bundles\blueprints-pack.bbp")
GUID_MAP = ROOT / "catalog_2" / "raw" / "guid_map.json"
TREES_OUT = ROOT / "catalog_2" / "raw" / "dialog_trees.json"

HEADER_RE = re.compile(rb"[\x01-\x3f]([A-Za-z_][A-Za-z0-9_]{3,60})\s+([0-9a-f]{32})(.)")
DIALOG_PREFIXES = ("Cue_", "Answer_", "BookPage_")
GUID32_RE = re.compile(rb"[0-9a-f]{32}")
TEXTREF_RE = re.compile(rb"\$([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")
FIELD_REF_TAIL = re.compile(rb"\$[A-Za-z_][A-Za-z0-9_]*\$")
LIT_RE = re.compile(
    r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9 .,!?«»'()\-_:]{4,}")
CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def parse_blocks(data: bytes) -> list[dict]:
    """Parse node blocks: name, asset guid, type byte, text refs, literals."""
    headers = list(HEADER_RE.finditer(data))
    blocks = []
    for i, m in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else min(
            len(data), m.start() + 4000)
        block = data[m.start():end]
        name = m.group(1).decode("ascii", "ignore")
        asset = m.group(2).decode()
        type_byte = chr(m.group(3)[0]) if 32 <= m.group(3)[0] < 127 else ""
        dialog = name.startswith(DIALOG_PREFIXES)
        texts = []
        for tm in TEXTREF_RE.finditer(block):
            pos = tm.start()
            look = block[max(0, pos - 64):pos]
            if FIELD_REF_TAIL.search(look):
                continue
            g = tm.group(1).decode()
            if g not in texts:
                texts.append(g)
        g_guids = [g.decode() for g in GUID32_RE.findall(block[len(m.group(0)):])]
        lit = []
        if texts:
            try:
                dec = block.decode("utf-8", errors="replace")
            except Exception:
                dec = ""
            for lm in LIT_RE.finditer(dec):
                s = lm.group(0)
                if len(s) < 5:
                    continue
                if not (CYRILLIC.search(s) or s.endswith(("_name", "_desc",
                                                          "_title", "_key"))):
                    continue
                if s not in lit:
                    lit.append(s)
                if len(lit) >= 8:
                    break
        blocks.append({"name": name, "asset": asset, "type": type_byte,
                       "dialog": dialog, "texts": texts,
                       "prev": g_guids[-1] if len(g_guids) >= 1 else "",
                       "aux": g_guids[-2] if len(g_guids) >= 2 else "",
                       "lit": lit})
    return blocks


def build_trees(blocks: list[dict], map_keys: set[str]) -> tuple[list[dict], dict, dict]:
    """Group dialog blocks into trees (contiguous file runs of dialog nodes)."""
    trees = []
    current = None
    last_idx = -2
    for idx, b in enumerate(blocks):
        if not b["dialog"] or not b["texts"]:
            continue
        if current is None or idx != last_idx + 1:
            current = {"tree_id": b["asset"] or b["name"],
                       "blocks": [], "cues": 0, "answers": 0, "books": 0}
            trees.append(current)
        last_idx = idx
        current["blocks"].append(b)
        if b["name"].startswith("Cue_"):
            current["cues"] += 1
        elif b["name"].startswith("Answer_"):
            current["answers"] += 1
        else:
            current["books"] += 1

    stats = {"foreign_refs": 0, "map_refs": 0, "multi_tree_guids": 0,
             "multi_block_guids": 0, "dups_in_run": 0, "non_dialog_refs": 0,
             "attr_dialog": 0, "attr_non_dialog": 0}
    out = []
    attrib: dict[str, dict] = {}
    used_tree_ids: set[str] = set()
    for t in trees:
        tid = t["tree_id"]
        if tid in used_tree_ids:
            n = 2
            while f"{tid}#{n}" in used_tree_ids:
                n += 1
            tid = f"{tid}#{n}"
        used_tree_ids.add(tid)
        bs = t["blocks"]
        texts_all = []
        for seq, b in enumerate(bs):
            in_map = [g for g in b["texts"] if g in map_keys]
            stats["map_refs"] += len(in_map)
            stats["foreign_refs"] += len(b["texts"]) - len(in_map)
            for g in in_map:
                if g in attrib:
                    stats["multi_tree_guids"] += 1
                else:
                    attrib[g] = {"tree_id": tid, "seq": seq, "block": b}
                texts_all.append(g)
        uniq = list(dict.fromkeys(texts_all))
        if len(uniq) != len(texts_all):
            stats["dups_in_run"] += 1
        out.append({"tree_id": tid, "nodes": len(bs),
                    "cues": t["cues"], "answers": t["answers"],
                    "books": t["books"], "text_guids": uniq,
                    "node_order": [b["asset"] for b in bs],
                    "blocks": bs})
    for b in blocks:
        if b["dialog"] or not b["texts"]:
            continue
        in_map = [g for g in b["texts"] if g in map_keys]
        stats["non_dialog_refs"] += len(in_map)
        for g in in_map:
            if g not in attrib:
                attrib[g] = {"tree_id": None, "seq": None, "block": b}
    return out, stats, attrib


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-map", action="store_true",
                    help="skip guid_map.json enrichment")
    args = ap.parse_args()

    data = BBP.read_bytes()
    print(f"BBP: {len(data) / 1024 / 1024:.0f} MB")
    blocks = parse_blocks(data)
    print(f"node blocks: {len(blocks)}, with text: {sum(1 for b in blocks if b['texts'])}")

    map_keys: set[str] = set()
    if not args.no_map:
        with open(GUID_MAP, encoding="utf-8") as f:
            guid_map = json.load(f)
        map_keys = set(guid_map.keys())
        print(f"guid_map loaded: {len(map_keys)} keys")

    trees, stats, attrib = build_trees(blocks, map_keys)

    all_texts = [g for t in trees for g in t["text_guids"]]
    unique_texts = set(all_texts)
    node_unique = set()
    for b in blocks:
        if not b["dialog"]:
            continue
        for g in b["texts"]:
            if g in map_keys:
                node_unique.add(g)

    # ---- validation ----
    errors = []
    if len(unique_texts) != len(node_unique):
        errors.append(f"trees unique {len(unique_texts)} != node unique {len(node_unique)}")
    if map_keys:
        foreign = unique_texts - map_keys
        if foreign:
            errors.append(f"tree text guids not in guid_map: {len(foreign)}")
    for t in trees:
        if t["nodes"] != len(t["node_order"]):
            errors.append(f"tree {t['tree_id']}: nodes {t['nodes']} != node_order {len(t['node_order'])}")

    print(f"trees: {len(trees)}, unique dialog text guids: {len(unique_texts)}, "
          f"foreign refs: {stats['foreign_refs']}, map refs: {stats['map_refs']}, "
          f"non-dialog refs: {stats['non_dialog_refs']}")
    if errors:
        print("FAIL:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("VALIDATION OK")

    out = {"version": "0.0.2", "source": str(BBP),
           "trees": [{k: v for k, v in t.items() if k != "blocks"} for t in trees],
           "stats": {"trees": len(trees),
                     "node_blocks": len(blocks),
                     "dialog_blocks": sum(1 for b in blocks if b["dialog"]),
                     "dialog_blocks_with_text": sum(1 for b in blocks if b["dialog"] and b["texts"]),
                     "unique_text_guids": len(unique_texts),
                     "map_refs": stats["map_refs"],
                     "foreign_refs": stats["foreign_refs"],
                     "non_dialog_refs": stats["non_dialog_refs"],
                     "multi_tree_guids": stats["multi_tree_guids"],
                     "multi_block_guids": stats["multi_block_guids"],
                     "dups_in_run": stats["dups_in_run"]}}
    TREES_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(TREES_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"trees -> {TREES_OUT}")

    if args.no_map:
        return

    # ---- enrich guid_map bbp layer (block-exact, overwrites windowed values) ----
    enriched = 0
    dialog_enriched = 0
    changed = 0
    for tg, a in attrib.items():
        entry = guid_map.get(tg)
        if entry is None:
            continue
        bbp = entry.get("bbp")
        if not isinstance(bbp, dict):
            bbp = {}
            entry["bbp"] = bbp
        b = a["block"]
        if bbp.get("dialog_owner") != b["name"] or bbp.get("bp_guid") != b["asset"]:
            changed += 1
        bbp["dialog_owner"] = b["name"]
        bbp["bp_guid"] = b["asset"]
        if b["type"]:
            tb = ord(b["type"])
            if tb == 0x45:
                bbp["role"] = "cue"
            elif tb == 0x5B:
                bbp["role"] = "answer"
            else:
                bbp["role"] = "unknown"
            bbp["type_byte"] = [tb]
        if a["tree_id"] is not None:
            bbp["tree_id"] = a["tree_id"]
            bbp["node_seq"] = a["seq"]
            if b["prev"]:
                bbp["node_prev"] = b["prev"]
            if b["aux"]:
                bbp["node_aux"] = b["aux"]
            if b["lit"]:
                bbp["node_lit"] = b["lit"]
            dialog_enriched += 1
        else:
            for stale in ("tree_id", "node_seq", "node_prev",
                          "node_aux", "node_lit"):
                bbp.pop(stale, None)
        enriched += 1
    with open(GUID_MAP, "w", encoding="utf-8") as f:
        json.dump(guid_map, f, ensure_ascii=False, indent=1)
    print(f"guid_map enriched: {enriched} GUIDs ({dialog_enriched} dialog), "
          f"{changed} attribution changed vs old windowed parser")


if __name__ == "__main__":
    main()