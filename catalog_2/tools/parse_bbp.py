#!/usr/bin/env python3
"""Parse blueprints-pack.bbp → catalog_2/raw/bbp_env_desc.yaml.

NOTE (2026-08-15): BBP serialization in WH40KRT does NOT embed class names as
ASCII — type identities are FNV-1 hashes. The only free signal in raw bytes is
the node asset name (e.g. "BookPage_0001", "Cue_0001", "Answer_0003"). For a
text GUID, the closest preceding node in the binary stream is usually the
dialog ancestor (Cue_/Answer_), not the actual owner blueprint.

Pilot run results (narrow_v2 5306 GUIDs):
    matched in BBP: 2652 / 5306
    useful (BookPage/Chapter/Page/Block/Objective/SequenceExit/Transition/Item):
                117 / 5306 (2.2%)
    noise (Cue_/Answer_/Command*): 1586
    other / unmatched: 3603

Conclusion: BBP name-prefix parsing is NOT a viable primary classifier for
env-desc text. It is kept here as a WEAK second-pass signal (~2% precision)
and a reproducible record of what was tried. The primary classifier must come
from elsewhere (sound/wem database, Unity text-asset dump, or LLM few-shot).

Output schema:
    bbp_parents:
      <text_guid>:
        primary: <parent_node_name>         # most common in window
        primary_count: <int>
        counts: {<parent_node_name>: <n>, ...}
        bp_guid: <32-hex of the matched parent>
        category: <BookPage | Objective | SequenceExit | Chapter | Page |
                   Block | Transition | Item | Noise | Other | None>

Categories are derived from the parent node name prefix.

Usage:
    python catalog_2/tools/parse_bbp.py
"""

from __future__ import annotations

import bisect
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
GAME = Path(
    r"C:/Program Files (x86)/Steam/steamapps/common"
    r"/Warhammer 40,000 Rogue Trader"
)
BBP = GAME / "Bundles" / "blueprints-pack.bbp"
ENV_DIR = ROOT / "Localization" / "ruRU" / "Environment_Descriptions"
NARROW_V2 = ENV_DIR / "_narrow_v2.yaml"
OUT = ROOT / "catalog_2" / "raw" / "bbp_env_desc.yaml"

LOOKAHEAD = 1500  # bytes back from $ for the parent node

# Same regex as dialog_roles.py, but capture every node (not just dialog ones)
NODE_NAME_RE = re.compile(
    rb"[\x01-\x3f]([A-Za-z_][A-Za-z0-9_]{3,60})\s+([0-9a-f]{32})"
)
TEXT_GUID_RE = re.compile(
    rb"[$]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)

# Categories — derived from name prefix. Order matters (more specific first).
CATEGORY_PREFIXES = (
    ("BookPage", "BookPage"),
    ("Book", "BookPage"),
    ("SequenceExit", "SequenceExit"),
    ("Sequence", "Sequence"),
    ("Objective", "Objective"),
    ("Chapter", "Chapter"),
    ("Page", "Page"),
    ("Block", "Block"),
    ("Text", "Block"),
    ("Transition", "Transition"),
    ("AreaEnter", "Transition"),
    ("AreaExit", "Transition"),
    ("AreaTransition", "Transition"),
    ("Item", "Item"),
    ("Loot", "Item"),
    ("Drop", "Item"),
    ("Reward", "Item"),
)

# Noise parents — these are NOT env-desc owners, even if they appear in the window
NOISE_PREFIXES = (
    "Cue_", "Answer_", "Question_",
    "Command", "Action", "Trigger", "Fade", "Zoom", "Delay", "Wait",
    "Move", "Look", "Play", "Set", "Add", "Remove", "Spawn", "Despawn",
    "Enable", "Disable", "Use", "Speak", "Selector", "Cover", "Strat_",
    "StageRun", "Script_", "Condition_", "Event", "Bark", "Comment",
    "Logic", "Unit", "Party", "Camera", "Console",
)


def categorize(name: str) -> str:
    if name.startswith(NOISE_PREFIXES):
        return "Noise"
    for prefix, cat in CATEGORY_PREFIXES:
        if name.startswith(prefix):
            return cat
    return "Other"


def main() -> int:
    if not BBP.exists():
        print(f"ERROR: {BBP} not found")
        return 1

    t0 = time.time()
    with open(BBP, "rb") as f:
        data = f.read()
    print(f"BBP: {len(data) / 1024 / 1024:.0f}MB")

    # Index nodes (positions + names + categories)
    print("Indexing BP nodes...")
    node_positions: list[int] = []
    node_names: list[str] = []
    node_hex: list[str] = []
    node_cats: list[str] = []
    for m in NODE_NAME_RE.finditer(data):
        name = m.group(1).decode("ascii", "ignore")
        node_positions.append(m.start())
        node_names.append(name)
        node_hex.append(m.group(2).decode("ascii"))
        node_cats.append(categorize(name))
    print(f"  {len(node_positions):,} nodes indexed")

    # Narrow v2
    print(f"Loading {NARROW_V2.name}...")
    narrow = yaml.safe_load(NARROW_V2.read_text(encoding="utf-8"))
    guids = [r["guid"] for r in narrow["records"]]
    print(f"  {len(guids)} text GUIDs to classify")

    # Set of narrow GUIDs for fast lookup
    narrow_set = set(guids)

    # Index text-refs (we only need positions for the narrow ones)
    print("Indexing text-refs...")
    text_positions: list[int] = []
    text_guids: list[str] = []
    for m in TEXT_GUID_RE.finditer(data):
        g = m.group(1).decode("ascii")
        if g in narrow_set:
            text_positions.append(m.start())
            text_guids.append(g)
    print(f"  {len(text_positions):,} text-refs within narrow set")

    # For each text-ref, find closest preceding node in LOOKAHEAD window
    print("Classifying...")
    parent_counts: dict[str, Counter] = defaultdict(Counter)
    parent_hex: dict[str, str] = {}
    for tr_pos, guid in zip(text_positions, text_guids):
        idx = bisect.bisect_right(node_positions, tr_pos) - 1
        if idx < 0:
            continue
        if tr_pos - node_positions[idx] > LOOKAHEAD:
            continue
        parent_counts[guid][node_names[idx]] += 1
        if guid not in parent_hex:
            parent_hex[guid] = node_hex[idx]

    # Build output
    bbp_parents: dict[str, dict] = {}
    not_found = 0
    cat_summary: Counter = Counter()
    for guid in guids:
        ctr = parent_counts.get(guid)
        if not ctr:
            bbp_parents[guid] = {"primary": None, "counts": {}, "bp_guid": None, "category": None}
            not_found += 1
            continue
        primary, primary_count = ctr.most_common(1)[0]
        cat = categorize(primary)
        cat_summary[cat] += 1
        bbp_parents[guid] = {
            "primary": primary,
            "primary_count": primary_count,
            "counts": dict(ctr),
            "bp_guid": parent_hex.get(guid),
            "category": cat,
        }

    print(f"\nResults:")
    print(f"  matched:      {len(guids) - not_found}/{len(guids)}")
    print(f"  not in BBP:   {not_found}")
    print(f"\nCategory distribution:")
    for cat, c in cat_summary.most_common():
        print(f"  {cat:20s}  {c:5d}")

    out = {
        "source": "WH40KRT_Data/Bundles/blueprints-pack.bbp",
        "extracted_by": "catalog_2/tools/parse_bbp.py",
        "narrow_source": "Localization/ruRU/Environment_Descriptions/_narrow_v2.yaml",
        "lookahead_bytes": LOOKAHEAD,
        "category_rules": {
            "noise": [p for p in NOISE_PREFIXES if not p.endswith("_")],
            "env": [
                {"prefix": p, "category": c}
                for p, c in CATEGORY_PREFIXES
            ],
        },
        "summary": {
            "narrow_total": len(guids),
            "matched": len(guids) - not_found,
            "not_in_bbp": not_found,
            "by_category": dict(cat_summary),
        },
        "bbp_parents": bbp_parents,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            out, f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=200,
        )

    print(f"\n-> {OUT}")
    print(f"   ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
