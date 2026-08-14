# Project: Antigravity CLI Reverse Engineering & Self-Polishing Memory Engine (Project Sentinel)

## Architecture
The system builds a background sidecar daemon integrated with `vazus_core` and the Antigravity CLI ecosystem (`C:\Users\Vaz\.gemini\antigravity-cli`).

- **Background Daemon Sidecar (`vazus_core/daemon_sidecar.py` & `system_daemon.py`)**:
  - Non-blocking SQLite WAL watcher (`mode=ro`) reading `conversation_summaries.db`, `conversations/<id>.db`, and `subagent_dialogues`.
  - Event dispatch queue delivering dialogue turns to R2 and R3 engines without lock contention.
  - Path normalization using `Path.home()` replacing hardcoded path strings.

- **Automated Skill Generation Engine (`vazus_core/auto_skill_engine.py`)**:
  - `TranscriptAnalyzer`: Vector clustering (cosine similarity >= 0.82) & multi-step trajectory analysis (>12 steps).
  - `SkillGenerator`: Synthesizes tools & command workflows into valid Markdown.
  - `SkillSyntacticValidator`: Enforces byte-0 `---` frontmatter, name/description length limits, and 57-char `"Use when ..."` trigger rules.
  - Auto-registers skills to `C:\Users\Vaz\.gemini\config\skills\<skill_name>\SKILL.md` and triggers `SkillIntentParser.build_index()`.

- **Persistent Context Memory Engine (`vazus_core/context_memory_engine.py`)**:
  - Dialogue Indexer: Extracts user preferences, architectural decisions (ADRs), and verified refactors into `vazus.db` (tables `kg_nodes`, `vec_kg_nodes` 768D float vector virtual table, `organic_insights`) and `services/memory/semantic/wiki` Zettelkasten.
  - Dynamic Prompt Injector: Constructs `<persistent_context>` XML blocks (retrieved via 768D vector similarity >= 0.70) and `<active_skills>` XML blocks (compressed via `ASTPruner` for >77% token savings).

- **E2E Verification & Integration Suite (`tests/`)**:
  - Programmatic pytest suite validating R1 (daemon health & multi-agent WAL concurrency), R2 (silent mock transcript skill generation), R3 (768D vector memory recall), and end-to-end integration.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Non-blocking CLI DB Watcher | Polling `conversation_summaries.db` and `<id>.db` via `mode=ro` WAL SQLite connections | M1 | R1 Survey |
| 2 | Daemon Sidecar Process | Background daemon process management, health checks, entry point refactoring | M1 | R1 Survey |
| 3 | Path Normalization | Replace hardcoded user home paths with dynamic `Path.home()` resolution | M1 | R1 Survey |
| 4 | Transcript Repetition Analyzer | Vector clustering (cosine similarity >= 0.82) across dialogue turns | M2 | R2 Survey |
| 5 | High-Step Trajectory Miner | Trajectory step analysis detecting trial-and-error workflows (>12 steps) | M2 | R2 Survey |
| 6 | Hermes SKILL.md Synthesizer | Synthesizes tool execution history into valid SKILL.md Markdown | M2 | R2 Survey |
| 7 | Hermes Frontmatter Validator | Strict validation of byte-0 `---`, name, description, and 57-char trigger phrase | M2 | R2 Survey |
| 8 | Auto-Skill Registration & Sync | Automatic file creation in `.gemini/config/skills/` and `SkillIntentParser` index refresh | M2 | R2 Survey |
| 9 | Dialogue Transcript Memory Indexer | Indexes turns to extract user preferences, ADRs, and refactors into `vazus.db` | M3 | R3 Survey |
| 10 | 768D Vector Memory Store | Stores float vectors in `vec_kg_nodes` and `organic_insights` with Obsidian wiki sync | M3 | R3 Survey |
| 11 | Prompt Context Injector | Dynamic context injector formatting `<persistent_context>` and `<active_skills>` (AST-pruned) | M3 | R3 Survey |
| 12 | R1 Daemon Health Pytest | Programmatic test verifying non-blocking initialization & 5-thread WAL concurrency | M4 | R3 Survey |
| 13 | R2 Skill Auto-Gen Pytest | Programmatic test verifying mock transcript processing & silent SKILL.md creation | M4 | R3 Survey |
| 14 | R3 Memory Recall Pytest | Programmatic test verifying 768D vector recall & persistent context formatting | M4 | R3 Survey |
| 15 | E2E Integration Suite | Full acceptance test proving all 4 acceptance criteria pass | M4 | Survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: R1 Reverse Engineering & Code Polish | Refactor `system_daemon.py`, create `daemon_sidecar.py` with read-only WAL CLI watchers and dynamic path resolution | none | IN_PROGRESS |
| 2 | M2: R2 Automated Skill Generation Engine | Build `auto_skill_engine.py` (TranscriptAnalyzer, SkillGenerator, SkillSyntacticValidator, AutoSkillEngineDaemon) | M1 | PLANNED |
| 3 | M3: R3 Persistent Context Memory | Build `context_memory_engine.py` (DialogueIndexer, VectorMemoryStore, PromptContextInjector) | M1, M2 | PLANNED |
| 4 | M4: Final E2E Test Suite & Forensic Audit | Write test scripts in `tests/`, execute full test suite, conduct forensic audit, verify acceptance criteria | M1, M2, M3 | PLANNED |

## Feature Inventory Cross-Check
- Total Features: 15
- Milestone 1: Features 1, 2, 3 (3 features)
- Milestone 2: Features 4, 5, 6, 7, 8 (5 features)
- Milestone 3: Features 9, 10, 11 (3 features)
- Milestone 4: Features 12, 13, 14, 15 (4 features)
- All 15 features assigned: YES (100% assigned).

## Interface Contracts
### `daemon_sidecar.py` ↔ `auto_skill_engine.py`
- `TranscriptEvent(conversation_id: str, step_idx: int, user_input: str, tool_calls: list[dict], status: str, timestamp: str)`
- `AutoSkillEngine.process_transcript_event(event: TranscriptEvent) -> Optional[str]` (returns generated `skill_path` or `None`)

### `daemon_sidecar.py` ↔ `context_memory_engine.py`
- `ContextMemoryEngine.index_dialogue_turn(conversation_id: str, prompt: str, response: str, metadata: dict) -> dict` (returns extracted insights & vector IDs)
- `ContextMemoryEngine.get_persistent_context(query: str, threshold: float = 0.70) -> str` (returns formatted `<persistent_context>` XML string)

### `auto_skill_engine.py` ↔ `dynamic_skill_dispatcher.py`
- `SkillSyntacticValidator.validate(skill_content: str) -> tuple[bool, list[str]]`
- `SkillIntentParser.build_index()`

## Code Layout
- `C:\vazus\vazus_core\system_daemon.py` (Owner: Worker M1)
- `C:\vazus\vazus_core\daemon_sidecar.py` (Owner: Worker M1)
- `C:\vazus\vazus_core\auto_skill_engine.py` (Owner: Worker M2)
- `C:\vazus\vazus_core\context_memory_engine.py` (Owner: Worker M3)
- `C:\vazus\tests\test_r1_daemon_health.py` (Owner: Worker M4)
- `C:\vazus\tests\test_r2_skill_autogen.py` (Owner: Worker M4)
- `C:\vazus\tests\test_r3_memory_recall.py` (Owner: Worker M4)
- `C:\vazus\tests\test_sentinel_e2e.py` (Owner: Worker M4)
