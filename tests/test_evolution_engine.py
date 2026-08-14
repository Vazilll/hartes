"""
tests.test_evolution_engine
Unit tests for vazus_core.evolution (Prompt Optimizer, Hebbian Compiler, Darwinian Evolver).
"""

import pytest
from vazus_core.evolution import run_prompt_optimization, compile_hebbian_tool, evaluate_fitness

def test_prompt_optimizer():
    res = run_prompt_optimization("unit_test_prompt", iterations=2)
    assert res["status"] == "SUCCESS"
    assert res["final_fitness"] > 0.85
    assert len(res["history"]) == 2

def test_hebbian_compiler():
    res = compile_hebbian_tool("unit_test_tool", "Unit test description", "def test(): pass")
    assert res["status"] == "COMPILED"
    assert res["tool_name"] == "unit_test_tool"

def test_darwinian_fitness():
    fitness = evaluate_fitness("C:/vazus/vazus_core")
    assert fitness > 0.0, "Fitness should be greater than 0"
