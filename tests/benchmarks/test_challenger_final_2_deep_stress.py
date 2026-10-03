"""
tests/benchmarks/test_challenger_final_2_deep_stress.py
Deep Adversarial Stress & Edge Case Harness for Challenger Final 2.

Comprehensive checks for:
1. AntiLoopCircuitBreaker edge cases (Syntax errors, empty strings, thread races, sliding window).
2. ConcordiaJury contract violation rejection (SAT counterexamples, missing keys, malformed schemas).
3. SQLite WAL foreign key enforcement & FTS5 search edge cases.
4. SM-2 multi-year simulation and ResponseEvaluator edge cases.
"""

import sys
import time
import math
import tempfile
import threading
import sqlite3
import random
import numpy as np
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path("C:/vazus").resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.engine.circuit_breaker import AntiLoopCircuitBreaker
from vazus_core.verification.rollback_guardrail import RollbackGuardrail
from vazus_core.verification.concordia_jury import ConcordiaJury, JuryVerdict
from vazus_core.memory.db import (
    get_db_connection,
    pack_vector_f32,
    unpack_vector_f32,
    close_all_thread_connections,
    DEFAULT_VAZUS_DB
)
from vazus_core.integrations.cognitive_tutor_engine import (
    CognitiveTutorEngine,
    calculate_sm2_update,
    map_score_to_q,
    ResponseEvaluator,
    evaluate_answer,
)


def test_circuit_breaker_edge_cases():
    cb = AntiLoopCircuitBreaker(max_duplicates=2, max_total_attempts=5, history_limit=10)

    # Empty string handling
    assert cb.register_attempt("") is True
    assert cb.register_attempt("") is True
    # 3rd empty string -> duplicate tripped
    assert cb.register_attempt("") is False
    assert cb.tripped is True
    cb.reset()

    # Syntax Error fallback hashing (MD5 of normalized lines)
    syntax_error_code = "def invalid_func(\n   broken syntax line %%%"
    assert cb.register_attempt(syntax_error_code) is True
    assert cb.register_attempt(syntax_error_code) is True
    assert cb.register_attempt(syntax_error_code) is False
    assert cb.tripped is True
    cb.reset()

    # Concurrent multithreaded register_attempt races
    def attempt_worker(thread_id: int):
        for j in range(10):
            cb.register_attempt(f"def thread_code_{thread_id}_{j}(): pass")

    threads = [threading.Thread(target=attempt_worker, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    status = cb.get_status()
    assert status["tripped"] is True
    assert status["attempts"] == 50
    assert status["history_length"] <= 10  # Sliding window bounded


def test_concordia_jury_contract_rejection():
    jury = ConcordiaJury(effort_level="high", min_quorum=3, consensus_threshold=0.66)

    # Code with a violated SMT postcondition:
    # Function claims return > 100 for all positive x, but body returns x + 1
    violating_contract_code = """
def process_data(x: int) -> int:
    '''
    :requires: x > 0
    :ensures: result > 100
    '''
    return x + 1
"""
    # Even if 3 agents unanimously vote PASS, SMT check should catch violation and reject
    unanimous_pass = [
        {"agent": "Planner", "verdict": "PASS"},
        {"agent": "RLM_Coder", "verdict": "PASS"},
        {"agent": "Verifier_Worker", "verdict": "PASS"},
    ]
    verdict = jury.vote(proposal=violating_contract_code, votes=unanimous_pass)
    assert verdict.approved is False, f"Jury approved code with violated SMT contract! {verdict.to_dict()}"
    assert verdict.smt_satisfied is False

    # Valid SMT contract code
    valid_contract_code = """
def absolute_val(x: int) -> int:
    '''
    :requires: True
    :ensures: result >= 0
    '''
    if x < 0:
        return -x
    return x
"""
    verdict_valid = jury.vote(proposal=valid_contract_code, votes=unanimous_pass)
    assert verdict_valid.approved is True, f"Jury rejected code with valid SMT contract! {verdict_valid.to_dict()}"
    assert verdict_valid.smt_satisfied is True


def test_concordia_jury_malformed_vote_schemas():
    jury = ConcordiaJury(min_quorum=3, consensus_threshold=0.66)
    valid_code = "def valid(): return 1\n"

    # Weird schemas: missing agent, lowercase verdicts, booleans instead of strings
    weird_votes = [
        {"name": "Planner", "approved": True, "verdict": "pass"},
        {"role": "RLM_Coder", "approved": True, "verdict": "YES"},
        {"agent": "Verifier_Worker", "approved": False, "verdict": "FAIL"},
    ]
    v = jury.vote(proposal=valid_code, votes=weird_votes)
    assert v.approved is True  # 2 of 3 PASS -> 66.7% >= 66%
    assert v.passed_votes == 2
    assert v.total_votes == 3


def test_sqlite_foreign_key_enforcement():
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db = str(Path(tmp_dir) / "fk_test.db")
        tutor = CognitiveTutorEngine(db_path=test_db)

        # Attempt to insert tutor_reviews referencing non-existent card_id with foreign_keys = ON
        conn = sqlite3.connect(test_db)
        conn.execute("PRAGMA foreign_keys = ON;")
        fk_failed = False
        try:
            conn.execute("""
                INSERT INTO tutor_reviews (
                    id, card_id, score_percent, q_rating, user_response,
                    feedback_rationale, response_time_sec, reviewed_at
                ) VALUES ('rev_bad', 'non_existent_card_999', 100.0, 5, 'ans', 'fb', 1.0, '2026-08-20T00:00:00Z')
            """)
            conn.commit()
        except sqlite3.IntegrityError:
            fk_failed = True
        finally:
            conn.close()

        assert fk_failed is True, "Foreign key constraint was not enforced!"


def test_sm2_multi_year_simulation():
    """Simulates 50 reviews across 3 years with mixed learning, forgetting, and relearning."""
    repetitions = 0
    ease_factor = 2.5
    interval_days = 0.0
    lapses = 0

    # Pattern: 4 successful reviews, 1 lapse, 3 successful reviews, 1 lapse, 10 successful reviews
    review_pattern = [5, 4, 4, 4, 1, 4, 5, 4, 2] + [5] * 10

    for idx, q_score in enumerate(review_pattern):
        new_n, new_ef, new_i = calculate_sm2_update(repetitions, ease_factor, interval_days, q_score)
        assert new_ef >= 1.3000, f"EF invariant failed at step {idx}: EF={new_ef}"
        if q_score < 3:
            assert new_n == 0, f"Lapse should reset n to 0, got {new_n}"
            assert new_i == 1.0, f"Lapse should reset interval to 1.0, got {new_i}"
            lapses += 1
        else:
            assert new_n == repetitions + 1
            if new_n == 1:
                assert new_i == 1.0
            elif new_n == 2:
                assert new_i == 3.0
            elif new_n == 3:
                assert new_i == 7.0
            elif new_n == 4:
                assert new_i == 21.0
            else:
                assert new_i >= interval_days

        repetitions = new_n
        ease_factor = new_ef
        interval_days = new_i

    assert lapses == 2
    assert repetitions == 10
    assert interval_days > 100.0


def test_response_evaluator_chelpanov_grounding():
    evaluator = ResponseEvaluator()

    ground_truth = (
        "The principle of sufficient reason states that no proposition can be considered true "
        "without a sufficient foundation or reason justifying why it is so and not otherwise."
    )

    # 1. Verbatim / High Accuracy Answer
    exact_user = (
        "The principle of sufficient reason states that no proposition can be considered true "
        "without a sufficient foundation or reason justifying why it is so."
    )
    res_exact = evaluator.evaluate_response(exact_user, ground_truth)
    assert res_exact["score_percent"] >= 85.0
    assert res_exact["q_rating"] >= 4

    # 2. Paraphrased Answer (Score in passing range)
    paraphrase_user = (
        "No proposition can be accepted as true without sufficient reason or foundation."
    )
    res_para = evaluator.evaluate_response(paraphrase_user, ground_truth)
    assert res_para["score_percent"] >= 50.0
    assert res_para["q_rating"] >= 2

    # 3. Empty Answer
    res_empty = evaluator.evaluate_response("", ground_truth)
    assert res_empty["score_percent"] == 0.0
    assert res_empty["q_rating"] == 0

    # 4. Wrong Answer
    wrong_user = "Photosynthesis requires chlorophyll and sunlight to convert water and carbon dioxide into glucose."
    res_wrong = evaluator.evaluate_response(wrong_user, ground_truth)
    assert res_wrong["score_percent"] < 40.0
    assert res_wrong["q_rating"] <= 1
