"""
tests/test_hermes_runtime_adapter.py — Unit tests for vazus_core.hermes_runtime_adapter module.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from vazus_core.hermes_runtime_adapter import HermesRuntimeAdapter, HermesSimulatorRunner, HermesOllamaRunner


def test_hermes_simulator_runner():
    sim = HermesSimulatorRunner()
    resp = sim.generate_response(
        system_prompt="Test system",
        user_prompt="Calculate sum of 25 and 17",
        history=[]
    )
    assert "<thinking>" in resp
    assert "<tool_call>" in resp
    assert "calculate_sum" in resp


def test_hermes_runtime_adapter_offline_execution():
    adapter = HermesRuntimeAdapter(force_simulator=True)
    
    # Register tool handler
    adapter.register_tool(
        name="calculate_sum",
        description="Calculates sum of two integers",
        parameters={"properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}},
        handler=lambda a, b: a + b
    )

    res = adapter.run_query(user_prompt="Please calculate math sum of 25 and 17")
    
    assert res["is_local_online"] is False
    assert "Hermes 3 Offline Simulator" in res["mode"]
    assert res["turns_used"] >= 1
    assert len(res["trace"]) >= 1
    assert res["trace"][0]["tool_name"] == "calculate_sum"
    assert res["trace"][0]["tool_result"] == 42


def test_hermes_ollama_runner_availability_check():
    ollama = HermesOllamaRunner(host="http://localhost:99999")  # Non-existent port
    assert ollama.is_available() is False
