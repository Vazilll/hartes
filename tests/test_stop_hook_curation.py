import sys
sys.path.insert(0, 'C:/vazus')
from unittest.mock import patch, MagicMock

def test_extracts_facts_from_session():
    from vazus_core.hooks.stop_hook import auto_curate_session_memory
    transcript = [
        {'role': 'user', 'content': 'zameni ephemeralMessage na message'},
        {'role': 'assistant', 'content': 'modified pre_invocation_hook.py line 458 — replaced ephemeralMessage'},
    ]
    with patch('vazus_core.hooks.stop_hook.Mem0Engine') as m:
        inst = MagicMock()
        m.return_value = inst
        auto_curate_session_memory(transcript, min_confidence=0.7)
        assert inst.add_fact.called

def test_empty_transcript_returns_empty():
    from vazus_core.hooks.stop_hook import auto_curate_session_memory
    assert auto_curate_session_memory([]) == []

def test_no_keywords_returns_empty():
    from vazus_core.hooks.stop_hook import auto_curate_session_memory
    transcript = [
        {'role': 'user', 'content': 'rasskazhi o sisteme'},
        {'role': 'assistant', 'content': 'sistema sostoit iz neskolkih modulei'},
    ]
    with patch('vazus_core.hooks.stop_hook.Mem0Engine') as m:
        inst = MagicMock()
        m.return_value = inst
        result = auto_curate_session_memory(transcript)
        assert not inst.add_fact.called
        assert result == []
