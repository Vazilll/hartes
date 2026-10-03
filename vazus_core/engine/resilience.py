"""
resilience.py — Circuit breaker, retry, and fallback utilities for Vazus OS.

Addresses Critical Blind Spot #1: All external calls (Cloud Run, Jules API,
MCP subprocess, Google Drive sync) have zero retry logic. A single timeout
silently kills the entire chain.

Usage:
    from vazus_core.resilience import resilient_call, resilient_subprocess

    # For HTTP calls
    result = resilient_call(requests.get, "https://api.example.com/health", timeout=5)

    # For subprocess MCP calls
    output = resilient_subprocess(["python", "mcp_client.py", "server", "tool", "{}"])
"""

import logging
import subprocess
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger("resilience")

T = TypeVar("T")

# ── Circuit Breaker State ──────────────────────────────────────────────
# Simple in-process circuit breaker. Not distributed, but sufficient for
# single-machine Vazus OS.

_circuit_state: Dict[str, Dict[str, Any]] = {}

CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_RECOVERY_TIMEOUT = 60  # seconds
CIRCUIT_HALF_OPEN_MAX = 1


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and requests are blocked."""

    pass


def _get_circuit(name: str) -> Dict[str, Any]:
    if name not in _circuit_state:
        _circuit_state[name] = {
            "state": "closed",  # closed, open, half-open
            "failure_count": 0,
            "last_failure_time": 0.0,
            "success_count": 0,
        }
    return _circuit_state[name]


def _check_circuit(name: str) -> None:
    """Check if circuit allows the call. Raises CircuitOpenError if not."""
    circuit = _get_circuit(name)

    if circuit["state"] == "closed":
        return

    if circuit["state"] == "open":
        elapsed = time.monotonic() - circuit["last_failure_time"]
        if elapsed >= CIRCUIT_RECOVERY_TIMEOUT:
            circuit["state"] = "half-open"
            circuit["success_count"] = 0
            logger.info("Circuit '%s' transitioning to half-open after %ds", name, int(elapsed))
            return
        raise CircuitOpenError(f"Circuit '{name}' is OPEN. {int(CIRCUIT_RECOVERY_TIMEOUT - elapsed)}s until retry.")

    # half-open — allow limited calls
    return


def _record_success(name: str) -> None:
    circuit = _get_circuit(name)
    if circuit["state"] == "half-open":
        circuit["success_count"] += 1
        if circuit["success_count"] >= CIRCUIT_HALF_OPEN_MAX:
            circuit["state"] = "closed"
            circuit["failure_count"] = 0
            logger.info("Circuit '%s' CLOSED (recovered)", name)
    else:
        circuit["failure_count"] = max(0, circuit["failure_count"] - 1)


def _record_failure(name: str) -> None:
    circuit = _get_circuit(name)
    circuit["failure_count"] += 1
    circuit["last_failure_time"] = time.monotonic()

    if circuit["state"] == "half-open":
        circuit["state"] = "open"
        logger.warning("Circuit '%s' re-OPENED from half-open", name)
    elif circuit["failure_count"] >= CIRCUIT_FAILURE_THRESHOLD:
        circuit["state"] = "open"
        logger.warning("Circuit '%s' OPENED after %d consecutive failures", name, circuit["failure_count"])


def get_circuit_status() -> Dict[str, Dict[str, Any]]:
    """Returns current state of all circuit breakers (for HUD/monitoring)."""
    return {k: dict(v) for k, v in _circuit_state.items()}


def reset_circuit(name: str) -> None:
    """Manually reset a circuit breaker to closed state."""
    if name in _circuit_state:
        _circuit_state[name] = {
            "state": "closed",
            "failure_count": 0,
            "last_failure_time": 0.0,
            "success_count": 0,
        }
        logger.info("Circuit '%s' manually reset", name)


# ── Retry with Exponential Backoff ─────────────────────────────────────


def resilient_call(
    func: Callable[..., T],
    *args: Any,
    circuit_name: Optional[str] = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    fallback: Optional[Callable[..., T]] = None,
    **kwargs: Any,
) -> Optional[T]:
    """
    Execute a callable with retry + exponential backoff + circuit breaker.

    Args:
        func: The function to call.
        circuit_name: Name for circuit breaker tracking. Auto-derived if None.
        max_retries: Maximum retry attempts (default: 3).
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay cap.
        fallback: Optional fallback function called if all retries fail.
        *args, **kwargs: Passed to func.

    Returns:
        Result of func, or fallback result, or None.
    """
    name = circuit_name or getattr(func, "__name__", "unknown")

    # Check circuit breaker
    try:
        _check_circuit(name)
    except CircuitOpenError as e:
        logger.warning("Skipping call: %s", e)
        if fallback:
            return fallback(*args, **kwargs)
        return None

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            result = func(*args, **kwargs)
            _record_success(name)
            return result
        except Exception as e:
            last_error = e
            _record_failure(name)
            if attempt < max_retries:
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                logger.warning(
                    "Retry %d/%d for '%s' after error: %s (delay: %.1fs)", attempt, max_retries, name, e, delay
                )
                time.sleep(delay)

    logger.error("All %d retries exhausted for '%s': %s", max_retries, name, last_error)

    if fallback:
        try:
            return fallback(*args, **kwargs)
        except Exception as fb_err:
            logger.error("Fallback also failed for '%s': %s", name, fb_err)

    return None


def resilient_subprocess(
    cmd: list,
    circuit_name: str = "mcp_subprocess",
    timeout: float = 30.0,
    max_retries: int = 2,
) -> Optional[str]:
    """
    Execute a subprocess with retry and circuit breaker.

    Used for MCP tool calls that go through subprocess.Popen/run.

    Returns:
        stdout as string, or None on failure.
    """

    def _run():
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Exit code {result.returncode}: {result.stderr[:200]}")
        return result.stdout

    return resilient_call(
        _run,
        circuit_name=circuit_name,
        max_retries=max_retries,
        base_delay=2.0,
        max_delay=15.0,
    )


# ── Decorator for easy integration ────────────────────────────────────


def with_resilience(
    circuit_name: Optional[str] = None,
    max_retries: int = 3,
    fallback_value: Any = None,
):
    """
    Decorator that adds retry + circuit breaker to any function.

    Example:
        @with_resilience(circuit_name="jules_api", max_retries=3)
        def check_jules_tasks():
            ...
    """

    def decorator(func: Callable) -> Callable:
        name = circuit_name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            def _fallback(*a, **kw):
                return fallback_value

            return resilient_call(
                func,
                *args,
                circuit_name=name,
                max_retries=max_retries,
                fallback=_fallback if fallback_value is not None else None,
                **kwargs,
            )

        return wrapper

    return decorator
