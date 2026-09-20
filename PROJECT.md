# Project: Vazus OS Performance & Storage Optimization

## Architecture
- **Storage & Git Layer**:
  - Historical repository blob pruning via `git-filter-repo` and `git gc --prune=now --aggressive`.
  - Static media decoupling: `knowledge/telegram_courses/` relocated to `C:\Users\Vaz\Videos\Courses` with dynamic path resolution via `VAZUS_COURSES_DIR`.
  - Tightened `.gitignore` to prevent re-tracking Whisper models, GGUF weights, and SQLite archives.
- **Canonical Database Layer (`services/memory/vazus.db`)**:
  - SQLite WAL mode engine with `PRAGMA synchronous = NORMAL` at runtime.
  - B-Tree index coverage across high-frequency lookup columns (`finance_transactions`, `mirea_schedule`, `mirea_milestones`, `nutrition_log`, `mi_scale_weighins`, `self_employed_receipts`, `subagent_memory_traces`, `mem0_facts`).
  - Maintenance cycle: `ANALYZE`, `PRAGMA optimize`, `VACUUM`, and `PRAGMA wal_checkpoint(TRUNCATE)`.
  - 100% invariant preservation of verified user records (810 transactions, 4 liabilities, 28 tax receipts, 18 debts, 95 schedule items, nutrition logs, BLE weigh-ins).
- **Antigravity Hook Lifecycle Layer (`vazus_core/hooks/`)**:
  - `vazus_core/__init__.py`: Lazy loading via module `__getattr__` to eliminate 2,347 ms eager import cascade (OpenVINO, NumPy, SuperGraphLinker, ConcordiaJury).
  - `pre_tool_hook.py`: Propositional fast-path validation for workspace path jail, dangerous commands, and null bytes (< 1.0 ms in-process, target < 15 ms).
  - `pre_invocation_hook.py`: Direct SQLite profile/trace retrieval, JSON skill caching (`logs/.skill_index_cache.json`), and non-blocking background hints (~19.5 ms Turn 0, < 0.5 ms Turn N > 0, target < 50 ms).
  - `post_tool_hook.py`: Lean HUD event dispatcher and non-blocking maintenance trigger.
- **Zero-Regression Verification Layer**:
  - Invariant preservation and 100% pass across core test suites:
    `pytest tests/test_academic_truth_engine.py tests/test_db_consolidation.py tests/test_stop_hook_curation.py`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Git History Blob Purge | Purge MP4s, Whisper models, SQLite commits from `.git` history using `git-filter-repo`, reducing `.git` to < 500 MB | M1 | explorer_1 |
| 2 | Media Courses Relocation | Relocate `knowledge/telegram_courses/` (27.12 GB) to `C:\Users\Vaz\Videos\Courses` and update references | M1 | explorer_1 |
| 3 | `.gitignore` Hardening | Add explicit exclusions for `.whisper_cache/`, `*.gguf`, `_archive/`, and media directories | M1 | explorer_1 |
| 4 | Workspace Footprint Reduction | Shrink total `C:\vazus` directory size below 10 GB (projected ~9.29 GB) | M1 | explorer_1 |
| 5 | Database Integrity & Record Check | Verify 100% record invariants (810 tx, 4 liab, 28 receipts, 18 debts, 95 schedule, nutrition, BLE) and `PRAGMA integrity_check` = `ok` | M2 | explorer_2 |
| 6 | Strategic B-Tree Indexing | Create 12 targeted B-Tree indices on frequently queried foreign keys and timestamp columns | M2 | explorer_2 |
| 7 | SQLite Compaction & Engine Tuning | Execute `ANALYZE`, `PRAGMA optimize`, `VACUUM`, and truncate WAL checkpoint | M2 | explorer_2 |
| 8 | Root Package Lazy Loading | Replace eager imports in `vazus_core/__init__.py` with `__getattr__` lazy loading, cutting import time from 2,347ms to < 2ms | M3 | explorer_3 |
| 9 | Pre-Tool Hook Fast-Path | Implement propositional fast-path security checks in `pre_tool_hook.py` achieving < 1.0 ms latency | M3 | explorer_3 |
| 10 | Pre-Invocation Hook Streamlining | Add JSON skill cache and direct SQLite queries in `pre_invocation_hook.py` achieving < 50 ms Turn 0 and < 0.5 ms Turn N | M3 | explorer_3 |
| 11 | Post-Tool Hook Optimization | Decouple heavy imports in `post_tool_hook.py` to ensure lightweight HUD telemetry | M3 | explorer_3 |
| 12 | Core Test Suite Zero-Regression | Verify 100% pass rate across `test_academic_truth_engine.py`, `test_db_consolidation.py`, `test_stop_hook_curation.py` | M4 | explorer_3 |
| 13 | Forensic Integrity Verification | Multi-agent review, adversarial challenge, and forensic audit of system invariants and absence of cheating | M4 | orchestrator |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Git Compression & Media Relocation | Features 1, 2, 3, 4 | none | IN_PROGRESS |
| 2 | M2: Database Compaction & Engine Tuning | Features 5, 6, 7 | none | PLANNED |
| 3 | M3: Antigravity Hook Latency Minimization | Features 8, 9, 10, 11 | none | PLANNED |
| 4 | M4: Zero-Regression Verification Gate & Forensic Audit | Features 12, 13 | M1, M2, M3 | PLANNED |

## Interface Contracts
### `knowledge/telegram_courses` ↔ `scripts/mcp_servers/telegram_mcp.py` & `vazus_core/integrations/telegram_indexer.py`
- `DEFAULT_COURSES_DIR = Path(os.environ.get("VAZUS_COURSES_DIR", r"C:\Users\Vaz\Videos\Courses"))`
- Allows seamless course index lookup both locally and across relocated media storage.

### `vazus_core/__init__.py` ↔ Consumers
- `__getattr__(name: str) -> Any`:
  - Dynamically imports `get_db_connection`, `DocstringAndBodyPruner`, `SuperGraphLinker`, `ConcordiaJury`, `UnifiedReasoningPipeline` only upon explicit access.
  - Exposes subpackages `engine`, `verification`, `memory`, `workers`, `integrations` via lazy attributes.
  - Guarantees `import vazus_core` takes < 5 ms.

### `vazus_core.hooks.pre_tool_hook`
- `run_pre_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]`
- Validates path jail and command safety in < 1.0 ms without invoking heavy external solvers unless ambiguous.

### `vazus_core.hooks.pre_invocation_hook`
- `run_pre_invocation(context: Dict[str, Any]) -> Dict[str, Any]`
- Injects user profile, memory traces, and matched skills in < 50 ms on Turn 0 and < 0.5 ms on Turn N > 0.

## Code Layout
- `.gitignore`: Git exclusion rules (owned by M1)
- `scripts/mcp_servers/telegram_mcp.py`, `vazus_core/integrations/telegram_indexer.py`: Relocated courses path resolution (owned by M1)
- `services/memory/vazus.db`: Canonical SQLite database (owned by M2)
- `vazus_core/__init__.py`: Lazy package exports (owned by M3)
- `vazus_core/hooks/pre_tool_hook.py`, `vazus_core/verification/substrate_guard.py`: Pre-tool security validation (owned by M3)
- `vazus_core/hooks/pre_invocation_hook.py`: Pre-invocation context injection & skill cache (owned by M3)
- `vazus_core/hooks/post_tool_hook.py`: Post-tool HUD telemetry (owned by M3)
- `tests/test_academic_truth_engine.py`, `tests/test_db_consolidation.py`, `tests/test_stop_hook_curation.py`: Core verification suites (owned by M4)
