#!/usr/bin/env python3
"""Query guid_map.json for a single GUID or a batch.

Usage:
    python catalog_2/tools/guid_info.py <guid>             # print one record
    python catalog_2/tools/guid_info.py <guid1> <guid2>    # print several
    python catalog_2/tools/guid_info.py --search "<text>"  # search by substring
    python catalog_2/tools/guid_info.py --owner <name>     # all GUIDs with owner containing <name>
    python catalog_2/tools/guid_info.py --field <field>    # all GUIDs with blueprint.field == <field>
    python catalog_2/tools/guid_info.py --class <cls>      # all GUIDs with blueprint.class containing <cls>
    python catalog_2/tools/guid_info.py --json <guid>      # raw JSON record

The map is built by catalog_2/tools/build_guid_map.py (all 77 691 ruRU.json GUIDs).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent.parent / "catalog_2" / "raw"
MAP = RAW / "guid_map.json"


def load() -> dict:
    with open(MAP, encoding="utf-8") as f:
        return json.load(f)


def print_record(rec: dict, show_json: bool = False) -> None:
    if show_json:
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        return
    print(f"guid:    {rec['guid']}")
    print(f"ru:      {rec['ru']}")
    print(f"flags:   {rec['flags']}  len: {rec['len']}")
    bp = rec.get("blueprint")
    if bp:
        print(f"blueprint:")
        print(f"  m_name: {bp['m_name']!r}")
        print(f"  owner:  {bp['owner']}  field: {bp['field']}")
        print(f"  class:  {bp['class']}")
        print(f"  path_id:{bp['path_id']}")
        if bp.get("neighbors"):
            print(f"  neighbors ({len(bp['neighbors'])}):")
            for n in bp["neighbors"]:
                print(f"    {n}")
    else:
        print("blueprint: (нет)")
    bb = rec.get("bbp")
    if bb:
        line = (f"bbp:     role={bb['role']}  dialog_owner={bb['dialog_owner']}  "
                f"category={bb['category']}  bp_guid={bb['bp_guid']}")
        if bb.get("tree_id"):
            line += (f"\n         tree_id={bb['tree_id']}  node_seq={bb['node_seq']}"
                     f"  prev={bb.get('node_prev', '')}")
            if bb.get("node_lit"):
                line += f"\n         node_lit={bb['node_lit']}"
        print(line)
    else:
        print("bbp:     (нет)")
    snd = rec.get("sound")
    if snd:
        print(f"sound:   event={snd['event']}  speaker={snd['speaker']}")
    if rec.get("owner_hint"):
        print(f"owner_hint: {rec['owner_hint']}")
    print(f"scenes:  {rec.get('scenes') or '(нет)'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Query guid_map.json")
    ap.add_argument("guids", nargs="*", help="one or more GUIDs (36-hex)")
    ap.add_argument("--search", help="find GUIDs whose ru text contains substring")
    ap.add_argument("--owner", help="find GUIDs whose blueprint owner contains substring")
    ap.add_argument("--field", help="find GUIDs with blueprint field == value")
    ap.add_argument("--class", dest="cls", help="find GUIDs whose blueprint class contains substring")
    ap.add_argument("--role", choices=["cue", "answer", "unknown"],
                    help="find GUIDs with bbp role")
    ap.add_argument("--category", help="find GUIDs with bbp category")
    ap.add_argument("--limit", type=int, default=50, help="max results for search modes")
    ap.add_argument("--json", action="store_true", help="raw JSON output")
    ap.add_argument("--count", action="store_true", help="only print the count")
    args = ap.parse_args()

    if not MAP.exists():
        print(f"ERROR: {MAP} not found — run catalog_2/tools/build_guid_map.py first")
        return 1

    data = load()
    found: list[tuple[str, dict]] = []

    if args.guids:
        for g in args.guids:
            rec = data.get(g)
            if rec is None:
                print(f"NOT FOUND: {g}")
                continue
            found.append((g, rec))
    else:
        for g, rec in data.items():
            if args.search and args.search.lower() not in rec["ru"].lower():
                continue
            bp = rec.get("blueprint") or {}
            if args.owner and (not bp.get("owner") or args.owner.lower() not in bp["owner"].lower()):
                continue
            if args.field and bp.get("field") != args.field:
                continue
            if args.cls and (not bp.get("class") or args.cls.lower() not in bp["class"].lower()):
                continue
            bb = rec.get("bbp") or {}
            if args.role and bb.get("role") != args.role:
                continue
            if args.category and bb.get("category") != args.category:
                continue
            found.append((g, rec))
            if len(found) >= args.limit:
                break

    if args.count:
        print(len(found))
        return 0
    if not found:
        print("(ничего не найдено)")
        return 0
    for g, rec in found:
        print_record(rec, show_json=args.json)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())