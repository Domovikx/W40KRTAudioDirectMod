"""Tests for generate_catalog.py — speaker detection, name mapping, event resolution."""

from __future__ import annotations

import pytest

from generate_catalog import build_name_to_char, detect_speaker, resolve_character


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def chars():
    return [
        {
            "name": "Кунрад Войгтвир",
            "gender": "M",
            "role": "Мастер шепотов",
            "personality": "коварный, манипулятивный",
            "voice": "aidar",
            "gemini_voice": "Sadaltager",
            "sound_keys": ["Kunrad", "KunradVoiceover"],
        },
        {
            "name": "Теодора фон Валанциус",
            "gender": "F",
            "role": "Лорд-капитан",
            "personality": "властная, решительная",
            "voice": "xenia",
            "gemini_voice": "Kore",
            "sound_keys": ["Theodora", "TheodoraVoiceover"],
        },
        {
            "name": "Абеляр Версериан",
            "gender": "M",
            "role": "Сенешаль",
            "personality": "суровый, верный",
            "voice": "eugene",
            "gemini_voice": "Algenib",
            "sound_keys": ["Abelard", "AbelardVoiceover"],
        },
    ]


# ── build_name_to_char ───────────────────────────────────────────────────

class TestBuildNameToChar:
    def test_first_name_mapped(self, chars):
        m = build_name_to_char(chars)
        assert m["Кунрад"] == "Кунрад Войгтвир"
        assert m["Теодора"] == "Теодора фон Валанциус"

    def test_last_name_mapped(self, chars):
        m = build_name_to_char(chars)
        assert m["Войгтвир"] == "Кунрад Войгтвир"
        assert m["Валанциус"] == "Теодора фон Валанциус"

    def test_full_name_mapped(self, chars):
        m = build_name_to_char(chars)
        assert m["Кунрад Войгтвир"] == "Кунрад Войгтвир"

    def test_npc_aliases(self, chars):
        m = build_name_to_char(chars)
        assert m["Архмилитант"] == "__NPC__"
        assert m["Сенешаль"] == "__NPC__"
        assert m["Мастер шепотов"] == "__NPC__"

    def test_empty_chars(self):
        assert build_name_to_char([]) == {
            "Архмилитант": "__NPC__",
            "Морт": "__NPC__",
            "Мастер шепотов": "__NPC__",
            "Сенешаль": "__NPC__",
        }


# ── detect_speaker ───────────────────────────────────────────────────────

class TestDetectSpeaker:
    def test_narration_at_start(self, chars):
        m = build_name_to_char(chars)
        text = '{n}Кунрад смеется и качает головой.{/n} "Достаточно будет сказать..."'
        assert detect_speaker(text, m) == "Кунрад Войгтвир"

    def test_narration_at_end(self, chars):
        m = build_name_to_char(chars)
        text = '"Мое почтение, {name}..." {n}Кунрад смеривает вас взглядом.{/n}'
        assert detect_speaker(text, m) == "Кунрад Войгтвир"

    def test_another_speaker(self, chars):
        m = build_name_to_char(chars)
        text = '{n}Теодора бросает на вас гневный взгляд.{/n} "Ты смеешь перечить мне!"'
        assert detect_speaker(text, m) == "Теодора фон Валанциус"

    def test_no_narration(self, chars):
        m = build_name_to_char(chars)
        text = '"Да. И вскоре вы с ним познакомитесь".'
        assert detect_speaker(text, m) is None

    def test_generic_description(self, chars):
        m = build_name_to_char(chars)
        text = '{n}Ваш собеседник слегка кланяется.{/n} "Счастлив угодить вам"'
        assert detect_speaker(text, m) is None

    def test_multiple_blocks_same_speaker(self, chars):
        m = build_name_to_char(chars)
        text = '{n}Кунрад злобно усмехается.{/n} "Ты думал..." {n}он делает паузу{/n} ...не выбирают'
        assert detect_speaker(text, m) == "Кунрад Войгтвир"

    def test_npc_role_not_mapped(self, chars):
        m = build_name_to_char(chars)
        text = '{n}Архмилитант оглядывается на вас.{/n} "Что, Лорд-капитан прислала?"'
        assert detect_speaker(text, m) == "__NPC__"

    def test_no_blocks_returns_none(self, chars):
        m = build_name_to_char(chars)
        assert detect_speaker("Просто текст без разметки", m) is None
        assert detect_speaker("", m) is None

    def test_only_closing_tag_no_opening(self, chars):
        m = build_name_to_char(chars)
        text = 'Текст с {/n} без открывающего'
        assert detect_speaker(text, m) is None

    def test_last_name_in_narration(self, chars):
        m = build_name_to_char(chars)
        text = '{n}Войгтвир колеблется секунду.{/n} "Когда все будет завершено..."'
        assert detect_speaker(text, m) == "Кунрад Войгтвир"

    def test_full_name_in_narration(self, chars):
        m = build_name_to_char(chars)
        text = '{n}Кунрад Войгтвир облегченно вздыхает.{/n} "Хвала провидению..."'
        assert detect_speaker(text, m) == "Кунрад Войгтвир"

    def test_male_suffix(self, chars):
        m = build_name_to_char(chars)
        text = '"{mf|ый|ая} день". {n}Теодора кивает.{/n} "Верно".'
        assert detect_speaker(text, m) == "Теодора фон Валанциус"

    def test_narration_with_generic_text_before_name(self, chars):
        m = build_name_to_char(chars)
        text = '{n}При ваших словах Кунрад белеет.{/n} "Смотрю, вы уже втерлись..."'
        # Name not at start of block — not detected (edge case, defaults to file owner)
        assert detect_speaker(text, m) is None

    def test_narration_with_title_and_name(self, chars):
        m = build_name_to_char(chars)
        text = '{n}Леди Теодора качает головой.{/n} "Кунрад... присмотри за гостем."'
        # "Леди" is not a known name token, so falls through — no match
        assert detect_speaker(text, m) is None


# ── resolve_character ────────────────────────────────────────────────────

class TestResolveCharacter:
    def test_exact_key_match(self, chars):
        char_map = {"Kunrad": "Кунрад Войгтвир", "Theodora": "Теодора фон Валанциус"}
        name, _ = resolve_character("PRL_KunradIntroduction_01", char_map, chars)
        assert name == "Кунрад Войгтвир"

    def test_theodora_event(self, chars):
        char_map = {"Kunrad": "Кунрад Войгтвир", "Theodora": "Теодора фон Валанциус"}
        name, _ = resolve_character("PRL_TheodoraSpeech_01", char_map, chars)
        assert name == "Теодора фон Валанциус"

    def test_no_match(self, chars):
        char_map = {"Kunrad": "Кунрад Войгтвир"}
        name, _ = resolve_character("UNKNOWN_EVENT_01", char_map, chars)
        assert name is None


# ── gemini_voice field in generated catalog ─────────────────────────────

@pytest.fixture(scope="session")
def kunrad_catalog():
    import yaml
    from pathlib import Path
    # __file__ is in .opencode/skills/text-catalog/scripts/ → go up 5 to mod root
    path = Path(__file__).parent.parent.parent.parent.parent / "catalog" / "people" / "Кунрад_Войгтвир.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestGeminiVoiceField:
    def test_every_phrase_has_gemini_voice_field(self, kunrad_catalog):
        for p in kunrad_catalog["phrases"]:
            assert "gemini_voice" in p, f'{p["event"]} missing gemini_voice'

    def test_npc_phrases_have_null_voice(self, kunrad_catalog):
        """Phrases with Архмилитант/Морт in {n} should have null voice."""
        npc_events = {"PRL_KunradUnpleasantNews_03", "PRL_KunradUnpleasantNews_06"}
        for p in kunrad_catalog["phrases"]:
            if p["event"] in npc_events:
                assert p["gemini_voice"] is None, f'{p["event"]} should have null voice'

    def test_kunrad_own_phrases_use_sadaltager(self, kunrad_catalog):
        """Phrases where speaker explicitly equals file owner."""
        for p in kunrad_catalog["phrases"]:
            if p["speaker"] == kunrad_catalog["name"]:
                assert p["gemini_voice"] == "Sadaltager", f'{p["event"]} expected Sadaltager'

    def test_theodora_phrases_use_kore(self, kunrad_catalog):
        """Theodora's 6 phrases should use Kore voice."""
        theodora_events = {
            "PRL_KunradUnpleasantNews_07",
            "PRL_KunradUnpleasantNews_09",
            "PRL_KunradUnpleasantNews_11",
            "PRL_KunradUnpleasantNews_12",
            "PRL_KunradUnpleasantNews_13",
            "PRL_KunradUnpleasantNews_14",
        }
        for p in kunrad_catalog["phrases"]:
            if p["event"] in theodora_events:
                assert p["gemini_voice"] == "Kore", \
                    f'{p["event"]}: expected Kore, got {p["gemini_voice"]}'

    def test_every_phrase_has_gemini_text_null(self, kunrad_catalog):
        for p in kunrad_catalog["phrases"]:
            assert "gemini_text" in p
            assert p["gemini_text"] is None
