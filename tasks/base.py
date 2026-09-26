"""
hartes.tasks.base — Core Task abstraction.

A Task is the first-class unit of work for the Hartes autonomous flywheel.
Inspired by DeepMind FunSearch's problem/evaluator/seed model, simplified
to fit a general-purpose coding assistant context.

Structure:
    Task
     ├── problem: str        — what the task is (human-readable description)
     ├── seed: str           — initial solution / starting code / context
     ├── evaluator()         — objective function: returns score 0.0–100.0
     └── generate_candidate() — calls LLM or FunSearch to produce a candidate

    TaskResult
     ├── status: TaskStatus  — SUCCESS | ESCALATED | TIMEOUT | ERROR
     ├── best_candidate: str — best produced output so far
     ├── score: float        — final score (0–100)
     └── rounds: int         — how many rounds were needed
"""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TaskStatus(str, Enum):
    SUCCESS = "SUCCESS"
    ESCALATED = "ESCALATED"  # anti-thrashing circuit tripped
    TIMEOUT = "TIMEOUT"       # max rounds exhausted
    ERROR = "ERROR"


@dataclass
class Candidate:
    """A single generated attempt at solving a Task."""
    code: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: float = field(default_factory=time.time)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.code.encode()).hexdigest()[:16]


@dataclass
class TaskResult:
    """Final result of running the harness loop on a Task."""
    task_id: str
    status: TaskStatus
    best_candidate: Optional[Candidate] = None
    score: float = 0.0
    rounds_used: int = 0
    escalation_briefing: Optional[str] = None
    error: Optional[str] = None
    duration_s: float = 0.0


class Task(ABC):
    """
    Base class for all Hartes tasks.

    Subclasses must implement:
      - problem_description: str property
      - seed: str property (initial solution or empty string)
      - evaluator(candidate: Candidate) -> float  [0.0 to 100.0]
      - generate_candidate(planner_fn, dead_ends) -> Candidate

    Convention:
      - evaluator() returns 100.0 for a perfect solution
      - evaluator() returns 0.0 for a completely broken solution
      - Admissibility threshold is 75.0 (matches QualityEvaluationEngine)
    """

    ADMISSIBILITY_THRESHOLD: float = 75.0

    def __init__(self, task_id: Optional[str] = None):
        self._task_id = task_id or self._generate_id()
        self._created_at = time.time()

    def _generate_id(self) -> str:
        ts = int(time.time() * 1000)
        cls = type(self).__name__
        return f"{cls}_{ts}"

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    @abstractmethod
    def problem_description(self) -> str:
        """Human-readable description of what this task is trying to solve."""
        ...

    @property
    @abstractmethod
    def seed(self) -> str:
        """Initial solution or empty string for tasks starting from scratch."""
        ...

    @abstractmethod
    def evaluator(self, candidate: Candidate) -> float:
        """
        Objective scoring function.
        Must be deterministic and free of side-effects.
        Returns a float in [0.0, 100.0].
        """
        ...

    @abstractmethod
    def generate_candidate(
        self,
        planner_fn: Callable[[str, List[Dict[str, Any]]], Dict[str, Any]],
        dead_ends: List[str],
        round_n: int = 1,
    ) -> Candidate:
        """
        Produce one candidate solution.

        Args:
            planner_fn: LLM planning function (GeminiPlanner.plan or mock).
            dead_ends:  List of previously failed candidate summaries to avoid.
            round_n:    Current round number (for prompt conditioning).

        Returns:
            A Candidate object with the generated code/content.
        """
        ...

    def is_admissible(self, score: float) -> bool:
        return score >= self.ADMISSIBILITY_THRESHOLD

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self._task_id}>"
