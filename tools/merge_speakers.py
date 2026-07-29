#!/usr/bin/env python3
"""Merge speaker corrections from generate_catalog into existing YAMLs (preserving parts)."""

import os, sys, shutil, yaml, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEOPLE = os.path.join(ROOT, "catalog", "people")
BACKUP = os.path.join(ROOT, "catalog", "people_bak")

# 1. Backup current YAMLs
if os.path.exists(BACKUP):
    shutil.rmtree(BACKUP)
shutil.copytree(PEOPLE, BACKUP)
print(f"Backed up to {BACKUP}")

# 2. Run generate_catalog.py (overwrites YAMLs, losing parts)
script = os.path.join(ROOT, ".opencode", "skills", "text-catalog", "scripts", "generate_catalog.py")
result = subprocess.run([sys.executable, script], capture_output=True, text=True, cwd=ROOT)
print(result.stdout)
if result.returncode != 0:
    print(f"ERROR: {result.stderr}")
    sys.exit(1)

# 3. Merge: for each phrase, keep speaker from new, everything else from old
for fname in os.listdir(PEOPLE):
    if not fname.endswith(".yaml") or fname == "index.yaml":
        continue

    old_path = os.path.join(BACKUP, fname)
    new_path = os.path.join(PEOPLE, fname)

    if not os.path.exists(old_path):
        print(f"  {fname}: new only (no old backup)")
        continue

    with open(old_path, encoding="utf-8") as f:
        old = yaml.safe_load(f)
    with open(new_path, encoding="utf-8") as f:
        new = yaml.safe_load(f)

    if not old or not new:
        continue

    # Build lookup: new_guid -> speaker
    new_speakers = {}
    for p in new.get("phrases", []):
        g = p.get("guid", "")
        s = p.get("speaker", "")
        if g and s:
            old_speaker = None
            for op in old.get("phrases", []):
                if op.get("guid") == g:
                    old_speaker = op.get("speaker")
                    break
            if s != old_speaker:
                new_speakers[g] = s

    # Apply speaker updates to old YAML + sync parts[] speakers to top-level
    changed = 0
    for op in old.get("phrases", []):
        g = op.get("guid", "")
        top_speaker = op.get("speaker", "")

        if g in new_speakers:
            new_speaker = new_speakers[g]
            old_top = op.get("speaker", "")
            op["speaker"] = new_speaker
            # Update parts[] that had the old top-level speaker
            for pp in op.get("parts", []):
                if pp.get("speaker") == old_top and old_top != "narrator":
                    pp["speaker"] = new_speaker
            changed += 1
        else:
            # Even without top-level change, sync parts[] to top-level speaker
            for pp in op.get("parts", []):
                if pp.get("speaker") != top_speaker and pp.get("speaker") not in ("narrator", "Narrator") and top_speaker:
                    pp["speaker"] = top_speaker
                    changed += 1

    if changed:
        with open(new_path, "w", encoding="utf-8") as f:
            yaml.dump(old, f, allow_unicode=True, indent=2,
                      sort_keys=False, default_flow_style=False, width=65535)
        print(f"  {fname}: updated {changed} speaker(s)")
    else:
        # Restore old (no changes needed)
        shutil.copy2(old_path, new_path)
        print(f"  {fname}: no changes")

# 4. Restore index.yaml from old (generate_catalog overwrites it but breaks parts count)
shutil.copy2(os.path.join(BACKUP, "index.yaml"), os.path.join(PEOPLE, "index.yaml"))
print("\nDone. Remove backup with: rm -rf catalog/people_bak")
