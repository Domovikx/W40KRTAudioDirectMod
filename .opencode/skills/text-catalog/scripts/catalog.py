#!/usr/bin/env python3
"""
Каталог диалоговых реплик для озвучки.
Читает Sound.json + ruRU.json + уже сгенерированные WAV + config/characters.yaml.

Usage:
    python catalog.py --stats              # статистика по персонажам
    python catalog.py --chars              # список всех персонажей
    python catalog.py --char Абеляр        # реплики Абеляра
    python catalog.py --char Абеляр --todo # только несгенерированные
    python catalog.py --json catalog.json  # экспорт в JSON
"""

from __future__ import annotations
import argparse, json, os, sys, yaml
from collections import defaultdict
from pathlib import Path

GAME = "C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40,000 Rogue Trader"
MOD_DIR = Path(__file__).parent.parent.parent.parent.parent  # корень мода
LOC_DIR = MOD_DIR / "Localization"


def load_sound_json() -> dict[str, str]:
    path = Path(GAME) / "WH40KRT_Data" / "StreamingAssets" / "Localization" / "Sound.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {guid: entry["Text"] for guid, entry in data["strings"].items()}


def load_texts(lang: str = "ruRU") -> dict[str, str]:
    path = Path(GAME) / "WH40KRT_Data" / "StreamingAssets" / "Localization" / f"{lang}.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {guid: entry["Text"] for guid, entry in data["strings"].items()}


def load_generated(lang: str = "ruRU") -> set[str]:
    wav_dir = LOC_DIR / lang
    if not wav_dir.exists():
        return set()
    return {f.stem for f in wav_dir.glob("*.wav") if len(f.stem) == 36}


def load_characters() -> list[dict]:
    """Загрузить персонажей из Localization/ruRU/people/ или config/characters.yaml."""
    people_dir = MOD_DIR / "Localization" / "ruRU" / "people"
    char_yaml = MOD_DIR / "config" / "characters.yaml"
    if people_dir.exists():
        chars = []
        for path in sorted(people_dir.glob("*.yaml")):
            with open(path, encoding="utf-8") as f:
                chars.append(yaml.safe_load(f))
        return chars
    if char_yaml.exists():
        with open(char_yaml, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("characters", [])
    return []


def build_char_map(chars: list[dict]) -> dict[str, str]:
    """sound_key → name для быстрого маппинга."""
    mapping = {}
    for c in chars:
        name = c["name"]
        for key in c.get("sound_keys", []):
            if key:
                mapping[key] = name
    return mapping


def resolve_character(event_name: str, char_map: dict[str, str],
                      chars: list[dict]) -> tuple[str | None, dict | None]:
    """Вернуть (name, char_dict) или (fallback_name, fallback_dict)."""
    for key in sorted(char_map, key=len, reverse=True):
        if key in event_name:
            name = char_map[key]
            for c in chars:
                if c["name"] == name:
                    return name, c
            return name, None
    # fallback
    for c in chars:
        if c["name"] == "NPC (по умолчанию)":
            return c["name"], c
    return None, None


def extract_catalog(lang: str = "ruRU", todo: bool = False):
    events = load_sound_json()
    texts = load_texts(lang)
    generated = load_generated(lang)
    chars = load_characters()
    char_map = build_char_map(chars)

    catalog = defaultdict(list)
    unassigned = []

    for guid, event in sorted(events.items(), key=lambda x: x[1]):
        if guid not in texts:
            continue
        text = texts[guid]
        if len(text) < 3:
            continue

        done = guid in generated
        if todo and done:
            continue

        name, char_data = resolve_character(event, char_map, chars)
        gender = char_data.get("gender", "?") if char_data else "?"
        entry = (guid, text, event, done, gender)

        if name:
            catalog[name].append(entry)
        else:
            unassigned.append(entry)

    return catalog, unassigned


def print_stats(catalog, unassigned, lang: str = "ruRU"):
    generated = load_generated(lang)
    total_guids = sum(len(v) for v in catalog.values()) + len(unassigned)

    print(f"{'Персонаж':<30} {'Пол':>4} {'Gemini голос':<20} {'Всего':>6} {'Осталось':>8}")
    print("-" * 74)
    for name in sorted(catalog):
        entries = catalog[name]
        total = len(entries)
        done = sum(1 for _, _, _, _, _, _ in entries if _[3])  # Hmm, wrong. Let me fix
        # Actually entries are tuples (guid, text, event, done, gender, gv)
        done = sum(1 for e in entries if e[3])
        left = total - done
        gender = entries[0][4] if entries else "?"
        gv = entries[0][5] if entries else "?"
        print(f"{name:<30} {gender:>4} {gv:<20} {total:>6} {left:>8}")

    if unassigned:
        print(f"{'(неопознано)':<30} {'?':>4} {'?':<20} {len(unassigned):>6} {'?':>8}")

    total_done = sum(1 for v in catalog.values() for e in v if e[3])
    print("-" * 74)
    print(f"{'ИТОГО':<30} {'':>4} {'':<20} {total_guids:>6} {total_guids - total_done:>8}")
    print(f"\nСгенерировано WAV: {len(generated)}")


def list_chars():
    """Вывести таблицу всех персонажей."""
    chars = load_characters()
    print(f"{'Персонаж':<30} {'Пол':>4} {'Sound keys':<30}")
    print("-" * 66)
    for c in chars:
        name = c["name"]
        g = c.get("gender", "?")
        keys = ", ".join(c.get("sound_keys", []))
        print(f"{name:<30} {g:>4} {keys:<30}")
    print(f"\nВсего: {len(chars)} персонажей")


def print_char(catalog, char_name: str, todo: bool = False):
    """Вывести реплики конкретного персонажа."""
    entries = catalog.get(char_name, [])
    if not entries:
        print(f"Нет реплик для '{char_name}'")
        return

    gender = entries[0][4]
    done_count = sum(1 for e in entries if e[3])
    print(f"Персонаж: {char_name} ({gender})")
    print(f"Реплик: {len(entries)}, готово: {done_count}\n")

    for guid, text, event, done, _ in entries:
        if todo and done:
            continue
        status = "✅" if done else "⬜"
        print(f"{status} {guid}")
        print(f"     {event}")
        # clean text for display
        text_clean = text.replace("\n", " ").strip()[:150]
        print(f"     {text_clean}")
        print()


def export_json(catalog, unassigned, path: str, todo_only: bool = False):
    data = {}
    for name, entries in catalog.items():
        char_entries = []
        for guid, text, event, done, gender in entries:
            if todo_only and done:
                continue
            char_entries.append({
                "guid": guid,
                "text": text,
                "event": event,
                "done": done,
                "gender": gender,
            })
        if char_entries:
            data[name] = char_entries

    # добавить неопознанные
    unassigned_data = [{
        "guid": guid, "text": text, "event": event, "done": done
    } for guid, text, event, done, _, _ in unassigned if not (todo_only and done)]

    total = sum(len(v) for v in data.values()) + len(unassigned_data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"characters": data, "unassigned": unassigned_data},
                  f, ensure_ascii=False, indent=2)
    print(f"Exported {total} entries to {path}")


def main():
    p = argparse.ArgumentParser(description="Каталог диалоговых реплик")
    p.add_argument("--char", help="Вывести реплики конкретного персонажа")
    p.add_argument("--chars", action="store_true", help="Список всех персонажей")
    p.add_argument("--todo", action="store_true", help="Только несгенерированные")
    p.add_argument("--stats", action="store_true", help="Статистика по персонажам")
    p.add_argument("--json", help="Экспорт в JSON файл")
    p.add_argument("--lang", default="ruRU", help="Язык (ruRU, enGB, ...)")
    args = p.parse_args()

    if args.chars:
        list_chars()
        return

    catalog, unassigned = extract_catalog(args.lang, args.todo)

    if args.stats:
        print_stats(catalog, unassigned, args.lang)
    elif args.char:
        # fuzzy match by any part of name
        chars = load_characters()
        matched = None
        for c in chars:
            name = c["name"]
            if (args.char.lower() in name.lower() or
                args.char.lower() in name.split()[-1].lower()):
                matched = name
                break
        if matched:
            print_char(catalog, matched, args.todo)
        else:
            print(f"Персонаж '{args.char}' не найден")
            print("Доступные: ", ", ".join(sorted(set(list(catalog.keys()) + [c["name"] for c in chars]))))
    elif args.json:
        export_json(catalog, unassigned, args.json, args.todo)
    else:
        print_stats(catalog, unassigned, args.lang)


if __name__ == "__main__":
    main()
