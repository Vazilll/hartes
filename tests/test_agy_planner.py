import hashlib
import pytest
from typing import Dict, Any

from llm.agy_planner import generate_mock_plan

def test_generate_mock_plan_standard_prompt():
    """Test standard prompt that doesn't trigger code generation."""
    user_input = "Hello, what is your name?"
    model_name = "flash-lite"

    result = generate_mock_plan(user_input, model_name)

    assert result["model"] == model_name
    assert result["thought"] == "Deterministic offline test planning"
    assert result["response"] == f"[MOCK] AgyPlanner response for prompt ({model_name})"
    assert result["tool_calls"] == []

    expected_sig = hashlib.sha256(result["response"].encode()).hexdigest()[:16]
    assert result["thought_signature"] == expected_sig

    assert result["usage"]["prompt_tokens"] == len(user_input) // 4
    assert result["usage"]["completion_tokens"] == len(result["response"]) // 4

def test_generate_mock_plan_optimize_with_code_block():
    """Test optimize prompt containing a markdown Python code block."""
    code_snippet = "def my_func():\n    pass"
    user_input = f"Please optimize this:\n```python\n{code_snippet}\n```"
    model_name = "pro"

    result = generate_mock_plan(user_input, model_name)

    expected_repaired = f"# Optimized by AgyPlanner (Test Mode)\n{code_snippet}\n"
    expected_response = f"```python\n{expected_repaired}```"

    assert result["response"] == expected_response
    assert result["model"] == model_name

    expected_sig = hashlib.sha256(result["response"].encode()).hexdigest()[:16]
    assert result["thought_signature"] == expected_sig

def test_generate_mock_plan_def_without_code_block():
    """Test prompt containing 'def ' but no markdown code block."""
    user_input = "def my_func():\n    return 42"
    model_name = "flash"

    result = generate_mock_plan(user_input, model_name)

    expected_repaired = f"# Optimized by AgyPlanner (Test Mode)\n{user_input}\n"
    expected_response = f"```python\n{expected_repaired}```"

    assert result["response"] == expected_response
    assert result["model"] == model_name

def test_generate_mock_plan_optimize_without_code_block_or_def():
    """Test optimize prompt without any code blocks or 'def '."""
    user_input = "Optimize this random text that doesn't have a function."
    model_name = "sonnet"

    result = generate_mock_plan(user_input, model_name)

    expected_response = (
        "```python\n"
        "# Optimized by AgyPlanner (Test Mode)\n"
        "def optimized_func(*args, **kwargs):\n"
        "    return True\n"
        "```"
    )

    assert result["response"] == expected_response
    assert result["model"] == model_name

def test_generate_mock_plan_structural_integrity():
    """Test the structure of the returned dictionary."""
    user_input = "test input"
    model_name = "test-model"

    result = generate_mock_plan(user_input, model_name)

    assert isinstance(result, dict)
    assert "thought" in result
    assert "thought_signature" in result
    assert "response" in result
    assert "tool_calls" in result
    assert "model" in result
    assert "usage" in result

    assert isinstance(result["usage"], dict)
    assert "prompt_tokens" in result["usage"]
    assert "completion_tokens" in result["usage"]

    # Check signature is 16 chars long hex
    assert len(result["thought_signature"]) == 16
    int(result["thought_signature"], 16) # Should not raise ValueError
