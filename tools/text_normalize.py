#!/usr/bin/env python3
"""Text normalization shared by the mapping pipeline.

Normalized text is the canonical "what the player sees" form:

- strip TMP rich-text tags `<align="center">...</align>` and `<...>` fragments
- strip game markup: {n} {/n} {g|...}{/g} {d|...}{/d} {mf|...} {rt_mf|...}
- strip outer quotation marks ("...", «...», "..." with closing punctuation)
- collapse whitespace and trim

Both sides of a match must be normalized: the catalog text (text_clean) and
the displayed value captured at runtime.
"""

from __future__ import annotations

import re

TMP_TAG_RE = re.compile(r"<[^>]*>")
GAME_MARKUP_RE = re.compile(r"\{/?[a-zA-Z_]+\|[^}]*\}|\{/?[a-zA-Z_]+\}")
OUTER_QUOTES_RE = re.compile(
    r'^\s*(["\u00ab\u201c\u201e])(.*?)([\u00bb\u201d\u201c"])\s*(\.?)\s*$'
)
WS_RE = re.compile(r"\s+")


def normalize(text: str | None) -> str:
    """Normalize for exact matching. Never returns None."""
    if not text:
        return ""
    s = text
    s = TMP_TAG_RE.sub("", s)          # <align="center"> etc.
    s = GAME_MARKUP_RE.sub("", s)      # {n} {/n} {g|...}{/g} {mf|a|b} {name}
    s = OUTER_QUOTES_RE.sub(r"\2\4", s)  # "Текст". / «Текст». / „Текст"
    s = WS_RE.sub(" ", s).strip()
    return s


def matches(displayed: str | None, catalog_text: str | None) -> bool:
    """True when the displayed text is exactly the catalog text (normalized)."""
    return normalize(displayed) == normalize(catalog_text)
