#!/usr/bin/env python3
"""Two-stage speaker audit: investigate then self-validate as antagonist.

Stage 1 (Investigator): scan all YAMLs for potential speaker bugs.
Stage 2 (Antagonist): for each finding, try to prove it's NOT a bug.
Only CONFIRMED issues are reported.

Run:  python tools/audit_speakers.py [--file catalog/people/Kunrad_Voigtvir.yaml]
"""

import sys, yaml, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".opencode/skills/text-catalog/scripts"))
from generate_catalog import _text_addresses_owner, build_name_to_char, load_char_metadata, detect_speaker, _split_segments


def load_name_map() -> dict:
    """Load Russian aliases + full names from config."""
    path = ROOT / "config" / "name_map.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    result = {}
    for section in ("ru_aliases", "title_aliases", "ru_full_names"):
        result.update(data.get(section, {}))
    return result


def is_self_introduction(text: str, speaker: str) -> bool:
    """Antagonist check: is the character just introducing themselves?"""
    # Remove {n}...{/n} blocks for dialog-only analysis
    cleaned = re.sub(r"\{n\}.*?\{/n\}", "", text).strip().strip('"').strip("\u201c").strip("\u00ab")

    # Patterns that indicate self-introduction
    intro_patterns = [
        f"Я — {speaker.split()[0]}" if speaker.split() else "",
        f"Меня зовут {speaker.split()[0]}" if speaker.split() else "",
        f"{speaker.split()[0]} — я" if speaker.split() else "",
        "Позвольте представиться",
        "моё имя",
        f"Я — {speaker}",
    ]
    for pat in intro_patterns:
        if pat and pat in cleaned:
            return True

    # Check if speaker says their own name (e.g. "Кунрад Войгтвир, Мастер шепотов")
    first_name_en = speaker.split()[0] if speaker.split() else ""
    if first_name_en and first_name_en in cleaned:
        # Only if it's clearly an introduction, not an address
        if cleaned.startswith(first_name_en) or cleaned.startswith(f"Я — {first_name_en}"):
            return True

    return False


def is_self_referential_narration(narrator_blocks: list, speaker: str, name_map: dict) -> bool:
    """Antagonist check: narrator describes the speaker's action — that's normal, not a bug."""
    for block in narrator_blocks:
        stripped = block.strip()
        for token, cn in name_map.items():
            if stripped.startswith(token) and cn == speaker:
                return True  # narrator talks ABOUT the speaker — normal
    return False


def investigator_antagonist(file_path: Path) -> list:
    """Two-stage check: find issues, then self-validate."""
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    char_name = data["name"]
    chars = load_char_metadata()
    name_map = build_name_to_char(chars)
    name_map.update(load_name_map())

    confirmed = []

    for p in data.get("phrases", []):
        guid = p["guid"]
        text = p.get("text", "")
        speaker = p.get("speaker", "")
        event = p.get("event", "")
        parts = p.get("parts", [])
        prefix = event.split("_")[0] if event else ""

        # Skip if already has speaker_override
        if any("speaker_override" in pp for pp in parts):
            continue

        # ---- STAGE 1: INVESTIGATOR ----
        flags = []
        suggested_speaker = None

        # Check SELF_ADDR: speaker addressed by name/title
        if speaker and _text_addresses_owner(text, speaker, name_map):
            flags.append("SELF_ADDR")
            ds = detect_speaker(text, name_map, char_name=char_name)
            if ds and ds != speaker and ds != "__NPC__":
                suggested_speaker = ds
            else:
                # Try to find speaker from narrator blocks directly
                segments = _split_segments(text)
                narrator_blocks = [s for s, is_narr in segments if is_narr]
                for block in narrator_blocks:
                    stripped = block.strip()
                    for token, cn in name_map.items():
                        if stripped.startswith(token) and cn != speaker and cn != "__NPC__":
                            if cn not in ("narrator", "Narrator"):
                                suggested_speaker = cn
                                break

        # ---- STAGE 2: ANTAGONIST ----
        if not flags:
            continue

        # Antagonist check 1: self-introduction?
        if is_self_introduction(text, speaker):
            continue

        # Antagonist check 2: narrator describes the speaker (normal)?
        segments = _split_segments(text)
        narrator_blocks = [s for s, is_narr in segments if is_narr]
        if is_self_referential_narration(narrator_blocks, speaker, name_map):
            continue

        # Antagonist check 3: PRL/CH event where speaker == file owner (scene-owner bug)
        if prefix in ("PRL", "CH1", "CH2", "CH3") and speaker == char_name and not suggested_speaker:
            # Can't determine who should speak — NEEDS_HUMAN
            flags.append("NEEDS_HUMAN")

        # CONFIRMED issue
        if suggested_speaker:
            confirmed.append((guid, event, speaker, suggested_speaker, flags, text[:100]))
        elif "NEEDS_HUMAN" in flags:
            confirmed.append((guid, event, speaker, "???", flags, text[:100]))

    return confirmed


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Audit YAMLs for speaker bugs")
    parser.add_argument("--file", help="Single YAML file to audit (omit for all)")
    parser.add_argument("--json", action="store_true", help="Output as JSON for subagent parsing")
    args = parser.parse_args()

    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted((ROOT / "catalog/people").glob("*.yaml"))
        files = [f for f in files if f.name != "index.yaml"]

    all_confirmed = []
    for f in files:
        if f.name == "index.yaml":
            continue
        issues = investigator_antagonist(f)
        if issues:
            print(f"\n=== {f.name} ({len(issues)} confirmed) ===")
            for guid, event, speaker, suggested, flags, text in issues:
                print(f"  GUID: {guid}")
                print(f"  event: {event}")
                print(f"  speaker: {speaker} -> suggested: {suggested}")
                print(f"  flags: {flags}")
                print(f"  text: {text}")
                print()
            all_confirmed.extend(issues)

    print(f"\nTotal confirmed issues: {len(all_confirmed)}")

    if args.json:
        import json
        print(json.dumps([{
            "guid": g, "event": e, "speaker": s, "suggested": sug,
            "flags": fl, "text": txt[:80]
        } for g, e, s, sug, fl, txt in all_confirmed], ensure_ascii=False, indent=2))

    return all_confirmed


if __name__ == "__main__":
    main()
