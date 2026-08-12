#!/usr/bin/env python3
"""
scripts/personal_tutor.py
CLI Runner for Spaced Repetition Active Learning Tutor in vazus SuperGraph OS.

Usage:
  python scripts/personal_tutor.py --test      # Runs non-interactive self-test (Exit Code 0)
  python scripts/personal_tutor.py --review    # Interactive recall review session
  python scripts/personal_tutor.py --stats     # Displays card mastery & review statistics
"""

import os
import sys
import argparse
import tempfile
import sqlite3
import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output encoding for Windows terminal compatibility
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from vazus_core.cognitive_tutor_engine import (
    CognitiveTutorEngine,
    calculate_sm2_update,
    generate_active_recall_question,
    evaluate_answer,
    parse_zettel_markdown,
    DEFAULT_DB_PATH
)


def run_self_test() -> int:
    """Runs a non-interactive self-test verifying SM-2 math, question generation, answer evaluation, and persistence."""
    print("==================================================")
    print("   Cognitive Tutor Engine CLI Self-Test Runner   ")
    print("==================================================")

    # 1. Test SM-2 Math
    print("[1/4] Verifying SM-2 Algorithm Math & Bounds...")
    # Initial state Q=5
    n, ef, i = calculate_sm2_update(0, 2.5, 0.0, 5)
    assert n == 1 and ef == 2.6 and i == 1.0, f"Failed Q=5 step 1: got n={n}, ef={ef}, i={i}"

    # Step sequence Q=4 (EF unchanged)
    n, ef, i = calculate_sm2_update(1, 2.6, 1.0, 4)
    assert n == 2 and ef == 2.6 and i == 3.0, f"Failed Q=4 step 2: got n={n}, ef={ef}, i={i}"

    n, ef, i = calculate_sm2_update(2, 2.6, 3.0, 4)
    assert n == 3 and ef == 2.6 and i == 7.0, f"Failed Q=4 step 3: got n={n}, ef={ef}, i={i}"

    n, ef, i = calculate_sm2_update(3, 2.6, 7.0, 4)
    assert n == 4 and ef == 2.6 and i == 21.0, f"Failed Q=4 step 4: got n={n}, ef={ef}, i={i}"

    # Lapse Q=1
    n, ef, i = calculate_sm2_update(4, 2.6, 21.0, 1)
    assert n == 0 and i == 1.0, f"Failed lapse Q=1: got n={n}, i={i}"

    # EF Lower Bound EF >= 1.3
    cur_ef = 1.4
    for _ in range(5):
        _, cur_ef, _ = calculate_sm2_update(0, cur_ef, 1.0, 0)
    assert cur_ef == 1.3, f"Failed EF lower bound: got ef={cur_ef}"
    print("     -> SM-2 math verified successfully.")

    # 2. Test Question Generation
    print("[2/4] Verifying Socratic Active Recall Question Generation...")
    thesis_dict = {
        "id": "thesis_001",
        "node_type": "ThesisNode",
        "name": "IA Diagnostics",
        "statement": "Analysis of Competing Hypotheses evaluates inconsistency scores across evidence."
    }
    q1 = generate_active_recall_question(thesis_dict)
    assert "question_text" in q1 and "target_answer" in q1, "Question dict missing keys"
    assert q1["question_type"] in ("FILL_IN_BLANK", "CONCEPT_EXPLANATION")

    protocol_dict = {
        "id": "protocol_001",
        "node_type": "ProtocolNode",
        "name": "SuperGraph Re-indexing Protocol",
        "prerequisites": ["Database connection online", "Vector index initialized"],
        "steps": ["Step 1: Extract AST", "Step 2: Generate 768D Embeddings", "Step 3: Persist SQLite"],
        "safety_warnings": ["Do not interrupt schema migration"]
    }
    q2 = generate_active_recall_question(protocol_dict)
    assert q2["question_type"] in ("PREREQUISITE_CHECK", "SEQUENCE_ORDERING", "SAFETY_WARNING")
    print("     -> Question generation verified successfully.")

    # 3. Test Response Evaluator
    print("[3/4] Verifying 768D Hybrid Answer Evaluator...")
    perfect_eval = evaluate_answer(q1, q1["target_answer"])
    assert perfect_eval["score_percent"] >= 90.0 and perfect_eval["q_rating"] == 5, f"Perfect score failed: {perfect_eval}"

    bad_eval = evaluate_answer(q1, "completely irrelevant gibberish text")
    assert bad_eval["score_percent"] < 50.0 and bad_eval["q_rating"] <= 2, f"Bad score failed: {bad_eval}"
    print("     -> Answer evaluation verified successfully.")

    # 4. Test SQLite Persistence & Tutor Engine
    print("[4/4] Verifying SQLite Engine Persistence & Review Processing...")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = tmp_db.name

    try:
        engine = CognitiveTutorEngine(db_path=tmp_db_path)
        card_ids = engine.create_cards_from_entity(thesis_dict)
        assert len(card_ids) > 0, "No cards persisted"

        due_cards = engine.get_due_cards()
        assert len(due_cards) > 0, "No due cards retrieved"

        cid = card_ids[0]
        review_res = engine.process_review(cid, q1["target_answer"], response_time_sec=2.5)
        assert review_res["q_rating"] == 5, "Review processing failed"

        stats = engine.get_mastery_stats()
        assert stats["total_cards"] >= 1, "Stats card count invalid"
        assert stats["total_reviews"] == 1, "Stats review count invalid"
        print("     -> SQLite engine persistence verified successfully.")
    finally:
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except OSError:
                pass

    print("==================================================")
    print("[SELF-TEST PASSED] All Cognitive Tutor Engine checks OK.")
    print("==================================================")
    return 0


def run_interactive_review(db_path: str, wiki_dir: str):
    """Runs interactive spaced repetition review session."""
    engine = CognitiveTutorEngine(db_path=db_path, wiki_dir=wiki_dir)
    engine.sync_zettelkasten_notes()

    due_cards = engine.get_due_cards(limit=10)

    # If no due cards exist in DB, create default sample cards
    if not due_cards:
        print("[Tutor] No due cards found in database. Initializing sample Socratic cards...")
        sample_thesis = {
            "id": "thesis_sm2_supermemo",
            "node_type": "ThesisNode",
            "name": "SuperMemo SM-2 Algorithm",
            "statement": "SuperMemo SM-2 adjusts card intervals exponentially based on Ease Factor and performance rating Q."
        }
        sample_protocol = {
            "id": "protocol_active_recall",
            "node_type": "ProtocolNode",
            "name": "Active Recall Testing",
            "prerequisites": ["Clear focus", "Ground truth target answer"],
            "steps": ["Read Socratic prompt", "Formulate mental response", "Submit verbatim answer", "Review AI feedback"],
            "safety_warnings": ["Avoid passive reading without active recall"]
        }
        engine.create_cards_from_entity(sample_thesis)
        engine.create_cards_from_entity(sample_protocol)
        due_cards = engine.get_due_cards(limit=10)

    print("\n" + "=" * 55)
    print(f"   SPACED REPETITION ACTIVE RECALL SESSION ({len(due_cards)} cards due)   ")
    print("=" * 55)

    if not sys.stdin.isatty():
        print("[Note] Running in non-interactive environment. Simulating 1 card review...")
        card = due_cards[0]
        print(f"\n[Card ID: {card['id']}] [{card['question_type']}]")
        print(f"Q: {card['question_text']}")
        sim_ans = card['target_answer']
        print(f"Simulated Answer: '{sim_ans}'")
        res = engine.process_review(card['id'], sim_ans, response_time_sec=1.5)
        print(f"\nAccuracy Score: {res['score_percent']}% | Q Rating: {res['q_rating']}/5")
        print(f"Feedback: {res['feedback_rationale']}")
        print(f"Next Review In: {res['sm2_update']['interval_days']} days (EF: {res['sm2_update']['ease_factor']})")
        print("\nSession complete.")
        return

    for idx, card in enumerate(due_cards, 1):
        print(f"\n--- Card [{idx}/{len(due_cards)}] (ID: {card['id']}) ---")
        print(f"Archetype : {card['question_type']}")
        print(f"Question  : {card['question_text']}")
        print("-" * 55)

        start_time = datetime.datetime.now()
        try:
            user_input = input("Your Answer > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nReview session ended early.")
            break

        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        if not user_input:
            print("[Pass/Skip] Zero answer provided.")
            user_input = ""

        res = engine.process_review(card['id'], user_input, response_time_sec=elapsed)

        print(f"\nTarget Answer : {card['target_answer']}")
        print(f"Score         : {res['score_percent']}% (Quality Q: {res['q_rating']}/5)")
        print(f"Feedback      : {res['feedback_rationale']}")
        print(f"SM-2 Update   : n={res['sm2_update']['repetition_n']}, EF={res['sm2_update']['ease_factor']}, next interval={res['sm2_update']['interval_days']} days")
        print(f"Next Review   : {res['sm2_update']['next_review_at']}")

        if idx < len(due_cards):
            try:
                cont = input("\nPress Enter for next card (or 'q' to quit) > ").strip().lower()
                if cont == 'q':
                    break
            except (EOFError, KeyboardInterrupt):
                break

    print("\n" + "=" * 55)
    print("   Review session complete. Memory retention updated!   ")
    print("=" * 55)


def print_stats(db_path: str):
    """Displays card mastery and review statistics."""
    engine = CognitiveTutorEngine(db_path=db_path)
    stats = engine.get_mastery_stats()

    print("\n" + "=" * 45)
    print("    COGNITIVE TUTOR MASTERY STATISTICS     ")
    print("=" * 45)
    print(f"Total Flashcards Registered : {stats['total_cards']}")
    print(f"Cards Due for Review Now   : {stats['due_cards']}")
    print(f"Total Review Logs Recorded  : {stats['total_reviews']}")
    print(f"Average Accuracy Score      : {stats['average_score_percent']}%")
    print(f"Average Quality Rating (Q)  : {stats['average_q_rating']} / 5.0")
    print(f"System Mastery Level        : {stats['mastery_level']}")
    print("-" * 45)
    print("Quality Rating Distribution (0-5):")
    for q, count in stats['q_distribution'].items():
        bar = "#" * min(30, count)
        print(f"  Q={q}: {count:4d} | {bar}")
    print("=" * 45 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Spaced Repetition Active Learning Tutor CLI for vazus SuperGraph OS.")
    parser.add_argument("--test", action="store_true", help="Run non-interactive self-test suite and return Exit Code 0.")
    parser.add_argument("--review", action="store_true", help="Start active recall interactive review session.")
    parser.add_argument("--stats", action="store_true", help="Print card mastery and review statistics.")
    parser.add_argument("--db-path", type=str, default=DEFAULT_DB_PATH, help="Path to SQLite database file.")
    parser.add_argument("--wiki-dir", type=str, default=r"C:\vazus\services\memory\semantic\wiki", help="Path to Zettelkasten wiki notes directory.")

    args = parser.parse_args()

    if args.test:
        sys.exit(run_self_test())
    elif args.review:
        run_interactive_review(args.db_path, args.wiki_dir)
    elif args.stats:
        print_stats(args.db_path)
    else:
        # Default behavior: run self-test cleanly returning Exit Code 0
        sys.exit(run_self_test())


if __name__ == "__main__":
    main()
