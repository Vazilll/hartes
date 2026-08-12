"""
Empirical Stress Test Harness for vazus_core/zettelkasten_exporter.py
Written by Challenger 1 (Milestone 3 R3)
"""

import os
import sys
import time
import shutil
import tempfile
import unittest
import json
import re
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(r"C:\vazus")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.zettelkasten_exporter import (
    export_zettelkasten_note,
    export_all_zettelkasten_notes,
    sanitize_zettel_id,
    sanitize_filename,
    format_yaml_frontmatter,
    _extract_entity_fields
)

try:
    import yaml
    HAS_PYYAML = True
except ImportError:
    HAS_PYYAML = False


class EmpiricalZettelkastenChallenger(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="empirical_zettel_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_windows_illegal_characters_and_collisions(self):
        """Test node IDs and titles with Windows illegal characters (< > : " / \\ | ? *) and filename collisions."""
        illegal_chars_id = 'node:<test>?"/\\|*1'
        sanitized_id = sanitize_zettel_id(illegal_chars_id)
        filename = sanitize_filename(illegal_chars_id)

        # Check filename for illegal Windows chars
        windows_illegal = set('<>:"/\\|?*')
        found_illegal = set(filename).intersection(windows_illegal)
        self.assertEqual(len(found_illegal), 0, f"Filename {filename} contains Windows illegal chars: {found_illegal}")

        # Test note export with illegal characters in name and id
        node = {
            "id": illegal_chars_id,
            "name": 'Protocol <V1.0>: "Test" / Path\\Check? | *All*',
            "node_type": "ProtocolNode",
            "domain": "test:domain/sub",
            "status": "HYPOTHESIS:DRAFT",
            "tags": ["tag:1", "tag<2>", "tag|3"],
            "sources": ['C:\\Path\\To "Source"\\file.py', 'http://example.com/query?a=1&b=2']
        }

        file_path = export_zettelkasten_note(node, output_dir=self.temp_dir)
        self.assertTrue(os.path.exists(file_path), "File should be created successfully")

        # Test ID Collision bug in export_all_zettelkasten_notes
        # Raw IDs that sanitize to identical Zettel IDs:
        colliding_nodes = [
            {"id": "node-100", "name": "Node Alpha"},
            {"id": "node_100", "name": "Node Beta"},
            {"id": "node@100", "name": "Node Gamma"},
            {"id": "node#100", "name": "Node Delta"}
        ]

        batch_out = export_all_zettelkasten_notes(colliding_nodes, output_dir=self.temp_dir, auto_reindex=False)
        # All 4 map to Zettel_node_100.md
        # Check how many distinct files were written vs how many paths returned
        unique_paths = set(batch_out)
        self.assertEqual(len(batch_out), 4, "Returned 4 path strings")
        print(f"[EMPIRICAL] Colliding nodes batch return length: {len(batch_out)}, unique paths on disk: {len(unique_paths)}")
        # Check file content - only the last one survived!
        with open(batch_out[0], "r", encoding="utf-8") as f:
            content = f.read()
        
        # Did earlier notes get overwritten?
        contains_alpha = "Node Alpha" in content
        contains_delta = "Node Delta" in content
        print(f"[EMPIRICAL BUG CHECK] Node Alpha survived: {contains_alpha}, Node Delta survived: {contains_delta}")

    def test_02_yaml_frontmatter_parser_validity(self):
        """Test if produced YAML frontmatter is valid YAML under edge case inputs."""
        if not HAS_PYYAML:
            self.skipTest("PyYAML not installed")

        test_cases = [
            {
                "title": 'Title with: colon and "quotes" and \\backslashes\\',
                "domain": "kgb:domain:with:colons",
                "status": "STATUS WITH SPACES & SYMBOLS #1",
                "tags": ["tag with space", "tag:colon", "tag#hash"],
                "sources": ['C:\\Users\\Vaz\\test.py', 'Source "with" quote']
            },
            {
                "title": 'Title ending with backslash\\',
                "domain": "test",
                "status": "HYPOTHESIS",
                "tags": ["iad"],
                "sources": ['C:\\Path\\Ending\\With\\Backslash\\']
            },
            {
                "title": "Title with newline\nNext Line",
                "domain": "test",
                "status": "HYPOTHESIS",
                "tags": ["iad"],
                "sources": ["source1"]
            }
        ]

        for idx, meta in enumerate(test_cases):
            yaml_block = format_yaml_frontmatter(meta)
            # Extract between ---
            parts = yaml_block.strip().split("---")
            yaml_content = parts[1].strip()

            try:
                parsed = yaml.safe_load(yaml_content)
                self.assertIsNotNone(parsed, f"Test case {idx} failed to parse YAML")
                self.assertIn("id", parsed)
                self.assertIn("title", parsed)
                print(f"[EMPIRICAL YAML PASS] Case {idx}: Successfully parsed YAML")
            except Exception as e:
                print(f"[EMPIRICAL YAML FAIL] Case {idx}: YAML parse error: {e}")
                print(f"Produced YAML:\n{yaml_block}\n")

    def test_03_obsidian_wikilink_corruption(self):
        """Test Wikilink generation when node titles/relations contain Obsidian special syntax (| ] [ \\n)."""
        node = {
            "id": "node_wikilink_test",
            "name": "Base Note"
        }
        related_edges = [
            {"source_id": "node_wikilink_test", "target_id": "target_1", "relation": "REQUIRES | MANDATORY"},
            {"source_id": "node_wikilink_test", "target_id": "target_2", "relation": "CAUSES]] [[HACK"}
        ]
        all_nodes_map = {
            "target_1": {"name": "Target | Pipe Title"},
            "target_2": {"name": "Target ]] Bracket Title"}
        }

        file_path = export_zettelkasten_note(
            node,
            output_dir=self.temp_dir,
            related_edges=related_edges,
            all_nodes_map=all_nodes_map
        )

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        print("\n--- Generated Wikilinks Section ---")
        lines = [line for line in content.splitlines() if "[[" in line]
        for line in lines:
            print(line)

        # Parse Obsidian wikilinks strictly
        # Standard Wikilink format: [[TargetNote|Label]]
        # A corrupted wikilink will have multiple pipes unescaped or closing brackets inside alias
        for line in lines:
            # Check if line breaks Wikilink format
            match = re.search(r'\[\[([^\]]+)\]\]', line)
            if not match:
                print(f"[EMPIRICAL WIKILINK FAIL] Line failed regex match: {line}")
            else:
                inside = match.group(1)
                # If target|label has unexpected extra pipes or nested brackets
                parts = inside.split("|")
                if len(parts) > 2:
                    print(f"[EMPIRICAL WIKILINK CORRUPTION] Extra pipe in wikilink: {line}")

    def test_04_empty_null_malformed_fields(self):
        """Test behavior under None/empty/malformed steps, safety warnings, confidence, etc."""
        malformed_node = {
            "id": "node_malformed",
            "name": None,
            "statement": None,
            "action_instruction": None,
            "node_type": "ProtocolNode",
            "confidence": None,
            "steps": ["Step 1", None, {"complex": "step"}, 123, "Step with \n newline"],
            "safety_warnings": [None, 456, "Warning \n with newline"],
            "frequency_periodicity": None,
            "properties": "INVALID_JSON_STRING"
        }

        try:
            file_path = export_zettelkasten_note(malformed_node, output_dir=self.temp_dir)
            self.assertTrue(os.path.exists(file_path))
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            print("[EMPIRICAL MALFORMED PASS] Export succeeded without unhandled exception")
        except Exception as e:
            print(f"[EMPIRICAL MALFORMED FAIL] Exception raised: {e}")

    def test_05_high_volume_batch_export_performance(self):
        """High-volume batch export benchmark (1,000 nodes)."""
        nodes = []
        edges = []
        for i in range(1000):
            nid = f"batch_node_{i:04d}"
            nodes.append({
                "id": nid,
                "name": f"Batch Analytical Thesis Node {i}",
                "statement": f"Analytical assertion number {i} regarding biohacking domain optimization.",
                "confidence": 0.85 + (i % 15) * 0.01,
                "domain": f"domain_{i % 5}",
                "ach_status": "ACCEPTED" if i % 2 == 0 else "HYPOTHESIS",
                "steps": [f"Execute step A for {i}", f"Execute step B for {i}"],
                "safety_warnings": [f"Risk warning for {i}"]
            })
            if i > 0:
                edges.append({
                    "source_id": f"batch_node_{i-1:04d}",
                    "target_id": nid,
                    "relation": "CAUSES"
                })

        extraction_data = {
            "nodes": nodes,
            "edges": edges
        }

        start_time = time.time()
        exported_paths = export_all_zettelkasten_notes(
            extraction_data,
            output_dir=self.temp_dir,
            auto_reindex=False
        )
        elapsed = time.time() - start_time

        self.assertEqual(len(exported_paths), 1000)
        print(f"[EMPIRICAL BENCHMARK] 1,000 notes exported in {elapsed:.3f} seconds ({1000/elapsed:.1f} notes/sec)")
        self.assertLess(elapsed, 10.0, "1,000 notes should export in under 10 seconds")


if __name__ == "__main__":
    unittest.main()
