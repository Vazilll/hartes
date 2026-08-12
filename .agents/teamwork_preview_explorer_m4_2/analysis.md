# Comprehensive Analysis Report: Spaced Repetition Database Schema Persistence & CLI Runner Architecture

**Milestone**: Milestone 4 (R4: Active Learning SM-2 Engine & Spaced Repetition Tutor)  
**Author**: Explorer 2 (`teamwork_preview_explorer_m4_2`)  
**Date**: 2026-07-24  
**Working Directory**: `C:\vazus\.agents\teamwork_preview_explorer_m4_2`  
**Target Codebase Paths**: `vazus_core/cognitive_tutor_engine.py` & `scripts/personal_tutor.py`

---

## 1. Executive Summary

This report delivers a thorough architectural investigation into the database schema persistence and Command Line Interface (CLI) runner for the active learning SuperMemo SM-2 spaced repetition tutor within the `vazus` SuperGraph OS.

The investigation confirmed that:
1. **SQLite Database Persistence (`vazus.db` & `dnts.db`)**:
   - `vazus.db` (`C:\vazus\vazus.db` and `C:\vazus\services\memory\vazus.db`) implements relational persistence for `tutor_cards` and `tutor_reviews` tables, complete with composite indexing (`idx_tutor_cards_due`) and backward-compatibility SQL views (`kg_flashcards` and `kg_review_logs`).
   - `dnts.db` (`C:\vazus\memory\dnts.db`) handles Graph Memory topology (`kg_nodes` and `kg_edges`), binding seamlessly to `tutor_cards.entity_id`.
2. **CLI Runner Architecture (`scripts/personal_tutor.py`)**:
   - Implements `--test` (non-interactive self-verification suite returning Exit Code 0 cleanly), `--review` (interactive recall study session with automated non-TTY fallback), and `--stats` (mastery statistics & histogram rendering).

---

## 2. Database Schema Persistence Architecture (`vazus.db` & `dnts.db`)

### 2.1 Database Layout & System Integration

The `vazus` SuperGraph OS utilizes a dual-database architecture:
- **`vazus.db`** (Relational & Subagent Ledger Store): Located at `C:\vazus\vazus.db` (and `C:\vazus\services\memory\vazus.db`). Contains AST topology, subagent dialogues, handoff ledgers, memory traces, and spaced repetition tutor state.
- **`dnts.db`** (Knowledge Graph & Vector Store): Located at `C:\vazus\memory\dnts.db`. Managed by `gomcp/dnts-brain.exe` and `kgb_analytical_extractor.py`, storing graph nodes (`kg_nodes`) and directional edges (`kg_edges`).

`CognitiveTutorEngine` binds `tutor_cards.entity_id` to entity nodes from both databases (`workspace_ast_nodes`, `kg_nodes`, `ThesisNode`, `ProtocolNode`, and Obsidian Zettelkasten Markdown notes).

---

### 2.2 Table Schemas

#### A. Table `tutor_cards`
Stores active recall flashcard state, SuperMemo SM-2 interval parameters, and scheduling metadata.

```sql
CREATE TABLE IF NOT EXISTS tutor_cards (
    id TEXT PRIMARY KEY,               -- Unique card ID (e.g. card_a1b2c3d4e5f6)
    entity_id TEXT NOT NULL,           -- Underlying AST node / entity ID (aliased to node_id)
    entity_type TEXT NOT NULL,         -- Entity type (ThesisNode, ProtocolNode, ZettelNote)
    question_type TEXT NOT NULL,       -- Archetype (FILL_IN_BLANK, CONCEPT_EXPLANATION, etc.)
    question_text TEXT NOT NULL,       -- Socratic prompt text (aliased to question)
    target_answer TEXT NOT NULL,       -- Ground truth target answer (aliased to answer_key)
    repetition_n INTEGER DEFAULT 0,    -- Successful repetition count n (aliased to repetitions)
    ease_factor REAL DEFAULT 2.5,      -- SuperMemo Ease Factor EF (min 1.3)
    interval_days REAL DEFAULT 0.0,    -- Current scheduled review interval I(n) in days
    lapses INTEGER DEFAULT 0,          -- Total count of failed review lapses (Q < 3)
    last_review_at TEXT,               -- ISO 8601 UTC timestamp of last review (aliased to last_reviewed)
    next_review_at TEXT,               -- ISO 8601 UTC timestamp when card is due (aliased to next_review_due)
    created_at TEXT NOT NULL,          -- Timestamp card was created
    updated_at TEXT NOT NULL           -- Timestamp card state was last updated
);
```

#### B. Table `tutor_reviews`
Logs historical active recall review attempts, scoring breakdown, quality rating, and user inputs.

```sql
CREATE TABLE IF NOT EXISTS tutor_reviews (
    id TEXT PRIMARY KEY,               -- Unique review log ID (e.g. review_f1e2d3c4b5a6)
    card_id TEXT NOT NULL,             -- Foreign key referencing tutor_cards(id)
    score_percent REAL NOT NULL,       -- Accuracy score S in [0.0, 100.0]% (aliased to score)
    q_rating INTEGER NOT NULL,         -- SM-2 Quality rating Q in [0..5] (aliased to quality)
    user_response TEXT NOT NULL,       -- Verbatim text input from user (aliased to user_answer)
    feedback_rationale TEXT NOT NULL,  -- Constructive feedback & missing concept analysis
    response_time_sec REAL DEFAULT 0,  -- Time taken in seconds to answer (aliased to review_time)
    reviewed_at TEXT NOT NULL,         -- ISO 8601 UTC timestamp of review execution
    FOREIGN KEY (card_id) REFERENCES tutor_cards(id) ON DELETE CASCADE
);
```

---

### 2.3 Field Mapping & Alias Specifications

To support both explicit requirements and legacy system aliases, `vazus_core/cognitive_tutor_engine.py` provides transparent field mappings:

| Standard Column Name | Requirement Alias | Data Type | Description |
| :--- | :--- | :--- | :--- |
| `id` | `card_id` | `TEXT` | Primary key of flashcard |
| `entity_id` | `node_id` | `TEXT` | ID of associated AST/Knowledge node |
| `question_text` | `question` | `TEXT` | Formulated active recall prompt |
| `target_answer` | `answer_key` | `TEXT` | Ground truth expected response |
| `repetition_n` | `repetitions` | `INTEGER` | Successful review iteration count |
| `interval_days` | `interval_days` | `REAL` | Scheduled interval $I(n)$ in days |
| `ease_factor` | `ease_factor` | `REAL` | SuperMemo Ease Factor $EF \ge 1.3$ |
| `next_review_at` | `next_review_due`| `TEXT` | ISO 8601 UTC due timestamp |
| `last_review_at` | `last_reviewed` | `TEXT` | ISO 8601 UTC timestamp of last review |

| Review Column Name | Requirement Alias | Data Type | Description |
| :--- | :--- | :--- | :--- |
| `id` | `review_id` | `TEXT` | Primary key of review log entry |
| `card_id` | `card_id` | `TEXT` | FK referencing `tutor_cards(id)` |
| `user_response` | `user_answer` | `TEXT` | Raw user response string |
| `score_percent` | `score` | `REAL` | Calculated accuracy $S \in [0, 100]\%$ |
| `q_rating` | `quality` | `INTEGER` | Quality rating $Q \in [0..5]$ |
| `response_time_sec` | `review_time` | `REAL` | Elapsed time in seconds |

---

### 2.4 Indexing & SQL View Aliases

1. **Due Card Query Index**:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_tutor_cards_due
   ON tutor_cards (next_review_at, ease_factor);
   ```
   *Rationale*: Optimizes `SELECT * FROM tutor_cards WHERE next_review_at IS NULL OR next_review_at <= ? ORDER BY next_review_at ASC` queries to $\mathcal{O}(\log N)$ execution time.

2. **Backward-Compatibility Aliases**:
   ```sql
   CREATE VIEW IF NOT EXISTS kg_flashcards AS SELECT * FROM tutor_cards;
   CREATE VIEW IF NOT EXISTS kg_review_logs AS SELECT * FROM tutor_reviews;
   ```

---

## 3. CLI Runner Architecture (`scripts/personal_tutor.py`)

`scripts/personal_tutor.py` serves as the CLI interface and verification runner for the spaced repetition system.

```
                    ┌─────────────────────────────────┐
                    │   scripts/personal_tutor.py     │
                    └────────────────┬────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
   ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
   │    --test     │         │   --review    │         │    --stats    │
   └───────┬───────┘         └───────┬───────┘         └───────┬───────┘
           │                         │                         │
  Non-Interactive           Interactive TTY           Mastery Metrics &
  Self-Test Suite          Study Session Loop          Q-Rating Summary
  (Exit Code 0)             (Auto-TTY Fallback)       Terminal Table
```

### 3.1 CLI Options & Dispatch Logic

- **`--test`**: Runs `run_self_test()`. Uses an isolated temporary SQLite database created via `tempfile.NamedTemporaryFile`, runs 4 verification stages, tears down temporary files, and cleanly exits with status code `0`.
- **`--review`**: Runs `run_interactive_review(db_path, wiki_dir)`. Syncs Zettelkasten notes, queries due cards, prompts user via `input()` when TTY is available, or auto-simulates 1 review cycle in non-TTY environments.
- **`--stats`**: Runs `print_stats(db_path)`. Computes aggregated statistics: total cards, due cards count, review count, average accuracy %, average Q rating, system mastery level, and ASCII distribution histogram.
- **Default (No Arguments)**: Defaults to `--test` non-interactive execution returning Exit Code `0`.

---

## 4. Empirical Verification & Tool Output

### 4.1 `--test` Non-Interactive Execution
Executed via terminal:
```bash
C:\vazus\.venv\Scripts\python.exe scripts/personal_tutor.py --test
```
**Output**:
```text
==================================================
   Cognitive Tutor Engine CLI Self-Test Runner   
==================================================
[1/4] Verifying SM-2 Algorithm Math & Bounds...
     -> SM-2 math verified successfully.
[2/4] Verifying Socratic Active Recall Question Generation...
     -> Question generation verified successfully.
[3/4] Verifying 768D Hybrid Answer Evaluator...
     -> Answer evaluation verified successfully.
[4/4] Verifying SQLite Engine Persistence & Review Processing...
     -> SQLite engine persistence verified successfully.
==================================================
[SELF-TEST PASSED] All Cognitive Tutor Engine checks OK.
==================================================
Exit Code: 0
```

### 4.2 `--stats` Execution
Executed via terminal:
```bash
C:\vazus\.venv\Scripts\python.exe scripts/personal_tutor.py --stats
```
**Output**:
```text
=============================================
    COGNITIVE TUTOR MASTERY STATISTICS     
=============================================
Total Flashcards Registered : 0
Cards Due for Review Now   : 0
Total Review Logs Recorded  : 0
Average Accuracy Score      : 0.0%
Average Quality Rating (Q)  : 0.0 / 5.0
System Mastery Level        : Novice
---------------------------------------------
Quality Rating Distribution (0-5):
  Q=0:    0 | 
  Q=1:    0 | 
  Q=2:    0 | 
  Q=3:    0 | 
  Q=4:    0 | 
  Q=5:    0 | 
=============================================
```

---

## 5. Architectural Recommendations for Implementation Workers

1. **Database Schema Enforcement**:
   - Ensure SQLite connection strings enable `PRAGMA foreign_keys = ON;`.
   - Maintain composite index `idx_tutor_cards_due` on `(next_review_at, ease_factor)` for scalable due queries.
2. **CLI Runner Non-Interactive Integrity**:
   - Preserve `sys.stdin.isatty()` safety checks in `--review` mode to guarantee that CLI scripts never hang when invoked by automated test frameworks or subagents.
   - Maintain the default fallback behavior of `main()` to execute `--test` returning Exit Code `0` when no flags are supplied.

---

**Report Completed By**: Explorer 2 (`teamwork_preview_explorer_m4_2`)  
**Artifact Path**: `C:\vazus\.agents\teamwork_preview_explorer_m4_2\analysis.md`
