#!/usr/bin/env python3
"""L2+L3 — sound-event speakers and owner hints for guid_map.json.

L2 (Sound.json): for voiced GUIDs, attaches the Wwise event name and a
speaker detected from the event name (ported extract_speaker_from_event from
v1 generate_catalog.py, ~88.9% precision).

    guid_map[guid]["sound"] = {"event": "<name>", "speaker": "<char>" | null}

L3 (owner prefixes): for blueprint owners (bark/env/other), classifies the
owner string into a character hint by token matching.

    guid_map[guid]["owner_hint"] = "<char>"   (only when matched)

Validation (exit 1 on failure):
    - every sound GUID exists in guid_map (subset of ruRU)
    - speaker coverage reported in stats

Usage:
    python catalog_2/tools/enrich_sound.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
GUID_MAP = ROOT / "catalog_2" / "raw" / "guid_map.json"
SOUND_JSON = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40,000 Rogue Trader\WH40KRT_Data\StreamingAssets\Localization\Sound.json")
NAME_MAP = ROOT / "config" / "name_map.yaml"

# (en name token | role word) -> full character name
CHAR_TOKENS = {
    "Abelard": "Abelard Werserian", "Werserian": "Abelard Werserian",
    "Cassia": "Cassia Orsellio", "Orsellio": "Cassia Orsellio",
    "Heinrix": "Heinrix van Calox", "Calox": "Heinrix van Calox",
    "Pasqal": "Pasqal Haneumann", "Haneumann": "Pasqal Haneumann",
    "Argenta": "Sister Argenta", "Idira": "Idira Tlass", "Tlass": "Idira Tlass",
    "Yrliet": "Yrliet Lanaeviss", "Lanaeviss": "Yrliet Lanaeviss",
    "Jae": "Jae Heydari", "Heydari": "Jae Heydari",
    "Kibellah": "Kibellah", "Ulfar": "Ulfar",
    "Marazhai": "Marazhai Aezyrraesh", "Aezyrraesh": "Marazhai Aezyrraesh",
    "Solomon": "Solomon Antar", "Antar": "Solomon Antar",
    "Kunrad": "Kunrad Voigtvir", "Voigtvir": "Kunrad Voigtvir",
    "Theodora": "Theodora von Valancius", "Valancius": "Theodora von Valancius",
    "Edelthrad": "Edelthrad", "Eogann": "Eogann", "Trazyn": "Trazyn",
    "Manipulus": "Manipulus",
    # in-game spellings found in event names
    "Pascal": "Pasqal Haneumann",
    "Solomorne": "Solomon Antar", "Solomorn": "Solomon Antar",
    # Companions role words (segment[1] of Companions_* events)
    "Smugler": "Jae Heydari", "Navigator": "Cassia Orsellio",
    "Techpriest": "Pasqal Haneumann", "Interrogator": "Heinrix van Calox",
    "Ranger": "Yrliet Lanaeviss", "Psyker": "Idira Tlass",
    "Sororitas": "Sister Argenta", "Seneschal": "Abelard Werserian",
    # voices.yaml voice names for generic fills
    "DefaultMale": "Generic Male NPC", "DefaultFemale": "Generic Female NPC",
}

RU_ROLE_TOKENS = {
    "Сенешаль": "Abelard Werserian", "сенешаль": "Abelard Werserian",
    "сенешаля": "Abelard Werserian",
    "Дознаватель": "Heinrix van Calox", "дознаватель": "Heinrix van Calox",
    "Интеррогатор": "Heinrix van Calox", "интеррогатор": "Heinrix van Calox",
    "Навигатор": "Cassia Orsellio", "навигатора": "Cassia Orsellio",
    "Псайкер": "Idira Tlass", "псайкер": "Idira Tlass",
    "Техножрец": "Pasqal Haneumann", "техножрец": "Pasqal Haneumann",
    "Следопыт": "Yrliet Lanaeviss", "следопыт": "Yrliet Lanaeviss",
    "Архмилитант": "Sister Argenta", "Контрабандистка": "Jae Heydari",
}


# Prefixes whose segment[1..2] are speaker names (may be camelCased with suffix).
# PRL/CH1-3/RMNC are scene names (subject, NOT speaker) — exact match only.
PREFIX_MATCH_PREFIXES = (
    "BNTRS", "Companions", "CompanionDialogue", "BS", "RM",
    "OfficialPropos", "ManipulusFirstMeet", "TrazynOffer", "TrazynFirstMeet",
    "TrazynInYourRoom", "TrazynShowdown", "TrazynAfterOffer", "ArbitesAfterSex",
)


def extract_speaker_from_event(event_name: str, aliases: dict[str, str]) -> str | None:
    parts = event_name.split("_")
    if not parts:
        return None
    prefix = parts[0]
    if prefix in ("NARR", "speaker", "DeathCultIntroduction"):
        return None
    use_prefix = prefix in PREFIX_MATCH_PREFIXES

    def _try(segment: str) -> str | None:
        r = aliases.get(segment.lower()) or aliases.get(segment)
        if r:
            return r
        if use_prefix and len(segment) >= 6:
            low = segment.lower()
            for k, v in aliases.items():
                if len(k) >= 5 and low.startswith(k.lower()):
                    return v
        return None

    candidates: list[str] = []
    if prefix == "BNTRS":
        if len(parts) >= 5 and parts[1] in ("Companion", "Reactivity") and parts[2] == "DLC3":
            candidates.append(parts[3])
        elif len(parts) >= 4:
            candidates.append(parts[2])
    elif prefix in ("Companions", "CompanionDialogue"):
        if len(parts) >= 2:
            candidates.append(parts[1])
    elif prefix in ("PRL", "CH1", "CH2", "CH3"):
        if len(parts) >= 2:
            for seg in parts[1:]:
                if _try(seg):
                    candidates.append(seg)
                    break
    elif prefix == "RMNC":
        for seg in parts[1:]:
            if _try(seg):
                candidates.append(seg)
                break
        else:
            for seg in parts[1:]:
                seg_lower = seg.lower()
                for key in aliases:
                    if key in seg_lower:
                        candidates.append(seg)
                        break
                if candidates:
                    break
    elif prefix in ("BS", "RM"):
        if len(parts) >= 3:
            candidates.append(parts[2])
    elif prefix in ("OfficialPropos", "ManipulusFirstMeet",
                     "TrazynOffer", "TrazynFirstMeet", "TrazynInYourRoom",
                     "TrazynShowdown", "TrazynAfterOffer", "ArbitesAfterSex"):
        if len(parts) >= 2:
            candidates.append(parts[1])
    elif prefix == "Solomorn":
        r = _try("solomorne") or _try("solomorn")
        if r:
            return r

    for c in candidates:
        r = _try(c)
        if r:
            return r
    return None


def build_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for token, char in CHAR_TOKENS.items():
        aliases[token.lower()] = char
        aliases[token] = char
    if NAME_MAP.exists():
        with open(NAME_MAP, encoding="utf-8") as f:
            nm = yaml.safe_load(f)
        for k in ("ru_aliases", "title_aliases", "ru_full_names"):
            for ru_name, char in (nm.get(k) or {}).items():
                aliases[ru_name.lower()] = char
                aliases[ru_name] = char
    people_dir = ROOT / "catalog" / "people"
    if people_dir.exists():
        for yf in sorted(people_dir.glob("*.yaml")):
            try:
                with open(yf, encoding="utf-8") as f:
                    person = yaml.safe_load(f)
            except Exception:
                continue
            cname = (person or {}).get("name") or ""
            for tok in re.split(r"[^A-Za-zА-Яа-яЁё]+", cname):
                if len(tok) > 1:
                    aliases[tok.lower()] = cname
                    aliases[tok] = cname
    for ru, char in RU_ROLE_TOKENS.items():
        aliases[ru.lower()] = char
        aliases[ru] = char
    return aliases


def owner_hint(owner: str, aliases: dict[str, str]) -> str | None:
    tokens = re.split(r"[^A-Za-zА-Яа-яЁё]+", owner)
    for tok in tokens:
        if not tok:
            continue
        r = aliases.get(tok.lower()) or aliases.get(tok)
        if r:
            return r
    return None


def main() -> None:
    with open(GUID_MAP, encoding="utf-8") as f:
        guid_map = json.load(f)
    print(f"guid_map loaded: {len(guid_map)} keys")

    with open(SOUND_JSON, encoding="utf-8") as f:
        sound_data = json.load(f)
    sound = sound_data.get("strings", sound_data)
    print(f"Sound.json events: {len(sound)}")

    aliases = build_aliases()

    # ---- L2 ----
    n_sound = 0
    n_speaker = 0
    missing = 0
    for g, info in sound.items():
        if g not in guid_map:
            continue
        event = info.get("Text", "")
        if not event:
            continue
        speaker = extract_speaker_from_event(event, aliases)
        entry = guid_map[g]
        entry["sound"] = {"event": event, "speaker": speaker}
        n_sound += 1
        if speaker:
            n_speaker += 1
    print(f"L2 sound events attached: {n_sound}, with speaker: {n_speaker}")

    # ---- L3 ----
    n_hint = 0
    for g, entry in guid_map.items():
        bp = entry.get("blueprint") or {}
        owner = bp.get("owner") or ""
        if not owner:
            continue
        h = owner_hint(owner, aliases)
        if h:
            entry["owner_hint"] = h
            n_hint += 1
    print(f"L3 owner hints: {n_hint}")

    errors = []
    sound_keys = set(sound)
    foreign = sound_keys - set(guid_map)
    if foreign:
        errors.append(f"sound guids not in guid_map: {len(foreign)}")

    with open(GUID_MAP, "w", encoding="utf-8") as f:
        json.dump(guid_map, f, ensure_ascii=False, indent=1)
    print(f"guid_map saved: {len(guid_map)} keys")

    if errors:
        print("FAIL:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"VALIDATION OK  sound={n_sound}  speaker={n_speaker}  hints={n_hint}")


if __name__ == "__main__":
    main()