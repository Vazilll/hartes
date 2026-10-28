import hashlib
from typing import Any, Callable, Dict, List

import pytest

from tasks.base import Task, Candidate, TaskResult, TaskStatus

class DummyTask(Task):
    @property
    def problem_description(self) -> str:
        return "Dummy problem"

    @property
    def seed(self) -> str:
        return "Dummy seed"

    def evaluator(self, candidate: Candidate) -> float:
        return 100.0 if candidate.code == "success" else 0.0

    def generate_candidate(
        self,
        planner_fn: Callable[[str, List[Dict[str, Any]]], Dict[str, Any]],
        dead_ends: List[str],
        round_n: int = 1,
    ) -> Candidate:
        return Candidate(code="dummy")

def test_candidate_content_hash():
    code = "print('hello')"
    candidate = Candidate(code=code)
    expected_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
    assert candidate.content_hash == expected_hash

def test_task_initialization():
    task = DummyTask()
    assert task.task_id.startswith("DummyTask_")
    assert repr(task) == f"<DummyTask id={task.task_id}>"

def test_task_custom_id():
    task = DummyTask(task_id="custom_id_123")
    assert task.task_id == "custom_id_123"

def test_task_is_admissible():
    task = DummyTask()
    assert task.is_admissible(100.0) is True
    assert task.is_admissible(75.0) is True
    assert task.is_admissible(74.9) is False
    assert task.is_admissible(0.0) is False

def test_task_result():
    result = TaskResult(
        task_id="test_id",
        status=TaskStatus.SUCCESS,
        score=90.0,
        rounds_used=2
    )
    assert result.task_id == "test_id"
    assert result.status == TaskStatus.SUCCESS
    assert result.score == 90.0
    assert result.rounds_used == 2
