"""
tests.test_rlm_antigravity — Tests for Google Antigravity SDK integration into MIT RLM.
Verifies AntigravityClient instantiation, usage summaries, and client routing.
"""

import sys
from pathlib import Path
import pytest

# Ensure rlm-mit is in path
HARNET_RLM_DIR = Path("/home/tarhes/Проекты/harnet/vendor/rlm")
PYENV_DIR = Path("/home/tarhes/Проекты/vazus")
for p in [str(HARNET_RLM_DIR), str(PYENV_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from rlm.clients import get_client
from rlm.clients.antigravity import AntigravityClient


def test_antigravity_client_instantiation():
    """Verify that AntigravityClient instantiates with default parameters."""
    client = AntigravityClient(model_name="gemini-3.7-flash")
    assert client.model_name == "gemini-3.7-flash"
    assert client.system_instructions is not None

    usage = client.get_usage_summary()
    assert usage.total_cost is None or usage.total_cost == 0.0
    
    last_usage = client.get_last_usage()
    assert last_usage.total_calls == 1


def test_rlm_get_client_routing_antigravity():
    """Verify that get_client('antigravity', ...) routes to AntigravityClient."""
    client = get_client("antigravity", {"model_name": "gemini-3.7-flash"})
    assert isinstance(client, AntigravityClient)
    assert client.model_name == "gemini-3.7-flash"
