"""
run_empirical_stress_tests.py
Adversarial empirical stress-test harness for Milestone 4 (Cognitive Tutor & SuperMemo SM-2 Engine).
Runs extensive property-based and boundary condition checks on SM-2 formula, score mapping, question generation, and persistence.
"""

import os
import sys
import tempfile
import sqlite3
import math
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.cognitive_tutor_engine import (
    CognitiveTutorEngine,
    calculate_sm2_update,
    map_score_to_q,
    generate_active_recall_question,
    generate_all_questions_for_entity,
    evaluate_answer,
    extract_keywords,
    parse_zettel_markdown,
    ResponseEvaluator
)

def test_sm2_boundary_and_stress():
    print("=== [STRESS TEST 1] SuperMemo SM-2 Math & Boundary Conditions ===")
    failures = []

    # 1.1 Milestone Interval Sequence Verification (Q=4, EF=2.5 default)
    # Expected milestones: n=1 -> 1.0, n=2 -> 3.0, n=3 -> 7.0, n=4 -> 21.0
    n, ef, i = 0, 2.5, 0.0
    milestones = []
    for step in range(1, 6):
        n, ef, i = calculate_sm2_update(n, ef, i, 4)
        milestones.append((n, ef, i))
    
    expected_milestones = [(1, 2.5, 1.0), (2, 2.5, 3.0), (3, 2.5, 7.0), (4, 2.5, 21.0), (5, 2.5, 53.0)] # 21 * 2.5 = 52.5 -> round(52.5) = 52 or 53 (in Python round(52.5) is 52 or round(21.0*2.5)=52/53)
    print(f"  Milestones sequence (Q=4, initial EF=2.5): {milestones}")
    if milestones[0] != (1, 2.5, 1.0) or milestones[1] != (2, 2.5, 3.0) or milestones[2] != (3, 2.5, 7.0) or milestones[3] != (4, 2.5, 21.0):
        failures.append(f"Milestones mismatch: expected 1, 3, 7, 21 days for steps 1..4, got {milestones[:4]}")

    # 1.2 Interval Reset on Failure (Q < 3) for all Q in {0, 1, 2} across various initial (n, I)
    for q_fail in [0, 1, 2]:
        for init_n in [1, 2, 4, 10, 100]:
            for init_i in [1.0, 3.0, 7.0, 21.0, 365.0]:
                n_out, ef_out, i_out = calculate_sm2_update(init_n, 2.5, init_i, q_fail)
                if n_out != 0:
                    failures.append(f"Reset failed for Q={q_fail}, n={init_n}: expected n=0, got n={n_out}")
                if i_out != 1.0:
                    failures.append(f"Reset failed for Q={q_fail}, I={init_i}: expected I=1.0, got I={i_out}")

    # 1.3 EF Lower Bound Enforcement (EF >= 1.3)
    # Repeated Q=0 failures from initial EF=2.5 and EF=1.4
    cur_ef = 2.5
    for round_idx in range(50):
        _, cur_ef, _ = calculate_sm2_update(0, cur_ef, 1.0, 0)
        if cur_ef < 1.3:
            failures.append(f"EF lower bound breached at round {round_idx}: ef={cur_ef} < 1.3")
    if cur_ef != 1.3:
        failures.append(f"EF did not clamp cleanly at 1.3 after 50 failures: got {cur_ef}")

    # 1.4 EF Delta calculation verification
    # Formula: delta_ef = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    # q=5: +0.10, q=4: 0.00, q=3: -0.14, q=2: -0.32, q=1: -0.54, q=0: -0.80
    expected_deltas = {
        5: 0.10,
        4: 0.00,
        3: -0.14,
        2: -0.32,
        1: -0.54,
        0: -0.80
    }
    for q_val, expected_delta in expected_deltas.items():
        _, new_ef, _ = calculate_sm2_update(0, 2.5, 1.0, q_val)
        actual_delta = round(new_ef - 2.5, 4)
        if actual_delta != expected_delta:
            failures.append(f"EF delta for Q={q_val}: expected {expected_delta}, got {actual_delta}")

    # 1.5 Clamping of out-of-bound arguments
    # q_rating = -10 -> clamped to 0
    _, ef_neg_q, _ = calculate_sm2_update(0, 2.5, 1.0, -10)
    _, ef_zero_q, _ = calculate_sm2_update(0, 2.5, 1.0, 0)
    if ef_neg_q != ef_zero_q:
        failures.append(f"Negative quality_rating not clamped to 0: q=-10 gave ef={ef_neg_q}")

    # q_rating = 10 -> clamped to 5
    _, ef_high_q, _ = calculate_sm2_update(0, 2.5, 1.0, 10)
    _, ef_five_q, _ = calculate_sm2_update(0, 2.5, 1.0, 5)
    if ef_high_q != ef_five_q:
        failures.append(f"High quality_rating not clamped to 5: q=10 gave ef={ef_high_q}")

    # ease_factor = 0.5 (< 1.3) -> clamped to 1.3 before update
    _, ef_low_init, _ = calculate_sm2_update(0, 0.5, 1.0, 4)
    # ef starts at max(1.3, 0.5) = 1.3, delta for q=4 is 0 -> ef_low_init should be 1.3
    if ef_low_init != 1.3:
        failures.append(f"Initial ease_factor < 1.3 not clamped to 1.3: got {ef_low_init}")

    print(f"  -> SM-2 Math Stress Test Complete. Failures count: {len(failures)}")
    for f in failures:
        print(f"     [FAIL] {f}")
    return failures


def test_score_mapping_stress():
    print("=== [STRESS TEST 2] Score Mapping (map_score_to_q) ===")
    failures = []

    test_cases = [
        (100.0, 5), (90.0, 5), (89.999, 4), (80.0, 4), (79.999, 3),
        (65.0, 3), (64.999, 2), (50.0, 2), (49.999, 1), (30.0, 1),
        (29.999, 0), (0.0, 0), (-100.0, 0), (150.0, 5)
    ]

    for score, expected_q in test_cases:
        q = map_score_to_q(score)
        if q != expected_q:
            failures.append(f"map_score_to_q({score}): expected Q={expected_q}, got Q={q}")

    print(f"  -> Score Mapping Stress Test Complete. Failures count: {len(failures)}")
    for f in failures:
        print(f"     [FAIL] {f}")
    return failures


def test_question_generation_stress():
    print("=== [STRESS TEST 3] Question Generation Boundary Cases ===")
    failures = []

    # 3.1 ThesisNode with long vs short statement
    short_thesis = {"node_type": "ThesisNode", "statement": "Short text"}
    q_short = generate_active_recall_question(short_thesis)
    if q_short["question_type"] != "CONCEPT_EXPLANATION":
        failures.append(f"Short statement should fallback to CONCEPT_EXPLANATION, got {q_short['question_type']}")

    long_thesis = {"node_type": "ThesisNode", "statement": "Analysis of Competing Hypotheses evaluates structured evidence matrices systematically."}
    q_long = generate_active_recall_question(long_thesis)
    if q_long["question_type"] not in ("FILL_IN_BLANK", "CONCEPT_EXPLANATION"):
        failures.append(f"Unexpected question_type for long thesis: {q_long['question_type']}")

    # 3.2 ProtocolNode with missing steps or prereqs
    prereq_proto = {"node_type": "ProtocolNode", "name": "P1", "prerequisites": ["A", "B"]}
    q_p1 = generate_active_recall_question(prereq_proto)
    if q_p1["question_type"] != "PREREQUISITE_CHECK":
        failures.append(f"Protocol with prereqs expected PREREQUISITE_CHECK, got {q_p1['question_type']}")

    steps_proto = {"node_type": "ProtocolNode", "name": "P2", "steps": ["Step 1", "Step 2"]}
    q_p2 = generate_active_recall_question(steps_proto)
    if q_p2["question_type"] != "SEQUENCE_ORDERING":
        failures.append(f"Protocol with steps expected SEQUENCE_ORDERING, got {q_p2['question_type']}")

    warn_proto = {"node_type": "ProtocolNode", "name": "P3", "warnings": ["Warn 1"]}
    q_p3 = generate_active_recall_question(warn_proto)
    if q_p3["question_type"] != "SAFETY_WARNING":
        failures.append(f"Protocol with warnings expected SAFETY_WARNING, got {q_p3['question_type']}")

    # 3.3 ZettelNote with Wikilinks
    zettel = {"node_type": "ZettelNote", "title": "Z1", "wikilinks": ["ConceptA"]}
    q_z = generate_active_recall_question(zettel)
    if q_z["question_type"] != "WIKILINK_SYNTHESIS":
        failures.append(f"Zettel with wikilinks expected WIKILINK_SYNTHESIS, got {q_z['question_type']}")

    # 3.4 Empty entity dict handling
    empty_q = generate_active_recall_question({})
    if not empty_q.get("question_text") or not empty_q.get("card_id"):
        failures.append("Empty entity dict produced invalid card structure")

    print(f"  -> Question Generation Stress Test Complete. Failures count: {len(failures)}")
    for f in failures:
        print(f"     [FAIL] {f}")
    return failures


def test_evaluator_stress():
    print("=== [STRESS TEST 4] Response Evaluator Hybrid Scoring ===")
    failures = []

    evaluator = ResponseEvaluator()

    # 4.1 Empty answer score
    res_empty = evaluator.evaluate_response("", "target ground truth answer")
    if res_empty["score_percent"] != 0.0 or res_empty["q_rating"] != 0:
        failures.append(f"Empty answer score mismatch: got score={res_empty['score_percent']}, q={res_empty['q_rating']}")

    # 4.2 Verbatim answer
    target = "SuperMemo SM-2 algorithm optimizes review intervals efficiently."
    res_verbatim = evaluator.evaluate_response(target, target)
    if res_verbatim["score_percent"] < 90.0 or res_verbatim["q_rating"] != 5:
        failures.append(f"Verbatim answer score mismatch: got score={res_verbatim['score_percent']}, q={res_verbatim['q_rating']}")

    # 4.3 Russian text Cyrillic support
    ru_target = "Алгоритм SuperMemo вычисляет интервал повторения."
    res_ru = evaluator.evaluate_response(ru_target, ru_target)
    if res_ru["score_percent"] < 90.0 or res_ru["q_rating"] != 5:
        failures.append(f"Russian verbatim answer score mismatch: got score={res_ru['score_percent']}, q={res_ru['q_rating']}")

    print(f"  -> Evaluator Stress Test Complete. Failures count: {len(failures)}")
    for f in failures:
        print(f"     [FAIL] {f}")
    return failures


def test_cli_mode_stress():
    print("=== [STRESS TEST 5] CLI Personal Tutor Mode Execution ===")
    failures = []

    cli_script = PROJECT_ROOT / "scripts" / "personal_tutor.py"

    # 5.1 Test --test flag
    proc_test = subprocess.run([sys.executable, str(cli_script), "--test"], capture_output=True, text=True)
    if proc_test.returncode != 0:
        failures.append(f"--test flag exit code != 0: got {proc_test.returncode}, stderr={proc_test.stderr}")

    # 5.2 Test --stats flag
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = tmp_db.name

    try:
        proc_stats = subprocess.run([sys.executable, str(cli_script), "--stats", "--db-path", tmp_db_path], capture_output=True, text=True)
        if proc_stats.returncode != 0 or "COGNITIVE TUTOR MASTERY STATISTICS" not in proc_stats.stdout:
            failures.append(f"--stats failed: returncode={proc_stats.returncode}, stdout={proc_stats.stdout}")
    finally:
        if os.path.exists(tmp_db_path):
            os.remove(tmp_db_path)

    print(f"  -> CLI Mode Stress Test Complete. Failures count: {len(failures)}")
    for f in failures:
        print(f"     [FAIL] {f}")
    return failures


def main():
    print("Starting Comprehensive Empirical Stress-Test Suite...")
    all_failures = []
    all_failures.extend(test_sm2_boundary_and_stress())
    all_failures.extend(test_score_mapping_stress())
    all_failures.extend(test_question_generation_stress())
    all_failures.extend(test_evaluator_stress())
    all_failures.extend(test_cli_mode_stress())

    print("\n==================================================")
    if not all_failures:
        print(" [VERDICT: PASSED] ALL EMPIRICAL STRESS TESTS PASSED CLEANLY!")
    else:
        print(f" [VERDICT: FAILED] FOUND {len(all_failures)} FAILURE MODES / ISSUES.")
    print("==================================================")

if __name__ == "__main__":
    main()
