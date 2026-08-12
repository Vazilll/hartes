# Handoff Report — Milestone 3 R3 Test Suite Specification

**Author**: Explorer 3 (`teamwork_preview_explorer_m3_3`)  
**Date**: 2026-07-24  
**Target File**: `C:\vazus\tests\test_zettelkasten_exporter.py`  
**Working Directory**: `C:\vazus\.agents\teamwork_preview_explorer_m3_3`  

---

## 1. Observation

Direct code inspection of existing test files in `C:\vazus\tests\` confirmed:
1. `tests/test_multimodal_knowledge.py` (66 lines) uses `unittest.TestCase` and tests Whisper fallback, Russian text normalization, thumbnail generation, transcript chunking, and SuperGraph indexing.
2. `tests/test_kgb_analytical_extractor.py` (162 lines) uses `unittest.TestCase` with `setUp`/`tearDown` managing isolated temporary SQLite databases via `tempfile.mkstemp(suffix=".db")`. It tests `ThesisNode`, `ProtocolNode`, `CAUSES`, `REQUIRES`, `CONTRADICTS` relations, 768D vector persistence, and ACH hypothesis matrices.
3. `tests/test_m2_r1_indexing_and_vector_search.py` (118 lines) inspects `SuperGraphLinker` behavior across `kg_nodes` (`memory_wiki`, `ast_code`) and `kg_edges` (`WIKILINK`, `CONTAINS_SECTION`, `SUPERGRAPH_LINK`).

Investigation into `vazus_core/supergraph_linker.py` confirmed `SuperGraphLinker.parse_wiki_note_content()` extracts `WikiNote` nodes (`wiki:<stem>`), `WikiSection` nodes (`wiki:<stem>#<sec_slug>`), `WIKILINK` edges, and `CONTAINS_SECTION` edges using `[[Note]]` regex matching.

---

## 2. Logic Chain

1. **Standardized Test Environment**: Following `test_kgb_analytical_extractor.py`, `test_zettelkasten_exporter.py` must use `unittest.TestCase` with `tempfile.TemporaryDirectory` and `tempfile.mkstemp` to ensure unit test isolation without modifying the primary `vazus.db` or the user's obsidian wiki files.
2. **YAML Frontmatter Verification**: Frontmatter MUST be bounded by `---` lines. Valid frontmatter requires 7 mandatory keys (`id`, `title`, `date`, `tags`, `domain`, `status`, `sources`). Test `test_01_yaml_frontmatter_parsing_and_validity` verifies parsing and schema validation logic.
3. **Atomic Section Structure**: Zettelkasten methodology mandates focused, single-claim notes with a standardized H1 + 4 H2 section layout (`Core Claim / Thesis`, `Analytical Evidence & Context`, `Action Checklist`, `Related Notes & Wikilinks`). Test `test_02_atomic_note_section_structure` validates section presence and header hierarchy.
4. **Dense Graph Connectivity (3+ Bidirectional Links)**: High graph quality requires at least 3 bidirectional `[[Wikilinks]]` per exported note. Test `test_03_verification_of_three_plus_bidirectional_wikilinks` creates a 4-node clique and validates reciprocal edge enforcement via `ZettelkastenExporter.verify_bidirectional_links()`.
5. **Action Checklists**: Notes require interactive tasks. Test `test_04_presence_of_action_checklists` verifies regex matching for `- [ ]` or `- [x]`.
6. **Batch Export Pipeline**: Test `test_05_batch_export_all_zettelkasten_notes` tests end-to-end extraction from `kg_nodes` into markdown files in the target directory.
7. **SuperGraph Linker Re-Indexing**: Test `test_06_supergraph_reindexing_integration` triggers `SuperGraphLinker` to verify that newly created markdown files are successfully parsed into `WikiNote` / `WikiSection` entries in `kg_nodes` and `WIKILINK` / `CONTAINS_SECTION` edges in `kg_edges`.

---

## 3. Caveats

- **PyYAML Dependency**: Parsing YAML frontmatter requires `pyyaml` (installed in `C:\vazus\.venv`). In case PyYAML is missing in a lightweight environment, a fallback regex parser is recommended.
- **Pre-existing Wiki Directory**: Batch export in production default points to `C:/vazus/services/memory/semantic/wiki`. In unit tests, tests MUST always pass explicit `output_dir` (using `tempfile.TemporaryDirectory`) to avoid overwriting production wiki notes.
- **Wikilink Naming Convention**: Note file stems use underscores for spaces (e.g. `Joint_Warmup_Protocol.md`), while `[[Wikilinks]]` may contain spaces or underscores. The link extraction logic normalizes spaces to underscores when resolving note target stems.

---

## 4. Conclusion

The automated test suite specification for Milestone 3 Requirement R3 (`tests/test_zettelkasten_exporter.py`) and the corresponding implementation contract (`vazus_core/zettelkasten_exporter.py`) have been fully designed, specified, and documented.

The specified unit/integration test cases cover:
1. `test_01_atomic_note_generation`: Verifies atomic note file creation in target directory and validates section hierarchy (H1 + 4 H2 sections).
2. `test_02_yaml_frontmatter`: Parses frontmatter metadata (`parse_yaml_frontmatter`) and validates schema compliance.
3. `test_03_bidirectional_wikilinks`: Counts `[[Wikilinks]]` and enforces $\ge 3$ bidirectional links per note.
4. `test_04_action_checklist`: Checks for presence of `- [ ]` markdown checklist items.
5. `test_05_batch_export_from_db`: Verifies batch export (`export_all_zettelkasten_notes`) from `vazus.db` analytics.
6. `test_06_supergraph_reindexing`: Verifies SuperGraphLinker re-indexing into `kg_nodes` and `kg_edges`.

---

## 5. Verification Method

To verify the test suite once implemented by the worker:

```powershell
C:\vazus\.venv\Scripts\python.exe -m unittest tests/test_zettelkasten_exporter.py -v
```

**Invalidation Conditions**:
- Failure to parse frontmatter bounded by `---`.
- Missing any of the 4 required H2 sections in generated Zettelkasten notes.
- Exported notes having $< 3$ bidirectional `[[Wikilinks]]`.
- SuperGraphLinker failing to create `WikiNote` / `WikiSection` nodes in SQLite `kg_nodes`.
