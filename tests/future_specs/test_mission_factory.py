"""
Tests for vazus_core.missions.mission_factory.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

from vazus_core.missions.mission_factory import (
    MissionTask,
    MissionValidator,
    MissionFactory,
)


# ── MissionValidator ──────────────────────────────────────────────────────────

class TestMissionValidator:
    def _task(self, keys, fn=None):
        return MissionTask(
            task_id="t1", role="Worker", description="Test task",
            input_payload={}, output_schema_keys=keys, validator_fn=fn
        )

    def test_valid_payload_passes(self):
        task = self._task(["result", "confidence"])
        ok, reason = MissionValidator.validate_payload(task, {"result": "ok", "confidence": 0.9})
        assert ok is True
        assert reason == "OK"

    def test_missing_schema_key_fails(self):
        task = self._task(["result", "confidence"])
        ok, reason = MissionValidator.validate_payload(task, {"result": "ok"})
        assert ok is False
        assert "confidence" in reason

    def test_non_dict_output_fails(self):
        task = self._task(["result"])
        ok, reason = MissionValidator.validate_payload(task, ["result"])
        assert ok is False
        assert "dict" in reason.lower()

    def test_custom_validator_fn_rejection(self):
        task = self._task(["score"], fn=lambda d: d["score"] > 0.8)
        ok, reason = MissionValidator.validate_payload(task, {"score": 0.5})
        assert ok is False
        assert "validator" in reason.lower()

    def test_custom_validator_fn_acceptance(self):
        task = self._task(["score"], fn=lambda d: d["score"] > 0.8)
        ok, _ = MissionValidator.validate_payload(task, {"score": 0.95})
        assert ok is True

    def test_custom_validator_exception_propagated(self):
        def bad_fn(d):
            raise ValueError("internal error")

        task = self._task(["x"], fn=bad_fn)
        ok, reason = MissionValidator.validate_payload(task, {"x": 1})
        assert ok is False
        assert "exception" in reason.lower()


# ── MissionFactory._extract_json ──────────────────────────────────────────────

class TestExtractJson:
    def setup_method(self):
        self.factory = MissionFactory()

    def test_parses_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        result = self.factory._extract_json(text)
        assert result == {"key": "value"}

    def test_parses_raw_json(self):
        text = '{"status": "ok", "count": 42}'
        result = self.factory._extract_json(text)
        assert result["status"] == "ok"

    def test_returns_none_on_invalid(self):
        result = self.factory._extract_json("not json at all {{{")
        assert result is None

    def test_nested_json_fence(self):
        payload = {"nested": {"a": 1}}
        text = f"```json\n{json.dumps(payload)}\n```"
        result = self.factory._extract_json(text)
        assert result["nested"]["a"] == 1


# ── MissionFactory.execute_mission ────────────────────────────────────────────

class TestExecuteMission:
    def _make_task(self, task_id: str, keys: list, payload: dict = None) -> MissionTask:
        return MissionTask(
            task_id=task_id,
            role="Analyst",
            description=f"Task {task_id}",
            input_payload=payload or {},
            output_schema_keys=keys,
        )

    def test_success_single_task(self):
        factory = MissionFactory()
        task = self._make_task("t1", ["summary"])

        llm_resp = '```json\n{"summary": "Analysis complete."}\n```'
        with patch(
            "vazus_core.missions.mission_factory.async_generate_llm",
            new=AsyncMock(return_value=llm_resp),
        ):
            result = asyncio.run(factory.execute_mission([task]))

        assert result["status"] == "SUCCESS"
        assert result["tasks_completed"] == 1
        assert task.status == "VALIDATED"

    def test_state_propagates_between_tasks(self):
        factory = MissionFactory()
        t1 = self._make_task("t1", ["analysis_result"])
        t2 = self._make_task("t2", ["final_report"])

        responses = [
            '```json\n{"analysis_result": "data processed"}\n```',
            '```json\n{"final_report": "report generated"}\n```',
        ]
        with patch(
            "vazus_core.missions.mission_factory.async_generate_llm",
            new=AsyncMock(side_effect=responses),
        ):
            result = asyncio.run(factory.execute_mission([t1, t2]))

        assert result["status"] == "SUCCESS"
        assert result["tasks_completed"] == 2
        assert "analysis_result" in result["mission_state"]
        assert "final_report" in result["mission_state"]

    def test_invalid_json_causes_failed(self):
        factory = MissionFactory()
        task = self._make_task("t1", ["result"])

        with patch(
            "vazus_core.missions.mission_factory.async_generate_llm",
            new=AsyncMock(return_value="Not valid JSON at all"),
        ):
            result = asyncio.run(factory.execute_mission([task]))

        assert result["status"] == "FAILED"
        assert result["failed_task"] == "t1"

    def test_missing_schema_key_causes_validation_error(self):
        factory = MissionFactory()
        task = self._make_task("t1", ["required_key"])

        with patch(
            "vazus_core.missions.mission_factory.async_generate_llm",
            new=AsyncMock(return_value='```json\n{"wrong_key": "oops"}\n```'),
        ):
            result = asyncio.run(factory.execute_mission([task]))

        assert result["status"] == "VALIDATION_ERROR"
        assert "required_key" in result["reason"]

    def test_empty_task_list_succeeds(self):
        factory = MissionFactory()
        result = asyncio.run(factory.execute_mission([]))
        assert result["status"] == "SUCCESS"
        assert result["tasks_completed"] == 0
