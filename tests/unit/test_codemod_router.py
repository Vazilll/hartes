"""
Unit tests for Layer 3 CodemodRouter & LibCSTPruner.
"""

import pytest
from vazus_core.codemods.libcst_pruner import LibCSTPruner
from vazus_core.codemods.codemod_router import CodemodRouter

def test_libcst_dead_function_excision():
    sample_code = """
# Useful header comment
def active_func():
    # Keep me
    return 42

def _dead_unused_helper():
    # Remove me
    return 0

# Useful footer comment
"""
    pruner = LibCSTPruner()
    modified, count = pruner.excise_dead_functions(sample_code, {"_dead_unused_helper"})
    assert count == 1
    assert "def _dead_unused_helper" not in modified
    assert "def active_func():" in modified
    assert "# Useful header comment" in modified
    assert "# Useful footer comment" in modified

def test_libcst_rename_function_calls():
    sample_code = """
def run():
    old_helper(10)
    other_func()
"""
    pruner = LibCSTPruner()
    modified, count = pruner.rename_function_calls(sample_code, "old_helper", "new_helper")
    assert count == 1
    assert "new_helper(10)" in modified
    assert "other_func()" in modified
