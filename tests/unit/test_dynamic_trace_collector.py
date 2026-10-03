"""
Unit tests for Layer 2 DynamicTraceCollector (PEP 669 sys.monitoring).
"""

import sys
import time
import pytest
from vazus_core.telemetry.dynamic_trace_collector import DynamicTraceCollector

def _sample_callee_helper(x: int) -> int:
    return x * 2

def _sample_caller_function():
    total = 0
    for i in range(5):
        total += _sample_callee_helper(i)
    return total

def test_dynamic_trace_collector_lifecycle(tmp_path):
    if not hasattr(sys, "monitoring"):
        pytest.skip("PEP 669 sys.monitoring not available")

    test_db = str(tmp_path / "test_trace.db")
    collector = DynamicTraceCollector(db_path=test_db)
    assert collector.start() is True

    # Execute sample functions
    result = _sample_caller_function()
    assert result == 20

    # Stop and flush
    collector.stop()
    assert len(collector.call_edges) == 0  # Flushed to DB

    # Verify hit count in DB
    fqn = collector._format_fqn(_sample_callee_helper.__code__)
    hits = collector.get_hit_count(fqn)
    # Hit count should be >= 5
    assert hits >= 5
