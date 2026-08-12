# Milestone 4 (R4) Unit Test Suite Specification: `tests/test_cognitive_tutor_engine.py`

**Working Directory**: `C:\vazus\.agents\teamwork_preview_explorer_m4_3`  
**Target Project**: `C:\vazus`  
**Author**: Explorer 3 (Milestone 4: R4 Active Learning Engine & SM-2 Engine)  
**Date**: 2026-07-24  

---

## 1. Executive Summary

This document specifies the complete unit test suite design for `tests/test_cognitive_tutor_engine.py` as required by Milestone 4 (R4: Active Learning Engine & SM-2 Engine) of the vazus SuperGraph OS.

The cognitive tutor engine (`vazus_core/cognitive_tutor_engine.py`) provides:
1. **Socratic Active Recall Question Generation**: Dynamic generation of flashcards from `ThesisNode`, `ProtocolNode`, and Obsidian Zettelkasten Markdown notes (`ZettelNote`).
2. **Hybrid Answer Evaluation & Scoring**: 0–100% accuracy scoring mapped to SuperMemo SM-2 Quality rating $Q \in [0..5]$ based on 768D semantic cosine similarity (or sequence ratio fallback), keyword recall, and token sequence matching.
3. **SuperMemo SM-2 Interval Scheduling**: Mathematical progression for review intervals ($I_1 = 1$, $I_2 = 3$, $I_3 = 7$, $I_4 = 21$ days), Ease Factor updates ($EF \ge 1.3$), and lapse resets ($n=0, I=1$ for $Q < 3$).
4. **SQLite Engine Persistence**: Full CRUD persistence for flashcards (`tutor_cards`), historical review logs (`tutor_reviews`), and alias views (`kg_flashcards`, `kg_review_logs`) in `vazus.db`.
5. **CLI Runner**: `python scripts/personal_tutor.py --test` execution returning Exit Code 0.

---

## 2. Detailed Test Cases Specification

The test suite in `tests/test_cognitive_tutor_engine.py` covers 5 core test cases:

### `test_01_socratic_question_generation`
- **Objective**: Verifies dynamic creation of active recall questions across different knowledge node types (`ThesisNode`, `ProtocolNode`, `ZettelNote`).
- **Target Functions**:
  - `vazus_core.cognitive_tutor_engine.generate_active_recall_question(entity_dict)`
  - `vazus_core.cognitive_tutor_engine.generate_all_questions_for_entity(entity_dict)`
  - `vazus_core.cognitive_tutor_engine.parse_zettel_markdown(file_path)`
- **Test Logic & Sub-cases**:
  1. **ThesisNode (Cloze / Fill-in-the-blank)**:
     - Input: `{"id": "t1", "node_type": "ThesisNode", "name": "IA Diagnostics", "statement": "Analysis of Competing Hypotheses evaluates inconsistency scores across evidence."}`
     - Expectations: `question_type` in `("FILL_IN_BLANK", "CONCEPT_EXPLANATION")`, `question_text` contains `[______]`, `target_answer` matches selected key term.
  2. **ProtocolNode (Multi-archetype generation)**:
     - Input: `{"id": "p1", "node_type": "ProtocolNode", "name": "SuperGraph Re-indexing Protocol", "prerequisites": ["Database connection online"], "steps": ["Extract AST", "Generate 768D Embeddings", "Persist SQLite"], "safety_warnings": ["Do not interrupt schema migration"]}`
     - Expectations: `generate_all_questions_for_entity` returns 3 questions covering `PREREQUISITE_CHECK`, `SEQUENCE_ORDERING`, and `SAFETY_WARNING`.
  3. **ZettelNote (Obsidian Wikilink Synthesis)**:
     - Input: Markdown file with `[[Link]]` wikilinks parsed via `parse_zettel_markdown(tmp_path)`.
     - Expectations: `question_type == "WIKILINK_SYNTHESIS"`, target answer includes wikilink reference.

---

### `test_02_answer_evaluation_scoring`
- **Objective**: Verifies continuous accuracy score $S \in [0, 100]\%$ computation, quality rating mapping $Q \in [0..5]$, and feedback rationale generation.
- **Target Functions / Classes**:
  - `vazus_core.cognitive_tutor_engine.map_score_to_q(score_percent)`
  - `vazus_core.cognitive_tutor_engine.ResponseEvaluator`
  - `vazus_core.cognitive_tutor_engine.evaluate_answer(question_dict, user_answer)`
- **Quality Score Mapping Table**:
  | Score Range $S$ | SM-2 Quality $Q$ | Evaluation Category |
  | :--- | :--- | :--- |
  | $S \ge 90.0\%$ | $Q = 5$ | Perfect Recall |
  | $80.0\% \le S < 90.0\%$ | $Q = 4$ | Good Recall |
  | $65.0\% \le S < 80.0\%$ | $Q = 3$ | Passable Recall |
  | $50.0\% \le S < 65.0\%$ | $Q = 2$ | Incomplete Recall |
  | $30.0\% \le S < 50.0\%$ | $Q = 1$ | Poor Recall |
  | $S < 30.0\%$ | $Q = 0$ | Blackout |
- **Test Logic & Sub-cases**:
  1. **Verbatim Ground Truth Match**:
     - User answer equals target answer $\implies S \ge 90.0\%$, $Q = 5$, rationale indicates outstanding recall.
  2. **Blank / Empty Input**:
     - User answer is `""` or whitespace $\implies S = 0.0\%$, $Q = 0$, `missing_concepts` populated.
  3. **Partial Keyword Match**:
     - User provides partial answer missing key terms $\implies 50.0\% \le S < 80.0\%$, $Q \in \{2, 3\}$.
  4. **Irrelevant Input**:
     - Random/unrelated text $\implies S < 50.0\%$, $Q \le 2$.

---

### `test_03_sm2_interval_scheduling`
- **Objective**: Verifies SuperMemo SM-2 interval mathematical progression ($1, 3, 7, 21$ days), Ease Factor updates, lower bound clamping ($EF \ge 1.3$), and lapse resets.
- **Target Function**:
  - `vazus_core.cognitive_tutor_engine.calculate_sm2_update(repetitions, ease_factor, interval_days, quality_rating)`
- **Mathematical Formulae**:
  - Ease Factor update:
    $$\Delta EF = 0.1 - (5 - Q) \times (0.08 + (5 - Q) \times 0.02)$$
    $$EF' = \max(1.3, EF + \Delta EF)$$
  - Repetition & Interval update ($Q \ge 3$ Pass):
    $$n' = n + 1$$
    $$I(1) = 1.0 \text{ day}, \quad I(2) = 3.0 \text{ days}, \quad I(3) = 7.0 \text{ days}, \quad I(4) = 21.0 \text{ days}$$
    $$I(n' > 4) = \text{round}(I_{prev} \times EF')$$
  - Lapse Reset ($Q < 3$ Fail):
    $$n' = 0, \quad I' = 1.0 \text{ day}$$
- **Test Logic & Sub-cases**:
  1. **Standard Progression ($Q=4..5$)**:
     - Iteration 1: $(n=0, EF=2.5, I=0.0, Q=5) \implies (n'=1, EF'=2.6, I'=1.0)$
     - Iteration 2: $(n=1, EF=2.6, I=1.0, Q=4) \implies (n'=2, EF'=2.6, I'=3.0)$
     - Iteration 3: $(n=2, EF=2.6, I=3.0, Q=4) \implies (n'=3, EF'=2.6, I'=7.0)$
     - Iteration 4: $(n=3, EF=2.6, I=7.0, Q=4) \implies (n'=4, EF'=2.6, I'=21.0)$
     - Iteration 5: $(n=4, EF=2.6, I=21.0, Q=4) \implies (n'=5, EF'=2.6, I'=55.0)$
  2. **Lapse Reset ($Q=1$)**:
     - $(n=4, EF=2.6, I=21.0, Q=1) \implies (n'=0, I'=1.0)$
  3. **Ease Factor Lower Bound**:
     - 5 consecutive $Q=0$ steps starting at $EF=1.4 \implies EF' = 1.3$ (clamped).

---

### `test_04_tutor_db_persistence`
- **Objective**: Verifies SQLite database table creation, flashcard CRUD operations, review log persistence, due card queries, legacy view aliases (`kg_flashcards`, `kg_review_logs`), and mastery statistics calculation.
- **Target Class**:
  - `vazus_core.cognitive_tutor_engine.CognitiveTutorEngine(db_path=...)`
- **Test Logic & Sub-cases**:
  1. **Isolated Test DB Initialization**:
     - Instantiate `CognitiveTutorEngine` with `tempfile.NamedTemporaryFile`.
     - Verify `tutor_cards` and `tutor_reviews` tables exist in SQLite schema via `sqlite_master`.
     - Verify alias views `kg_flashcards` and `kg_review_logs` exist.
  2. **Card Creation & Retrieval**:
     - Call `create_cards_from_entity(thesis_dict)`.
     - Call `get_card(card_id)` and `get_due_cards()` to verify card state in DB.
     - Query view `kg_flashcards` to ensure alias view returns saved cards.
  3. **Review Processing Persistence**:
     - Call `process_review(card_id, answer, response_time_sec=2.5)`.
     - Check updated `repetition_n`, `ease_factor`, `interval_days`, `last_review_at`, `next_review_at` in `tutor_cards`.
     - Query `tutor_reviews` and `kg_review_logs` to confirm review record persistence.
  4. **Mastery Statistics Calculation**:
     - Call `get_mastery_stats()` and verify return fields: `total_cards`, `due_cards`, `total_reviews`, `average_score_percent`, `average_q_rating`, `mastery_level`.

---

### `test_05_personal_tutor_cli_test_mode`
- **Objective**: Verifies that invoking `python scripts/personal_tutor.py --test` executes non-interactively and exits cleanly with Exit Code 0.
- **Execution Strategy**:
  - Use `subprocess.run([sys.executable, "scripts/personal_tutor.py", "--test"], capture_output=True, text=True, timeout=60)`.
- **Assertions**:
  - `result.returncode == 0`.
  - `"[SELF-TEST PASSED] All Cognitive Tutor Engine checks OK."` present in stdout.

---

## 3. Complete Reference Code for `tests/test_cognitive_tutor_engine.py`

Below is the complete, production-grade test file specification to be added to `tests/test_cognitive_tutor_engine.py`:

```python
"""
tests/test_cognitive_tutor_engine.py
Unit Test Suite for Spaced Repetition Active Learning Tutor & SM-2 Engine in vazus SuperGraph OS.

Milestone 4 (R4) Test Suite.
Covering:
1. test_01_socratic_question_generation
2. test_02_answer_evaluation_scoring
3. test_03_sm2_interval_scheduling
4. test_04_tutor_db_persistence
5. test_05_personal_tutor_cli_test_mode
"""

import os
import sys
import tempfile
import sqlite3
import subprocess
from pathlib import Path
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.cognitive_tutor_engine import (
    CognitiveTutorEngine,
    ResponseEvaluator,
    calculate_sm2_update,
    generate_active_recall_question,
    generate_all_questions_for_entity,
    evaluate_answer,
    map_score_to_q,
    parse_zettel_markdown,
    extract_keywords
)


def test_01_socratic_question_generation(tmp_path):
    """Verifies Socratic active recall question creation for ThesisNode, ProtocolNode, and ZettelNote."""
    # 1. ThesisNode Generation
    thesis_dict = {
        "id": "thesis_001",
        "node_type": "ThesisNode",
        "name": "IA Diagnostics",
        "statement": "Analysis of Competing Hypotheses evaluates inconsistency scores across evidence."
    }
    q_thesis = generate_active_recall_question(thesis_dict)
    assert q_thesis["entity_id"] == "thesis_001"
    assert q_thesis["entity_type"] == "ThesisNode"
    assert q_thesis["question_type"] in ("FILL_IN_BLANK", "CONCEPT_EXPLANATION")
    assert "question_text" in q_thesis and len(q_thesis["question_text"]) > 0
    assert "target_answer" in q_thesis and len(q_thesis["target_answer"]) > 0

    if q_thesis["question_type"] == "FILL_IN_BLANK":
        assert "[______]" in q_thesis["question_text"]

    # 2. ProtocolNode Generation (Multi-question creation)
    protocol_dict = {
        "id": "protocol_001",
        "node_type": "ProtocolNode",
        "name": "SuperGraph Re-indexing Protocol",
        "prerequisites": ["Database connection online", "Vector index initialized"],
        "steps": ["Step 1: Extract AST", "Step 2: Generate 768D Embeddings", "Step 3: Persist SQLite"],
        "safety_warnings": ["Do not interrupt schema migration"]
    }
    protocol_qs = generate_all_questions_for_entity(protocol_dict)
    assert len(protocol_qs) >= 3, "Expected questions for prerequisites, sequence ordering, and safety warnings"
    q_types = [q["question_type"] for q in protocol_qs]
    assert "PREREQUISITE_CHECK" in q_types
    assert "SEQUENCE_ORDERING" in q_types
    assert "SAFETY_WARNING" in q_types

    # 3. Zettel Note Generation via Markdown Parsing
    zettel_md = tmp_path / "Zettel_Test_001.md"
    zettel_md.write_text(
        "---\nid: zettel_001\ntitle: SuperGraph AST Linking\n---\n"
        "# SuperGraph AST Linking\n\n"
        "## Core Claim\nAST call graph nodes link directly to 768D embeddings.\n\n"
        "Relates to [[Vector Memory]] and [[Obsidian Wiki]].\n",
        encoding="utf-8"
    )

    z_entity = parse_zettel_markdown(zettel_md)
    assert z_entity["id"] == "zettel_001"
    assert z_entity["node_type"] == "ZettelNote"
    assert "Vector Memory" in z_entity["wikilinks"]

    q_zettel = generate_active_recall_question(z_entity)
    assert q_zettel["question_type"] == "WIKILINK_SYNTHESIS"
    assert "Vector Memory" in q_zettel["question_text"]


def test_02_answer_evaluation_scoring():
    """Verifies 0-100% answer scoring, Q mapping (0-5), and metric evaluation."""
    q_dict = {
        "question_text": "What is SuperMemo SM-2?",
        "target_answer": "SuperMemo SM-2 adjusts card intervals exponentially based on Ease Factor and quality rating Q."
    }

    # Pass embedder=None to test offline evaluator deterministically
    evaluator = ResponseEvaluator(embedder=None)

    # 1. Perfect Match (>= 90%, Q=5)
    perfect_eval = evaluator.evaluate_response(q_dict["target_answer"], q_dict["target_answer"])
    assert perfect_eval["score_percent"] >= 90.0
    assert perfect_eval["q_rating"] == 5
    assert map_score_to_q(perfect_eval["score_percent"]) == 5

    # 2. Blank Answer (0%, Q=0)
    blank_eval = evaluator.evaluate_response("", q_dict["target_answer"])
    assert blank_eval["score_percent"] == 0.0
    assert blank_eval["q_rating"] == 0
    assert len(blank_eval["missing_concepts"]) > 0

    # 3. Partial Keyword Answer (Partial score, Q=2 or 3)
    partial_eval = evaluator.evaluate_response("SuperMemo adjusts intervals exponentially", q_dict["target_answer"])
    assert 40.0 <= partial_eval["score_percent"] < 90.0
    assert partial_eval["q_rating"] in (2, 3, 4)

    # 4. Completely Irrelevant Answer (< 50%, Q<=2)
    bad_eval = evaluator.evaluate_response("Quantum entanglement in optical physics", q_dict["target_answer"])
    assert bad_eval["score_percent"] < 50.0
    assert bad_eval["q_rating"] <= 2


def test_03_sm2_interval_scheduling():
    """Verifies SuperMemo SM-2 interval progression (1, 3, 7, 21 days), EF lower bound, and lapse handling."""
    # Step 1: Initial state n=0, EF=2.5, I=0.0, Q=5
    n, ef, i = calculate_sm2_update(0, 2.5, 0.0, 5)
    assert n == 1
    assert ef == 2.6
    assert i == 1.0

    # Step 2: Second review n=1, EF=2.6, I=1.0, Q=4
    n, ef, i = calculate_sm2_update(1, 2.6, 1.0, 4)
    assert n == 2
    assert ef == 2.6
    assert i == 3.0

    # Step 3: Third review n=2, EF=2.6, I=3.0, Q=4
    n, ef, i = calculate_sm2_update(2, 2.6, 3.0, 4)
    assert n == 3
    assert ef == 2.6
    assert i == 7.0

    # Step 4: Fourth review n=3, EF=2.6, I=7.0, Q=4
    n, ef, i = calculate_sm2_update(3, 2.6, 7.0, 4)
    assert n == 4
    assert ef == 2.6
    assert i == 21.0

    # Step 5: Fifth review n=4, EF=2.6, I=21.0, Q=4 -> I = round(21 * 2.6) = 55.0
    n, ef, i = calculate_sm2_update(4, 2.6, 21.0, 4)
    assert n == 5
    assert ef == 2.6
    assert i == 55.0

    # Step 6: Lapse Q=1 -> resets n=0 and interval=1.0
    n_lapse, ef_lapse, i_lapse = calculate_sm2_update(4, 2.6, 21.0, 1)
    assert n_lapse == 0
    assert i_lapse == 1.0

    # Step 7: Ease Factor lower bound EF >= 1.3
    cur_ef = 1.4
    for _ in range(5):
        _, cur_ef, _ = calculate_sm2_update(0, cur_ef, 1.0, 0)
    assert cur_ef == 1.3


def test_04_tutor_db_persistence():
    """Verifies SQLite persistence to tutor_cards, tutor_reviews, and views kg_flashcards, kg_review_logs."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = tmp_db.name

    try:
        engine = CognitiveTutorEngine(db_path=db_path)

        # Verify tables and alias views exist in SQLite
        with sqlite3.connect(db_path) as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')").fetchall()]
            assert "tutor_cards" in tables
            assert "tutor_reviews" in tables
            assert "kg_flashcards" in tables
            assert "kg_review_logs" in tables

        # Insert cards from entity
        thesis = {
            "id": "thesis_db_test",
            "node_type": "ThesisNode",
            "name": "SQLite Persistence",
            "statement": "SQLite persistence provides reliable flashcard state."
        }
        card_ids = engine.create_cards_from_entity(thesis)
        assert len(card_ids) > 0
        cid = card_ids[0]

        # Verify card retrieval
        card = engine.get_card(cid)
        assert card is not None
        assert card["id"] == cid
        assert card["repetition_n"] == 0

        # Verify due cards
        due = engine.get_due_cards()
        assert len(due) >= 1

        # Process review
        review_res = engine.process_review(cid, "SQLite persistence provides reliable flashcard state.", response_time_sec=1.8)
        assert review_res["q_rating"] == 5
        assert review_res["sm2_update"]["repetition_n"] == 1
        assert review_res["sm2_update"]["interval_days"] == 1.0

        # Verify updated card state in DB
        updated_card = engine.get_card(cid)
        assert updated_card["repetition_n"] == 1
        assert updated_card["interval_days"] == 1.0

        # Verify review log persistence via alias view kg_review_logs
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            log = conn.execute("SELECT * FROM kg_review_logs WHERE card_id = ?", (cid,)).fetchone()
            assert log is not None
            assert log["q_rating"] == 5
            assert log["response_time_sec"] == 1.8

        # Verify mastery stats calculation
        stats = engine.get_mastery_stats()
        assert stats["total_cards"] >= 1
        assert stats["total_reviews"] == 1
        assert stats["average_q_rating"] == 5.0

    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass


def test_05_personal_tutor_cli_test_mode():
    """Verifies python scripts/personal_tutor.py --test runs cleanly with exit code 0."""
    script_path = PROJECT_ROOT / "scripts" / "personal_tutor.py"
    assert script_path.exists(), f"CLI runner script not found at {script_path}"

    cmd = [sys.executable, str(script_path), "--test"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60)

    assert res.returncode == 0, f"CLI runner exited with non-zero code {res.returncode}. Stderr:\n{res.stderr}"
    assert "[SELF-TEST PASSED] All Cognitive Tutor Engine checks OK." in res.stdout
```

---

## 4. Verification & Implementation Roadmap

1. **Test Suite Location**: Place test specification code in `C:\vazus\tests\test_cognitive_tutor_engine.py`.
2. **Execution Command**:
   ```bash
   C:\vazus\.venv\Scripts\pytest.exe tests/test_cognitive_tutor_engine.py -v
   ```
3. **CLI Runner Command**:
   ```bash
   C:\vazus\.venv\Scripts\python.exe scripts/personal_tutor.py --test
   ```
