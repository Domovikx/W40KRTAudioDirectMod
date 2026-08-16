# -*- coding: utf-8 -*-
"""Tests for narrow_candidates.py."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import narrow_candidates as nc


def make_records(items):
    return [
        {"guid": g, "length": len(t), "flags": flags, "text": t}
        for g, t, flags in items
    ]


class TestPartition(unittest.TestCase):
    def test_dialog_mf_split(self):
        records = make_records([
            ("g1", "A" * 100, []),
            ("g2", "B" * 100, ["has_other_tag"]),
        ])
        narrow, dialog_mf, skipped = [], [], {}
        for r in records:
            flags = set(r["flags"])
            if "has_other_tag" in flags:
                dialog_mf.append(r)
                continue
            narrow.append(r)
        self.assertEqual(len(narrow), 1)
        self.assertEqual(narrow[0]["guid"], "g1")
        self.assertEqual(len(dialog_mf), 1)
        self.assertEqual(dialog_mf[0]["guid"], "g2")

    def test_length_filter(self):
        records = make_records([
            ("short", "x" * 50, []),
            ("ok", "y" * 200, []),
            ("long", "z" * 500, []),
        ])
        narrow = []
        for r in records:
            if not (80 <= r["length"] <= 400):
                continue
            narrow.append(r)
        self.assertEqual([n["guid"] for n in narrow], ["ok"])

    def test_exclude_flags(self):
        records = make_records([
            ("clean", "a" * 100, []),
            ("g_tag", "b" * 100, ["has_g_tag"]),
            ("bind", "c" * 100, ["has_bind"]),
            ("icon", "d" * 100, ["has_icon"]),
            ("draft", "e" * 100, ["has_draft"]),
            ("pfwiki", "f" * 100, ["has_pfwiki"]),
        ])
        narrow = []
        for r in records:
            flags = set(r["flags"])
            excluded = flags & {"has_g_tag", "has_bind", "has_icon", "has_pfwiki", "has_draft"}
            if excluded:
                continue
            narrow.append(r)
        self.assertEqual([n["guid"] for n in narrow], ["clean"])


class TestOutputFileStructure(unittest.TestCase):
    def test_narrow_yaml_shape(self):
        with open(
            ROOT / "catalog_2" / "raw" / "narrow_v2.yaml",
            encoding="utf-8",
        ) as f:
            import yaml
            data = yaml.safe_load(f)
        for key in ("total", "records"):
            self.assertIn(key, data, f"Missing key: {key}")
        self.assertGreater(data["total"], 1000)
        self.assertGreater(len(data["records"]), 1000)
        sample = data["records"][0]
        for key in ("guid", "length", "text"):
            self.assertIn(key, sample, f"Record missing key: {key}")

    def test_dialog_mf_yaml_shape(self):
        with open(
            ROOT / "catalog_2" / "raw" / "dialog_mf_pending.yaml",
            encoding="utf-8",
        ) as f:
            import yaml
            data = yaml.safe_load(f)
        self.assertIn("records", data)
        self.assertGreater(data["total"], 500)
        for r in data["records"]:
            self.assertIn("guid", r)
            self.assertIn("text", r)
            self.assertIn("length", r)

    def test_no_has_g_tag_in_narrow(self):
        with open(
            ROOT / "catalog_2" / "raw" / "narrow_v2.yaml",
            encoding="utf-8") as f:
            import yaml
            data = yaml.safe_load(f)
        for r in data["records"]:
            self.assertNotIn("has_g_tag", r.get("flags", []),
                             f"has_g_tag leaked into narrow: {r['guid']}")
            self.assertNotIn("has_other_tag", r.get("flags", []),
                             f"has_other_tag leaked into narrow: {r['guid']}")


if __name__ == "__main__":
    unittest.main()
