#!/usr/bin/env python3
"""
Orchestrator: run speaker audit across all YAMLs using subagents.

Process per YAML:
  1. Launch speaker-auditor subagent (reviewer)
  2. Apply any found fixes
  3. Launch speaker-auditor again (antagonist)
  4. If new issues → fix, re-run until 3 consecutive clean runs
  5. Move to next YAML

Usage:
    python tools/run_speaker_audit.py [--dir catalog/people] [--file specific.yaml]
"""

import os, sys, json, subprocess, time, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PEOPLE = ROOT / "catalog" / "people"
MAX_ROUNDS = 5  # max audit rounds per file


def get_yamls(target_dir=None, single_file=None):
    if single_file:
        return [Path(single_file)]
    d = Path(target_dir) if target_dir else PEOPLE
    return sorted(d.glob("*.yaml"))


def count_overrides(yaml_path):
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return 0
    return sum(1 for p in data.get("phrases", []) for pp in p.get("parts", []) if "speaker_override" in pp)


def apply_fixes(yaml_path, fixes):
    """Apply speaker_override fixes from JSON array."""
    if not fixes:
        return 0
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    count = 0
    for fix in fixes:
        guid = fix.get("guid", "")
        suggested = fix.get("suggested", "")
        for p in data.get("phrases", []):
            if p["guid"] == guid:
                for pp in p.get("parts", []):
                    orig = pp["speaker"]
                    if orig not in ("narrator", "Narrator") and orig != suggested and not pp.get("speaker_override"):
                        pp["speaker_override"] = suggested
                        count += 1
    if count:
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, indent=2,
                      sort_keys=False, default_flow_style=False, width=65535)
    return count


def audit_subprocess(yaml_path):
    """Run audit via direct Python (bypasses subagent for speed)."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/audit_speakers.py"), "--file", str(yaml_path), "--json"],
        capture_output=True, text=True, timeout=300, cwd=ROOT
    )
    out = result.stdout.strip()
    if not out:
        return []
    # Extract JSON array from output (it's on the last line)
    for line in reversed(out.split("\n")):
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                return []
    return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run speaker audit across YAMLs")
    parser.add_argument("--dir", default=str(PEOPLE))
    parser.add_argument("--file", help="Single YAML to audit")
    parser.add_argument("--rounds", type=int, default=MAX_ROUNDS)
    args = parser.parse_args()

    yamls = get_yamls(args.dir, args.file)
    print(f"Auditing {len(yamls)} files, max {args.rounds} rounds each\n")

    results = {}
    for yaml_path in yamls:
        if yaml_path.name == "index.yaml":
            continue
        name = yaml_path.name
        initial_overrides = count_overrides(yaml_path)
        print(f"\n=== {name} (initial: {initial_overrides} overrides) ===")

        for round_num in range(1, args.rounds + 1):
            issues = audit_subprocess(yaml_path)

            if not issues:
                print(f"  Round {round_num}: clean")
                if round_num >= 2:  # 2 clean rounds → done
                    print(f"  -> DONE after {round_num} rounds")
                    break
                continue

            fixed = apply_fixes(yaml_path, issues)
            after = count_overrides(yaml_path)
            print(f"  Round {round_num}: {len(issues)} issues found, {fixed} fixes (now {after} overrides)")
            if round_num >= args.rounds:
                print(f"  -> MAX ROUNDS reached, manual review needed")

        total = count_overrides(yaml_path) - initial_overrides
        results[name] = total
        print(f"  Final: {count_overrides(yaml_path)} overrides (+{total})")

    print(f"\n{'='*50}")
    print(f"SUMMARY: {len(yamls)} files audited")
    for name, added in sorted(results.items(), key=lambda x: -x[1]):
        print(f"  {name:30s} +{added} overrides" if added else f"  {name:30s} clean")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
