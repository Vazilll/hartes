import os
import sys
import pytest
import time
from unittest.mock import patch, MagicMock

from llm.gemini_planner import _read_api_key, GeminiPlanner, MAX_RETRIES

@pytest.fixture
def mock_genai():
    with patch.dict('sys.modules', {'google.generativeai': MagicMock()}):
        yield sys.modules['google.generativeai']

@pytest.fixture
def clean_env():
    # Remove relevant keys from os.environ
    keys_to_remove = ["GEMINI_API_KEY", "GOOGLE_API_KEY"]
    original_env = {}
    for key in keys_to_remove:
        if key in os.environ:
            original_env[key] = os.environ.pop(key)
    yield
    for key, value in original_env.items():
        os.environ[key] = value

def test_read_api_key_success(clean_env):
    os.environ["GEMINI_API_KEY"] = "test-key"
    assert _read_api_key() == "test-key"

def test_read_api_key_failure(clean_env):
    with pytest.raises(EnvironmentError, match="GEMINI_API_KEY environment variable not set."):
        _read_api_key()

def test_gemini_planner_init_import_error(clean_env):
    os.environ["GEMINI_API_KEY"] = "test-key"
    with patch.dict('sys.modules', {'google.generativeai': None}):
        with pytest.raises(ImportError, match="google-generativeai not installed."):
            GeminiPlanner()

def test_gemini_planner_plan_success(mock_genai, clean_env):
    os.environ["GEMINI_API_KEY"] = "test-key"

    # Mocking the client
    mock_client = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_client

    mock_chat = MagicMock()
    mock_client.start_chat.return_value = mock_chat

    class MockResp:
        pass
    mock_resp = MockResp()
    mock_resp.text = "test response"

    # Mocking usage metadata
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 10
    mock_usage.candidates_token_count = 5
    mock_resp.usage_metadata = mock_usage

    mock_chat.send_message.return_value = mock_resp

    planner = GeminiPlanner()
    history = [{"role": "user", "content": "hello"}, {"role": "model", "content": "hi"}]

    result = planner.plan("test input", history)

    mock_client.start_chat.assert_called_once_with(history=[
        {"role": "user", "parts": ["hello"]},
        {"role": "model", "parts": ["hi"]}
    ])
    mock_chat.send_message.assert_called_once_with("test input")

    assert result["thought"] == ""
    assert "thought_signature" in result
    assert result["response"] == "test response"
    assert result["tool_calls"] == []
    assert result["model"] == "gemini-2.0-flash-lite"
    assert result["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}

@patch('time.sleep')
def test_gemini_planner_plan_retries_and_failure(mock_sleep, mock_genai, clean_env):
    os.environ["GEMINI_API_KEY"] = "test-key"

    mock_client = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_client

    mock_chat = MagicMock()
    mock_client.start_chat.return_value = mock_chat

    # Raise exception on send_message
    mock_chat.send_message.side_effect = Exception("API error")

    planner = GeminiPlanner()

    with pytest.raises(RuntimeError, match=f"Gemini API failed after {MAX_RETRIES} attempts"):
        planner.plan("test input", [])

    assert mock_chat.send_message.call_count == MAX_RETRIES
    assert mock_sleep.call_count == MAX_RETRIES

def test_gemini_planner_call_proxy(mock_genai, clean_env):
    os.environ["GEMINI_API_KEY"] = "test-key"

    mock_client = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_client

    mock_chat = MagicMock()
    mock_client.start_chat.return_value = mock_chat

    class MockResp:
        pass
    mock_resp = MockResp()
    mock_resp.text = "test response"
    mock_resp.usage_metadata = None
    mock_chat.send_message.return_value = mock_resp

    planner = GeminiPlanner()

    # using __call__
    result = planner("test input", [])

    assert result["response"] == "test response"
