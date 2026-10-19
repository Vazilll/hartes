"""
Tests for vazus_core.missions.circuit_breaker and vazus_core.missions.verifiable_ledger.
"""

import time
import tempfile
from pathlib import Path
from vazus_core.missions.circuit_breaker import AgentCircuitBreaker, CircuitState
from vazus_core.missions.verifiable_ledger import VerifiableLedger


def test_circuit_breaker_flow():
    cb = AgentCircuitBreaker(failure_threshold=2, recovery_timeout_sec=0.2)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True

    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True

    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    # Wait for recovery timeout
    time.sleep(0.25)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


def test_verifiable_ledger_hash_chain():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_vazus.db"
        ledger = VerifiableLedger(db_path=db_path)

        rec1 = ledger.record_handoff(
            mission_id="m1",
            task_id="t1",
            role="Worker1",
            input_payload={"query": "test"},
            output_payload={"code": "def foo(): pass"}
        )
        assert rec1.record_hash != ""
        assert rec1.previous_record_hash == "GENESIS_BLOCK_0000000000000000"

        rec2 = ledger.record_handoff(
            mission_id="m1",
            task_id="t2",
            role="Verifier",
            input_payload={"code": "def foo(): pass"},
            output_payload={"verified": True}
        )
        assert rec2.record_hash != ""
        assert rec2.previous_record_hash == rec1.record_hash
