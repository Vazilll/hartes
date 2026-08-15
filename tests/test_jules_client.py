"""
tests/test_jules_client.py -- Unit tests for Google Jules REST API Client & Pipeline Fallback.
"""

import os
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from vazus_core.jules_client import (
    JulesClient,
    JulesSource,
    JulesSessionRequest,
    JulesSession,
    JulesActivity
)
from vazus_core.unified_reasoning_pipeline import UnifiedReasoningPipeline


def test_jules_dataclasses():
    """Verify dataclasses and dict conversion helpers."""
    source_dict = {
        "id": "src-001",
        "name": "sources/src-001",
        "repositoryUrl": "https://github.com/vazus/vazus",
        "defaultBranch": "main"
    }
    src = JulesSource.from_dict(source_dict)
    assert src.id == "src-001"
    assert src.repository_url == "https://github.com/vazus/vazus"
    assert src.default_branch == "main"

    req = JulesSessionRequest(
        source_id="vazus-main",
        prompt="Verify contracts",
        title="Precommit Check"
    )
    req_dict = req.to_dict()
    assert req_dict["prompt"] == "Verify contracts"
    assert req_dict["title"] == "Precommit Check"

    sess_dict = {
        "name": "sessions/sess-999",
        "state": "SUCCEEDED",
        "source": "sources/vazus-main",
        "title": "Analysis Session"
    }
    sess = JulesSession.from_dict(sess_dict)
    assert sess.id == "sess-999"
    assert sess.state == "SUCCEEDED"
    assert sess.source_id == "vazus-main"

    act_dict = {
        "name": "activities/act-1",
        "activityType": "ANALYSIS",
        "status": "SUCCESS",
        "message": "Step completed"
    }
    act = JulesActivity.from_dict(act_dict, session_id="sess-999")
    assert act.id == "act-1"
    assert act.session_id == "sess-999"
    assert act.activity_type == "ANALYSIS"


def test_client_missing_api_key_fallback():
    """Verify JulesClient returns fallback signals when JULES_API_KEY is not set."""
    async def _test():
        with patch.dict(os.environ, {"JULES_API_KEY": ""}):
            client = JulesClient(api_key=None)

            sources_res = await client.list_sources_async()
            assert sources_res["fallback"] is True
            assert "JULES_API_KEY is not set" in sources_res["reason"]

            create_res = await client.create_session_async("vazus-main", "Test prompt")
            assert create_res["fallback"] is True
            assert create_res["session"] is None

            get_res = await client.get_session_async("sess-123")
            assert get_res["fallback"] is True

            act_res = await client.list_activities_async("sess-123")
            assert act_res["fallback"] is True

            precommit_res = await client.verify_precommit_cloud_async("def foo(): pass", "Task prompt")
            assert precommit_res["fallback"] is True
            assert precommit_res["verified"] is False

    asyncio.run(_test())


def test_list_sources_success_and_rate_limit():
    """Verify list_sources_async handles HTTP 200 and HTTP 429 rate limits."""
    async def _test():
        client = JulesClient(api_key="test-api-key")

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {
            "sources": [
                {"id": "src-1", "name": "sources/src-1", "repositoryUrl": "https://github.com/vazus/repo1"}
            ]
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp_200
            res = await client.list_sources_async()
            assert res["fallback"] is False
            assert len(res["sources"]) == 1
            assert res["sources"][0].id == "src-1"

        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.text = "Rate Limit Exceeded"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp_429
            res = await client.list_sources_async()
            assert res["fallback"] is True
            assert "HTTP 429" in res["reason"]

    asyncio.run(_test())


def test_session_lifecycle_management():
    """Verify session creation, polling, and activities listing (httpx fully mocked).

    VAZUS_JULES_LIVE=1 opts out of the pytest offline guard so the mocked
    request path itself is exercised without any real network traffic.
    """
    async def _test():
        client = JulesClient(api_key="test-api-key")

        with patch.dict(os.environ, {"VAZUS_JULES_LIVE": "1"}):
            mock_post_resp = MagicMock()
            mock_post_resp.status_code = 201
            mock_post_resp.json.return_value = {
                "name": "sessions/sess-100",
                "state": "PENDING",
                "source": "sources/vazus-main",
                "title": "Cloud VM Verification"
            }

            mock_get_resp = MagicMock()
            mock_get_resp.status_code = 200
            mock_get_resp.json.return_value = {
                "name": "sessions/sess-100",
                "state": "SUCCEEDED",
                "source": "sources/vazus-main"
            }

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_post_resp
                create_res = await client.create_session_async("vazus-main", "Verify patch")
                assert create_res["fallback"] is False
                assert create_res["session"].id == "sess-100"
                assert create_res["session"].state == "PENDING"

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_get_resp
                get_res = await client.get_session_async("sess-100")
                assert get_res["fallback"] is False
                assert get_res["session"].state == "SUCCEEDED"

    asyncio.run(_test())


def test_network_error_handling():
    """Verify client captures network exceptions and signals fallback."""
    async def _test():
        client = JulesClient(api_key="test-api-key")

        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
            res = await client.list_sources_async()
            assert res["fallback"] is True
            assert "Network error" in res["reason"]

    asyncio.run(_test())


def test_unified_pipeline_jules_fallback_integration():
    """Verify UnifiedReasoningPipeline gracefully falls back when Jules API key is absent."""
    async def _test():
        pipeline = UnifiedReasoningPipeline(effort_level="low")

        with patch.dict(os.environ, {"JULES_API_KEY": ""}, clear=True):
            pipeline.jules_client.api_key = None

            result = await pipeline.execute_pipeline(
                task_prompt="Implement Jules client integration",
                code_proposal="def add(a: int, b: int) -> int:\n    return a + b\n"
            )

            assert result["jules_verification"]["fallback"] is True
            assert result["status"] in ("APPROVED", "REJECTED")
            assert "smt_verification" in result
            assert "jury_result" in result

    asyncio.run(_test())