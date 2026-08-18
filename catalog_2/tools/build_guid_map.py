#!/usr/bin/env python3
"""Build guid_map.json — full per-GUID information map for ALL ruRU.json GUIDs.

Sources:
  P1  ruRU.json                    — base set (77 691): text, flags, len
  P3  Bundles/blueprint.assets     — blueprint owner: m_Name -> owner+field,
                                     class, path_id, neighbors (GUIDs in the
                                     same MonoBehaviour blob)
  P4  Bundles/blueprints-pack.bbp  — role (cue/answer/unknown), dialog_owner
                                     (closest preceding node name), category
  P5  Bundles/*.scenes + *.res     — scene filenames where the GUID appears
                                     (skips *_static* / staticforart / *.ui)

Validation (mandatory): the output map keys must EXACTLY equal ruRU.json keys
(77 691, no duplicates, no foreign GUIDs). Printed at the end; on mismatch the
script exits with code 1.

Output:
  catalog_2/raw/guid_map.json       — {"<guid>": {record}, ...}
  catalog_2/raw/guid_map_stats.yaml — coverage + category census

Record schema:
  {
    "guid": "...", "ru": "...", "flags": [...], "len": N,
    "blueprint": {path_id, m_name, owner, field, class, neighbors: [...]} | null,
    "bbp": {role, dialog_owner, category, bp_guid} | null,
    "scenes": ["file.scenes", ...]
  }

Usage:
    python catalog_2/tools/build_guid_map.py [--no-scenes]
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "catalog_2" / "raw"
GAME = Path(
    r"C:/Program Files (x86)/Steam/steamapps/common"
    r"/Warhammer 40,000 Rogue Trader"
)
BUNDLES = GAME / "Bundles"
RURU = GAME / "WH40KRT_Data" / "StreamingAssets" / "Localization" / "ruRU.json"
BLUEPRINT_ASSETS = BUNDLES / "blueprint.assets"
BBP = BUNDLES / "blueprints-pack.bbp"

OUT_JSON = RAW / "guid_map.json"
OUT_STATS = RAW / "guid_map_stats.yaml"

LOOKAHEAD = 1500  # bytes back from a text-ref for the parent node (BBP)

GUID_RE = re.compile(
    rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
# $<guid> — actual text reference inside a BP node body
TEXT_REF_RE = re.compile(rb"[$]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")
# BP node header: <len><Name> <32hex><TYPE-BYTE>
NODE_RE = re.compile(
    rb"[\x01-\x3f]([A-Za-z_][A-Za-z0-9_]{3,60})\s+([0-9a-f]{32})(.)"
)

# Known field suffixes in MonoBehaviour m_Name ("<Owner>_<field>")
FIELD_SUFFIXES = (
    "DescriptionText", "DisplayName", "Description", "AdditionalString",
    "ShortDescription", "FullDescription", "item_desc", "desc",
    "Text", "Name", "name", "Fluff", "fluff", "About", "Title", "Hint",
    "Tooltip", "Note", "Quote", "Bark", "Label",
)

# BBP categories — rules inherited from the Phase 2 pilot (parse_bbp.py,
# deleted in Phase 6; history in manifests/latest.yaml)
CATEGORY_PREFIXES = (
    ("BookPage", "BookPage"), ("Book", "BookPage"),
    ("SequenceExit", "SequenceExit"), ("Sequence", "Sequence"),
    ("Objective", "Objective"), ("Chapter", "Chapter"), ("Page", "Page"),
    ("Block", "Block"), ("Text", "Block"), ("Transition", "Transition"),
    ("AreaEnter", "Transition"), ("AreaExit", "Transition"),
    ("AreaTransition", "Transition"), ("Item", "Item"), ("Loot", "Item"),
    ("Drop", "Item"), ("Reward", "Item"),
)
NOISE_PREFIXES = (
    "Cue_", "Answer_", "Question_", "Command", "Action", "Trigger", "Fade",
    "Zoom", "Delay", "Wait", "Move", "Look", "Play", "Set", "Add", "Remove",
    "Spawn", "Despawn", "Enable", "Disable", "Use", "Speak", "Selector",
    "Cover", "Strat_", "StageRun", "Script_", "Condition_", "Event", "Bark",
    "Comment", "Logic", "Unit", "Party", "Camera", "Console",
)

SCENE_SKIP_PATTERNS = ("static", "forart", "worldart", "worldtex")
SCENE_INCLUDE_SUFFIXES = (".scenes", ".res")


def categorize(name: str) -> str:
    if name.startswith(NOISE_PREFIXES):
        return "Noise"
    for prefix, cat in CATEGORY_PREFIXES:
        if name.startswith(prefix):
            return cat
    return "Other"


def split_owner_field(m_name: str) -> tuple[str | None, str | None]:
    """'InHeadsPrayers_desc' -> ('InHeadsPrayers', 'desc');
    'X_Feature_.Description' -> ('X_Feature_', 'Description');
    unknown -> (full name, None)."""
    if not m_name:
        return None, None
    for suffix in FIELD_SUFFIXES:
        for sep in ("_", "."):
            marker = sep + suffix
            if m_name.endswith(marker):
                return m_name[: -len(marker)], suffix
    return m_name, None


# ---------------------------------------------------------------- P1: ruRU
def load_base() -> dict[str, dict]:
    with open(RURU, encoding="utf-8") as f:
        data = json.load(f)
    strings = data["strings"]
    recs = {}
    for guid, info in strings.items():
        text = info["Text"]
        recs[guid] = {
            "guid": guid,
            "ru": text,
            "flags": compute_flags(text),
            "len": len(text),
            "blueprint": None,
            "bbp": None,
            "scenes": [],
        }
    return recs


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
    if text.startswith('"') or text.endswith('"'):
        flags.append("quote")
    if "{n}" in text:
        flags.append("narration")
    if re.search(r"\{mf\|\|", text):
        flags.append("mf")
    if re.search(r"\{rt_mf", text):
        flags.append("rt_mf")
    return flags


# ------------------------------------------------------ P3: blueprint.assets
def scan_blueprint(recs: dict[str, dict], base: set[str]) -> None:
    import UnityPy

    t0 = time.time()
    env = UnityPy.load(str(BLUEPRINT_ASSETS))

    scripts: dict[int, str] = {}
    for obj in env.objects:
        if obj.type.name != "MonoScript":
            continue
        try:
            d = obj.read()
            ns = getattr(d, "m_Namespace", "") or ""
            cn = getattr(d, "m_ClassName", "") or ""
            scripts[obj.path_id] = (ns + "." + cn) if ns else cn
        except Exception:
            scripts[obj.path_id] = "?"

    n_blobs = 0
    n_hits = 0
    multi = Counter()
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            raw = obj.get_raw_data()
            d = obj.read()
        except Exception:
            continue
        if not raw:
            continue
        n_blobs += 1
        blob_guids = {m.group().decode() for m in GUID_RE.finditer(raw)} & base
        if not blob_guids:
            continue
        m_name = getattr(d, "m_Name", "") or ""
        owner, field = split_owner_field(m_name)
        sid = getattr(getattr(d, "m_Script", None), "path_id", None)
        cls = scripts.get(sid) if sid is not None else None
        n_hits += len(blob_guids)
        for g in blob_guids:
            rec = recs[g]
            if rec["blueprint"] is not None:
                multi["multi_owner"] += 1
                continue
            rec["blueprint"] = {
                "path_id": obj.path_id,
                "m_name": m_name,
                "owner": owner,
                "field": field,
                "class": cls,
                "neighbors": sorted(blob_guids - {g}),
            }

    print(f"  P3 blueprint.assets: {n_blobs} blobs, {n_hits} GUID hits, "
          f"multi-owner: {multi['multi_owner']}, {time.time() - t0:.0f}s")


# ---------------------------------------------------------------- P4: BBP
def scan_bbp(recs: dict[str, dict], base: set[str]) -> None:
    t0 = time.time()
    with open(BBP, "rb") as f:
        data = f.read()
    print(f"  P4 BBP: {len(data) / 1024 / 1024:.0f}MB loaded")

    # node index: position -> (name, hex, type_byte)
    node_pos: list[int] = []
    node_name: list[str] = []
    node_hex: list[str] = []
    node_byte: list[int] = []
    for m in NODE_RE.finditer(data):
        node_pos.append(m.start())
        node_name.append(m.group(1).decode("ascii", "ignore"))
        node_hex.append(m.group(2).decode("ascii"))
        node_byte.append(m.group(3)[0])

    # text-ref positions for base-set GUIDs
    ref_pos: list[int] = []
    ref_guid: list[str] = []
    for m in TEXT_REF_RE.finditer(data):
        g = m.group(1).decode("ascii")
        if g in base:
            ref_pos.append(m.start())
            ref_guid.append(g)

    # role: any 0x45 -> cue, any 0x5B -> answer (same rule as dialog_roles.py)
    role_bytes: dict[str, set[int]] = {}
    for tr_pos, g in zip(ref_pos, ref_guid):
        idx = bisect.bisect_right(node_pos, tr_pos) - 1
        if idx < 0 or tr_pos - node_pos[idx] > LOOKAHEAD:
            continue
        rec = recs[g]
        if rec["bbp"] is None:
            rec["bbp"] = {
                "role": None,
                "dialog_owner": node_name[idx],
                "category": categorize(node_name[idx]),
                "bp_guid": node_hex[idx],
                "type_byte": None,
            }
        role_bytes.setdefault(g, set()).add(node_byte[idx])

    for g, bytes_set in role_bytes.items():
        if 0x45 in bytes_set:
            recs[g]["bbp"]["role"] = "cue"
        elif 0x5B in bytes_set:
            recs[g]["bbp"]["role"] = "answer"
        else:
            recs[g]["bbp"]["role"] = "unknown"
        recs[g]["bbp"]["type_byte"] = sorted(bytes_set)

    n_bbp = sum(1 for r in recs.values() if r["bbp"] is not None)
    print(f"  P4 BBP: {len(ref_pos)} text-refs in base, {n_bbp} GUIDs with owner, "
          f"{time.time() - t0:.0f}s")


# ---------------------------------------------------------------- P5: scenes
def scene_files() -> list[Path]:
    files = []
    for p in sorted(BUNDLES.iterdir()):
        if not p.is_file() or not p.name.endswith(SCENE_INCLUDE_SUFFIXES):
            continue
        if p.name in ("blueprint.assets",):
            continue
        low = p.name.lower()
        if any(pat in low for pat in SCENE_SKIP_PATTERNS):
            continue
        files.append(p)
    return files


def scan_scenes(recs: dict[str, dict], base: set[str], deep: bool = False) -> None:
    files = scene_files()
    total_mb = sum(p.stat().st_size for p in files) / 1024 / 1024
    print(f"  P5 scenes: {len(files)} files, {total_mb:.0f}MB, "
          f"deep={'yes' if deep else 'no (raw bytes only)'}")
    t0 = time.time()
    n_hits = 0
    for i, p in enumerate(files, 1):
        found: set[str]
        if deep:
            import UnityPy
            found = set()
            try:
                env = UnityPy.load(str(p))
            except Exception:
                env = None
            if env is not None:
                for obj in env.objects:
                    try:
                        raw = obj.get_raw_data()
                    except Exception:
                        continue
                    if not raw:
                        continue
                    for m in GUID_RE.finditer(raw):
                        g = m.group().decode()
                        if g in base:
                            found.add(g)
        else:
            with open(p, "rb") as f:
                data = f.read()
            found = set()
            for m in GUID_RE.finditer(data):
                g = m.group().decode()
                if g in base:
                    found.add(g)
        for g in found:
            if p.name not in recs[g]["scenes"]:
                recs[g]["scenes"].append(p.name)
        n_hits += len(found)
        if i % 100 == 0 or i == len(files):
            el = time.time() - t0
            print(f"    [{i}/{len(files)}] {p.name}: {len(found)} hits "
                  f"({el:.0f}s, {el / i:.2f}s/file)")
    n_scenes = sum(1 for r in recs.values() if r["scenes"])
    print(f"  P5 scenes: {n_hits} GUID hits, {n_scenes} GUIDs with scenes, "
          f"{time.time() - t0:.0f}s")


# ------------------------------------------------------------ validation
def validate(recs: dict[str, dict], ru_keys: set[str]) -> None:
    problems: list[str] = []
    if len(recs) != len(ru_keys):
        problems.append(f"count mismatch: {len(recs)} != {len(ru_keys)}")
    if set(recs.keys()) != ru_keys:
        extra = set(recs) - ru_keys
        missing = ru_keys - set(recs)
        if extra:
            problems.append(f"foreign GUIDs: {len(extra)} (first: {sorted(extra)[:3]})")
        if missing:
            problems.append(f"missing GUIDs: {len(missing)} (first: {sorted(missing)[:3]})")
    dup_guid = len(recs) - len(set(recs))
    if dup_guid:
        problems.append(f"duplicate keys: {dup_guid}")
    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print(f"VALIDATION OK: {len(recs)} == {len(ru_keys)} GUIDs, no dup/foreign")


# ----------------------------------------------------------------- stats
def build_stats(recs: dict[str, dict]) -> dict:
    n = len(recs)
    bp = sum(1 for r in recs.values() if r["blueprint"])
    bbp = sum(1 for r in recs.values() if r["bbp"])
    scenes = sum(1 for r in recs.values() if r["scenes"])
    role_c = Counter(r["bbp"]["role"] for r in recs.values() if r["bbp"])
    cat_c = Counter(r["bbp"]["category"] for r in recs.values() if r["bbp"])
    cls_c = Counter(r["blueprint"]["class"] for r in recs.values()
                    if r["blueprint"] and r["blueprint"]["class"])
    field_c = Counter(r["blueprint"]["field"] for r in recs.values()
                      if r["blueprint"] and r["blueprint"]["field"])
    flag_c = Counter(f for r in recs.values() for f in r["flags"])
    scene_c = Counter(s for r in recs.values() for s in r["scenes"])
    multi_scene = sum(1 for r in recs.values() if len(r["scenes"]) > 1)
    return {
        "total": n,
        "coverage": {
            "blueprint": bp,
            "blueprint_pct": round(100 * bp / n, 1),
            "bbp": bbp,
            "bbp_pct": round(100 * bbp / n, 1),
            "scenes": scenes,
            "scenes_pct": round(100 * scenes / n, 1),
            "any_source": sum(1 for r in recs.values()
                              if r["blueprint"] or r["bbp"] or r["scenes"]),
            "multi_scene": multi_scene,
        },
        "roles": dict(role_c),
        "bbp_categories": dict(cat_c.most_common()),
        "blueprint_classes": dict(cls_c.most_common(30)),
        "blueprint_fields": dict(field_c.most_common(20)),
        "flags": dict(flag_c.most_common()),
        "top_scenes": dict(scene_c.most_common(20)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-scenes", action="store_true",
                    help="skip the slow scenes scan (P5)")
    ap.add_argument("--deep-scenes", action="store_true",
                    help="decompress scene bundles via UnityPy (P5, ~5 min, "
                         "much higher coverage than raw byte scan)")
    args = ap.parse_args()

    if not RURU.exists():
        print(f"ERROR: {RURU} not found")
        return 1

    t0 = time.time()
    print("P1: ruRU.json base...")
    recs = load_base()
    base = set(recs)
    print(f"  {len(recs)} GUIDs, {time.time() - t0:.0f}s")

    print("P3: blueprint.assets...")
    scan_blueprint(recs, base)

    print("P4: blueprints-pack.bbp...")
    scan_bbp(recs, base)

    if not args.no_scenes:
        print("P5: scenes + res...")
        scan_scenes(recs, base, deep=args.deep_scenes)

    print("\nValidation...")
    validate(recs, set(load_base()))

    RAW.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)
    print(f"-> {OUT_JSON} ({OUT_JSON.stat().st_size / 1024 / 1024:.1f}MB)")

    stats = build_stats(recs)
    stats["extracted_by"] = "catalog_2/tools/build_guid_map.py"
    stats["sources"] = {
        "P1": "WH40KRT_Data/StreamingAssets/Localization/ruRU.json",
        "P3": "Bundles/blueprint.assets",
        "P4": "Bundles/blueprints-pack.bbp",
        "P5": "Bundles/*.scenes + *.res (без static/forart/ui)",
    }
    with open(OUT_STATS, "w", encoding="utf-8") as f:
        yaml.safe_dump(stats, f, allow_unicode=True, sort_keys=False)
    print(f"-> {OUT_STATS}")

    print(f"\nTotal: {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())