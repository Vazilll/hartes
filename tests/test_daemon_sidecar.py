"""
test_daemon_sidecar.py — Test suite for DaemonSidecar (transcript watcher).

Tests module import, class instantiation, and core methods.
"""

from vazus_core.workers.daemon_sidecar import DaemonSidecar, TranscriptEvent


def test_daemon_sidecar_instantiation(tmp_path):
    """Verify DaemonSidecar can be instantiated with default args."""
    ds = DaemonSidecar(cli_dir=str(tmp_path))
    assert ds is not None


def test_daemon_sidecar_status(tmp_path):
    """Verify DaemonSidecar.status() returns a dict with expected keys."""
    ds = DaemonSidecar(cli_dir=str(tmp_path))
    status = ds.status()
    assert isinstance(status, dict)
    assert "status" in status


def test_transcript_event_dataclass():
    """Verify TranscriptEvent dataclass works."""
    evt = TranscriptEvent(
        conversation_id="test-conv-123",
        step_idx=0,
        user_input="hello",
        tool_calls=[],
    )
    assert evt.conversation_id == "test-conv-123"
    d = evt.to_dict()
    assert isinstance(d, dict)
    assert d["conversation_id"] == "test-conv-123"
    assert d["step_idx"] == 0


def test_daemon_sidecar_trigger_auto_improver(tmp_path):
    """Verify DaemonSidecar.trigger_auto_improver_if_needed works without raising."""
    ds = DaemonSidecar(cli_dir=str(tmp_path))
    res = ds.trigger_auto_improver_if_needed(force=False)
    assert isinstance(res, dict)
    assert "triggered" in res

