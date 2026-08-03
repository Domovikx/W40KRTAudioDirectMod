"""Tests for tools/text_normalize.py — canonical display form."""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from text_normalize import normalize, matches  # noqa: E402


def test_tmp_tags_stripped():
    assert normalize('<align="center">Текст</align>') == "Текст"


def test_narration_markup_stripped():
    assert normalize("{n}Бла-бла{/n}") == "Бла-бла"


def test_g_markup_stripped():
    assert normalize("{g|Encyclopedia:Mechadendrite}текст{/g}") == "текст"


def test_mf_markup_stripped():
    assert normalize("Я бы очень удивил{mf|ся|ась}") == "Я бы очень удивил"


def test_name_markup_stripped():
    assert normalize("{name}, что ты делаешь?") == ", что ты делаешь?"


def test_outer_quotes_stripped():
    assert normalize('"Нет".') == "Нет."
    assert normalize('"Слава Омниссии, подателю Знания".') == "Слава Омниссии, подателю Знания."


def test_guillemets_stripped():
    assert normalize("«Текст».") == "Текст."


def test_whitespace_collapsed():
    assert normalize("  Много   пробелов \n и\n переносов ") == "Много пробелов и переносов"


def test_empty_and_none():
    assert normalize(None) == ""
    assert normalize("") == ""
    assert normalize("   ") == ""


def test_matches_exact_after_normalization():
    assert matches('<align="center">"Нет".</align>', '"Нет".')
    assert matches('"Нет".', "Нет.")
    assert not matches('"Нет". {n}Стариковский шепот.{/n} "Тревога".', '"Нет".')
    assert not matches("Привет, как дела?", "Привет")


def test_matches_full_phrase():
    displayed = '"Нет". {n}Стариковский шепот заползает вам в уши.{/n} "Тревога твоя не пуста".'
    catalog = '"Нет". {n}Стариковский шепот заползает вам в уши.{/n} "Тревога твоя не пуста".'
    assert matches(displayed, catalog)
