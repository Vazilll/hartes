"""Regression tests for bounded, fail-closed Gate-4 critic-jury calls."""

from __future__ import annotations

import asyncio
import time

from vazus_core.verification import critic_jury


def test_critic_jury_total_timeout_abstains_without_hanging(monkeypatch):
    async def slow_llm(**_kwargs):
        await asyncio.sleep(60)
        return '{"files": {"vazus_core/example.py": {"verdict": "CONFIRM", "issue": ""}}}'

    monkeypatch.setattr("vazus_core.engine.llm_client.async_generate_llm", slow_llm)
    items = [{
        "path": "vazus_core/example.py",
        "proposal": "def example():\n    return 1\n",
        "evidence": "UNVERIFIED",
    }]

    started = time.monotonic()
    result = critic_jury.run_critic_jury_batches_sync(
        items,
        models=["test-a", "test-b"],
        timeout_seconds=0.05,
    )
    elapsed = time.monotonic() - started

    verdict = result["verdicts"]["vazus_core/example.py"]
    assert elapsed < 1.0
    assert verdict["verdict"] == "ABSTAIN"
    assert verdict["approved"] is False
    assert "timeout" in verdict["issue"].lower()
    assert result["fail_closed"] is True
