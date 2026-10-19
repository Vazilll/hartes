# Original User Request

## Initial Request — 2026-09-20T15:09:24Z

Comprehensive end-to-end performance and storage optimization of Vazus OS: strip 22 GB of legacy binary blobs from git history, relocate 27.8 GB of media courses out of the workspace, optimize SQLite database storage and query latencies, and minimize Antigravity hook execution overhead with zero regression.

Working directory: C:\vazus
Integrity mode: development

## Requirements

### R1. Git Repository Compression & Media Relocation
Safely purge large historical binary blobs (committed MP4 videos, Whisper models, SQLite dumps) from `.git` commit history using `git-filter-repo` or aggressive object pruning, reducing `.git` footprint from 22.3 GB to < 500 MB. Move `knowledge/telegram_courses/` (27.8 GB) to `C:\Users\Vaz\Videos\Courses` and update `.gitignore` so the active code workspace is decoupled from static media. The total directory size of `C:\vazus` must shrink below 10 GB.

### R2. Database Compaction & Engine Tuning
Optimize canonical SQLite storage (`services/memory/vazus.db`) by executing `VACUUM`, `ANALYZE`, and `PRAGMA optimize`, ensuring `WAL` journal mode and proper B-Tree indexing. Preserve 100% of verified user records (810 financial transactions, 4 liabilities, 28 tax receipts, 18 academic debts, 95 schedule slots, nutrition logs, BLE weight records).

### R3. Antigravity Hook Latency Minimization
Profile and streamline active lifecycle hooks (`vazus_core/hooks/pre_tool_hook.py`, `pre_invocation_hook.py`, `post_tool_hook.py`) to eliminate redundant disk I/O, heavy regex re-compilations, or slow subprocess invocations. Ensure per-tool execution latency stays under 15 ms and turn-0 invocation context injection stays under 50 ms.

### R4. Zero-Regression Verification Gate
Verify that all system invariants, AST call topologies, and core services remain 100% intact. The test suite (`pytest tests/test_academic_truth_engine.py tests/test_db_consolidation.py tests/test_stop_hook_curation.py`) must pass completely with 0 failures.

## Acceptance Criteria

### Storage & Repository Metrics
- [ ] `.git` directory size is reduced to under 500 MB (from 22.3 GB).
- [ ] `knowledge/telegram_courses/` is relocated out of the git workspace, with `.gitignore` properly updated.
- [ ] Total workspace size `C:\vazus` is under 10 GB.

### Database Integrity & Performance
- [ ] `services/memory/vazus.db` passes `PRAGMA integrity_check` with result `ok`.
- [ ] All 810 transactions, 18 debts, 95 schedule items, and nutrition logs remain intact and queryable.
- [ ] Database is compacted with freed pages recovered via `VACUUM`.

### Hook Latency & Test Pass
- [ ] `pre_tool_hook.py` executes in < 15 ms on typical tool invocations.
- [ ] `pre_invocation_hook.py` executes in < 50 ms.
- [ ] 100% pass rate across core test suites with zero broken imports.
