import os
from unittest import mock
import pytest

from llm.gemini_planner import GeminiPlanner

def test_gemini_planner_api_error_retry():
    """
    Test that GeminiPlanner correctly handles API errors, retries the specified
    number of times with exponential backoff, and ultimately raises a RuntimeError
    if all attempts fail.
    """
    with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"}):
        with mock.patch("llm.gemini_planner.GeminiPlanner._build_client") as mock_build_client:
            mock_client = mock.Mock()
            mock_build_client.return_value = mock_client

            mock_chat = mock.Mock()
            mock_client.start_chat.return_value = mock_chat

            # Make the API call raise an exception on every attempt
            mock_chat.send_message.side_effect = Exception("Test API Error")

            # Make sure we also mock models in case it is accessed via client.models
            mock_models = mock.Mock()
            mock_client.models = mock_models
            mock_models.generate_content.side_effect = Exception("Test API Error")

            planner = GeminiPlanner()

            # Mock time.sleep to avoid actually waiting during the test
            with mock.patch("llm.gemini_planner.time.sleep") as mock_sleep:
                with pytest.raises(RuntimeError, match="Gemini API failed after 3 attempts: Test API Error"):
                    planner.plan("test input", [])

                # Check that we slept with exponential backoff
                # RETRY_BACKOFF_S is 2.0. So wait times: 2.0 * 2^0, 2.0 * 2^1, 2.0 * 2^2 -> 2.0, 4.0, 8.0
                assert mock_sleep.call_args_list == [mock.call(2.0), mock.call(4.0), mock.call(8.0)]
