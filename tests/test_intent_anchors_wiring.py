"""tests/test_intent_anchors_wiring.py — extractor, hook retrieval, and orchestrator injection of J-Space intent anchors."""

import os

import pytest

from vazus_core.memory.intent_extractor import extract_intent_candidates, propose_from_session
from vazus_core.memory.unified_j_workspace import UnifiedJWorkspace


_KEEPALIVE: list = []


def _load_retriever():
    """pre_invocation_hook rewraps sys.stdout/stderr at import (breaks pytest capture); restore them."""
    import sys

    saved = sys.stdout, sys.stderr
    try:
        from vazus_core.hooks.pre_invocation_hook import _retrieve_intent_anchors
    finally:
        _KEEPALIVE.append((sys.stdout, sys.stderr))  # a GC'd wrapper would close pytest's capture file
        sys.stdout, sys.stderr = saved
    return _retrieve_intent_anchors


def _msgs(*texts):
    return [{"role": "user", "content": t} for t in texts]


def test_extractor_finds_constraints_and_goals_and_caps():
    msgs = _msgs(
        "Привет, как дела у тебя сегодня?",
        "<USER_REQUEST>Никогда не решай задачи МИРЭА за меня. Цель: закрыть долги до 15.10.</USER_REQUEST>",
        "Нужно, чтобы смысл не менялся. Запрещено создавать заглушки в коде. Нельзя удалять файлы без проверки.",
    )
    found = extract_intent_candidates(msgs)
    assert 1 <= len(found) <= 3
    assert ("constraint" in {k for k, s in found if "МИРЭА" in s}), found
    assert all(not s.startswith("<") for _, s in found)


def test_extractor_ignores_assistant_and_chitchat():
    assert extract_intent_candidates([{"role": "assistant", "content": "Никогда не делай этого, всегда проверяй."}]) == []
    assert extract_intent_candidates(_msgs("Просто обычное сообщение без правил.")) == []


def test_propose_from_session_only_proposes():
    ws = UnifiedJWorkspace(db_path=":memory:")
    out = propose_from_session(_msgs("Никогда не удаляй файлы без проверки зависимостей."), workspace=ws)
    assert out and out[0]["status"] == "proposed"
    assert ws.get_intents() == [] and ws.get_intent_context() == ""


def test_pre_invocation_injects_confirmed_and_nudges_pending(tmp_path, monkeypatch):
    db = str(tmp_path / "v.db")
    ws = UnifiedJWorkspace(db_path=db)
    ws.confirm_intent(ws.propose_intent("Никаких заглушек", kind="constraint")["intent_id"])
    ws.propose_intent("Новая гипотеза-цель")
    monkeypatch.setenv("VAZUS_DB_PATH", db)
    _retrieve_intent_anchors = _load_retriever()

    first = _retrieve_intent_anchors(0)
    assert "Никаких заглушек" in first and "1 proposed intent" in first
    later = _retrieve_intent_anchors(3)
    assert "Никаких заглушек" in later and "proposed intent" not in later
    assert "Новая гипотеза-цель" not in first  # proposals never leak into context


def test_pre_invocation_fail_open_without_table(tmp_path, monkeypatch):
    import sqlite3

    db = tmp_path / "empty.db"
    sqlite3.connect(db).close()
    monkeypatch.setenv("VAZUS_DB_PATH", str(db))
    _retrieve_intent_anchors = _load_retriever()

    assert _retrieve_intent_anchors(0) is None


def test_orchestrator_intent_block_fail_open_and_confirmed(tmp_path):
    from vazus_core.engine.silicon_orchestrator import SiliconOrchestrator

    db = str(tmp_path / "o.db")
    orch = SiliconOrchestrator(db_path=db)
    assert orch._intent_block() == ""
    ws = UnifiedJWorkspace(db_path=db)
    ws.confirm_intent(ws.propose_intent("Смысл не дрейфует")["intent_id"])
    orch._intents = None
    assert "Смысл не дрейфует" in orch._intent_block()


