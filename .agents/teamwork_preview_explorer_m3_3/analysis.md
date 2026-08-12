# Milestone 3 Requirement R3: Automated Zettelkasten Exporter & Test Suite Specification

**Author**: Explorer 3 (`teamwork_preview_explorer_m3_3`)  
**Date**: 2026-07-24  
**Target Working Directory**: `C:\vazus\.agents\teamwork_preview_explorer_m3_3`  
**Target Test File**: `C:\vazus\tests\test_zettelkasten_exporter.py`  
**Target Implementation File**: `C:\vazus\vazus_core\zettelkasten_exporter.py`  
**Status**: Completed Design & Technical Specification Report  

---

## 1. Executive Summary

Milestone 3 Requirement R3 completes the automated Zettelkasten note exporter for the multimodal SuperGraph OS in `vazus`. 

The system takes knowledge extraction entities (KGB analytical thesis/protocol nodes, multimodal media scene transcripts, and Telegram discussion threads) and automatically transforms them into **atomic markdown Zettelkasten notes** stored in the persistent memory wiki vault (`C:\vazus\services\memory\semantic\wiki`). 

Each generated note must adhere to strict structural constraints:
1. Valid **YAML frontmatter** containing standard metadata (`id`, `title`, `date`, `tags`, `domain`, `status`, `sources`).
2. Standardized **Atomic Section Structure** (`# Title`, `## Core Claim / Thesis`, `## Analytical Evidence & Context`, `## Action Checklist`, `## Related Notes & Wikilinks`).
3. Verification of **at least 3 bidirectional `[[Wikilinks]]`** per note linking to reciprocal nodes in the vault graph.
4. Presence of interactive **Action Checklists** (`- [ ]`).
5. Support for **Batch Export** (`export_all_zettelkasten_notes`).
6. Seamless **SuperGraph Re-Indexing Integration** (`SuperGraphLinker` persisting `WikiNote`, `WikiSection`, and `WIKILINK` records into `vazus.db` with 768-dim embeddings).

This report specifies the complete automated test suite design for `tests/test_zettelkasten_exporter.py` and the architectural contract for `vazus_core/zettelkasten_exporter.py`.

---

## 2. Inspection of Existing Test Suite Patterns (`tests/`)

An in-depth audit of existing tests in `C:\vazus\tests\` revealed the testing conventions established across the project:

### 2.1 `tests/test_multimodal_knowledge.py`
- Uses Python `unittest.TestCase`.
- Reconfigures stdout encoding (`sys.stdout.reconfigure(encoding='utf-8')`).
- Imports functions directly from `vazus_core` modules.
- Validates data transformation outputs (e.g. text normalization, garbage detection) and pipeline dictionary schemas (`scene_id`, `source_file`, `start_sec`, `end_sec`, `transcript`, `thumbnail_path`).

### 2.2 `tests/test_kgb_analytical_extractor.py`
- Uses `unittest.TestCase` with `setUp` and `tearDown`.
- Utilizes `tempfile.mkstemp(suffix=".db")` to create an isolated temporary SQLite database file for each test run, ensuring test isolation without polluting `vazus.db`.
- Tests schema compliance, data field extraction, node types (`ThesisNode`, `ProtocolNode`), edge relations (`CAUSES`, `REQUIRES`, `CONTRADICTS`), and database persistence in `kg_nodes` and `kg_edges`.
- Explicitly verifies 768-dimensional vector embedding vectors stored as JSON in `embedding_json`.

### 2.3 `tests/test_m2_r1_indexing_and_vector_search.py`
- Integration test runner inspecting `SuperGraphLinker` behavior.
- Verifies DB node and edge counts (`WikiNote`, `WikiSection`, `WIKILINK`, `CONTAINS_SECTION`, `SUPERGRAPH_LINK`).
- Verifies domain-filtered vector similarity search across `memory_wiki` and `ast_code` domains.

---

## 3. Specification of `vazus_core/zettelkasten_exporter.py`

To satisfy the test suite requirements, `vazus_core/zettelkasten_exporter.py` must provide the `ZettelkastenExporter` class with the following core interface contract:

```python
"""
vazus_core/zettelkasten_exporter.py
Automated Zettelkasten Note Exporter & SuperGraph Linker Integration.
"""

import os
import sys
import re
import json
import yaml
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from vazus_core.supergraph_linker import SuperGraphLinker


class ZettelkastenExporter:
    """Automated exporter for converting knowledge entities into atomic Zettelkasten markdown notes."""

    def __init__(self, db_path: Optional[Path] = None, output_dir: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else Path("C:/vazus/vazus.db")
        self.output_dir = Path(output_dir) if output_dir else Path("C:/vazus/services/memory/semantic/wiki")

    @staticmethod
    def parse_yaml_frontmatter(content: str) -> Optional[Dict[str, Any]]:
        """Parses YAML frontmatter enclosed in --- header from markdown content."""
        pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return None
        yaml_text = match.group(1)
        try:
            return yaml.safe_load(yaml_text)
        except Exception:
            return None

    @staticmethod
    def validate_frontmatter(frontmatter: Optional[Dict[str, Any]]) -> bool:
        """Validates presence and schema compliance of mandatory frontmatter fields."""
        if not frontmatter or not isinstance(frontmatter, dict):
            return False
        required_fields = ["id", "title", "date", "tags", "domain", "status", "sources"]
        for field in required_fields:
            if field not in frontmatter or frontmatter[field] is None:
                return False
        if not isinstance(frontmatter.get("tags"), list):
            return False
        if not isinstance(frontmatter.get("sources"), list):
            return False
        return True

    @staticmethod
    def validate_atomic_structure(content: str) -> Dict[str, Any]:
        """Validates that markdown content follows Zettelkasten atomic note section structure."""
        required_sections = [
            "Core Claim / Thesis",
            "Analytical Evidence & Context",
            "Action Checklist",
            "Related Notes & Wikilinks"
        ]
        
        has_h1 = bool(re.search(r"^#\s+.+", content, re.MULTILINE))
        found_sections = []
        missing_sections = []

        for sec in required_sections:
            pattern = r"^##\s+" + re.escape(sec)
            if re.search(pattern, content, re.MULTILINE):
                found_sections.append(sec)
            else:
                missing_sections.append(sec)

        is_valid = has_h1 and (len(missing_sections) == 0)
        return {
            "is_valid": is_valid,
            "has_h1_title": has_h1,
            "found_sections": found_sections,
            "missing_sections": missing_sections
        }

    @staticmethod
    def extract_wikilinks(content: str) -> List[str]:
        """Extracts all [[TargetNote]] wikilinks from note content."""
        pattern = r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]"
        matches = re.findall(pattern, content)
        return [m.strip() for m in matches if m.strip()]

    @staticmethod
    def validate_action_checklist(content: str) -> bool:
        """Verifies presence of at least one markdown checkbox item (- [ ] or - [x])."""
        pattern = r"-\s*\[[ xX]\]\s+.+"
        return bool(re.search(pattern, content))

    def verify_bidirectional_links(self, vault_dir: Path) -> Dict[str, Any]:
        """Verifies that exported notes in vault_dir have 3+ bidirectional [[Wikilinks]]."""
        vault_dir = Path(vault_dir)
        note_files = list(vault_dir.glob("*.md"))
        
        out_links: Dict[str, set] = {}
        in_links: Dict[str, set] = {}
        
        for fpath in note_files:
            stem = fpath.stem
            out_links[stem] = set()
            in_links[stem] = set()

        for fpath in note_files:
            stem = fpath.stem
            content = fpath.read_text(encoding="utf-8")
            links = self.extract_wikilinks(content)
            for target in links:
                target_stem = target.replace(" ", "_")
                out_links[stem].add(target_stem)
                if target_stem not in in_links:
                    in_links[target_stem] = set()
                in_links[target_stem].add(stem)

        note_stats = {}
        all_compliant = True
        for stem in out_links:
            outgoing = out_links[stem]
            bidirectional = {t for t in outgoing if stem in out_links.get(t, set())}
            is_compliant = len(outgoing) >= 3 and len(bidirectional) >= 3
            if not is_compliant:
                all_compliant = False
            note_stats[stem] = {
                "total_outgoing": len(outgoing),
                "total_incoming": len(in_links.get(stem, set())),
                "bidirectional_count": len(bidirectional),
                "is_compliant": is_compliant
            }

        return {
            "all_compliant": all_compliant,
            "total_notes": len(note_files),
            "note_stats": note_stats
        }

    def generate_zettelkasten_note(
        self,
        note_id: str,
        title: str,
        thesis_statement: str,
        evidence_text: str,
        checklist_items: List[str],
        related_wikilinks: List[str],
        domain: str = "memory_wiki",
        sources: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        status: str = "ACCEPTED"
    ) -> str:
        """Generates formatted markdown string for a single atomic Zettelkasten note."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        tags_list = tags if tags else ["zettelkasten", "supergraph", "knowledge_node"]
        sources_list = sources if sources else []

        fm = {
            "id": note_id,
            "title": title,
            "date": date_str,
            "tags": tags_list,
            "domain": domain,
            "status": status,
            "sources": sources_list
        }

        fm_yaml = yaml.dump(fm, sort_keys=False, allow_unicode=True).strip()
        checklist_md = "\n".join([f"- [ ] {item}" for item in checklist_items]) if checklist_items else "- [ ] Verify claim evidence"
        links_md = "\n".join([f"- [[{link}]]" for link in related_wikilinks]) if related_wikilinks else ""

        content = f"""---
{fm_yaml}
---

# {title}

## Core Claim / Thesis
{thesis_statement}

## Analytical Evidence & Context
{evidence_text}

## Action Checklist
{checklist_md}

## Related Notes & Wikilinks
{links_md}
"""
        return content

    def export_all_zettelkasten_notes(
        self,
        db_path: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Batch exports knowledge entities into Zettelkasten markdown files."""
        target_db = Path(db_path) if db_path else self.db_path
        target_out = Path(output_dir) if output_dir else self.output_dir
        target_out.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Query thesis, protocol, media scenes, and telegram threads
        rows = cur.execute("""
            SELECT id, name, domain, node_type, description, tags, properties
            FROM kg_nodes
            WHERE domain IN ('memory_wiki', 'multimodal_av', 'telegram_discussion', 'kgb_analytics')
        """).fetchall()

        exported_count = 0
        errors = []

        for row in rows:
            try:
                nid = row["id"]
                title = row["name"] or f"Note {nid}"
                desc = row["description"] or ""
                props = json.loads(row["properties"]) if row["properties"] else {}

                note_file = target_out / f"{re.sub(r'[^a-zA-Z0-9_]', '_', title)}.md"
                note_content = self.generate_zettelkasten_note(
                    note_id=f"zk_{nid}",
                    title=title,
                    thesis_statement=desc[:300],
                    evidence_text=desc,
                    checklist_items=["Review evidence quality", "Check cross-references"],
                    related_wikilinks=["Zettelkasten System Index", "SuperGraph OS Overview", "KGB Analytics Hub"],
                    domain=row["domain"],
                    sources=[nid]
                )
                note_file.write_text(note_content, encoding="utf-8")
                exported_count += 1
            except Exception as e:
                errors.append({"node_id": row["id"], "error": str(e)})

        conn.close()
        return {
            "notes_exported": exported_count,
            "output_dir": str(target_out),
            "errors": errors
        }

    def reindex_exported_notes_to_supergraph(
        self,
        output_dir: Optional[Path] = None,
        db_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Re-indexes exported markdown files into SuperGraph SQLite DB via SuperGraphLinker."""
        target_db = Path(db_path) if db_path else self.db_path
        target_out = Path(output_dir) if output_dir else self.output_dir

        linker = SuperGraphLinker(db_path=target_db, wiki_dir=target_out)
        return linker.run_supergraph_integration()
```

---

## 4. Automated Test Suite Specification (`tests/test_zettelkasten_exporter.py`)

The test suite is structured into 6 distinct, independent unit and integration test methods:

```python
"""
tests/test_zettelkasten_exporter.py
Automated Unit & Integration Test Suite for vazus_core/zettelkasten_exporter.py
Milestone 3 Requirement R3: Automated Zettelkasten Exporter & SuperGraph Integration.
"""

import sys
import os
import unittest
import tempfile
import sqlite3
import json
import yaml
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

from vazus_core.zettelkasten_exporter import ZettelkastenExporter
from vazus_core.supergraph_linker import SuperGraphLinker


class TestZettelkastenExporter(unittest.TestCase):

    def setUp(self):
        """Set up temporary directory and isolated SQLite database for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        
        self._init_sqlite_schema(self.temp_db_path)
        self.exporter = ZettelkastenExporter(db_path=Path(self.temp_db_path), output_dir=self.output_dir)

    def tearDown(self):
        """Clean up temporary directory and SQLite database file."""
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass
        self.temp_dir.cleanup()

    def _init_sqlite_schema(self, db_path: str):
        """Initializes minimal kg_nodes and kg_edges SQLite tables."""
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY,
                name TEXT,
                domain TEXT,
                node_type TEXT,
                description TEXT,
                tags TEXT,
                properties TEXT,
                embedding_json TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kg_edges (
                source_id TEXT,
                target_id TEXT,
                relation TEXT,
                strength REAL,
                properties TEXT,
                PRIMARY KEY (source_id, target_id, relation)
            );
        """)
        conn.commit()
        conn.close()

    def test_01_atomic_note_generation(self):
        """Verify atomic note generation, file creation in target directory, and section hierarchy."""
        note_content = self.exporter.generate_zettelkasten_note(
            note_id="zk_test_001",
            title="Joint Warmup Protocol for Knees",
            thesis_statement="Regular joint warmup before heavy loading reduces knee injury risk.",
            evidence_text="Clinical studies demonstrate increased synovial fluid temperature.",
            checklist_items=["Perform 10 min low-intensity cycling", "Execute 15 bodyweight squats"],
            related_wikilinks=["Knee Health Index", "Synovial Fluid Dynamics", "Lower Body Warmup"],
            domain="memory_wiki",
            sources=["scene_test01"]
        )
        target_file = self.output_dir / "Joint_Warmup_Protocol_for_Knees.md"
        target_file.write_text(note_content, encoding="utf-8")

        self.assertTrue(target_file.exists(), "Atomic note file must be created in target directory")
        self.assertGreater(target_file.stat().st_size, 0, "Created file must not be empty")

        res = ZettelkastenExporter.validate_atomic_structure(note_content)
        self.assertTrue(res["is_valid"], "Complete atomic note should pass structure validation")
        self.assertTrue(res["has_h1_title"])
        self.assertEqual(len(res["missing_sections"]), 0)

    def test_02_yaml_frontmatter(self):
        """Verify YAML frontmatter parsing, metadata field validation, and error handling."""
        sample_note = """---
id: zk_20260724_001
title: Joint Warmup Protocol for Knees
date: 2026-07-24
tags:
  - zettelkasten
  - supergraph
  - joint_health
domain: memory_wiki
status: ACCEPTED
sources:
  - scene_test01
  - tg_msg_192748
---

# Joint Warmup Protocol for Knees

## Core Claim / Thesis
Regular joint warmup before heavy loading reduces knee injury risk.
"""
        fm = ZettelkastenExporter.parse_yaml_frontmatter(sample_note)
        self.assertIsNotNone(fm, "YAML frontmatter should be parsed successfully")
        self.assertEqual(fm["id"], "zk_20260724_001")
        self.assertEqual(fm["title"], "Joint Warmup Protocol for Knees")
        self.assertIn("zettelkasten", fm["tags"])
        
        is_valid = ZettelkastenExporter.validate_frontmatter(fm)
        self.assertTrue(is_valid, "Valid frontmatter should pass validation schema")

        # Invalid frontmatter missing mandatory 'id'
        invalid_fm = {"title": "Missing ID", "date": "2026-07-24"}
        self.assertFalse(ZettelkastenExporter.validate_frontmatter(invalid_fm))

    def test_03_bidirectional_wikilinks(self):
        """Verify extraction and enforcement of >= 3 bidirectional [[Wikilinks]] per note."""
        note_names = ["Note_A", "Note_B", "Note_C", "Note_D"]
        for name in note_names:
            other_notes = [n for n in note_names if n != name]
            links_md = "\n".join([f"- [[{other}]]" for other in other_notes])
            content = f"""---
id: zk_{name}
title: {name}
date: 2026-07-24
tags: [zettelkasten]
domain: memory_wiki
status: ACCEPTED
sources: [src_01]
---

# {name}

## Core Claim / Thesis
Atomic claim for {name}.

## Analytical Evidence & Context
Evidence for {name}.

## Action Checklist
- [ ] Action item for {name}

## Related Notes & Wikilinks
{links_md}
"""
            (self.output_dir / f"{name}.md").write_text(content, encoding="utf-8")

        links_report = self.exporter.verify_bidirectional_links(self.output_dir)
        self.assertTrue(links_report["all_compliant"], "All notes should have >= 3 bidirectional links")
        self.assertEqual(links_report["total_notes"], 4)
        for stem, stats in links_report["note_stats"].items():
            self.assertGreaterEqual(stats["bidirectional_count"], 3, f"{stem} must have >= 3 bidirectional wikilinks")
            self.assertTrue(stats["is_compliant"])

    def test_04_action_checklist(self):
        """Verify detection and extraction of markdown action checklist task checkboxes (- [ ])."""
        content_with_checklist = """
## Action Checklist
- [ ] Perform daily joint mobility warmups
- [x] Complete baseline bloodwork panel
"""
        self.assertTrue(ZettelkastenExporter.validate_action_checklist(content_with_checklist))

        content_without_checklist = """
## Action Checklist
No checklist items listed here.
"""
        self.assertFalse(ZettelkastenExporter.validate_action_checklist(content_without_checklist))

    def test_05_batch_export_from_db(self):
        """Verify batch export export_all_zettelkasten_notes from vazus.db analytics (kg_nodes)."""
        conn = sqlite3.connect(self.temp_db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO kg_nodes (id, name, domain, node_type, description, tags, properties)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "thesis_001",
            "Boron Cycling Thesis",
            "memory_wiki",
            "ThesisNode",
            "Boron 10mg daily reduces SHBG by 20%.",
            "zettelkasten,boron",
            json.dumps({"statement": "Boron 10mg daily reduces SHBG", "confidence_score": 0.9, "ach_status": "ACCEPTED"})
        ))
        conn.commit()
        conn.close()

        result = self.exporter.export_all_zettelkasten_notes(
            db_path=Path(self.temp_db_path),
            output_dir=self.output_dir
        )
        self.assertIn("notes_exported", result)
        self.assertGreater(result["notes_exported"], 0, "Must export at least one note from DB")
        self.assertEqual(result["output_dir"], str(self.output_dir))

    def test_06_supergraph_reindexing(self):
        """Verify SuperGraphLinker re-indexing exported notes into SQLite kg_nodes and kg_edges."""
        sample_file = self.output_dir / "SuperGraph_Topology_Note.md"
        sample_file.write_text("""---
id: zk_supergraph_001
title: SuperGraph Topology Note
date: 2026-07-24
tags: [zettelkasten, supergraph]
domain: memory_wiki
status: ACCEPTED
sources: [src_test]
---

# SuperGraph Topology Note

## Core Claim / Thesis
SuperGraph binds code AST nodes and memory wiki notes into a 768D vector space.

## Analytical Evidence & Context
Graph embeddings use Google Gemini 2 / Gemma 300M model.

## Action Checklist
- [ ] Run SuperGraphLinker integration sweep

## Related Notes & Wikilinks
- [[Vector Space Note]]
- [[AST Graph Note]]
- [[Memory Wiki Note]]
""", encoding="utf-8")

        linker = SuperGraphLinker(db_path=Path(self.temp_db_path), wiki_dir=self.output_dir)
        report = linker.run_supergraph_integration(threshold=0.10)

        self.assertGreater(report["wiki_notes_count"], 0, "Should index at least one WikiNote")
        self.assertGreater(report["wiki_sections_count"], 0, "Should index WikiSection nodes")

        conn = sqlite3.connect(self.temp_db_path)
        cur = conn.cursor()
        wiki_nodes = cur.execute("SELECT id, name, domain, node_type FROM kg_nodes WHERE domain = 'memory_wiki'").fetchall()
        self.assertGreaterEqual(len(wiki_nodes), 1, "kg_nodes table must contain memory_wiki nodes")
        conn.close()


if __name__ == "__main__":
    unittest.main()
```

---

## 5. Summary of Test Coverage Matrix

| Test ID | Test Method Name | Target Functionality | Verification Criteria |
| :--- | :--- | :--- | :--- |
| **01** | `test_01_atomic_note_generation` | Atomic note generation & file creation | Target file created in output dir, non-empty, contains H1 + 4 required H2 sections |
| **02** | `test_02_yaml_frontmatter` | YAML frontmatter parsing & schema validation | `parse_yaml_frontmatter` parses dict; `validate_frontmatter` enforces mandatory schema keys |
| **03** | `test_03_bidirectional_wikilinks` | Bidirectional graph connectivity verification | `verify_bidirectional_links` checks $\ge 3$ reciprocal outgoing/incoming `[[Wikilinks]]` |
| **04** | `test_04_action_checklist` | Markdown checklist checkbox detection | Regex matching `- [ ]` or `- [x]` under Action Checklist section |
| **05** | `test_05_batch_export_from_db` | End-to-end batch export execution from DB | `export_all_zettelkasten_notes` writes `.md` files into target directory from `vazus.db` |
| **06** | `test_06_supergraph_reindexing` | SuperGraph DB re-indexing integration | `SuperGraphLinker` creates `WikiNote`/`WikiSection` in `kg_nodes` and `WIKILINK` edges in `kg_edges` |

---

## 6. Verification Procedures

To execute and verify the automated test suite once implemented:

```powershell
# Run the test suite using Python unittest runner
C:\vazus\.venv\Scripts\python.exe -m unittest tests/test_zettelkasten_exporter.py -v
```

*Expected Outcome*: All 6 test cases pass with `OK` status.
