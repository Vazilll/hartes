import pathlib
import pytest
from unittest import mock

from tasks.registry import TaskRegistry
from tasks.base import Task, Candidate

class DummyTask(Task):
    @property
    def problem_description(self) -> str:
        return "dummy"

    @property
    def seed(self) -> str:
        return "seed"

    def evaluator(self, candidate: Candidate) -> float:
        return 100.0

    def generate_candidate(self, planner_fn, dead_ends, round_n=1) -> Candidate:
        return Candidate(code="dummy")

class AbstractDummyTask(Task):
    @property
    def problem_description(self) -> str:
        return "abstract dummy"

    @property
    def seed(self) -> str:
        return "seed"

    # missing evaluator and generate_candidate makes it abstract

class AnotherDummyTask(Task):
    @property
    def problem_description(self) -> str:
        return "another"

    @property
    def seed(self) -> str:
        return "seed"

    def evaluator(self, candidate: Candidate) -> float:
        return 100.0

    def generate_candidate(self, planner_fn, dead_ends, round_n=1) -> Candidate:
        return Candidate(code="another")

@pytest.fixture(autouse=True)
def reset_registry():
    """Reset TaskRegistry class state before and after each test."""
    original_registry = TaskRegistry._registry.copy()
    original_discovered = TaskRegistry._discovered

    TaskRegistry._registry.clear()
    TaskRegistry._discovered = False

    yield

    TaskRegistry._registry = original_registry
    TaskRegistry._discovered = original_discovered

def test_missing_builtin_dir():
    """Test behavior when the builtin directory doesn't exist."""
    with mock.patch.object(pathlib.Path, "exists", return_value=False):
        TaskRegistry._discover()
        assert TaskRegistry._discovered is True
        assert len(TaskRegistry._registry) == 0

def test_discover_mocked_modules():
    """Test discovering tasks with mocked pkgutil and importlib."""
    modules = [
        (None, "good_module", False),
        (None, "broken_module", False),
        (None, "abstract_module", False),
    ]

    class GoodModule:
        GoodTask = DummyTask
        NotATask = int

    class AbstractModule:
        AbsTask = AbstractDummyTask

    def mock_import_module(name):
        if name.endswith("good_module"):
            return GoodModule
        elif name.endswith("abstract_module"):
            return AbstractModule
        elif name.endswith("broken_module"):
            raise ImportError("broken")
        raise ImportError(f"Unknown: {name}")

    with mock.patch.object(pathlib.Path, "exists", return_value=True), \
         mock.patch("pkgutil.iter_modules", return_value=modules), \
         mock.patch("importlib.import_module", side_effect=mock_import_module):

        TaskRegistry._discover()

        assert TaskRegistry._discovered is True
        assert "good_module" in TaskRegistry._registry
        assert TaskRegistry._registry["good_module"] == DummyTask

        # broken should be skipped
        assert "broken_module" not in TaskRegistry._registry

        # abstract should be skipped
        assert "abstract_module" not in TaskRegistry._registry

def test_load_existing_task():
    """Test loading an existing task with arguments."""
    TaskRegistry._registry = {"dummy": DummyTask}
    TaskRegistry._discovered = True

    task = TaskRegistry.load("dummy", task_id="test_id_123")

    assert isinstance(task, DummyTask)
    assert task.task_id == "test_id_123"

def test_load_nonexistent_task():
    """Test error when loading an unknown task."""
    TaskRegistry._registry = {"dummy": DummyTask}
    TaskRegistry._discovered = True

    with pytest.raises(KeyError, match=r"No task named 'missing'. Available: \[dummy\]"):
        TaskRegistry.load("missing")

def test_list_available():
    """Test listing available tasks."""
    TaskRegistry._registry = {"dummy": DummyTask, "another": AnotherDummyTask}
    TaskRegistry._discovered = True

    available = TaskRegistry.list_available()
    assert available == ["another", "dummy"]
