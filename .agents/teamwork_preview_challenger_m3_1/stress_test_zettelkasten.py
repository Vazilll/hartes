"""
Empirical Stress Testing Harness for vazus_core/zettelkasten_exporter.py
"""

import os
import sys
import tempfile
import shutil
import re
import unittest
import yaml
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.zettelkasten_exporter import (
    export_zettelkasten_note,
    export_all_zettelkasten_notes,
    sanitize_zettel_id,
    sanitize_filename,
    format_yaml_frontmatter
)


class EmpiricalZettelkastenStressTest(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="zettel_stress_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_edge_case_special_characters_in_title(self):
        """Test entity titles with quotes, colons, slashes, unicode, and emojis."""
        special_entity = {
            "id": "special_char_001",
            "name": 'Test "Quotes" & <Tags> & /Slashes/ : Colon - Тест Кириллицы 🚀',
            "statement": 'High-level claim with "quotes" and <xml> tags & emoji 💡',
            "domain": "test_domain",
            "status": "HYPOTHESIS",
            "sources": ['File "Path"/With/Slashes.py', 'Source <2>']
        }

        note_path = export_zettelkasten_note(special_entity, output_dir=self.test_dir)
        self.assertTrue(os.path.exists(note_path), "File should be created")

        with open(note_path, "r", encoding="utf-8") as f:
            content = f.read()

        parts = content.split("---")
        self.assertGreaterEqual(len(parts), 3, "Frontmatter must be delimited by ---")
        frontmatter_raw = parts[1]

        # Verify YAML frontmatter is valid YAML syntax
        parsed_yaml = yaml.safe_load(frontmatter_raw)
        self.assertIsNotNone(parsed_yaml)
        self.assertEqual(parsed_yaml["id"], "Zettel_special_char_001")
        self.assertIn('Test "Quotes"', parsed_yaml["title"])

        # Check Wikilinks count >= 3
        wikilinks = re.findall(r'\[\[([^\]]+)\]\]', content)
        self.assertGreaterEqual(len(wikilinks), 3, "Must contain >= 3 Wikilinks")

        # Check Action Checkbox items
        checkboxes = re.findall(r'-\s*\[\s*\]\s+.+', content)
        self.assertGreater(len(checkboxes), 0, "Must contain action checkboxes")

    def test_edge_case_empty_entity(self):
        """Test exporting empty/None entity dict."""
        empty_entity = {}
        note_path = export_zettelkasten_note(empty_entity, output_dir=self.test_dir)
        self.assertTrue(os.path.exists(note_path), "File should be created for empty entity")

        with open(note_path, "r", encoding="utf-8") as f:
            content = f.read()

        parts = content.split("---")
        parsed_yaml = yaml.safe_load(parts[1])
        self.assertEqual(parsed_yaml["id"], "Zettel_entity_unknown")
        self.assertEqual(parsed_yaml["title"], "Untitled Note")

        wikilinks = re.findall(r'\[\[([^\]]+)\]\]', content)
        self.assertGreaterEqual(len(wikilinks), 3)

    def test_edge_case_overwrite_existing_file(self):
        """Test exporting same entity ID twice overwrites correctly without corruption."""
        entity = {
            "id": "overwrite_test",
            "name": "Version 1 Title",
            "statement": "Version 1 Statement"
        }

        path1 = export_zettelkasten_note(entity, output_dir=self.test_dir)
        with open(path1, "r", encoding="utf-8") as f:
            c1 = f.read()
        self.assertIn("Version 1 Title", c1)

        # Overwrite with Version 2
        entity["name"] = "Version 2 Title Updated"
        entity["statement"] = "Version 2 Statement Updated"
        path2 = export_zettelkasten_note(entity, output_dir=self.test_dir)

        self.assertEqual(path1, path2)
        with open(path2, "r", encoding="utf-8") as f:
            c2 = f.read()
        self.assertIn("Version 2 Title Updated", c2)
        self.assertNotIn("Version 1 Title", c2)

    def test_bidirectional_wikilink_formatting(self):
        """Verify wikilinks structure, label pipe parsing, and hub fallbacks."""
        edges = [
            {"source_id": "node_a", "target_id": "node_b", "relation": "CAUSES"},
            {"source_id": "node_a", "target_id": "node_c", "relation": "REQUIRES"}
        ]
        all_nodes_map = {
            "node_b": {"id": "node_b", "name": "Node B Title"},
            "node_c": {"id": "node_c", "name": "Node C Title"}
        }

        node_a = {"id": "node_a", "name": "Node A Title"}
        path = export_zettelkasten_note(
            node_a,
            output_dir=self.test_dir,
            related_edges=edges,
            all_nodes_map=all_nodes_map
        )

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        wikilinks = re.findall(r'\[\[([^\]]+)\]\]', content)
        self.assertGreaterEqual(len(wikilinks), 3)
        self.assertTrue(any("Zettel_node_b" in wl for wl in wikilinks))
        self.assertTrue(any("Zettel_node_c" in wl for wl in wikilinks))


if __name__ == "__main__":
    unittest.main()
