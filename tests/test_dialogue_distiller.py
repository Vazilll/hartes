import pytest
from vazus_core.memory.dialogue_distiller import extract_session_essence, distill_all_sessions

def test_extract_session_essence_filters_empty():
    assert extract_session_essence([]) == ""

def test_extract_session_essence_finds_topics():
    msgs = [
        {"role": "user", "content": "разверни Cloud Run для Gemini Spark"},
        {"role": "assistant", "content": "Успешно развернут gemini-bridge на vazus-supergraph-prod в регионе us-central1"}
    ]
    essence = extract_session_essence(msgs)
    assert "Cloud Run" in essence or "gemini-bridge" in essence
    assert "vazus-supergraph-prod" in essence

def test_distill_all_sessions_smoke():
    summary_md = distill_all_sessions(max_sessions=3)
    assert isinstance(summary_md, str)
    assert len(summary_md) > 50
