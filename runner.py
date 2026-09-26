"""
hartes — Main CLI runner.

The single entry point for the Hartes autonomous flywheel.
Connects Task → Memory → AntiThrashing → QualityEngine → LLM into one loop.

Usage:
    python -m hartes run --task=code_optimizer --input=my_script.py
    python -m hartes run --task=code_optimizer --input=my_script.py --test-cmd="pytest tests/"
    python -m hartes list
    python -m hartes run --task=code_optimizer --inline="def foo(): pass" --model=flash

Exit codes:
    0 — SUCCESS (admissible candidate found)
    1 — ESCALATED (anti-thrashing circuit tripped, human needed)
    2 — TIMEOUT (max rounds exhausted)
    3 — ERROR (internal exception)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import Optional

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hartes.runner")

# ── Exit codes ────────────────────────────────────────────────────────────────
EXIT_SUCCESS   = 0
EXIT_ESCALATED = 1
EXIT_TIMEOUT   = 2
EXIT_ERROR     = 3

# ── Default hyperparameters ───────────────────────────────────────────────────
DEFAULT_MAX_ROUNDS = 5
DEFAULT_MODEL      = "flash-lite"


def run(
    task_name: str,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    model: str = DEFAULT_MODEL,
    **task_kwargs,
) -> dict:
    """
    Main harness loop.

    DeepSeek-style simplicity:
        for round in 1..max_rounds:
            1. Pre-flight: reject known dead-ends
            2. Generate candidate (LLM)
            3. Evaluate (objective scorer)
            4. Record result (reflexion memory)
            5. Accept if admissible OR trip circuit breaker
    """
    t0 = time.perf_counter()

    # ── Infrastructure ────────────────────────────────────────────────────────
    from tasks.registry import TaskRegistry
    from llm.gemini_planner import GeminiPlanner
    from vazus_autonomous_harness.memory.episodic_store import EpisodicMemoryStore
    from vazus_autonomous_harness.memory.preflight_filter import PreFlightFilter
    from vazus_autonomous_harness.engine.anti_thrashing import (
        AntiThrashingCircuitBreaker,
        TaskAttempt,
    )
    from vazus_autonomous_harness.verification.quality_engine import QualityEvaluationEngine
    from tasks.base import TaskStatus, TaskResult

    task = TaskRegistry.load(task_name, **task_kwargs)
    planner = GeminiPlanner(model=model)
    memory = EpisodicMemoryStore()
    preflight = PreFlightFilter(episodic_store=memory)
    breaker = AntiThrashingCircuitBreaker()
    quality = QualityEvaluationEngine()

    best_candidate = None
    best_score = 0.0

    logger.info("Starting harness loop: task=%s, max_rounds=%d, model=%s",
                task_name, max_rounds, model)

    for round_n in range(1, max_rounds + 1):
        logger.info("── Round %d/%d ──", round_n, max_rounds)

        # 1. Pre-flight: retrieve dead-ends from episodic memory
        try:
            similar_failures = memory.retrieve_similar_dead_ends(
                task.problem_description, limit=5
            )
            dead_end_summaries = [r.candidate_summary for r in similar_failures]
        except Exception:
            dead_end_summaries = []

        # 2. Generate candidate via LLM
        try:
            candidate = task.generate_candidate(
                planner_fn=planner,
                dead_ends=dead_end_summaries,
                round_n=round_n,
            )
            logger.info("Generated candidate: %s (%d chars)", candidate.content_hash, len(candidate.code))
        except Exception as exc:
            logger.error("Candidate generation failed: %s", exc)
            _record_failure(memory, task, f"generation_error: {exc}", round_n, 0.0)
            continue

        # 3. Evaluate candidate (objective scorer)
        try:
            score = task.evaluator(candidate)
        except Exception as exc:
            logger.error("Evaluation failed: %s", exc)
            score = 0.0

        logger.info("Score: %.1f / 100.0 (admissible: %s)", score, task.is_admissible(score))

        # Track best
        if score > best_score:
            best_score = score
            best_candidate = candidate

        # 4. Record result in episodic memory
        _record_failure(memory, task, candidate.code[:200], round_n, score)

        # 5a. Accept if admissible
        if task.is_admissible(score):
            duration = time.perf_counter() - t0
            result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.SUCCESS,
                best_candidate=candidate,
                score=score,
                rounds_used=round_n,
                duration_s=duration,
            )
            logger.info("SUCCESS in %d rounds (%.1f pts, %.1fs)", round_n, score, duration)
            return _serialize_result(result)

        # 5b. Check anti-thrashing circuit
        attempt = TaskAttempt(
            task_id=task.task_id,
            cycle_number=round_n,
            score=score,
            code_hash=candidate.content_hash,
            error_message=None if score > 0 else "score=0",
            missing_prerequisite=None,
        )
        if breaker.record_attempt(attempt):
            briefing = breaker.generate_escalation_briefing(task.task_id)
            duration = time.perf_counter() - t0
            result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.ESCALATED,
                best_candidate=best_candidate,
                score=best_score,
                rounds_used=round_n,
                escalation_briefing=briefing,
                duration_s=duration,
            )
            logger.warning("ESCALATED: anti-thrashing circuit tripped after round %d", round_n)
            return _serialize_result(result)

    # max_rounds exhausted
    duration = time.perf_counter() - t0
    result = TaskResult(
        task_id=task.task_id,
        status=TaskStatus.TIMEOUT,
        best_candidate=best_candidate,
        score=best_score,
        rounds_used=max_rounds,
        duration_s=duration,
    )
    logger.info("TIMEOUT: %d rounds exhausted. Best score: %.1f", max_rounds, best_score)
    return _serialize_result(result)


def _record_failure(memory, task, summary: str, round_n: int, score: float) -> None:
    """Store a reflexion record for every round (pass or fail)."""
    try:
        from vazus_autonomous_harness.memory.reflexion_engine import (
            ContinuousReflexionGenerator,
        )
        from vazus_autonomous_harness.verification.quality_engine import QualityScore
        # Build a minimal QualityScore for the reflexion engine
        qs = QualityScore(
            total_score=score,
            correctness_smt=min(score * 0.4, 40.0),
            empirical_integrity=min(score * 0.3, 30.0),
            parsimony_efficiency=min(score * 0.15, 15.0),
            academic_sovereignty=min(score * 0.15, 15.0),
            is_admissible=score >= 75.0,
        )
        record = ContinuousReflexionGenerator(task_id=task.task_id).from_quality_score(
            candidate_summary=summary[:200],
            quality_score=qs,
        )
        memory.insert_record(record)
    except Exception:
        pass  # reflexion is best-effort; never crash the main loop


def _serialize_result(result) -> dict:
    """Convert TaskResult to a JSON-serializable dict."""
    return {
        "status": result.status.value,
        "task_id": result.task_id,
        "score": round(result.score, 2),
        "rounds_used": result.rounds_used,
        "duration_s": round(result.duration_s, 2),
        "best_candidate_hash": result.best_candidate.content_hash if result.best_candidate else None,
        "best_candidate_preview": (result.best_candidate.code[:300] + "...") if result.best_candidate else None,
        "escalation_briefing": result.escalation_briefing,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hartes",
        description="Hartes Autonomous Flywheel — run a task through the quality loop.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List all available tasks.")

    # run
    run_p = subparsers.add_parser("run", help="Run a task through the harness loop.")
    run_p.add_argument("--task", required=True, help="Task name (e.g. code_optimizer).")
    run_p.add_argument("--input", dest="input_file", help="Path to input file.")
    run_p.add_argument("--inline", dest="inline_code", help="Inline code string.")
    run_p.add_argument("--test-cmd", dest="test_command", help="Shell command to run tests.")
    run_p.add_argument("--model", default=DEFAULT_MODEL,
                       help=f"LLM model shortname. Options: flash-lite (default), flash, pro.")
    run_p.add_argument("--rounds", type=int, default=DEFAULT_MAX_ROUNDS,
                       help=f"Maximum optimization rounds (default: {DEFAULT_MAX_ROUNDS}).")
    run_p.add_argument("--json", dest="output_json", action="store_true",
                       help="Output result as JSON.")
    return parser


def main(argv: Optional[list] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        from tasks.registry import TaskRegistry
        available = TaskRegistry.list_available()
        print("Available tasks:")
        for name in available:
            print(f"  • {name}")
        return EXIT_SUCCESS

    if args.command == "run":
        task_kwargs = {}
        if args.input_file:
            task_kwargs["input_file"] = args.input_file
        if args.inline_code:
            task_kwargs["inline_code"] = args.inline_code
        if getattr(args, "test_command", None):
            task_kwargs["test_command"] = args.test_command

        try:
            result = run(
                task_name=args.task,
                max_rounds=args.rounds,
                model=args.model,
                **task_kwargs,
            )
        except Exception as exc:
            logger.error("Fatal error: %s", exc, exc_info=True)
            return EXIT_ERROR

        if args.output_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"\n{'='*60}")
            print(f"  Status : {result['status']}")
            print(f"  Score  : {result['score']}/100.0")
            print(f"  Rounds : {result['rounds_used']}")
            print(f"  Time   : {result['duration_s']}s")
            if result.get("best_candidate_preview"):
                print(f"\n  Best candidate (preview):")
                print(f"  {result['best_candidate_preview'][:200]}")
            if result.get("escalation_briefing"):
                print(f"\n  ⚠ Escalation required. Briefing:")
                print(result["escalation_briefing"][:500])
            print(f"{'='*60}")

        status_map = {
            "SUCCESS":   EXIT_SUCCESS,
            "ESCALATED": EXIT_ESCALATED,
            "TIMEOUT":   EXIT_TIMEOUT,
            "ERROR":     EXIT_ERROR,
        }
        return status_map.get(result["status"], EXIT_ERROR)

    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
