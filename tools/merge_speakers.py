#!/usr/bin/env python3
"""Rebuild the catalog safely:

1. Backup catalog/people -> catalog/people_bak
2. Run generate_catalog.py (fresh routing: player answers -> Player_Answers.yaml)
3. Union-merge each file: keep old phrases (with parts), apply new speakers,
   add genuinely new phrases, REMOVE player answers (answer-only roles).
4. Player_Answers.yaml: carry parts from old files where available.
5. Recompute total_phrases and index.yaml.

Usage:
    python tools/merge_speakers.py
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import time
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEOPLE = os.path.join(ROOT, "catalog", "people")
BACKUP = os.path.join(ROOT, "catalog", "people_bak")
ROLES_PATH = os.path.join(ROOT, "catalog", "dialog_roles.yaml")
GENERATE = os.path.join(ROOT, ".opencode", "skills", "text-catalog", "scripts", "generate_catalog.py")
GENERIC_FILE = "Generic_Male_NPC.yaml"


def load_roles() -> dict:
    if not os.path.exists(ROLES_PATH):
        print("WARN: catalog/dialog_roles.yaml not found — player answers will not be filtered")
        return {}
    with open(ROLES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def safe_filename(name: str) -> str:
    return name.replace(" ", "_").replace("(", "").replace(")", "")


def file_key(data: dict) -> str:
    """Canonical identity of a character file: its inner `name`."""
    return data.get("name") or ""


def merge_phrases(old_phrases: list, new_phrases: list, is_answer) -> list:
    """Union of old and new phrases; drops player answers.

    Existing phrases KEEP their speaker (manual review result) — the machine
    speaker from generate_catalog is applied only to genuinely NEW phrases.

    A phrase is dropped as a player answer ONLY when it has no Sound.json
    event: voiced phrases (event) sitting in Answer nodes are NPC lines.
    """
    def _is_player(p) -> bool:
        return is_answer(p.get("guid", "")) and not p.get("event")

    result = []
    seen = set()

    for op in old_phrases:
        g = op.get("guid", "")
        if not g or _is_player(op):
            continue  # player answer -> Player_Answers.yaml
        result.append(op)
        seen.add(g)

    for p in new_phrases:
        g = p.get("guid", "")
        if g and g not in seen and not _is_player(p):
            result.append(p)
            seen.add(g)

    return result


def build_player_answers(new_player: list, old_by_file: dict, is_answer) -> list:
    """Player answers, preferring old phrases (with parts) where they existed.

    Old phrases are picked up ONLY when they have no Sound.json event —
    voiced phrases in Answer nodes are NPC lines, not player answers.
    """
    old_by_guid = {}
    for fname, data in old_by_file.items():
        for p in data.get("phrases", []):
            g = p.get("guid", "")
            if g and is_answer(g) and not p.get("event"):
                old_by_guid.setdefault(g, p)
    result = []
    for p in new_player:
        g = p.get("guid", "")
        if g in old_by_guid:
            result.append(old_by_guid[g])
        else:
            result.append(p)
    return result


def rewrite_with_count(path: str, data: dict, prev_text: str | None = None) -> bool:
    """Write the YAML only when its content actually changed (keeps git diffs clean)."""
    data["total_phrases"] = len(data.get("phrases", []))
    text = yaml.dump(data, allow_unicode=True, indent=2,
                     sort_keys=False, default_flow_style=False, width=65535)
    if prev_text is not None and text == prev_text:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def dedup_people(people_dir: str, fresh_by_guid: dict) -> int:
    """One GUID must live in exactly one character file.

    For GUIDs present in 2+ files the canonical copy is chosen by priority:
    1. the file the fresh generate_catalog.py routed it to (fresh_by_guid),
    2. the non-generic (per-character) file,
    3. the first file (fallback).
    Duplicate copies are removed from all other files. Returns removed count.
    """
    by_guid: dict[str, list[str]] = {}
    files_data: dict[str, tuple[str, dict]] = {}
    for fname in sorted(os.listdir(people_dir)):
        if not fname.endswith(".yaml") or fname in ("index.yaml", "Player_Answers.yaml"):
            continue
        path = os.path.join(people_dir, fname)
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        files_data[fname] = (path, data)
        for ph in data.get("phrases", []):
            g = ph.get("guid", "")
            if g:
                by_guid.setdefault(g, []).append(fname)

    removed = 0
    for g, files in by_guid.items():
        if len(files) < 2:
            continue
        if g in fresh_by_guid and fresh_by_guid[g] in files:
            keep = fresh_by_guid[g]
        elif any(f != GENERIC_FILE for f in files):
            keep = min(f for f in files if f != GENERIC_FILE)
        else:
            keep = files[0]
        for fname in files:
            if fname == keep:
                continue
            path, data = files_data[fname]
            data["phrases"] = [p for p in data.get("phrases", [])
                               if p.get("guid") != g]
            data["total_phrases"] = len(data["phrases"])
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, indent=2,
                          sort_keys=False, default_flow_style=False, width=65535)
            removed += 1
            print(f"  dedup: removed {g} from {fname} (kept in {keep})")
    return removed


def write_index() -> None:
    entries = []
    total = 0
    for path in sorted(glob.glob(os.path.join(PEOPLE, "*.yaml"))):
        fname = os.path.basename(path)
        if fname in ("index.yaml", "Player_Answers.yaml"):
            continue
        with open(path, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        n = len(d.get("phrases", []))
        entries.append({"name": d.get("name", fname), "doc": d.get("doc", ""),
                        "total_phrases": n})
        total += n
    index_path = os.path.join(PEOPLE, "index.yaml")
    with open(index_path, "w", encoding="utf-8") as f:
        yaml.dump({
            "generated": "merge_speakers rebuild",
            "total_characters": len(entries),
            "total_phrases": total,
            "characters": entries,
        }, f, allow_unicode=True, indent=2, sort_keys=False, default_flow_style=False)


def step(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_old_people(backup_dir: str) -> tuple[dict, dict, list]:
    """(name -> old data, name -> old filename, orphan filenames) from the backup.

    Per-character files only. When several files share the same `name`, the
    canonical file (safe_filename(name).yaml) wins; the others are orphans.
    """
    old_by_name = {}
    old_files_by_name = {}
    orphans = []
    for fname in os.listdir(backup_dir):
        if not fname.endswith(".yaml") or fname in ("index.yaml", "Player_Answers.yaml"):
            continue
        with open(os.path.join(backup_dir, fname), encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        key = file_key(data)
        if not key:
            continue
        canonical = safe_filename(key) + ".yaml"
        if key not in old_files_by_name:
            old_by_name[key] = data
            old_files_by_name[key] = fname
            if fname != canonical:
                orphans.append(fname)
        elif fname == canonical:
            old_by_name[key] = data
            old_files_by_name[key] = fname
        else:
            orphans.append(fname)
    return old_by_name, old_files_by_name, orphans


def main() -> int:
    step("1/6 backup catalog/people -> people_bak")
    if os.path.exists(BACKUP):
        shutil.rmtree(BACKUP)
    shutil.copytree(PEOPLE, BACKUP, dirs_exist_ok=True)
    print(f"Backed up to {BACKUP}")

    step("2/6 running generate_catalog.py (may take a few minutes)")
    result = subprocess.run([sys.executable, GENERATE], capture_output=True, text=True, cwd=ROOT)
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        return 1

    step("3/6 loading dialog roles")
    roles = load_roles()
    is_answer = lambda g: roles.get(g) == "answer"

    step("4/6 merging per-character files (preserving parts)")
    old_by_name, old_files_by_name, orphans = load_old_people(BACKUP)

    # Remove orphan files (duplicates with the same `name`, non-canonical name)
    for orphan in orphans:
        op = os.path.join(PEOPLE, orphan)
        if os.path.exists(op):
            os.remove(op)
            print(f"  removed orphan file: {orphan}")

    new_names = set()
    for fname in os.listdir(PEOPLE):
        if not fname.endswith(".yaml") or fname in ("index.yaml", "Player_Answers.yaml"):
            continue
        with open(os.path.join(PEOPLE, fname), encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        new_names.add(file_key(data))

    fresh_by_guid: dict = {}

    for name, old_data in old_by_name.items():
        if not name:
            continue
        new_path = os.path.join(PEOPLE, safe_filename(name) + ".yaml")
        new_data = {}
        prev_text = None
        if os.path.exists(new_path):
            with open(new_path, encoding="utf-8") as f:
                prev_text = f.read()
            new_data = yaml.safe_load(prev_text) or {}
            for ph in new_data.get("phrases", []):
                g = ph.get("guid", "")
                if g:
                    fresh_by_guid.setdefault(g, safe_filename(name) + ".yaml")
        old_data["phrases"] = merge_phrases(old_data.get("phrases", []),
                                            new_data.get("phrases", []), is_answer)
        changed = rewrite_with_count(new_path, old_data, prev_text)
        print(f"  {name}: merged, total={len(old_data['phrases'])}{'' if changed else ' (no changes)'}")

    step("4b/6 deduplicating GUIDs across files")
    removed = dedup_people(PEOPLE, fresh_by_guid)
    if removed:
        print(f"  dedup: removed {removed} duplicate phrase(s)")
    else:
        print("  dedup: no duplicate GUIDs")

    # Player_Answers.yaml: prefer old phrases (with parts)
    pa_path = os.path.join(PEOPLE, "Player_Answers.yaml")
    if os.path.exists(pa_path):
        with open(pa_path, encoding="utf-8") as f:
            pa_raw = f.read()
        pa = yaml.safe_load(pa_raw) or {}
        pa["phrases"] = build_player_answers(pa.get("phrases", []), old_by_name, is_answer)
        rewrite_with_count(pa_path, pa, pa_raw)
        print(f"  Player_Answers.yaml: {len(pa['phrases'])} phrases")

    step("5/6 rebuilding index.yaml")
    write_index()
    step("6/6 verifying no duplicate GUIDs")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", os.path.join("tools", "test_pipeline.py"),
         "-q", "-k", "no_duplicate_guids"],
        capture_output=True, text=True, cwd=ROOT)
    print(result.stdout or result.stderr)
    if result.returncode != 0:
        print("ERROR: duplicate GUIDs detected after rebuild — fix routing before committing")
        return 1
    print("OK: no duplicate GUIDs. Remove backup with: rm -rf catalog/people_bak")
    return 0


if __name__ == "__main__":
    sys.exit(main())
