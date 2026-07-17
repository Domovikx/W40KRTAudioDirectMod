"""Convert catalog/people/Кунрад_Войгтвир.yaml to new parts format."""

import re
import yaml
import sys

CHAR = "Кунрад_Войгтвир"
CHAR_NAME = "Кунрад Войгтвир"

# Match {n}...{/n} blocks
NARRATOR_RE = re.compile(r"\{n\}(.*?)\{/n\}")
# Match {g|...}...{/g} blocks — keep inner text
GAME_TAG_RE = re.compile(r"\{g\|[^}]*\}(.*?)\{/g\}")
# Match standalone {g|...} encyclopedia links
GAME_REF_RE = re.compile(r"\{g\|[^}]*\}")


def strip_game_tags(text: str) -> str:
    text = GAME_TAG_RE.sub(r"\1", text)
    text = GAME_REF_RE.sub("", text)
    return text


def split_into_parts(text: str):
    """Split dialog text into narrator/Kunrad parts."""
    parts = []
    last_end = 0

    for m in NARRATOR_RE.finditer(text):
        start, end = m.start(), m.end()

        # Text before this narrator block = Kunrad
        if start > last_end:
            kunrad_text = text[last_end:start].strip().strip('"').strip()
            if kunrad_text:
                parts.append({"speaker": CHAR, "text_clean": strip_game_tags(kunrad_text)})

        # Narrator block
        narrator_text = m.group(1).strip().strip('"').strip()
        if narrator_text:
            parts.append({"speaker": "narrator", "text_clean": strip_game_tags(narrator_text)})

        last_end = end

    # Remaining text after last narrator block = Kunrad
    remaining = text[last_end:].strip().strip('"').strip()
    if remaining:
        parts.append({"speaker": CHAR, "text_clean": strip_game_tags(remaining)})

    # If no narrator blocks at all, everything is Kunrad
    if not parts:
        cleaned = strip_game_tags(text).strip().strip('"').strip()
        if cleaned:
            parts.append({"speaker": CHAR, "text_clean": cleaned})

    return parts


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else (
        r"C:\Users\Domo\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager\W40KRTAudioDirectMod\catalog\people\Кунрад_Войгтвир.yaml"
    )

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    total = 0
    converted = 0
    skipped = 0

    for phrase in data.get("phrases", []):
        total += 1

        # Skip if already in new format
        if "parts" in phrase:
            skipped += 1
            continue

        text = phrase.get("text", "")
        if not text:
            continue

        parts = split_into_parts(text)
        if parts:
            phrase["text_original"] = phrase.pop("text")

        phrase["parts"] = parts
        converted += 1

        # Remove old fields
        for old in ["speaker", "gemini_voice", "gemini_text", "wav", "gemini_audio", "voice"]:
            phrase.pop(old, None)

    # Remove header-level old fields
    for old in ["voice", "gemini_voice", "total_phrases", "gemini_audio"]:
        data.pop(old, None)

    data["total_phrases_new"] = total

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, width=120)

    print(f"Done: {total} total, {converted} converted, {skipped} already new-format")


if __name__ == "__main__":
    main()
