"""Clean raw game dialog text into TTS-ready text_clean.

Handles all known markup patterns from W40KRT localization:
- {g|...}...{/g}, {d|...}...{/d} — encyclopedia links (keep inner text)
- {mf|word1|word2} — gender selection (pick masculine form)
- {rt_mf|word1|word2} — runtime gender (pick masculine form)
- {n}...{/n} — narrator narration blocks (returned separately)
- {name} — player name placeholder (kept verbatim)
- Outer "..." quotes stripped from character speech

Usage:
    from clean_text import clean_text, split_into_parts

    parts = split_into_parts(text_original)
    for part in parts:
        print(part["speaker"], clean_text(part["text"]))
"""

import re
from typing import List


def clean_text(raw: str, keep_outer_quotes: bool = False, name_replacement: str = "КЭП") -> str:
    s = raw

    s = _strip_outer_quotes(s, keep=keep_outer_quotes)

    s = re.sub(r"\{g\|[^}]*\}([^}]*?)\{/g\}", r"\1", s)
    s = re.sub(r"\{d\|[^}]*\}([^}]*?)\{/d\}", r"\1", s)

    s = re.sub(r"\{mf\|([^|]*)\|[^}]*\}", r"\1", s)
    s = re.sub(r"\{rt_mf\|([^|]*)\|[^}]*\}", r"\1", s)

    if name_replacement:
        s = s.replace("{name}", name_replacement)

    s = _normalize_whitespace(s)

    return s.strip()


def split_into_parts(raw: str, default_speaker: str = "character", name_replacement: str = "КЭП") -> List[dict]:
    parts: List[dict] = []

    segments = _split_narrator_blocks(raw)

    for segment_text, is_narrator in segments:
        text = clean_text(segment_text, keep_outer_quotes=is_narrator, name_replacement=name_replacement).strip()
        if not text:
            continue
        if text in _LEFT_QUOTES or text in _RIGHT_QUOTES:
            continue
        parts.append({
            "speaker": "narrator" if is_narrator else default_speaker,
            "text_clean": text,
        })

    return parts


_LEFT_QUOTES = {"\u201c", "\u00ab", '"'}
_RIGHT_QUOTES = {"\u201d", "\u00bb", '"'}


def _strip_outer_quotes(s: str, keep: bool = False) -> str:
    if keep:
        return s
    s = s.strip()
    if not s:
        return s

    if s[0] not in _LEFT_QUOTES:
        return s

    for i in range(len(s) - 1, -1, -1):
        if s[i] in _RIGHT_QUOTES:
            return (s[1:i] + s[i + 1:]).strip()

    return s


def _split_narrator_blocks(raw: str) -> List:
    results = []
    pattern = re.compile(r"\{n\}(.*?)\{/n\}", re.DOTALL)
    pos = 0

    for m in pattern.finditer(raw):
        before = raw[pos : m.start()]
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


def _normalize_whitespace(s: str) -> str:
    s = re.sub(r"[ \t]+", " ", s)

    s = re.sub(r"^ +", "", s, flags=re.MULTILINE)
    s = s.replace("\n", " ")

    s = re.sub(r"\s+([.,!?;:])", r"\1", s)
    s = re.sub(r"(\()\s+", r"\1", s)
    s = re.sub(r"\s+(\))", r"\1", s)

    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()
