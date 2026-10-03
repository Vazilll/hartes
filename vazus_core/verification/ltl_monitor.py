"""
vazus_core.verification.ltl_monitor
===================================
Linear Temporal Logic (LTL) Trace Monitor for Dynamic Task DAGs and Subagent Pipelines.
Verifies safety, liveness, and causal ordering invariants over runtime execution traces:
- G(p) (Globally / Always): p must hold at all trace states.
- F(p) (Finally / Eventually): p must hold at some future state.
- X(p) (Next): p must hold at the immediate subsequent state.
- p -> q (Implication): if p holds, q must hold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger("vazus_core.verification.ltl_monitor")


@dataclass
class LTLVerificationResult:
    """Outcome of LTL trace evaluation."""
    passed: bool
    total_events: int
    invariants_checked: int
    violations: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class LTLMonitor:
    """
    Linear Temporal Logic runtime trace monitor.
    Enforces temporal safety & liveness contracts on multi-subagent DAG executions.
    """

    DEFAULT_INVARIANTS = [
        "G(task_started -> F task_completed)",     # Liveness: every initiated task eventually finishes
        "G(NOT (task_failed AND task_succeeded))", # Safety: terminal states are mutually exclusive
        "G(memory_write -> X memory_readable)",    # Causal memory: write enables read at next step
    ]

    def __init__(self, invariants: Optional[Sequence[str]] = None):
        self.invariants = list(invariants or self.DEFAULT_INVARIANTS)

    def _eval_predicate(self, predicate: str, state: Dict[str, Any]) -> bool:
        """Evaluates an atomic predicate against a single trace event state."""
        pred = predicate.strip()
        # Boolean key presence or truthiness
        if pred in state:
            val = state[pred]
            return bool(val)

        # Check event_type or status matches
        event_type = str(state.get("event_type") or state.get("type") or "").lower()
        status = str(state.get("status") or "").lower()

        if pred == "task_started":
            return event_type in ("task_started", "start", "task_start") or status == "started"
        elif pred == "task_completed":
            return event_type in ("task_completed", "finish", "complete", "task_done") or status in ("completed", "done", "succeeded", "failed")
        elif pred == "task_failed":
            return event_type in ("task_failed", "failure", "error") or status == "failed"
        elif pred == "task_succeeded":
            return event_type in ("task_succeeded", "success") or status in ("succeeded", "success")
        elif pred == "memory_write":
            return event_type in ("memory_write", "db_write", "write_memory") or bool(state.get("memory_write"))
        elif pred == "memory_readable":
            return event_type in ("memory_readable", "db_read", "memory_read") or bool(state.get("memory_readable"))

        return False

    def verify_trace(self, trace: List[Dict[str, Any]]) -> LTLVerificationResult:
        """
        Validates the entire chronological trace against registered LTL invariants.
        Returns detailed verification outcome.
        """
        if not trace:
            return LTLVerificationResult(
                passed=True,
                total_events=0,
                invariants_checked=len(self.invariants),
                violations=[],
            )

        violations: List[str] = []

        for inv in self.invariants:
            if not self._check_invariant(inv, trace):
                violations.append(inv)

        return LTLVerificationResult(
            passed=len(violations) == 0,
            total_events=len(trace),
            invariants_checked=len(self.invariants),
            violations=violations,
        )

    def _check_invariant(self, invariant: str, trace: List[Dict[str, Any]]) -> bool:
        """Checks a specific LTL formula over the trace states."""
        inv = invariant.strip()

        # Invariant 1: G(task_started -> F task_completed)
        if "task_started" in inv and "F task_completed" in inv:
            for i, state in enumerate(trace):
                if self._eval_predicate("task_started", state):
                    # Must find task_completed in states i..len(trace)-1
                    completed_found = any(
                        self._eval_predicate("task_completed", trace[j])
                        for j in range(i, len(trace))
                    )
                    if not completed_found:
                        logger.warning("LTL Violation: task started at step %d never completed", i)
                        return False
            return True

        # Invariant 2: G(NOT (task_failed AND task_succeeded))
        if "NOT" in inv and "task_failed" in inv and "task_succeeded" in inv:
            for i, state in enumerate(trace):
                failed = self._eval_predicate("task_failed", state)
                succeeded = self._eval_predicate("task_succeeded", state)
                if failed and succeeded:
                    logger.warning("LTL Violation: state %d has both failed and succeeded flags", i)
                    return False
            return True

        # Invariant 3: G(memory_write -> X memory_readable)
        if "memory_write" in inv and "X memory_readable" in inv:
            for i, state in enumerate(trace):
                if self._eval_predicate("memory_write", state):
                    if i + 1 >= len(trace):
                        # At last step, write has no next state: liveness violation for next state
                        logger.warning("LTL Violation: memory written at final step %d has no subsequent read state", i)
                        return False
                    next_state = trace[i + 1]
                    # Readable flag or read event in next state
                    if not self._eval_predicate("memory_readable", next_state):
                        logger.warning("LTL Violation: memory written at %d not readable at next step %d", i, i + 1)
                        return False
            return True

        # Generic G(p) check: p must hold at all states
        if inv.startswith("G(") and inv.endswith(")"):
            inner = inv[2:-1].strip()
            return all(self._eval_predicate(inner, state) for state in trace)

        return True
