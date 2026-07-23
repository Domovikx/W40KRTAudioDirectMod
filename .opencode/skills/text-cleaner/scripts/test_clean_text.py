"""Tests for clean_text.py — all patterns from actual game data + edge cases."""

from __future__ import annotations

import pytest

from clean_text import clean_text, split_into_parts

LQ = "\u201c"
RQ = "\u201d"
LQ_G = "\u00ab"
RQ_G = "\u00bb"


G = lambda tag, inner: f"{{g|Encyclopedia:{tag}}}{inner}{{/g}}"
D = lambda tag, inner: f"{{d|Encyclopedia:{tag}}}{inner}{{/d}}"
MF = lambda m, f: f"{{mf|{m}|{f}}}"
RT_MF = lambda m, f: f"{{rt_mf|{m}|{f}}}"


class TestCleanText:
    def test_encyclopedia_g_tag(self):
        assert clean_text(G("Emperor", "Бога-Императора")) == "Бога-Императора"

    def test_encyclopedia_g_tag_with_surrounding_text(self):
        raw = f"величия {G('Emperor', 'Бога-Императора')}, нашедшее"
        assert clean_text(raw) == "величия Бога-Императора, нашедшее"

    def test_encyclopedia_d_tag(self):
        assert clean_text(D("CharGen_MOT_GreatDeed", "смелость")) == "смелость"

    def test_encyclopedia_d_tag_with_surrounding(self):
        raw = f"речь идёт о {D('Emperor', 'Повелителе')} Человечества."
        assert clean_text(raw) == "речь идёт о Повелителе Человечества."

    def test_mf_both_forms(self):
        assert clean_text(MF("иков", "иц")) == "иков"

    def test_mf_first_form_empty(self):
        raw = f"герцог{MF('', 'иня')}"
        assert clean_text(raw) == "герцог"

    def test_mf_second_form_empty(self):
        raw = f"разобравши{MF('йся', '')}"
        assert clean_text(raw) == "разобравшийся"

    def test_mf_in_word_middle(self):
        raw = f"казненн{MF('ым', 'ой')}"
        assert clean_text(raw) == "казненным"

    def test_mf_adjacent_tags(self):
        assert clean_text(f"{MF('Его', 'Ее')} Светлости") == "Его Светлости"

    def test_rt_mf_first_empty(self):
        raw = f"пожаловал{RT_MF('', 'а')}"
        assert clean_text(raw) == "пожаловал"

    def test_rt_mf_both_forms(self):
        assert clean_text(RT_MF("его", "ее")) == "его"

    def test_player_name_replaced_default(self):
        raw = "Вряд ли тебе известны пределы возможного, {name}"
        assert clean_text(raw) == "Вряд ли тебе известны пределы возможного, КЭП"

    def test_player_name_replaced_custom(self):
        raw = "Вряд ли тебе известны пределы возможного, {name}"
        assert clean_text(raw, name_replacement="Капитан") == "Вряд ли тебе известны пределы возможного, Капитан"

    def test_player_name_empty_replacement(self):
        raw = "Вряд ли тебе известны пределы возможного, {name}"
        assert clean_text(raw, name_replacement="") == "Вряд ли тебе известны пределы возможного, {name}"

    def test_outer_quotes_stripped_standard(self):
        raw = f"{LQ}Прекрасное место для размышлений{RQ}."
        assert clean_text(raw) == "Прекрасное место для размышлений."

    def test_outer_quotes_stripped_with_ellipsis(self):
        raw = f"{LQ}Я вижу ваше изумление... да.{RQ}"
        assert clean_text(raw) == "Я вижу ваше изумление... да."

    def test_inner_quotes_preserved(self):
        raw = f"Особенности имперских традиций. {LQ}Лорд-капитан{RQ} — священный титул."
        assert clean_text(
            raw
        ) == f"Особенности имперских традиций. {LQ}Лорд-капитан{RQ} — священный титул."

    def test_inner_quotes_preserved_after_outer_strip(self):
        raw = f"{LQ}Особенности имперских традиций. {LQ}Лорд-капитан{RQ} — священный титул{RQ}."
        expected = f"Особенности имперских традиций. {LQ}Лорд-капитан{RQ} — священный титул."
        assert clean_text(raw) == expected

    def test_ellipsis_preserved(self):
        raw = f"{LQ}Мое почтение, лорд-капитан...{RQ}"
        assert clean_text(raw) == "Мое почтение, лорд-капитан..."

    def test_em_dash_preserved(self):
        raw = "Кунрад тонко улыбается — то ли вам, то ли своим мыслям."
        assert clean_text(raw) == raw

    def test_complex_real_example(self):
        raw = (
            f"{LQ}Особенности {G('Imperium', 'имперских')} традиций. "
            f"{LQ}Лорд-капитан{RQ} — священный титул, закрепленный в анналах "
            f"{G('LexImperialis', 'Лекс Империалис')} с самого появления "
            f"Вольных Торговцев на службе Бога-Императора, и не подлежит "
            f"каким-либо изменениям{RQ}."
        )
        expected = (
            "Особенности имперских традиций. "
            f"{LQ}Лорд-капитан{RQ} — священный титул, закрепленный в анналах "
            "Лекс Империалис с самого появления "
            "Вольных Торговцев на службе Бога-Императора, и не подлежит "
            "каким-либо изменениям."
        )
        assert clean_text(raw) == expected

    def test_empty_g_tag(self):
        raw = f'не замечать". {G("Psyker", "")}'
        assert clean_text(raw) == 'не замечать".'

    def test_newlines_in_text(self):
        assert clean_text("строка один\nстрока два") == "строка один строка два"

    def test_multiple_spaces(self):
        assert clean_text("два  пробела   здесь") == "два пробела здесь"

    def test_whitespace_before_punctuation(self):
        assert clean_text("слово , слово .") == "слово, слово."

    def test_only_whitespace(self):
        assert clean_text("   ") == ""
        assert clean_text("") == ""

    def test_exclamation_and_question_with_quotes(self):
        raw = f"{LQ}Как ты посмел?!{RQ}"
        assert clean_text(raw) == "Как ты посмел?!"
        raw2 = f"{LQ}Как ты посмел?!{RQ}."
        assert clean_text(raw2) == "Как ты посмел?!."

    def test_keep_outer_quotes_true(self):
        raw = f"{LQ}текст в кавычках{RQ}"
        assert clean_text(raw, keep_outer_quotes=True) == raw

    def test_no_markup(self):
        assert clean_text("Просто обычный текст.") == "Просто обычный текст."

    def test_leading_trailing_spaces(self):
        raw = f"  {LQ}текст с пробелами{RQ}  "
        assert clean_text(raw) == "текст с пробелами"

    def test_guillemet_quotes(self):
        raw = f"{LQ_G}текст{RQ_G}"
        assert clean_text(raw) == "текст"

    def test_guillemet_with_trailing_punct(self):
        raw = f"{LQ_G}текст{RQ_G}."
        assert clean_text(raw) == "текст."


class TestSplitIntoParts:
    def test_single_character_no_narrator(self):
        raw = f"{LQ}Мое почтение, лорд-капитан{RQ}."
        parts = split_into_parts(raw)
        assert len(parts) == 1
        assert parts[0]["speaker"] == "character"
        assert parts[0]["text_clean"] == "Мое почтение, лорд-капитан."

    def test_narrator_only(self):
        raw = "{n}Кунрад смеется и качает головой.{/n}"
        parts = split_into_parts(raw)
        assert len(parts) == 1
        assert parts[0]["speaker"] == "narrator"
        assert parts[0]["text_clean"] == "Кунрад смеется и качает головой."

    def test_narrator_then_character(self):
        raw = "{n}Мужчина удовлетворенно кивает.{/n} " + f"{LQ}Потому что таково предназначение{RQ}."
        parts = split_into_parts(raw)
        assert len(parts) == 2
        assert parts[0]["speaker"] == "narrator"
        assert parts[1]["speaker"] == "character"
        assert parts[1]["text_clean"] == "Потому что таково предназначение."

    def test_character_then_narrator(self):
        raw = f"{LQ}Мое почтение, лорд-капитан...{RQ} {{n}}Кунрад смеривает вас взглядом.{{/n}}"
        parts = split_into_parts(raw)
        assert len(parts) == 2
        assert parts[0]["speaker"] == "character"
        assert parts[1]["speaker"] == "narrator"

    def test_complex_multipart(self):
        raw = (
            f"{LQ}{MF('Наш', 'Наша')} наследн{MF('ик', 'ица')}...{RQ} "
            "{n}Голос Теодоры звучит торжественно.{/n} "
            f"{LQ}Ты готов?{RQ}"
        )
        parts = split_into_parts(raw)
        assert len(parts) == 3
        assert "Наш" in parts[0]["text_clean"]
        assert "наследник" in parts[0]["text_clean"]
        assert parts[1]["speaker"] == "narrator"
        assert parts[2]["text_clean"] == "Ты готов?"

    def test_multiple_narrator_blocks(self):
        raw = (
            "{n}Кунрад смеривает вас.{/n} "
            f"{LQ}Если точнее{RQ} "
            "{n}он качает головой{/n} "
            f"{LQ}Да.{RQ}"
        )
        parts = split_into_parts(raw)
        assert len(parts) == 4
        assert parts[0]["speaker"] == "narrator"
        assert parts[1]["speaker"] == "character"
        assert parts[2]["speaker"] == "narrator"
        assert parts[3]["speaker"] == "character"

    def test_narrator_with_inner_g_tags(self):
        raw = (
            f"{{n}}Взгляд {G('Emperor', 'Бога-Императора')} устремлен вниз.{{/n}} "
            f"{LQ}Да.{RQ}"
        )
        parts = split_into_parts(raw)
        assert len(parts) == 2
        assert "Бога-Императора" in parts[0]["text_clean"]
        assert "{g|" not in parts[0]["text_clean"]

    def test_no_blocks_returns_single_part(self):
        raw = "Просто текст без разметки."
        parts = split_into_parts(raw)
        assert len(parts) == 1
        assert parts[0]["speaker"] == "character"
        assert parts[0]["text_clean"] == raw

    def test_empty_text_returns_empty(self):
        assert split_into_parts("") == []
        assert split_into_parts("   ") == []

    def test_narrator_blocks_with_extra_whitespace(self):
        raw = f"  {{n}}  Кунрад качает головой.  {{/n}}   {LQ}Да.{RQ}   "
        parts = split_into_parts(raw)
        assert len(parts) == 2
        assert parts[0]["text_clean"] == "Кунрад качает головой."
        assert parts[1]["text_clean"] == "Да."

    def test_default_speaker_override(self):
        raw = f"{LQ}Привет.{RQ}"
        parts = split_into_parts(raw, default_speaker="Kunrad Voigtvir")
        assert parts[0]["speaker"] == "Kunrad Voigtvir"

    def test_only_opening_narrator_tag(self):
        raw = f"{LQ}{{n}}Незакрытый тест. Да.{RQ}"
        parts = split_into_parts(raw)
        assert len(parts) == 1
        assert parts[0]["speaker"] != "narrator"

    def test_no_newline_in_any_part(self):
        raw = "строка один\nстрока два\n" + f"{LQ}привет{RQ}"
        parts = split_into_parts(raw)
        for part in parts:
            assert "\n" not in part["text_clean"], f"text_clean contains \\n: {repr(part['text_clean'])}"

    def test_multi_newline_all_parts_clean(self):
        LQ_val = LQ
        RQ_val = RQ
        raw = "{n}стро\nка\n\nодин{/n}\n" + LQ_val + "стро\nка\n\nдва" + RQ_val + "\n{n}стро\nка три{/n}"
        parts = split_into_parts(raw)
        for part in parts:
            assert "\n" not in part["text_clean"], f"text_clean contains \\n: {repr(part['text_clean'])}"

    def test_narrator_contains_inner_quotes(self):
        raw = "{n}Сказал: " + f"{LQ}Да{RQ}" + ". И ушел.{/n}"
        parts = split_into_parts(raw)
        assert len(parts) == 1
        assert parts[0]["speaker"] == "narrator"


class TestRegressionFromKunradYaml:
    """Real phrases from Kunrad Voigtvir.yaml to verify roundtrip fidelity."""

    def test_phrase_01_character(self):
        raw = f"{LQ}Прекрасное место для размышлений{RQ}."
        assert clean_text(raw) == "Прекрасное место для размышлений."

    def test_phrase_01_narrator_unchanged(self):
        raw = "Взгляд приблизившегося к вам мужчины устремлен вниз — в глубины корабельного храма, раскинувшего свои своды на нижней палубе."
        assert clean_text(raw) == raw

    def test_phrase_01_second_part(self):
        raw = (
            f"{LQ}Отсюда открывается лучший вид на кафедральный собор. "
            f"Завораживает, не правда ли? Свидетельство величия "
            f"{G('Emperor', 'Бога-Императора')}, нашедшее "
            f"безукоризненное воплощение{RQ}."
        )
        result = clean_text(raw)
        assert "Бога-Императора" in result
        assert "{g|" not in result
        assert result == (
            "Отсюда открывается лучший вид на кафедральный собор. "
            "Завораживает, не правда ли? Свидетельство величия "
            "Бога-Императора, нашедшее "
            "безукоризненное воплощение."
        )

    def test_phrase_09_with_narrator_in_middle(self):
        raw = (
            f"{LQ}Дозвольте представиться: Кунрад Войгтвир, "
            f"Мастер шепотов на службе Ее Светлости "
            f"{G('RogueTrader', 'Вольного Торговца')} "
            f"Теодоры фон Валанциус. К вашим услугам. "
            f"Я еще не имел удовольствия общаться с вами лично...{RQ} "
            "{n}Кунрад склоняет голову и устремляет на вас внимательный взгляд.{/n}"
        )
        parts = split_into_parts(raw)
        assert len(parts) == 2
        assert parts[1]["speaker"] == "narrator"
        assert "Вольного Торговца" in parts[0]["text_clean"]
        assert "{g|" not in parts[0]["text_clean"]

    def test_phrase_10_with_mf(self):
        raw = (
            f"{LQ}Мое почтение, лорд-капитан...{RQ} "
            "{n}Кунрад смеривает вас взглядом, тонко улыбаясь.{/n} "
            f"{LQ}Если точнее — лорд-капитан фон Валанциус, "
            f"один из благословенного рода Вольных Торговцев на службе "
            f"{G('Imperium', 'Империума Человечества')}. "
            f"Вероятно, подобное родство оказалось для вас сюрпризом. "
            f"Неудивительно — свидетельства этого были утрачены с поколениями, "
            f"разделяющими вас и Лорд-капитана Теодору. "
            f"Слуги Ее Светлости потратили немало сил, чтобы обнаружить "
            f"и удостоверить эту кровную связь. "
            f"Связь, делающую вас одн{MF('им', 'ой')} "
            f"из наследн{MF('иков', 'иц')}{RQ}"
        )
        parts = split_into_parts(raw)
        assert len(parts) == 3
        assert "одним из наследников" in parts[2]["text_clean"]
        assert "{mf|" not in parts[2]["text_clean"]

    def test_real_kunrad_phrase_full_split(self):
        raw = (
            f"{LQ}{{n}}Мужчина удовлетворенно кивает, словно ваш ответ "
            f"подтвердил какую-то его мысль.{{/n}} "
            f"{LQ}Потому что таково предназначение храмов "
            f"Бога-Императора — внушать трепет и преклонение. "
            f"Ибо долг каждого из слуг Его — в безустанной службе, "
            f"пока не представится возможность отдать самую жизнь "
            f"за Повелителя Человечества{RQ}. "
            f"{{n}}Ваш собеседник вздыхает и поворачивается к вам.{{/n}}{RQ}"
        )
        parts = split_into_parts(raw)
        assert len(parts) == 3
        assert parts[0]["speaker"] == "narrator"
        assert parts[2]["speaker"] == "narrator"
        assert "Бога-Императора" in parts[1]["text_clean"]

    def test_phrase_24_with_mf_and_g(self):
        raw = (
            f"{LQ}{{n}}Ваш собеседник бросает на вас "
            f"заинтересованный взгляд.{{/n}} "
            f"{LQ}Ваше положение не сможет долго оберегать вас "
            f"при подобных речах. Поостерегитесь — вас ждет "
            f"куда более интересная и насыщенная судьба, "
            f"чем быть казненн{MF('ым', 'ой')} "
            f"по обвинению в ереси{RQ}."
        )
        parts = split_into_parts(raw)
        assert len(parts) == 2
        assert "казненным" in parts[1]["text_clean"]


class TestEdgeCases:
    def test_nested_brackets_in_g(self):
        assert clean_text(G("Test(1)", "текст")) == "текст"

    def test_double_outer_quotes(self):
        raw = '""двойные кавычки""'
        result = clean_text(raw)
        assert result == '"двойные кавычки"'

    def test_mf_with_numbers(self):
        raw = f"шаг{MF('1', '2')}"
        assert clean_text(raw) == "шаг1"

    def test_multiple_encyclopedia_same_line(self):
        raw = f"{G('A', '')} {G('B', 'текст')} {G('C', 'еще')}"
        assert clean_text(raw) == "текст еще"

    def test_whitespace_after_stripped_outer_quotes(self):
        raw = f"  {LQ}текст{RQ}  "
        assert clean_text(raw) == "текст"

    def test_punctuation_after_g_tag(self):
        raw = f"идет {G('War', 'война')}, и"
        assert clean_text(raw) == "идет война, и"

    def test_punctuation_before_g_tag(self):
        raw = f"власть, {G('Emperor', 'данная')} ему"
        assert clean_text(raw) == "власть, данная ему"

    def test_ellipsis_with_tags(self):
        raw = (
            f"{LQ}{MF('Он', 'Она')} думал{MF('', 'а')}... "
            f"{G('War', 'Война')}... конец{RQ}."
        )
        assert clean_text(raw) == "Он думал... Война... конец."

    def test_mixed_g_d_tags(self):
        raw = f"{G('A', 'один')} {D('B', 'два')}"
        assert clean_text(raw) == "один два"

    def test_empty_g_d_tags_stripped(self):
        raw = f"{G('A', '')} {D('B', '')} текст"
        assert clean_text(raw) == "текст"

    def test_raw_ascii_quotes_stripped(self):
        raw = '"Простой текст в ASCII кавычках"'
        result = clean_text(raw)
        assert result == "Простой текст в ASCII кавычках"

    def test_mf_empty_both(self):
        raw = f"{MF('', '')}"
        assert clean_text(raw) == ""
