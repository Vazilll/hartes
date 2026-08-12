"""
Empirical Harness Part 2: Deeper Edge Cases for vazus_core/zettelkasten_exporter.py
Written by Challenger 1 (Milestone 3 R3)
"""

import os
import sys
import unittest
import tempfile
import shutil
import json
import sqlite3
import re
from pathlib import Path

PROJECT_ROOT = Path(r"C:\vazus")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.zettelkasten_exporter import (
    export_zettelkasten_note,
    export_all_zettelkasten_notes,
    sanitize_zettel_id,
    sanitize_filename,
    format_yaml_frontmatter,
    _extract_entity_fields,
    _extract_nodes_and_edges_from_db
)

class EmpiricalDeepEdgeCases(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="empirical_zettel_2_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_06_cyrillic_and_unicode_handling(self):
        """Test Russian / Cyrillic titles, emojis, and non-ASCII character sanitization."""
        raw_id_ru = "тезис_001_витамин_d3"
        sanitized_id = sanitize_zettel_id(raw_id_ru)
        print(f"[EMPIRICAL SANITIZE] Input Cyrillic ID: '{raw_id_ru}' -> Sanitized ID: '{sanitized_id}'")

        # Notice: sanitize_zettel_id uses re.sub(r'[^a-zA-Z0-9_-]', '_', str(raw_id).strip())
        # So ALL Cyrillic characters are stripped/replaced with underscores!
        # "тезис_001_витамин_d3" becomes "Zettel__001__d3" or "Zettel_001_d3"!
        # Russian entity IDs completely lose their semantic identity!

        node_ru = {
            "id": raw_id_ru,
            "name": "Приём Витамина D3 ☀️ и K2 💊",
            "statement": "Витамин D3 требует сопроводительного приёма Витамина K2.",
            "domain": "биохакинг_аналитика",
            "tags": ["иад", "витамин_d3", "ноотропы"]
        }

        file_path = export_zettelkasten_note(node_ru, output_dir=self.temp_dir)
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Приём Витамина D3 ☀️ и K2 💊", content)
        print(f"[EMPIRICAL UNICODE PASS] File path created: {file_path}")

    def test_07_multiline_and_raw_sentence_inputs(self):
        """Test multiline statements, steps, and sources containing line breaks."""
        multiline_node = {
            "id": "node_multiline",
            "name": "Multiline Thesis Node\nWith Newline In Name",
            "statement": "Line 1 of thesis statement.\nLine 2 of thesis statement.\nLine 3 of thesis statement.",
            "node_type": "ThesisNode",
            "steps": ["Step 1: First instruction\nSecond line of step 1", "Step 2: Simple step"],
            "safety_warnings": ["Warning line 1\nWarning line 2"],
            "sources": ["Source file 1\nwith newline", "Source file 2"]
        }

        file_path = export_zettelkasten_note(multiline_node, output_dir=self.temp_dir)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if frontmatter broke because source has newline
        parts = content.split("---")
        if len(parts) >= 3:
            fm = parts[1]
            print(f"Frontmatter with multiline source:\n{fm}")
            # Check if source formatting produced invalid multiline YAML
            lines = fm.splitlines()
            for l in lines:
                if l.startswith(" - ") and not l.startswith('  - "'):
                    print(f"[EMPIRICAL MULTILINE YAML WARN] Bad line in frontmatter: {l}")

    def test_08_extract_from_db_locked_or_corrupt(self):
        """Test DB extraction helper with nonexistent, invalid, or locked DB."""
        # Nonexistent DB
        nodes, edges = _extract_nodes_and_edges_from_db("nonexistent_file.db")
        self.assertEqual(len(nodes), 0)
        self.assertEqual(len(edges), 0)

        # Corrupt DB file
        corrupt_db = Path(self.temp_dir) / "corrupt.db"
        with open(corrupt_db, "wb") as f:
            f.write(b"NOT A SQLITE FILE")

        nodes, edges = _extract_nodes_and_edges_from_db(str(corrupt_db))
        self.assertEqual(len(nodes), 0)
        self.assertEqual(len(edges), 0)
        print("[EMPIRICAL DB EXTRACTION PASS] Gracefully handled corrupt DB")


if __name__ == "__main__":
    unittest.main()
