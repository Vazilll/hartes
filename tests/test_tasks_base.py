import pytest
import time
import hashlib
from typing import Callable, List, Dict, Any

from tasks.base import Candidate, TaskStatus, TaskResult, Task


def test_candidate_defaults():
    candidate = Candidate(code="print('hello')")
    assert candidate.code == "print('hello')"
    assert candidate.metadata == {}
    assert isinstance(candidate.generated_at, float)
    assert candidate.generated_at <= time.time()


def test_candidate_content_hash():
    code = "def add(a, b): return a + b"
    candidate = Candidate(code=code)
    expected_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
    assert candidate.content_hash == expected_hash


def test_task_status_enum():
    assert TaskStatus.SUCCESS.value == "SUCCESS"
    assert TaskStatus.ESCALATED.value == "ESCALATED"
    assert TaskStatus.TIMEOUT.value == "TIMEOUT"
    assert TaskStatus.ERROR.value == "ERROR"
    assert TaskStatus.SUCCESS == "SUCCESS"


def test_task_result_defaults():
    result = TaskResult(task_id="test_id", status=TaskStatus.SUCCESS)
    assert result.task_id == "test_id"
    assert result.status == TaskStatus.SUCCESS
    assert result.best_candidate is None
    assert result.score == 0.0
    assert result.rounds_used == 0
    assert result.escalation_briefing is None
    assert result.error is None
    assert result.duration_s == 0.0


def test_task_cannot_instantiate_abc():
    with pytest.raises(TypeError):
        Task()


class DummyTask(Task):
    @property
    def problem_description(self) -> str:
        return "Dummy problem"

    @property
    def seed(self) -> str:
        return "Dummy seed"

    def evaluator(self, candidate: Candidate) -> float:
        return 100.0 if candidate.code == "correct" else 0.0

    def generate_candidate(
        self,
        planner_fn: Callable[[str, List[Dict[str, Any]]], Dict[str, Any]],
        dead_ends: List[str],
        round_n: int = 1,
    ) -> Candidate:
        return Candidate(code="generated code")


def test_task_custom_id():
    task = DummyTask(task_id="custom_id_123")
    assert task.task_id == "custom_id_123"


def test_task_auto_id_and_repr():
    task = DummyTask()
    assert task.task_id.startswith("DummyTask_")

    repr_str = repr(task)
    assert repr_str == f"<DummyTask id={task.task_id}>"


def test_task_is_admissible():
    task = DummyTask()
    assert task.is_admissible(75.0) is True
    assert task.is_admissible(75.1) is True
    assert task.is_admissible(100.0) is True

    assert task.is_admissible(74.9) is False
    assert task.is_admissible(0.0) is False

def test_dummy_task_methods():
    task = DummyTask()
    assert task.problem_description == "Dummy problem"
    assert task.seed == "Dummy seed"

    good_cand = Candidate(code="correct")
    bad_cand = Candidate(code="incorrect")
    assert task.evaluator(good_cand) == 100.0
    assert task.evaluator(bad_cand) == 0.0

    generated = task.generate_candidate(lambda x, y: {}, [])
    assert generated.code == "generated code"
