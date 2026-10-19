"""
Unit tests for Aider RepoMap and Meta TestGen-LLM engines.
"""

from vazus_core.engine.repomap_engine import RepoMapEngine
from vazus_core.verification.testgen_engine import AssuredTestGenEngine


def test_repomap_generation():
    engine = RepoMapEngine(max_tokens=800)
    repomap = engine.generate_repomap(target_dir="vazus_core/engine")
    assert "# REPOSITORY STRUCTURAL MAP" in repomap
    assert "vazus_core/engine/" in repomap
    assert "class " in repomap or "def " in repomap


def test_testgen_engine_reward_hacking_detection():
    testgen = AssuredTestGenEngine()

    fake_test_1 = "def test_dummy():\n    pass\n"
    fake_test_2 = "def test_dummy():\n    assert True\n"
    fake_test_3 = "def test_dummy():\n    assert 1 == 1\n"
    valid_test = "def test_real():\n    val = 2 + 2\n    assert val == 4\n"

    assert testgen._is_reward_hacking(fake_test_1) is True
    assert testgen._is_reward_hacking(fake_test_2) is True
    assert testgen._is_reward_hacking(fake_test_3) is True
    assert testgen._is_reward_hacking(valid_test) is False
