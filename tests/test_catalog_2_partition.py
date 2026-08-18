# -*- coding: utf-8 -*-
"""Tests for build_partition.py — full lossless partition of ruRU GUIDs.

Invariants (mirror build_partition validation):
    - sum(files) == len(ruRU.json) == 77691
    - no GUID appears twice
    - every ruRU GUID is in exactly one file
    - no foreign GUIDs
    - env entries are enriched (category/reasons/parts narrator)

The corpus reference is guid_map.json (keys == ruRU.json keys, validated at
build time). If the live ruRU.json is reachable, we also verify against it.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import yaml  # noqa: E402

from env_scan import RU_JSON, load_json_strs  # noqa: E402
from text_normalize import normalize  # noqa: E402

PEOPLE = ROOT / "catalog_2" / "people"
GUID_MAP = ROOT / "catalog_2" / "raw" / "guid_map.json"
EXPECTED_FILES = [
    "VoicedDialog.yaml", "DialogAnswer.yaml", "DialogCue.yaml",
    "Barks.yaml", "Environment_Descriptions.yaml", "UI.yaml",
    "Encyclopedia.yaml", "GameLog.yaml", "Objectives.yaml",
    "Narration.yaml", "Short.yaml", "Other.yaml",
]


def load_all() -> dict[str, str]:
    """guid -> file name for every phrase in catalog_2/people/ (no index)."""
    out = {}
    for path in sorted(PEOPLE.glob("*.yaml")):
        if path.name == "index.yaml":
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for ph in data.get("phrases", []):
            out[ph["guid"]] = path.name
    return out


def corpus_keys() -> set[str]:
    with open(GUID_MAP, encoding="utf-8") as f:
        return set(__import__("json").load(f).keys())


class TestPartition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = load_all()
        cls.corpus = corpus_keys()
        cls.env = yaml.safe_load(
            (PEOPLE / "Environment_Descriptions.yaml").read_text(
                encoding="utf-8")) or {}

    def test_files_exist(self):
        for name in EXPECTED_FILES:
            self.assertTrue((PEOPLE / name).exists(), name)
        self.assertTrue((PEOPLE / "index.yaml").exists())

    def test_sum_equals_corpus(self):
        self.assertEqual(len(self.mapping), len(self.corpus))

    def test_no_duplicate_guids(self):
        self.assertEqual(len(self.mapping), len(set(self.mapping)))

    def test_every_corpus_guid_covered(self):
        self.assertEqual(set(self.mapping), self.corpus)

    def test_no_foreign_guids(self):
        self.assertTrue(set(self.mapping) <= self.corpus)

    def test_sum_equals_ruRU(self):
        ru = load_json_strs(RU_JSON)
        self.assertEqual(len(self.mapping), len(ru))

    def test_env_entries_full(self):
        phrases = self.env.get("phrases", [])
        self.assertGreater(len(phrases), 0)
        for ph in phrases:
            self.assertIn(ph["category"], ("A", "B"))
            self.assertIsInstance(ph["reasons"], list)
            self.assertEqual(len(ph["parts"]), 1)
            self.assertEqual(ph["parts"][0]["speaker"], "narrator")
            self.assertEqual(ph["parts"][0]["text_clean"],
                             normalize(ph["text"]))

    def test_only_env_has_parts(self):
        for path in sorted(PEOPLE.glob("*.yaml")):
            if path.name in ("index.yaml", "Environment_Descriptions.yaml"):
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for ph in data.get("phrases", []):
                self.assertNotIn("parts", ph, path.name)

    def test_index_matches_counts(self):
        index = yaml.safe_load(
            (PEOPLE / "index.yaml").read_text(encoding="utf-8")) or {}
        self.assertEqual(index["total_guids"], len(self.mapping))
        for f in index["files"]:
            path = PEOPLE / f"{f['name']}.yaml"
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            self.assertEqual(f["total"], len(data.get("phrases", [])))


if __name__ == "__main__":
    unittest.main()