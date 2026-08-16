# -*- coding: utf-8 -*-
"""Tests for extract_non_dialog.py.

Validates filters and flag detection on a synthetic mini ruRU.json snapshot.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import extract_non_dialog as ext


class TestIsCandidate(unittest.TestCase):
    def test_keeps_plain_text(self):
        self.assertTrue(ext.is_candidate("Стол из древесины"))

    def test_keeps_with_g_tag(self):
        self.assertTrue(ext.is_candidate("Урон от {g|Encyclopedia:Fire}огня{/g}"))

    def test_keeps_short_two_chars(self):
        self.assertTrue(ext.is_candidate("Ок"))

    def test_drops_dialog_with_quotes(self):
        self.assertFalse(ext.is_candidate('"Привет", — сказал он.'))

    def test_drops_narration_block(self):
        self.assertFalse(ext.is_candidate("{n}Варп бушует.{/n}"))

    def test_drops_junk_one_char(self):
        self.assertFalse(ext.is_candidate("x"))

    def test_drops_empty(self):
        self.assertFalse(ext.is_candidate(""))
        self.assertFalse(ext.is_candidate("   "))

    def test_drops_whitespace_then_short(self):
        self.assertFalse(ext.is_candidate("  a  "))


class TestComputeFlags(unittest.TestCase):
    def test_has_g_tag(self):
        self.assertIn("has_g_tag", ext.compute_flags("Урон от {g|Encyclopedia:Fire}огня{/g}"))

    def test_has_bind(self):
        self.assertIn("has_bind", ext.compute_flags("Нажмите [{bind|HighlightObjects}]"))

    def test_has_icon(self):
        self.assertIn("has_icon", ext.compute_flags("Кликните {mouse_icon|LeftMouse}"))

    def test_is_short(self):
        self.assertIn("is_short", ext.compute_flags("Ок"))
        self.assertIn("is_short", ext.compute_flags("Двадцать девять символов!!"))

    def test_not_short(self):
        self.assertNotIn("is_short", ext.compute_flags("Это достаточно длинный текст для проверки"))

    def test_has_draft(self):
        self.assertIn("has_draft", ext.compute_flags("[draft] черновик"))
        self.assertIn("has_draft", ext.compute_flags("[Draft] черновик"))

    def test_has_pfwiki(self):
        self.assertIn("has_pfwiki", ext.compute_flags("Thanks to pathfinderwiki.com team"))

    def test_has_pfwiki_case_insensitive(self):
        self.assertIn("has_pfwiki", ext.compute_flags("Thanks to PathfinderWiki.com team"))

    def test_has_newline(self):
        self.assertIn("has_newline", ext.compute_flags("Line 1\nLine 2"))

    def test_has_other_tag_d(self):
        self.assertIn("has_other_tag", ext.compute_flags("Damage {d|1d6}"))

    def test_has_other_tag_mf(self):
        self.assertIn("has_other_tag", ext.compute_flags("Хороший {mf|самец|самка}"))

    def test_no_flags(self):
        self.assertEqual(
            ext.compute_flags(
                "Освещенный свечами алтарь с копией две тысячи тома Лекс Империалис"
            ),
            [],
        )

    def test_has_bracket(self):
        self.assertIn("has_bracket", ext.compute_flags("[Присмотреться к губернатору]"))

    def test_no_bracket_when_only_open(self):
        self.assertNotIn(
            "has_bracket",
            ext.compute_flags("Это просто текст с квадратной скобкой] в конце"),
        )


class TestNoGuidLeakToCatalog(unittest.TestCase):
    def test_known_environment_guids_not_in_catalog(self):
        with open(
            ROOT / "catalog_2" / "raw" / "source.yaml",
            encoding="utf-8",
        ) as f:
            import yaml
            data = yaml.safe_load(f)
        source_guids = {r["guid"] for r in data["records"]}

        catalog_guids = ext.load_catalog_guids()
        overlap = source_guids & catalog_guids
        self.assertEqual(
            overlap, set(),
            f"{len(overlap)} GUIDs from source.yaml are also in catalog/people/*.yaml",
        )


class TestOutputFileStructure(unittest.TestCase):
    def test_source_yaml_shape(self):
        with open(
            ROOT / "catalog_2" / "raw" / "source.yaml",
            encoding="utf-8",
        ) as f:
            import yaml
            data = yaml.safe_load(f)
        for key in ("source", "filter", "total_in_source", "skipped_in_catalog",
                    "skipped_dialog", "skipped_junk", "written", "records"):
            self.assertIn(key, data, f"Missing header key: {key}")
        self.assertGreater(len(data["records"]), 5000)
        sample = data["records"][0]
        for key in ("guid", "length", "flags", "text"):
            self.assertIn(key, sample, f"Record missing key: {key}")


class TestEndToEndSynthetic(unittest.TestCase):
    def test_fake_ruru_and_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            game_dir = tmp_path / "WH40KRT_Data" / "StreamingAssets" / "Localization"
            game_dir.mkdir(parents=True)
            catalog_dir = tmp_path / "catalog" / "people"
            catalog_dir.mkdir(parents=True)
            out_dir = tmp_path / "catalog_2" / "raw"
            out_dir.mkdir(parents=True)

            import json
            ruru = {
                "strings": {
                    "g1": {"Offset": 0, "Text": "Стол из древесины"},
                    "g2": {"Offset": 0, "Text": '"Привет"'},
                    "g3": {"Offset": 0, "Text": "{n}Нарратив{/n}"},
                    "g4": {"Offset": 0, "Text": "x"},
                    "g5": {"Offset": 0, "Text": ""},
                    "g6": {"Offset": 0, "Text": "[{bind|HighlightObjects}]"},
                    "g7": {"Offset": 0, "Text": "pathfinderwiki указан"},
                    "g8": {"Offset": 0, "Text": "Длинный текст про {g|Encyclopedia:Fire}огонь{/g}, явно требующий энциклопедии"},
                    "g9": {"Offset": 0, "Text": "Без всего"},
                }
            }
            with open(game_dir / "ruRU.json", "w", encoding="utf-8") as f:
                json.dump(ruru, f)

            catalog = {"name": "Test", "phrases": [{"guid": "g2"}]}
            with open(catalog_dir / "test.yaml", "w", encoding="utf-8") as f:
                yaml_lib = __import__("yaml")
                yaml_lib.safe_dump(catalog, f, allow_unicode=True)

            ext.GAME = tmp_path / "WH40KRT_Data"
            ext.PEOPLE_DIR = catalog_dir
            ext.OUT_PATH = out_dir / "source.yaml"

            old_argv = sys.argv
            sys.argv = ["extract_non_dialog"]
            try:
                ext.main()
            finally:
                sys.argv = old_argv

            with open(out_dir / "source.yaml", encoding="utf-8") as f:
                result = __import__("yaml").safe_load(f)
            guids = [r["guid"] for r in result["records"]]
            self.assertIn("g1", guids)
            self.assertIn("g8", guids)
            self.assertIn("g9", guids)
            self.assertNotIn("g2", guids)
            self.assertNotIn("g3", guids)
            self.assertNotIn("g4", guids)
            self.assertNotIn("g5", guids)
            self.assertIn("g6", guids)
            self.assertIn("g7", guids)

            g6 = next(r for r in result["records"] if r["guid"] == "g6")
            self.assertIn("has_bind", g6["flags"])
            g7 = next(r for r in result["records"] if r["guid"] == "g7")
            self.assertIn("has_pfwiki", g7["flags"])


if __name__ == "__main__":
    unittest.main()
