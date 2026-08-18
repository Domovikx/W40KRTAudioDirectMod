# -*- coding: utf-8 -*-
"""Tests for build_trees.py (L1b) + enrich_sound.py (L2/L3).

Invariants (mirror build_trees validation):
    - unique(tree text_guids) == unique(bare $textGUIDs in dialog node blocks
      that exist in guid_map) — deterministic sum anchor (subset of 77691)
    - every tree text GUID exists in guid_map.json
    - per tree: nodes == len(node_order); node_order has no dups
    - L2: sound GUIDs ⊆ guid_map; every sound entry has event + speaker field
    - L3: owner_hint, when present, is a non-empty string
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "catalog_2" / "tools"))

GUID_MAP = ROOT / "catalog_2" / "raw" / "guid_map.json"
TREES = ROOT / "catalog_2" / "raw" / "dialog_trees.json"


class TestDialogTrees(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(GUID_MAP, encoding="utf-8") as f:
            cls.guid_map = json.load(f)
        with open(TREES, encoding="utf-8") as f:
            cls.trees_data = json.load(f)
        cls.trees = cls.trees_data["trees"]
        cls.stats = cls.trees_data["stats"]

    def test_trees_exist(self):
        self.assertGreater(len(self.trees), 0)

    def test_no_dup_text_guids_in_tree(self):
        for t in self.trees:
            self.assertEqual(len(t["text_guids"]),
                             len(set(t["text_guids"])))

    def test_tree_texts_in_guid_map(self):
        for t in self.trees:
            for g in t["text_guids"]:
                self.assertIn(g, self.guid_map)

    def test_tree_nodes_consistency(self):
        for t in self.trees:
            self.assertEqual(t["nodes"], len(t["node_order"]))
            self.assertEqual(t["nodes"],
                             t["cues"] + t["answers"] + t["books"])
            self.assertEqual(len(t["node_order"]),
                             len(set(t["node_order"])))

    def test_sum_anchor(self):
        all_texts = [g for t in self.trees for g in t["text_guids"]]
        self.assertEqual(len(set(all_texts)), self.stats["unique_text_guids"])

    def test_tree_enrichment_present(self):
        n = 0
        for g, entry in self.guid_map.items():
            bbp = entry.get("bbp") or {}
            if bbp.get("tree_id") is not None:
                n += 1
                self.assertIn(bbp["tree_id"],
                              {t["tree_id"] for t in self.trees})
                self.assertIsInstance(bbp["node_seq"], int)
        self.assertGreater(n, 0)

    def test_no_dup_tree_attribution(self):
        seen = set()
        for t in self.trees:
            self.assertNotIn(t["tree_id"], seen)
            seen.add(t["tree_id"])

    def test_sound_layer(self):
        n = 0
        for g, entry in self.guid_map.items():
            s = entry.get("sound")
            if s is None:
                continue
            n += 1
            self.assertIn("event", s)
            self.assertIn("speaker", s)
        self.assertGreater(n, 0)

    def test_owner_hints(self):
        for g, entry in self.guid_map.items():
            h = entry.get("owner_hint")
            if h is not None:
                self.assertIsInstance(h, str)
                self.assertGreater(len(h), 0)


if __name__ == "__main__":
    unittest.main()