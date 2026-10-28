import pytest
import sys
import argparse
from unittest.mock import patch, MagicMock

import runner
from tasks.base import TaskStatus, TaskResult

def test_build_parser_list():
    parser = runner._build_parser()
    args = parser.parse_args(["list"])
    assert args.command == "list"

def test_build_parser_run():
    parser = runner._build_parser()
    args = parser.parse_args(["run", "--task", "my_task", "--inline", "code", "--model", "gpt", "--rounds", "10"])
    assert args.command == "run"
    assert args.task == "my_task"
    assert args.inline_code == "code"
    assert args.model == "gpt"
    assert args.rounds == 10

def test_build_parser_daemon():
    parser = runner._build_parser()
    args = parser.parse_args(["daemon", "--interval", "10", "--max-cycles", "5"])
    assert args.command == "daemon"
    assert args.interval == 10.0
    assert args.max_cycles == 5

def test_main_list_command(capsys, monkeypatch):
    from tasks.registry import TaskRegistry
    monkeypatch.setattr(TaskRegistry, "list_available", lambda: ["task_a", "task_b"])

    assert runner.main(["list"]) == runner.EXIT_SUCCESS
    out, err = capsys.readouterr()
    assert "task_a" in out
    assert "task_b" in out

@patch("runner.run")
def test_main_run_success(mock_run, capsys):
    mock_run.return_value = {
        "status": "SUCCESS",
        "task_id": "test",
        "score": 100.0,
        "rounds_used": 1,
        "duration_s": 0.5,
        "best_candidate_preview": "def foo(): pass",
        "escalation_briefing": None
    }

    assert runner.main(["run", "--task", "test_task"]) == runner.EXIT_SUCCESS
    mock_run.assert_called_once_with(
        task_name="test_task",
        max_rounds=5, # default
        model=runner.DEFAULT_MODEL
    )

    out, err = capsys.readouterr()
    assert "Status : SUCCESS" in out
    assert "Score  : 100.0/100.0" in out

@patch("runner.run")
def test_main_run_error(mock_run, capsys):
    mock_run.side_effect = Exception("Internal error")

    assert runner.main(["run", "--task", "test_task"]) == runner.EXIT_ERROR

@patch("vazus_autonomous_harness.daemon.autonomous_flywheel.AutonomousFlywheelDaemon")
def test_main_daemon(mock_daemon):
    mock_instance = MagicMock()
    mock_daemon.return_value = mock_instance

    assert runner.main(["daemon", "--interval", "15"]) == runner.EXIT_SUCCESS
    mock_daemon.assert_called_once_with(interval_seconds=15.0, model=runner.DEFAULT_MODEL, max_cycles=None)
    mock_instance.start.assert_called_once()
