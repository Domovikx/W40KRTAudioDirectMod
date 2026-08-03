#!/usr/bin/env python3
"""Extract GUID->Speaker mapping from blueprints-pack.bbp.

Single pass: scan for all $GUID patterns, look backwards for Russian speaker name.
Filter to only Sound.json GUIDs. RU->EN map from config/name_map.yaml.
"""

import os, json, yaml, re
from pathlib import Path
from collections import defaultdict

GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40,000 Rogue Trader"
BBP = os.path.join(GAME, "Bundles", "blueprints-pack.bbp")
SOUND = os.path.join(GAME, "WH40KRT_Data", "StreamingAssets", "Localization", "Sound.json")
ROOT = Path(__file__).resolve().parent.parent
CONFIG_NAME_MAP = ROOT / "config" / "name_map.yaml"
OUT = ROOT / "catalog" / "bbp_speakers.yaml"

with open(CONFIG_NAME_MAP, encoding="utf-8") as f:
    name_map_data = yaml.safe_load(f)
RU_TO_EN = name_map_data.get("ru_aliases", {})

# $GUID regex — use [$] to avoid backslash issues
GUID_RE = re.compile(rb'[$]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})')


def build_sound_set() -> set:
    with open(SOUND, encoding="utf-8") as f:
        sound = json.load(f)
    return set(sound["strings"].keys())


def build_ru_bytes_map() -> dict:
    """Build {ru_bytes: en_name} for fast lookup in binary."""
    result = {}
    for ru_name, en_name in RU_TO_EN.items():
        result[ru_name.encode("utf-8")] = en_name
    return result


def find_nearest_speaker(data: bytes, pos: int, max_lookback: int = 500) -> str | None:
    """Look backwards from pos for the nearest Russian speaker name."""
    start = max(0, pos - max_lookback)
    chunk = data[start:pos]
    best_name = None
    best_dist = max_lookback + 1
    for ru_bytes, en_name in RU_BYTES.items():
        idx = chunk.rfind(ru_bytes)
        if idx >= 0:
            dist = pos - (start + idx)
            if dist < best_dist:
                best_dist = dist
                best_name = en_name
    return best_name


def main():
    sound_set = build_sound_set()
    global RU_BYTES
    RU_BYTES = build_ru_bytes_map()

    with open(BBP, "rb") as f:
        data = f.read()
    print(f"BBP: {len(data)/1024/1024:.0f}MB, Sound.json: {len(sound_set)} GUIDs")

    results = {}
    total_match = 0
    in_sound = 0

    for m in GUID_RE.finditer(data):
        guid = m.group(1).decode("ascii")
        total_match += 1

        if guid not in sound_set:
            continue
        in_sound += 1

        speaker = find_nearest_speaker(data, m.start())
        if speaker:
            results[guid] = speaker

    print(f"Total \$GUID in BBP: {total_match}")
    print(f"Sound.json GUIDs found in BBP: {in_sound}")
    print(f"With speaker name: {len(results)}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        yaml.dump({"speakers": results}, f, allow_unicode=True, default_flow_style=False)
    print(f"Saved to {OUT}")

    if results:
        from collections import Counter
        speaker_counts = Counter(results.values())
        print(f"\nSpeakers ({len(speaker_counts)}):")
        for name, count in speaker_counts.most_common():
            print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
