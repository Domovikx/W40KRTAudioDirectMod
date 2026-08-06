#!/usr/bin/env python3
"""Scan the catalog for speaker candidates that need manual/agent review.

Finds and ranks suspicious parts across all catalog/people/*.yaml:

  OWNER_MISMATCH     — part.speaker differs from the file owner, no override
  NARR_MISMATCH      — narration names character X != owner, owner speaks after
  SELF_ADDR          — non-narrator text addresses the part speaker by name/title
  GENDER             — self-referential grammar ("я сказал/сказала") contradicts voice
  COMPANIONS_MISMATCH — Companions_X event where part speaker != expected companion

Known-good Companions parts (speaker == expected companion) are reported as
KNOWN, not candidates.

Usage:
    python tools/scan_speaker_candidates.py [--file X.yaml] [--json out.json]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEOPLE = os.path.join(ROOT, "catalog", "people")
VOICES = os.path.join(ROOT, "config", "voices.yaml")
NAME_MAP = os.path.join(ROOT, "config", "name_map.yaml")

COMPANIONS = {
    "Smugler": "Jae Heydari",
    "Smuggler": "Jae Heydari",
    "Navigator": "Cassia Orsellio",
    "Techpriest": "Pasqal Haneumann",
    "Interrogator": "Heinrix van Calox",
    "Ranger": "Yrliet Lanaeviss",
    "Psyker": "Idira Tlass",
    "Sororitas": "Sister Argenta",
    "Seneschal": "Abelard Werserian",
    "Ulfar": "Ulfar",
    "Marazhai": "Marazhai Aezyrraesh",
    "Kibellah": "Kibellah",
}

FEM_SELF = re.compile(
    r"\bя\s+(?:же\s+|уж\s+|не\s+|бы\s+)*(?:поверила|сказала|сделала|была|могла|хотела|"
    r"знала|помнила|поняла|услышала|увидела|решила|пошла|встала|улыбнулась|спросила|"
    r"ответила|произнесла|добавила|вздохнула|огляделась|шагнула|кивнула|посмотрела|"
    r"подошла|вернулась|прервала|перевела|склонилась|присела|вздрогнула|остановилась|"
    r"поднялась|уверена|готова|должна|рада|сама|одна)\b", re.I)

MASC_SELF = re.compile(
    r"\bя\s+(?:же\s+|уж\s+|не\s+|бы\s+)*(?:поверил|сказал|сделал|был|мог|хотел|знал|"
    r"помнил|понял|услышал|увидел|решил|пошёл|пошел|встал|улыбнулся|спросил|ответил|"
    r"произнёс|произнес|добавил|вздохнул|огляделся|шагнул|кивнул|посмотрел|подошёл|"
    r"подошел|вернулся|прервал|перевёл|перевел|склонился|присел|вздрогнул|остановился|"
    r"поднялся|уверен|готов|должен|рад|сам|один)\b", re.I)

NARR = re.compile(r"\{n\}(.*?)\{/n\}", re.DOTALL)


def load_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_voice(speaker: str, voices: dict) -> str | None:
    norm = speaker.lower().replace("_", " ").replace("-", " ").strip()
    for vname, ref in voices.get("references", {}).items():
        for c in ref.get("characters", []):
            nc = c.lower().replace("_", " ").replace("-", " ").strip()
            if norm == nc or norm in nc or nc in norm:
                return vname
    return None


def voice_gender(vname: str, voices: dict) -> str | None:
    return voices.get("references", {}).get(vname, {}).get("gender")


def split_segments(raw: str) -> list[tuple[str, bool]]:
    results: list[tuple[str, bool]] = []
    pos = 0
    for m in NARR.finditer(raw):
        before = raw[pos:m.start()]
        if before.strip():
            results.append((before, False))
        results.append((m.group(1), True))
        pos = m.end()
    after = raw[pos:]
    if after.strip():
        results.append((after, False))
    if not results:
        results.append((raw, False))
    return results


def load_names() -> dict:
    if not os.path.exists(NAME_MAP):
        return {}
    with open(NAME_MAP, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    result: dict[str, str] = {}
    for section in ("ru_aliases", "title_aliases", "ru_full_names"):
        result.update(data.get(section, {}))
    return result


def leading_name(text: str, names: dict) -> tuple[str, str] | None:
    stripped = text.strip().strip("\"'«»„“”")
    for token, cn in sorted(names.items(), key=lambda x: -len(x[0])):
        if len(token) > 2 and stripped.startswith(token):
            return token, cn
    return None


def scan_file(path: str, names: dict, voices: dict) -> dict:
    data = load_yaml(path)
    owner = data.get("name", "")
    candidates: list[dict] = []
    known: list[dict] = []

    for ph in data.get("phrases", []):
        guid = ph.get("guid", "")
        event = ph.get("event", "") or ""
        segments = split_segments(ph.get("text", "") or "")
        non_narr_segments = [s for s, is_n in segments if not is_n]
        parts = ph.get("parts", [])

        exp_companion = None
        if event.startswith("Companions_"):
            role = event.split("_", 1)[1].split("_", 1)[0]
            exp_companion = COMPANIONS.get(role)

        for idx, pp in enumerate(parts, start=1):
            spk = pp.get("speaker", "")
            ovr = pp.get("speaker_override")
            effective = ovr or spk
            tc = (pp.get("text_clean") or "").strip()
            if not tc:
                continue

            flags: list[str] = []
            reason: list[str] = []
            is_narr_part = spk == "narrator"

            if exp_companion and not is_narr_part:
                if spk == exp_companion and not ovr:
                    known.append({
                        "guid": guid, "part": idx, "speaker": spk,
                        "text": tc[:100], "event": event[:40],
                    })
                    continue
                if spk != exp_companion and not ovr and spk == owner:
                    flags.append("COMPANIONS_MISMATCH")
                    reason.append(f"event {event[:30]}: expected {exp_companion}")

            if not is_narr_part and spk != owner and not ovr:
                flags.append("OWNER_MISMATCH")
                reason.append(f"speaker '{spk}' != owner '{owner}'")

            vname = resolve_voice(effective, voices)
            g = voice_gender(vname, voices) if vname else None
            if g == "male" and FEM_SELF.search(tc):
                flags.append("GENDER")
                reason.append('"я ..." feminine on male voice')
            if g == "female" and MASC_SELF.search(tc):
                flags.append("GENDER")
                reason.append('"я ..." masculine on female voice')

            if not is_narr_part:
                first = non_narr_segments[0].strip().strip("\"'«»„“”") if non_narr_segments else ""
                for token, cn in names.items():
                    if cn == effective and len(token) > 1 and first.startswith(token):
                        flags.append("SELF_ADDR")
                        reason.append(f"text addresses '{token}'")
                        break

            if not is_narr_part and not ovr and spk == owner:
                for seg_text, is_narr in segments:
                    if not is_narr:
                        continue
                    named = leading_name(seg_text, names)
                    if named and named[1] != owner:
                        flags.append("NARR_MISMATCH")
                        reason.append(f"narration names {named[1]}, owner speaks")
                        break

            if flags:
                candidates.append({
                    "guid": guid,
                    "part": idx,
                    "speaker": spk,
                    "override": ovr,
                    "voice": vname,
                    "event": event[:40],
                    "text": tc[:120],
                    "flags": flags,
                    "reason": "; ".join(reason),
                })

    candidates.sort(key=lambda c: (-len(c["flags"]), c["guid"]))
    return {"candidates": candidates, "known": known}


def main() -> int:
    p = argparse.ArgumentParser(description="Scan catalog for speaker candidates")
    p.add_argument("--file", help="Scan only this file (catalog/people/X.yaml)")
    p.add_argument("--json", help="Write report to this JSON file")
    p.add_argument("--include-player-answers", action="store_true")
    args = p.parse_args()

    voices = load_yaml(VOICES)
    names = load_names()
    files = [args.file] if args.file else sorted(glob.glob(os.path.join(PEOPLE, "*.yaml")))
    report: list[dict] = []

    for path in files:
        base = os.path.basename(path)
        if base == "index.yaml":
            continue
        if base == "Player_Answers.yaml" and not args.include_player_answers:
            continue
        res = scan_file(path, names, voices)
        if res["candidates"]:
            report.append({"file": base, "candidates": res["candidates"]})
        if res["known"] and base == "Generic_Male_NPC.yaml":
            print(f"  [{base}] known-good Companions parts: {len(res['known'])}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"written {args.json}")

    total = 0
    for entry in report:
        n = len(entry["candidates"])
        total += n
        print(f"\n=== {entry['file']}: {n} ===")
        for c in entry["candidates"]:
            print(f"  [{','.join(c['flags'])}] {c['guid'][:8]} p{c['part']} "
                  f"spk={c['speaker']} ovr={c['override']} -> {c['voice']}")
            print(f"      {c['reason']} | {c['text']}")
    print(f"\nTOTAL candidates: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
