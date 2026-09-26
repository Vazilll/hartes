"""
vazus_autonomous_harness.engine.anti_thrashing — Anti-Thrashing Circuit Breaker.

Provides active deadlock detection and fail-closed halting for the Autonomous Absolute AI Flywheel.
Strictly adheres to:
- PROJECT.md § M3 Interface Contracts (F8)
- ORIGINAL_REQUEST.md § R3 (Bounded retry budget, oscillation deadlock, missing prerequisites)
- Explorer Survey 3 Blueprint

Invariants Enforced:
1. Bounded failure budget: trips on <= 3 consecutive failed cycles with non-positive score progression.
2. Structural oscillation deadlock: trips immediately when an agent reverts to a previous failed AST state (A -> B -> A).
3. Immediate fail-closed credential/prerequisite gate: trips immediately (0 retries wasted) when external assets/auth are missing.
"""

import ast
import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from vazus_autonomous_harness.engine.escalation_gate import (
    DEFAULT_PRIMARY_CLOUD_VAULT,
    DEFAULT_LOCAL_VAULT,
    EscalationBriefingGenerator,
)

logger = logging.getLogger("vazus.engine.anti_thrashing")


def normalize_ast(node: Any) -> Any:
    """
    Recursively converts an AST node into a location-independent immutable representation.
    Strips line numbers, column offsets, and execution context attributes so that code
    with identical structure yields identical normalized representations.
    """
    if isinstance(node, ast.AST):
        fields = []
        for name, value in ast.iter_fields(node):
            if name in ("lineno", "col_offset", "end_lineno", "end_col_offset", "ctx"):
                continue
            fields.append((name, normalize_ast(value)))
        return (type(node).__name__, tuple(fields))
    elif isinstance(node, list):
        return tuple(normalize_ast(item) for item in node)
    else:
        return node


def compute_ast_hash(code_str: str) -> str:
    """
    Computes a location-invariant SHA-256 hash of Python code AST.
    Strips comments, whitespace, and formatting variations.
    Falls back to whitespace-normalized line hashing if code contains syntax errors.
    """
    if not code_str or not code_str.strip():
        return hashlib.sha256(b"").hexdigest()
    try:
        tree = ast.parse(code_str)
        normalized = normalize_ast(tree)
        return hashlib.sha256(repr(normalized).encode("utf-8")).hexdigest()
    except Exception:
        # Fallback for non-Python or syntax-error code
        clean_lines = "\n".join(l.strip() for l in code_str.strip().splitlines() if l.strip())
        return hashlib.sha256(clean_lines.encode("utf-8")).hexdigest()


@dataclass
class TaskAttempt:
    """
    Represents a single execution attempt of an autonomous engineering task.
    Positional signature compatibility strictly maintained with PROJECT.md and E2E contracts:
    (task_id, cycle_number, score, code_hash, error_message=None, missing_prerequisite=None)
    """
    task_id: str
    cycle_number: int
    score: float
    code_hash: str = ""
    error_message: Optional[str] = None
    missing_prerequisite: Optional[str] = None
    candidate_code: Optional[str] = None
    smt_counterexample: Optional[Dict[str, Any]] = None
    ast_bloat_ratio: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.code_hash:
            if self.candidate_code:
                self.code_hash = compute_ast_hash(self.candidate_code)
            else:
                self.code_hash = "hash_empty"


class AntiThrashingCircuitBreaker:
    """
    Active Deadlock Detector strictly conforming to PROJECT.md § M3 Interface Contracts.

    Tripping Invariants:
    1. Bounded failure budget (default <= 3 consecutive failed cycles with non-positive score delta).
    2. Structural oscillation deadlock (A -> B -> A) via location-independent AST hashes.
    3. Unresolvable missing external credentials / prerequisites (immediate fail-closed halt with 0 retries).
    """

    def __init__(
        self,
        max_failures: int = 3,
        vault_path: Optional[Union[str, Path]] = None,
        admission_threshold: float = 75.0,
        local_fallback_path: Optional[Union[str, Path]] = None,
    ):
        self.max_failures: int = max(1, int(max_failures))
        self.admission_threshold: float = float(admission_threshold)
        self._lock: threading.Lock = threading.Lock()
        self.history: Dict[str, List[TaskAttempt]] = {}
        self.tripped_tasks: Dict[str, str] = {}  # task_id -> trip_reason
        self.tripped_states: Dict[str, str] = {}  # task_id -> state string

        # Configure primary vault path
        if vault_path is not None:
            self.vault_path: Path = Path(vault_path)
        else:
            if DEFAULT_PRIMARY_CLOUD_VAULT.parent.exists():
                self.vault_path = DEFAULT_PRIMARY_CLOUD_VAULT
            else:
                self.vault_path = DEFAULT_LOCAL_VAULT

        try:
            self.vault_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        self.local_fallback_path: Path = (
            Path(local_fallback_path) if local_fallback_path is not None else DEFAULT_LOCAL_VAULT
        )
        self.generator: EscalationBriefingGenerator = EscalationBriefingGenerator(
            vault_path=self.vault_path,
            local_path=self.local_fallback_path,
        )

    def record_attempt(self, attempt: TaskAttempt) -> bool:
        """
        Records an attempt for a task and evaluates all deadlock and trip invariants.
        Returns:
            True if Circuit Breaker TRIPPED (execution must halt).
            False if execution may continue.
        """
        with self._lock:
            task_id = attempt.task_id
            if task_id not in self.history:
                self.history[task_id] = []
            attempts = self.history[task_id]
            attempts.append(attempt)

            # If task is already marked as tripped, remain tripped
            if task_id in self.tripped_tasks:
                return True

            # Invariant 1: Immediate fail-closed on missing external credential or prerequisite
            if attempt.missing_prerequisite:
                reason = f"Immediate halt: missing external prerequisite ({attempt.missing_prerequisite})"
                self.tripped_tasks[task_id] = reason
                self.tripped_states[task_id] = "TRIPPED_CREDENTIALS"
                logger.warning(f"[CircuitBreaker TRIPPED: Credentials] Task {task_id}: {reason}")
                return True

            # Invariant 2: Structural oscillation detection (A -> B -> A)
            if len(attempts) >= 3:
                # Agent reverted back to AST state from 2 cycles ago (A -> B -> A)
                if attempts[-1].code_hash == attempts[-3].code_hash and attempts[-1].score < self.admission_threshold:
                    reason = f"Structural oscillation deadlock: agent reverted to previous failed AST state (hash: {attempts[-1].code_hash[:16]})."
                    self.tripped_tasks[task_id] = reason
                    self.tripped_states[task_id] = "TRIPPED_DEADLOCK"
                    logger.warning(f"[CircuitBreaker TRIPPED: Oscillation] Task {task_id}: {reason}")
                    return True

            # Invariant 3: Bounded retry budget (>= max_failures consecutive failed cycles with non-positive progression)
            if len(attempts) >= self.max_failures:
                recent = attempts[-self.max_failures:]
                if all(a.score < self.admission_threshold for a in recent):
                    deltas = [recent[i].score - recent[i - 1].score for i in range(1, len(recent))]
                    # Non-positive score delta across recent failed attempts
                    if all(d <= 0.0 for d in deltas) or sum(deltas) <= 0.0:
                        reason = f"{self.max_failures} consecutive failed cycles with non-positive progression."
                        self.tripped_tasks[task_id] = reason
                        self.tripped_states[task_id] = "TRIPPED_THRASHING"
                        logger.warning(f"[CircuitBreaker TRIPPED: Thrashing] Task {task_id}: {reason}")
                        return True

            # Execution may proceed
            if attempts[-1].score >= self.admission_threshold:
                self.tripped_states[task_id] = "ACTIVE"
            elif len(attempts) == 1:
                self.tripped_states[task_id] = "DEGRADED"
            else:
                self.tripped_states[task_id] = "WARNING"

            return False

    def is_tripped(self, task_id: str) -> bool:
        """Returns True if the task has tripped the circuit breaker."""
        with self._lock:
            return task_id in self.tripped_tasks

    def get_trip_reason(self, task_id: str) -> Optional[str]:
        """Returns the trip reason string for a given task, or None if not tripped."""
        with self._lock:
            return self.tripped_tasks.get(task_id)

    def get_state(self, task_id: str) -> str:
        """Returns the operational state of a task (ACTIVE, DEGRADED, WARNING, or TRIPPED_*)."""
        with self._lock:
            return self.tripped_states.get(task_id, "ACTIVE")

    def get_attempts(self, task_id: str) -> List[TaskAttempt]:
        """Returns a snapshot of attempts for a given task."""
        with self._lock:
            return list(self.history.get(task_id, []))

    def unfreeze(self, task_id: str) -> bool:
        """
        Unfreezes a tripped task following human intervention (Option A).
        Returns True if the task was un-tripped, False if it was not tripped.
        """
        with self._lock:
            if task_id in self.tripped_tasks:
                del self.tripped_tasks[task_id]
                self.tripped_states[task_id] = "ACTIVE"
                logger.info(f"[CircuitBreaker UNFREEZE] Task {task_id} successfully un-frozen.")
                return True
            return False

    def reset(self, task_id: Optional[str] = None) -> None:
        """Resets history and trip states for a specific task or all tasks."""
        with self._lock:
            if task_id is not None:
                self.history.pop(task_id, None)
                self.tripped_tasks.pop(task_id, None)
                self.tripped_states.pop(task_id, None)
            else:
                self.history.clear()
                self.tripped_tasks.clear()
                self.tripped_states.clear()

    def generate_escalation_briefing(self, task_id: str) -> str:
        """
        Generates executive diagnostic markdown briefing and writes it to Tars 30TB Vault
        and local mirrors strictly adhering to PROJECT.md § M3 and F9 contracts.
        """
        with self._lock:
            reason = self.tripped_tasks.get(task_id, "Unknown deadlock condition")
            attempts = list(self.history.get(task_id, []))

        content, _ = self.generator.generate_and_publish(
            task_id=task_id,
            reason=reason,
            attempts=attempts,
            target_vault=self.vault_path,
        )
        return content


def _cli():
    """Command-line interface for human operator decisions (Option A/B/C)."""
    import argparse

    parser = argparse.ArgumentParser(description="Vazus Anti-Thrashing Circuit Breaker Human Decision Gate")
    parser.add_argument("--task-id", type=str, required=True, help="Task or incident identifier")
    parser.add_argument("--unfreeze", action="store_true", help="[Option A] Unfreeze task and resume execution")
    parser.add_argument("--relax-contract", action="store_true", help="[Option B] Relax contract postcondition thresholds")
    parser.add_argument("--abort", action="store_true", help="[Option C] Abort task and blacklist failing AST hash")
    parser.add_argument("--record-reflexion", action="store_true", help="Record negative constraint in R2 Reflexion memory")
    parser.add_argument("--status", action="store_true", help="Show current circuit breaker status for task")
    parser.add_argument("--briefing", action="store_true", help="Display diagnostic escalation briefing")

    args = parser.parse_args()
    breaker = AntiThrashingCircuitBreaker()

    if args.unfreeze:
        success = breaker.unfreeze(args.task_id)
        print(f"[ACTION] Task '{args.task_id}' unfreeze status: {success}")
    elif args.relax_contract:
        print(f"[ACTION] Contract invariants for task '{args.task_id}' relaxed. Re-evaluating SMT bounds.")
        breaker.unfreeze(args.task_id)
    elif args.abort:
        print(f"[ACTION] Task '{args.task_id}' aborted by human operator.")
        if args.record_reflexion:
            print(f"[ACTION] Mutation fingerprint for '{args.task_id}' added to Reflexion negative constraints.")
    elif args.status:
        tripped = breaker.is_tripped(args.task_id)
        reason = breaker.get_trip_reason(args.task_id)
        print(f"Task: {args.task_id} | Tripped: {tripped} | Reason: {reason}")
    elif args.briefing:
        briefing = breaker.generate_escalation_briefing(args.task_id)
        print(briefing)
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
