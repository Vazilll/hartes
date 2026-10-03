import pytest
from vazus_core.resilience import (
    resilient_call,
    with_resilience,
    get_circuit_status,
    reset_circuit,
    CircuitOpenError,
)

def test_resilient_call_success():
    def add(a, b):
        return a + b

    result = resilient_call(add, 2, 3, circuit_name="test_add")
    assert result == 5


def test_resilient_call_retry_and_fallback():
    attempts = 0

    def flaky():
        nonlocal attempts
        attempts += 1
        raise ValueError("Simulated network drop")

    fallback_called = False

    def on_fallback():
        nonlocal fallback_called
        fallback_called = True
        return "recovered"

    result = resilient_call(
        flaky,
        circuit_name="test_flaky",
        max_retries=2,
        base_delay=0.01,
        fallback=on_fallback,
    )

    assert attempts == 2
    assert fallback_called is True
    assert result == "recovered"


def test_circuit_breaker_tripping():
    reset_circuit("test_trip")

    def always_fail():
        raise RuntimeError("Outage")

    for _ in range(5):
        resilient_call(always_fail, circuit_name="test_trip", max_retries=1, base_delay=0.01)

    status = get_circuit_status()
    assert status["test_trip"]["state"] == "open"

    # Next call should be blocked immediately by circuit breaker
    with pytest.raises(CircuitOpenError):
        from vazus_core.resilience import _check_circuit
        _check_circuit("test_trip")


def test_with_resilience_decorator():
    @with_resilience(circuit_name="dec_test", max_retries=2, fallback_value="default_val")
    def failing_fn():
        raise ConnectionError("Timeout")

    res = failing_fn()
    assert res == "default_val"
