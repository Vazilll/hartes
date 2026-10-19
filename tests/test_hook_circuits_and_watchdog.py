"""
tests/test_hook_circuits_and_watchdog.py
========================================
Comprehensive Unit & Integration tests for Vazus OS Lifecycle Hooks,
Context Watchdog, SQLite J-Space Tool Activations, and Cloud Sync Memory Circuit.

Verifies:
1. Turn N >= 25 Context Watchdog in pre_invocation_hook injects warning and generates handoff.
2. J-Space tool activation recording into SQLite table j_space_tool_activations.
3. Stop hook guarantees handoff creation at invocation_num >= 20 and calls VazusUnifiedHub().sync_state_to_cloud_file().
"""

import io
import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure vazus root in path
ROOT_DIR = Path("C:/vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.hooks.pre_invocation_hook import (
    handle_pre_invocation,
    record_j_space_tool_activation,
    run_pre_invocation_hook,
    main as pre_invocation_main,
)
from vazus_core.hooks.stop_hook import (
    _persist_session_memories,
    main as stop_hook_main,
    run_stop_hook,
)


def test_turn_n_context_watchdog_warning_direct():
    """
    Verifies that on Turn N >= 25, handle_pre_invocation triggers check_and_generate_handoff
    and injects the Context Watchdog warning into injectSteps.
    """
    hook_data = {
        "invocationNum": 25,
        "userPrompt": "какая погода сегодня",
        "messages": [
            {"role": "user", "content": "какая погода сегодня"}
        ],
    }

    with patch("vazus_core.workers.handoff_generator.check_and_generate_handoff") as mock_handoff:
        mock_handoff.return_value = {"should_handoff": True, "turn_index": 25}

        result = handle_pre_invocation(hook_data)

        assert "injectSteps" in result, f"Expected 'injectSteps' in result, got: {result}"
        assert len(result["injectSteps"]) > 0
        message = result["injectSteps"][0].get("message", "")
        assert "> ⚠️ **[Context Watchdog]**:" in message
        assert "25 шагов" in message
        assert r"C:\vazus\data\logs\latest_handoff.md" in message

        # Verify check_and_generate_handoff was called with turn_index=25
        mock_handoff.assert_called_once()
        _, kwargs = mock_handoff.call_args
        assert kwargs.get("turn_index") == 25 or mock_handoff.call_args[0][0] == 25


def test_turn_n_context_watchdog_with_tool_directive():
    """
    Verifies that on Turn N >= 25 with a tool-activating prompt,
    BOTH Context Watchdog warning and J-Space tool directive are injected together into injectSteps.
    """
    hook_data = {
        "invocationNum": 27,
        "userPrompt": "сделай бэкап базы данных vazus.db",
        "messages": [
            {"role": "user", "content": "сделай бэкап базы данных vazus.db"}
        ],
    }

    with patch("vazus_core.workers.handoff_generator.check_and_generate_handoff") as mock_handoff:
        mock_handoff.return_value = {"should_handoff": True, "turn_index": 27}

        result = handle_pre_invocation(hook_data)

        assert "injectSteps" in result
        message = result["injectSteps"][0].get("message", "")
        # Watchdog warning present
        assert "> ⚠️ **[Context Watchdog]**:" in message
        assert "27 шагов" in message
        # J-Space tool directive also present in same injection
        assert "⚡ [J-Space NPU Tool Activation]:" in message
        assert "db_backup" in message


def test_turn_n_below_threshold_no_watchdog():
    """
    Verifies that on Turn N < 25 with an irrelevant prompt,
    Context Watchdog is NOT triggered and empty result is returned.
    """
    hook_data = {
        "invocationNum": 10,
        "userPrompt": "расскажи рецепт торта",
        "messages": [
            {"role": "user", "content": "расскажи рецепт торта"}
        ],
    }

    with patch("vazus_core.workers.handoff_generator.check_and_generate_handoff") as mock_handoff:
        result = handle_pre_invocation(hook_data)
        assert mock_handoff.call_count == 0
        assert result == {}


@pytest.mark.anyio
async def test_async_run_pre_invocation_hook_watchdog():
    """
    Verifies the async run_pre_invocation_hook wrapper includes Context Watchdog warning
    and injectSteps when turn_index >= 25.
    """
    with patch("vazus_core.workers.handoff_generator.check_and_generate_handoff") as mock_handoff:
        mock_handoff.return_value = {"should_handoff": True, "turn_index": 26}

        res = await run_pre_invocation_hook(
            session_id="test_session_wd",
            user_prompt="продолжай выполнение",
            turn_index=26,
            messages=[{"role": "user", "content": "продолжай выполнение"}],
        )

        assert res["status"] == "SUCCESS"
        assert res["turn_index"] == 26
        assert "> ⚠️ **[Context Watchdog]**:" in res["injected_context"]
        assert "26 шагов" in res["injected_context"]
        assert "injectSteps" in res
        assert "> ⚠️ **[Context Watchdog]**:" in res["injectSteps"][0]["message"]
        mock_handoff.assert_called_once()


def test_j_space_tool_activation_recording(tmp_path):
    """
    Verifies that record_j_space_tool_activation creates SQLite table j_space_tool_activations
    and inserts tool_name, prompt, invocation_num, timestamp.
    """
    test_db = tmp_path / "test_activations.db"

    success = record_j_space_tool_activation(
        tool_name="vazus-sandbox",
        prompt="создай песочницу для изоляции",
        invocation_num=3,
        db_path=str(test_db),
    )
    assert success is True

    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()
    cur.execute("SELECT tool_name, prompt, invocation_num, timestamp FROM j_space_tool_activations")
    rows = cur.fetchall()
    conn.close()

    assert len(rows) == 1
    tool_name, prompt, inv_num, ts = rows[0]
    assert tool_name == "vazus-sandbox"
    assert prompt == "создай песочницу для изоляции"
    assert inv_num == 3
    assert ts is not None and len(ts) > 10


def test_j_space_tool_activation_recording_fallback():
    """
    Verifies that record_j_space_tool_activation gracefully handles unwritable/invalid DB path
    without raising unhandled exceptions (safe fallback).
    """
    invalid_path = "Z:\\invalid_drive_non_existent\\impossible.db"
    success = record_j_space_tool_activation(
        tool_name="test-tool",
        prompt="test prompt",
        invocation_num=1,
        db_path=invalid_path,
    )
    assert success is False


def test_pre_invocation_records_tool_activation_on_dispatch(tmp_path):
    """
    Verifies that when handle_pre_invocation dispatches a tool, it automatically
    records the activation into j_space_tool_activations in the target database.
    """
    test_db = tmp_path / "dispatch_activations.db"
    hook_data = {
        "invocationNum": 2,
        "userPrompt": "сделай бэкап базы данных vazus.db",
        "messages": [{"role": "user", "content": "сделай бэкап базы данных vazus.db"}],
    }

    with patch.dict(os.environ, {"VAZUS_DB_PATH": str(test_db)}):
        result = handle_pre_invocation(hook_data)
        assert "injectSteps" in result
        assert "db_backup" in result["injectSteps"][0]["message"]

        conn = sqlite3.connect(str(test_db))
        cur = conn.cursor()
        cur.execute("SELECT tool_name, invocation_num FROM j_space_tool_activations WHERE tool_name = 'db_backup'")
        rows = cur.fetchall()
        conn.close()

        assert len(rows) >= 1
        assert rows[0][0] == "db_backup"
        assert rows[0][1] == 2


def test_stop_hook_cloud_sync_and_handoff_at_threshold():
    """
    Verifies that stop_hook triggers check_and_generate_handoff when invocation_num >= 20,
    and unconditionally executes VazusUnifiedHub().sync_state_to_cloud_file() at the end.
    """
    messages = [
        {"role": "user", "content": "выполни аудит задолженностей МИРЭА и сформируй отчет"},
        {"role": "assistant", "content": "создан отчет по академическим задолженностям"},
    ]

    with patch("vazus_core.workers.handoff_generator.check_and_generate_handoff") as mock_handoff, \
         patch("vazus_core.engine.unified_hub.VazusUnifiedHub.sync_state_to_cloud_file") as mock_cloud_sync:

        mock_handoff.return_value = {"should_handoff": True, "turn_index": 20}
        mock_cloud_sync.return_value = {"synced": True, "targets": ["cloud.json"]}

        _persist_session_memories(
            conversation_id="test_session_stop_20",
            invocation_num=20,
            messages=messages,
        )

        # 1. Handoff generation must be called for turn >= 20
        mock_handoff.assert_called_once()
        _, kwargs = mock_handoff.call_args
        assert kwargs.get("turn_index") == 20 or mock_handoff.call_args[0][0] == 20

        # 2. Cloud sync must be called at end of session
        mock_cloud_sync.assert_called_once()


def test_stop_hook_below_threshold_skips_handoff_but_syncs_cloud():
    """
    Verifies that stop_hook does NOT generate handoff when invocation_num < 20,
    but STILL calls sync_state_to_cloud_file() at the end of _persist_session_memories.
    """
    messages = [
        {"role": "user", "content": "краткий вопрос по синтаксису python функций"},
        {"role": "assistant", "content": "обновлен модуль и решено определение функции"},
    ]

    with patch("vazus_core.workers.handoff_generator.check_and_generate_handoff") as mock_handoff, \
         patch("vazus_core.engine.unified_hub.VazusUnifiedHub.sync_state_to_cloud_file") as mock_cloud_sync:

        mock_cloud_sync.return_value = {"synced": True, "targets": ["cloud.json"]}

        _persist_session_memories(
            conversation_id="test_session_stop_5",
            invocation_num=5,
            messages=messages,
        )

        # Handoff NOT called below threshold 20
        assert mock_handoff.call_count == 0

        # Cloud sync STILL called
        mock_cloud_sync.assert_called_once()


def test_stop_hook_main_pipeline():
    """
    Verifies stop_hook.main() end-to-end with simulated JSON input on stdin,
    confirming handoff generation at invocationNum >= 20 and 'stop' decision output.
    """
    payload = json.dumps({
        "conversationId": "test_conv_main_pipe",
        "invocationNum": 22,
        "messages": [
            {"role": "user", "content": "запусти рефакторинг модулей системы"},
            {"role": "assistant", "content": "исправлен и рефакторен модуль stop_hook"},
        ],
    })

    with patch("sys.stdin", io.StringIO(payload)), \
         patch("vazus_core.hooks.stop_hook._check_termination_gates", return_value=None), \
         patch("vazus_core.workers.handoff_generator.check_and_generate_handoff") as mock_handoff, \
         patch("vazus_core.engine.unified_hub.VazusUnifiedHub.sync_state_to_cloud_file") as mock_cloud_sync, \
         patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:

        mock_handoff.return_value = {"should_handoff": True, "turn_index": 22}
        mock_cloud_sync.return_value = {"synced": True, "targets": []}

        stop_hook_main()

        output_str = mock_stdout.getvalue().strip()
        assert json.loads(output_str) == {"decision": "stop"}
        assert mock_handoff.call_count >= 1
        assert mock_cloud_sync.call_count >= 1


@pytest.mark.anyio
async def test_async_run_stop_hook_circuit():
    """
    Verifies async run_stop_hook triggers handoff at turn >= 20 and sync_state_to_cloud_file.
    """
    with patch("vazus_core.workers.handoff_generator.check_and_generate_handoff") as mock_handoff, \
         patch("vazus_core.engine.unified_hub.VazusUnifiedHub.sync_state_to_cloud_file") as mock_cloud_sync:

        mock_handoff.return_value = {"should_handoff": True, "turn_index": 24}
        mock_cloud_sync.return_value = {"synced": True}

        res = await run_stop_hook(
            session_id="test_async_stop",
            invocation_num=24,
            messages=[{"role": "user", "content": "тестовое сообщение"}],
        )

        assert res["status"] == "CONSOLIDATED"
        assert res["decision"] == "stop"
        mock_handoff.assert_called_once()
        mock_cloud_sync.assert_called_once()
