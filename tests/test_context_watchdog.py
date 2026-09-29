"""
test_context_watchdog.py — Test Suite for ContextWatchdog Worker.
==================================================================
"""

import json
from pathlib import Path

from vazus_core.workers.context_watchdog import ContextWatchdog


def _create_mock_session(brain_dir: Path, session_id: str, user_turn_count: int, char_padding: int = 100):
    logs_dir = brain_dir / session_id / ".system_generated" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    transcript_file = logs_dir / "transcript.jsonl"

    with open(transcript_file, "w", encoding="utf-8") as f:
        for i in range(user_turn_count):
            entry = {
                "step_index": i,
                "type": "USER_INPUT",
                "content": f"User query number {i} " + ("x" * char_padding),
            }
            f.write(json.dumps(entry) + "\n")


def test_context_watchdog_instantiation():
    """Verify default initialization."""
    cw = ContextWatchdog()
    assert cw.warn_turns == 15
    assert cw.compress_turns == 25
    assert cw.warn_chars == 70_000


def test_context_watchdog_healthy_session(tmp_path):
    """Verify small session is rated HEALTHY."""
    _create_mock_session(tmp_path, "session_small", user_turn_count=5)
    cw = ContextWatchdog(brain_dir=tmp_path)
    res = cw.inspect_session("session_small")

    assert res["status"] == "OK"
    assert res["user_turns"] == 5
    assert res["level"] == "HEALTHY"
    assert res["needs_compression"] is False


def test_context_watchdog_warn_session(tmp_path):
    """Verify session above warn threshold is rated WARN."""
    _create_mock_session(tmp_path, "session_warn", user_turn_count=16)
    cw = ContextWatchdog(brain_dir=tmp_path)
    res = cw.inspect_session("session_warn")

    assert res["status"] == "OK"
    assert res["user_turns"] == 16
    assert res["level"] == "WARN"
    assert res["needs_compression"] is False


def test_context_watchdog_critical_session(tmp_path):
    """Verify session above compress threshold triggers CRITICAL_COMPRESS."""
    _create_mock_session(tmp_path, "session_critical", user_turn_count=26)
    cw = ContextWatchdog(brain_dir=tmp_path)
    res = cw.inspect_session("session_critical")

    assert res["status"] == "OK"
    assert res["user_turns"] == 26
    assert res["level"] == "CRITICAL_COMPRESS"
    assert res["needs_compression"] is True


def test_context_watchdog_missing_transcript(tmp_path):
    """Verify missing session transcript is handled cleanly without exceptions."""
    cw = ContextWatchdog(brain_dir=tmp_path)
    res = cw.inspect_session("non_existent_session")

    assert res["status"] == "NOT_FOUND"
    assert res["level"] == "HEALTHY"
    assert res["needs_compression"] is False
