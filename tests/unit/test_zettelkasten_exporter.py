"""
tests/test_zettelkasten_exporter.py
Unit Test Suite for Automated Zettelkasten Obsidian Wiki Exporter (Milestone 3 R3).

Tests:
- test_01_atomic_note_generation: Verifies creation of .md files with proper H1 and H2 headings.
- test_02_yaml_frontmatter: Parses YAML frontmatter and checks mandatory fields (id, title, date, tags, domain, status, sources).
- test_03_bidirectional_wikilinks: Verifies >= 3 [[Wikilinks]] per note.
- test_04_action_checklist: Verifies '- [ ]' checklist items presence.
- test_05_batch_export_from_db: Tests batch export from vazus.db / KGB analytics.
- test_06_supergraph_reindexing: Verifies supergraph re-indexing integration.
"""

import os
import sys
import unittest
import tempfile
import shutil
import sqlite3
import json
import re
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.zettelkasten_exporter import (
    export_zettelkasten_note,
    export_all_zettelkasten_notes,
    sanitize_zettel_id,
    sanitize_filename
)
from vazus_core.kgb_analytical_extractor import ThesisNode, ProtocolNode, KGBAnalyticalExtractor


class TestZettelkastenExporter(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="zettel_test_")
        self.sample_thesis = ThesisNode(
            id="thesis_test_001",
            name="Приём Витамина D3 10000 МЕ требует Витамин K2 и Магний",
            statement="Приём высоких доз Витамина D3 (10000 МЕ) требует обязательного сопроводительного приёма Витамина K2 и Магния.",
            confidence=0.95,
            domain="biohacking_analytics",
            ach_status="ACCEPTED",
            source_file="C:/vazus/knowledge/course_scene_01.oga",
            scene_id="scene_01",
            start_sec=12.5,
            end_sec=120.0,
            tags="iad,biohacking,d3,k2"
        )
        self.sample_protocol = ProtocolNode(
            id="protocol_test_002",
            name="Протокол циклирования ноотропного комплекса",
            action_instruction="Принимать Фонтурацетам 100 мг утром в течение 5 дней с перерывом на 2 дня.",
            steps=[
                "Принимать 100 мг Фонтурацетам утром до еды",
                "Добавить 300 мг Альфа-GPC для предотвращения истощения холина",
                "Сделать обязательный 2-дневный перерыв на выходных"
            ],
            safety_warnings=["Не принимать после 15:00 во избежание бессонницы"],
            domain="biohacking_protocols",
            source_file="C:/vazus/knowledge/course_scene_02.oga",
            scene_id="scene_02",
            tags="iad,protocol,nootropics"
        )

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_atomic_note_generation(self):
        """Verifies creation of .md files in target directory with proper H1 and H2 headings."""
        file_path = export_zettelkasten_note(self.sample_thesis, output_dir=self.temp_dir)
        self.assertTrue(os.path.exists(file_path), "Exported file path must exist")
        self.assertTrue(file_path.endswith(".md"), "File must have .md extension")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify H1 Heading
        self.assertIn("# ", content, "Note must contain H1 title heading")
        self.assertIn(self.sample_thesis.name, content, "Note H1 must contain note name")

        # Verify H2 Headings
        self.assertIn("## Core Claim / Thesis", content, "Note must contain '## Core Claim / Thesis'")
        self.assertIn("## Analytical Evidence & Context", content, "Note must contain '## Analytical Evidence & Context'")
        self.assertIn("## Action Checklist", content, "Note must contain '## Action Checklist'")
        self.assertIn("## Related Notes & Wikilinks", content, "Note must contain '## Related Notes & Wikilinks'")

        # Test ProtocolNode headings
        proto_path = export_zettelkasten_note(self.sample_protocol, output_dir=self.temp_dir)
        with open(proto_path, "r", encoding="utf-8") as f:
            proto_content = f.read()

        self.assertIn("## Protocol Directives", proto_content, "Protocol note must contain '## Protocol Directives'")

    def test_02_yaml_frontmatter(self):
        """Parses YAML frontmatter and checks mandatory fields (id, title, date, tags, domain, status, sources)."""
        file_path = export_zettelkasten_note(self.sample_thesis, output_dir=self.temp_dir)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Frontmatter must be enclosed in ---
        parts = content.split("---")
        self.assertGreaterEqual(len(parts), 3, "Note must contain YAML frontmatter enclosed in '---'")

        frontmatter_text = parts[1]

        mandatory_fields = ["id:", "title:", "date:", "tags:", "domain:", "status:", "sources:"]
        for field in mandatory_fields:
            self.assertIn(field, frontmatter_text, f"Frontmatter must contain mandatory key '{field}'")

        expected_id = sanitize_zettel_id(self.sample_thesis.id)
        self.assertIn(expected_id, frontmatter_text, f"Frontmatter id must match '{expected_id}'")
        self.assertIn(self.sample_thesis.domain, frontmatter_text, "Frontmatter domain must match entity domain")
        self.assertIn(self.sample_thesis.ach_status, frontmatter_text, "Frontmatter status must match entity status")

    def test_03_bidirectional_wikilinks(self):
        """Verifies >= 3 [[Wikilinks]] per note."""
        related_edges = [
            {"source_id": self.sample_thesis.id, "target_id": "thesis_target_101", "relation": "REQUIRES"},
            {"source_id": self.sample_thesis.id, "target_id": "thesis_target_102", "relation": "CAUSES"},
            {"source_id": self.sample_thesis.id, "target_id": "thesis_target_103", "relation": "CONTRADICTS"}
        ]
        file_path = export_zettelkasten_note(
            self.sample_thesis,
            output_dir=self.temp_dir,
            related_edges=related_edges
        )

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        wikilinks = re.findall(r'\[\[([^\]]+)\]\]', content)
        self.assertGreaterEqual(len(wikilinks), 3, f"Note must contain at least 3 [[Wikilinks]], found {len(wikilinks)}")

        for link in wikilinks:
            self.assertTrue(len(link) > 0, "Wikilink target must not be empty")

    def test_04_action_checklist(self):
        """Verifies '- [ ]' checklist items presence."""
        file_path = export_zettelkasten_note(self.sample_protocol, output_dir=self.temp_dir)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        checklist_items = re.findall(r'-\s*\[\s*\]\s+.+', content)
        self.assertGreater(len(checklist_items), 0, "Note must contain at least one '- [ ]' action checklist item")

    def test_05_batch_export_from_db(self):
        """Tests batch export from vazus.db / KGB analytics."""
        extractor = KGBAnalyticalExtractor()
        extraction_res = extractor.extract({
            "scene_id": "scene_batch_test",
            "transcript": "Приём креатина 5г в день вызывает рост phosphocreatine. Приём требует запивать водой. Нельзя принимать с кофеином."
        })

        exported_paths = export_all_zettelkasten_notes(
            extraction_res,
            output_dir=self.temp_dir,
            auto_reindex=False
        )

        self.assertGreater(len(exported_paths), 0, "Batch export must generate at least one note path")
        for path in exported_paths:
            self.assertTrue(os.path.exists(path), f"Batch exported file {path} must exist on disk")

        # Test batch export from isolated test DB path
        test_vazus_db = os.path.join(self.temp_dir, "test_vazus.db")
        conn = sqlite3.connect(test_vazus_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY,
                name TEXT,
                domain TEXT,
                node_type TEXT,
                description TEXT,
                tags TEXT,
                properties TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_edges (
                source_id TEXT,
                target_id TEXT,
                relation TEXT,
                strength REAL,
                properties TEXT
            )
        """)
        conn.execute(
            "INSERT INTO kg_nodes (id, name, domain, node_type, description, tags, properties) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("thesis_test_001", "Приём Витамина D3", "biohacking", "ThesisNode", "Описание", "d3,k2", json.dumps({"raw_sentence": "Приём Витамина D3"}))
        )
        conn.commit()
        conn.close()

        db_exported_paths = export_all_zettelkasten_notes(
            test_vazus_db,
            output_dir=self.temp_dir,
            auto_reindex=False
        )
        self.assertGreater(len(db_exported_paths), 0, "Batch export from test_vazus.db must generate notes")

    def test_06_supergraph_reindexing(self):
        """Verifies supergraph re-indexing integration."""
        extraction_res = {
            "nodes": [self.sample_thesis.to_dict(), self.sample_protocol.to_dict()],
            "edges": [
                {"source_id": self.sample_thesis.id, "target_id": self.sample_protocol.id, "relation": "REQUIRES"}
            ]
        }
        test_db = os.path.join(self.temp_dir, "test_zettel.db")
        exported_paths = export_all_zettelkasten_notes(
            extraction_res,
            output_dir=self.temp_dir,
            auto_reindex=True,
            db_path=test_db
        )

        self.assertGreaterEqual(len(exported_paths), 2, "Export with auto_reindex must complete successfully for all nodes")
        for path in exported_paths:
            self.assertTrue(os.path.exists(path), f"File {path} must exist after auto_reindex export")

    def test_07_cyrillic_zettel_id_preservation(self):
        """Verifies sanitize_zettel_id preserves Cyrillic characters."""
        raw_cyrillic_id = "thesis_приём_витамина_d3"
        clean_id = sanitize_zettel_id(raw_cyrillic_id)
        self.assertEqual(clean_id, "Zettel_thesis_приём_витамина_d3")
        self.assertIn("приём", clean_id)


if __name__ == "__main__":
    unittest.main()
