"""
Tests for runner.py CLI.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

import runner
from runner import EXIT_SUCCESS, EXIT_ESCALATED, EXIT_TIMEOUT, EXIT_ERROR

def test_main_list(monkeypatch, capsys):
    mock_list_available = MagicMock(return_value=["task1", "task2"])
    monkeypatch.setattr("tasks.registry.TaskRegistry.list_available", mock_list_available)

    result = runner.main(["list"])

    assert result == EXIT_SUCCESS
    captured = capsys.readouterr()
    assert "Available tasks:" in captured.out
    assert "  • task1" in captured.out
    assert "  • task2" in captured.out
    mock_list_available.assert_called_once()

def test_main_run_success(monkeypatch, capsys):
    mock_run = MagicMock(return_value={
        "status": "SUCCESS",
        "score": 95.0,
        "rounds_used": 1,
        "duration_s": 2.5,
        "task_id": "test_id"
    })
    monkeypatch.setattr("runner.run", mock_run)

    result = runner.main(["run", "--task", "my_task"])

    assert result == EXIT_SUCCESS
    mock_run.assert_called_once_with(
        task_name="my_task",
        max_rounds=runner.DEFAULT_MAX_ROUNDS,
        model=runner.DEFAULT_MODEL
    )
    captured = capsys.readouterr()
    assert "Status : SUCCESS" in captured.out
    assert "Score  : 95.0/100.0" in captured.out

def test_main_run_escalated(monkeypatch):
    mock_run = MagicMock(return_value={
        "status": "ESCALATED",
        "score": 50.0,
        "rounds_used": 5,
        "duration_s": 10.0,
        "task_id": "test_id"
    })
    monkeypatch.setattr("runner.run", mock_run)

    result = runner.main(["run", "--task", "my_task"])

    assert result == EXIT_ESCALATED

def test_main_run_timeout(monkeypatch):
    mock_run = MagicMock(return_value={
        "status": "TIMEOUT",
        "score": 40.0,
        "rounds_used": 5,
        "duration_s": 15.0,
        "task_id": "test_id"
    })
    monkeypatch.setattr("runner.run", mock_run)

    result = runner.main(["run", "--task", "my_task"])

    assert result == EXIT_TIMEOUT

def test_main_run_error(monkeypatch, caplog):
    mock_run = MagicMock(side_effect=RuntimeError("Some error"))
    monkeypatch.setattr("runner.run", mock_run)

    result = runner.main(["run", "--task", "my_task"])

    assert result == EXIT_ERROR
    assert "Fatal error: Some error" in caplog.text

def test_main_run_json(monkeypatch, capsys):
    expected_output = {
        "status": "SUCCESS",
        "score": 90.0,
        "rounds_used": 2,
        "duration_s": 3.0,
        "task_id": "test_id"
    }
    mock_run = MagicMock(return_value=expected_output)
    monkeypatch.setattr("runner.run", mock_run)

    result = runner.main(["run", "--task", "my_task", "--json"])

    assert result == EXIT_SUCCESS
    captured = capsys.readouterr()
    output_json = json.loads(captured.out)
    assert output_json == expected_output

def test_main_daemon(monkeypatch):
    mock_daemon_cls = MagicMock()
    mock_daemon_inst = MagicMock()
    mock_daemon_cls.return_value = mock_daemon_inst

    monkeypatch.setattr("vazus_autonomous_harness.daemon.autonomous_flywheel.AutonomousFlywheelDaemon", mock_daemon_cls)

    result = runner.main(["daemon", "--interval", "15.5", "--max-cycles", "10"])

    assert result == EXIT_SUCCESS
    mock_daemon_cls.assert_called_once_with(
        interval_seconds=15.5,
        model=runner.DEFAULT_MODEL,
        max_cycles=10
    )
    mock_daemon_inst.start.assert_called_once()

def test_serialize_result():
    class MockBestCandidate:
        content_hash = "abc123hash"
        code = "def foo():\n    return 42"

    class MockTaskResult:
        def __init__(self, status_val):
            class Status:
                value = status_val
            self.status = Status()
            self.task_id = "test_task_123"
            self.score = 85.1234
            self.rounds_used = 3
            self.duration_s = 4.5678
            self.best_candidate = MockBestCandidate()
            self.escalation_briefing = "Need more specific types"

    result = MockTaskResult("SUCCESS")
    serialized = runner._serialize_result(result)

    assert serialized == {
        "status": "SUCCESS",
        "task_id": "test_task_123",
        "score": 85.12,
        "rounds_used": 3,
        "duration_s": 4.57,
        "best_candidate_hash": "abc123hash",
        "best_candidate_preview": "def foo():\n    return 42...",
        "escalation_briefing": "Need more specific types",
    }
