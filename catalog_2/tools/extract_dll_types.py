#!/usr/bin/env python3
"""Extract relevant TypeDef metadata from game DLLs into catalog_2/raw/dll_types.yaml.

Scans Kingmaker.*.dll and Code.dll for classes with description-relevant fields
(Description, Text, Note, Book, Encyclopedia, etc). Only types whose fields
match the filter are saved — keeps the YAML small and focused.

Usage:
    python catalog_2/tools/extract_dll_types.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import dnfile
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
GAME = Path(
    r"C:/Program Files (x86)/Steam/steamapps/common"
    r"/Warhammer 40,000 Rogue Trader/WH40KRT_Data/Managed"
)
OUT = ROOT / "catalog_2" / "raw" / "dll_types.yaml"

NAME_KEYWORDS = [
    "BlueprintEncyclopedia",
    "BlueprintItemNote",
    "BlueprintBook",
    "BlueprintPointOfInterest",
    "BlueprintArea",
    "BlueprintCue",
    "BlueprintDialog",
    "BlueprintExamine",
    "BlueprintEnvironment",
    "BlueprintScene",
    "BlueprintTransition",
    "BlueprintLocation",
    "BlueprintInteract",
    "AreaEnter",
    "AreaTransition",
    "ScriptZone",
    "RandomEncounter",
    "LocationList",
]

FIELD_KEYWORDS = [
    "Description", "Text", "Cue", "Note", "Book", "Page", "Block",
    "Encyclopedia", "Encounter", "Transition", "Location", "Stage",
]

NAMESPACE_PREFIXES = ("Kingmaker", "Code", "Warhammer")

TARGET_DLLS = [
    "Code.dll",
    "Kingmaker.Enums.dll",
    "BundlesBaseTypes.dll",
]


def ns_of(type_row) -> str:
    ns = type_row.TypeNamespace
    if ns is None:
        return ""
    if isinstance(ns, str):
        return ns
    return str(ns.value) if hasattr(ns, "value") else str(ns)


def row_idx(idx) -> int:
    if idx is None:
        return 0
    if hasattr(idx, "row_index"):
        return int(idx.row_index)
    try:
        return int(idx)
    except (TypeError, ValueError):
        return 0


def scan_dll(dll_path: Path, name_keywords: list[str], field_keywords: list[str]) -> list[dict]:
    pe = dnfile.dnPE(str(dll_path))
    pe.parse_data_directories()
    mdt = pe.net.mdtables

    type_rows = list(mdt.TypeDef.rows)
    type_count = len(type_rows)
    field_count = len(mdt.Field.rows)

    fl_starts: list[int] = [0] * (type_count + 1)
    for i, row in enumerate(type_rows):
        fl = row.FieldList
        fl_starts[i] = row_idx(fl[0]) if fl and len(fl) > 0 else 0
    fl_starts[type_count] = field_count + 1

    matches: list[dict] = []
    for i, row in enumerate(type_rows):
        name = row.TypeName.value
        ns = ns_of(row)
        if not any(ns.startswith(p) for p in NAMESPACE_PREFIXES):
            continue
        if not any(kw.lower() in name.lower() for kw in name_keywords):
            continue

        fl_start = fl_starts[i]
        fl_end = fl_starts[i + 1]
        if fl_start <= 0 or fl_start > field_count:
            continue

        fields: list[str] = []
        for fi in range(fl_start - 1, fl_end - 1):
            if fi >= field_count:
                break
            f = mdt.Field.rows[fi]
            try:
                fname = f.Name.value
            except AttributeError:
                continue
            if any(kw.lower() in fname.lower() for kw in field_keywords):
                fields.append(fname)

        if fields:
            matches.append({
                "namespace": ns,
                "name": name,
                "fields": fields,
            })

    return matches


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    by_dll: dict[str, list[dict]] = {}
    total = 0
    for dll in TARGET_DLLS:
        path = GAME / dll
        if not path.exists():
            print(f"  SKIP {dll} (not found)", flush=True)
            continue
        try:
            matches = scan_dll(path, NAME_KEYWORDS, FIELD_KEYWORDS)
        except Exception as e:
            print(f"  ERROR {dll}: {e}", flush=True)
            continue
        by_dll[dll] = matches
        total += len(matches)
        print(f"  {dll}: {len(matches)} types", flush=True)

    out = {
        "source": "WH40KRT_Data/Managed/*.dll",
        "extracted_by": "catalog_2/tools/extract_dll_types.py",
        "tool": "dnfile (Python)",
        "name_keywords": NAME_KEYWORDS,
        "field_keywords": FIELD_KEYWORDS,
        "total_types": total,
        "by_dll": by_dll,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            out, f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=160,
        )

    print(f"-> {OUT} ({total} types)", flush=True)


if __name__ == "__main__":
    main()
