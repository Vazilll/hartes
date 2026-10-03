"""
tests/test_j_space_tool_dispatcher.py
======================================
Unit & Integration Tests for NPU Speculative Tool Dispatcher & J-Space Tool Indexer.

Verifies:
1. Fast response time of Julia-1 ONNX classifier + J-Space latent search (< 50 ms).
2. Activation accuracy (sandbox query activates vazus-sandbox, backup query activates db_backup).
3. Directive formatting for LLM context (⚡ [J-Space NPU Tool Activation]: ...).
4. Direct class and instance queries on JSpaceToolIndexer.find_tools_for_query.
5. Pre-invocation hook integration on Turn 0 and Turn > 0.
"""

import sys
import time
import pytest
from pathlib import Path

# Ensure vazus root in path
ROOT_DIR = Path("C:/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.engine.j_space_tool_dispatcher import (
    ToolMatch,
    JSpaceToolIndexer,
    JSpaceToolDispatcher,
    DispatchResult,
    format_tool_directive,
    get_default_dispatcher,
    dispatch_tools,
)
from vazus_core.hooks.pre_invocation_hook import run_pre_invocation_hook


@pytest.fixture(scope="module")
def dispatcher():
    """Initializes and warms up the JSpaceToolDispatcher singleton."""
    disp = get_default_dispatcher()
    # Warmup invocation to preload OpenVINO / ONNX runtime graphs
    disp.dispatch("warmup query test")
    return disp


def test_indexer_find_tools_for_query_sandbox():
    """Verifies that a sandbox-related query accurately activates vazus-sandbox."""
    query = "создай песочницу для тестирования изоляции кода"
    matches = JSpaceToolIndexer.find_tools_for_query(query, top_k=3, min_similarity=0.35)

    assert len(matches) > 0, f"Expected matches for '{query}', got empty list"
    assert matches[0].name == "vazus-sandbox", f"Expected top tool 'vazus-sandbox', got '{matches[0].name}'"
    assert matches[0].similarity >= 0.35, f"Similarity {matches[0].similarity} must be >= 0.35"
    assert "Windows Sandbox" in matches[0].description


def test_indexer_find_tools_for_query_backup():
    """Verifies that a database backup query accurately activates db_backup."""
    query = "сделай бэкап базы данных vazus.db"
    matches = JSpaceToolIndexer.find_tools_for_query(query, top_k=3, min_similarity=0.35)

    assert len(matches) > 0, f"Expected matches for '{query}', got empty list"
    assert matches[0].name == "db_backup", f"Expected top tool 'db_backup', got '{matches[0].name}'"
    assert matches[0].similarity >= 0.35, f"Similarity {matches[0].similarity} must be >= 0.35"
    assert "SQLite" in matches[0].description or "backup" in matches[0].description.lower()


def test_indexer_negative_irrelevant_query():
    """Verifies that completely unrelated queries do not trigger any tool activation."""
    query = "какая погода сегодня в Санкт-Петербурге на Марсе"
    matches = JSpaceToolIndexer.find_tools_for_query(query, top_k=3, min_similarity=0.35)

    assert len(matches) == 0, f"Expected 0 matches for irrelevant query, got: {[m.name for m in matches]}"


def test_dispatcher_accuracy_and_directive_formatting(dispatcher):
    """Verifies the exact formatting of the micro-directive for model context injection."""
    # 1. Sandbox directive
    sandbox_res = dispatcher.dispatch("запусти тесты в изолированной песочнице")
    assert sandbox_res.startswith("⚡ [J-Space NPU Tool Activation]: "), f"Invalid prefix: {sandbox_res}"
    assert "vazus-sandbox" in sandbox_res
    assert "(" in sandbox_res and ")" in sandbox_res

    # 2. Backup directive
    backup_res = dispatcher.dispatch("сохрани резервную копию и сделай бэкап базы")
    assert backup_res.startswith("⚡ [J-Space NPU Tool Activation]: "), f"Invalid prefix: {backup_res}"
    assert "db_backup" in backup_res

    # 3. Irrelevant prompt yields empty string
    irr_res = dispatcher.dispatch("напиши рецепт яблочного пирога")
    assert irr_res == "", f"Expected empty directive for cooking recipe, got: {irr_res}"


def test_format_tool_directive_helper():
    """Verifies format_tool_directive with multiple tool matches."""
    m1 = ToolMatch(
        name="vazus-sandbox",
        description="Windows Sandbox isolated execution",
        similarity=0.92,
        domain="code",
    )
    m2 = ToolMatch(
        name="db_backup",
        description="Automated SQLite database backup",
        similarity=0.88,
        domain="system_architecture",
    )

    formatted = format_tool_directive([m1, m2])
    assert formatted.startswith("⚡ [J-Space NPU Tool Activation]: ")
    assert "vazus-sandbox (Windows Sandbox isolated execution)" in formatted
    assert "db_backup (Automated SQLite database backup)" in formatted
    assert ", " in formatted

    # Empty list
    assert format_tool_directive([]) == ""


def test_fast_response_time_under_50ms(dispatcher):
    """
    Verifies that the NPU-accelerated classifier + J-Space latent search
    completes in < 50 ms (and typically < 20 ms on Intel AI Boost NPU).
    """
    sample_queries = [
        "создай песочницу для тестирования",
        "сделай бэкап базы данных vazus.db",
        "проверь задолженности по матанализу в мирэа",
        "посмотри расходы в тинькофф и налог самозанятости",
    ]

    for q in sample_queries:
        t0 = time.perf_counter()
        result = dispatcher.dispatch_detailed(q)
        wall_time_ms = (time.perf_counter() - t0) * 1000.0

        # Assert wall clock latency is under the 50 ms SLA requirement
        assert wall_time_ms < 50.0, f"Query '{q}' took {wall_time_ms:.2f} ms (expected < 50 ms)"
        assert result.latency_ms < 50.0, f"Internal latency {result.latency_ms} ms >= 50 ms"


def test_empty_and_whitespace_prompts(dispatcher):
    """Verifies that empty or whitespace prompts safely return empty directives without exceptions."""
    assert dispatcher.dispatch("") == ""
    assert dispatcher.dispatch("   ") == ""
    assert dispatcher.dispatch("\n\t  \n") == ""
    detailed = dispatcher.dispatch_detailed("")
    assert detailed.directive == ""
    assert len(detailed.matches) == 0


def test_pre_invocation_hook_integration_turn_0_and_turn_n():
    """
    Verifies that pre_invocation_hook correctly injects the J-Space tool directive
    on both Turn 0 (with memory/skills) and Turn > 0 (lean micro-directive).
    """
    import asyncio

    async def _test():
        # 1. Turn 0: Sandbox query
        res_turn0 = await run_pre_invocation_hook(
            session_id="test_session_turn0",
            user_prompt="создай песочницу для изоляции тестов",
            turn_index=0,
        )
        assert res_turn0["status"] == "SUCCESS"
        assert "vazus-sandbox" in res_turn0["injected_context"]
        assert "⚡ [J-Space NPU Tool Activation]:" in res_turn0["injected_context"]
        assert "vazus-sandbox" in res_turn0.get("j_space_tool_directive", "")

        # 2. Turn 1 (Turn > 0): Backup query
        res_turn1 = await run_pre_invocation_hook(
            session_id="test_session_turn1",
            user_prompt="сделай бэкап базы данных vazus.db",
            turn_index=1,
        )
        assert res_turn1["status"] == "SUCCESS"
        assert "db_backup" in res_turn1["injected_context"]
        assert "⚡ [J-Space NPU Tool Activation]:" in res_turn1["injected_context"]
        assert "db_backup" in res_turn1.get("j_space_tool_directive", "")

        # 3. Turn 2 (Turn > 0): Irrelevant query (must NOT inject anything to avoid context bloat)
        res_turn2 = await run_pre_invocation_hook(
            session_id="test_session_turn2",
            user_prompt="какая погода в Риме",
            turn_index=2,
        )
        assert res_turn2["status"] == "SUCCESS"
        assert res_turn2["injected_context"] == ""
        assert res_turn2.get("j_space_tool_directive", "") == ""

    asyncio.run(_test())


def test_custom_tool_registration():
    """Verifies that custom tools can be registered into an isolated indexer."""
    custom_indexer = JSpaceToolIndexer(auto_bootstrap=False)
    custom_indexer.register_tool(
        name="custom_profiler",
        description="High-frequency CPU cache miss profiler",
        tags=["профайлер", "profiler", "cache miss", "кэш", "память"],
        domain="code",
        category="diagnostics",
    )

    matches = custom_indexer.find_tools("запусти профайлер кэша памяти", top_k=2, min_similarity=0.35)
    assert len(matches) == 1
    assert matches[0].name == "custom_profiler"
    assert matches[0].category == "diagnostics"
    assert matches[0].similarity >= 0.35
