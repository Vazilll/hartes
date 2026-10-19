"""
tests/unit/test_darwinian_mutation_isolation.py
Unit and empirical verification tests for Darwinian mutation isolation in ephemeral overlays.
Proves that evaluate_variant_pytest executes isolated mutant code rather than the base repository.
"""

import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path

from vazus_core.evolution.darwinian_evolver import (
    evaluate_variant_pytest,
    _evaluate_variant_in_overlay,
    _sanitized_pytest_env,
)


class TestDarwinianMutationIsolation:
    """Empirical proof suite for Darwinian mutation isolation."""

    def test_mutant_overlay_execution_vs_base_repo(self, tmp_path):
        """
        Empirical proof: pytest registers sentinel presence in the mutant overlay
        while the base repository fails the exact same probe test.
        """
        base_file = r"C:\vazus\vazus_core\verification\ast_pruner.py"
        with open(base_file, "r", encoding="utf-8") as f:
            base_code = f.read()

        mutant_code = base_code + "\n__MUTANT_SENTINEL_8888__ = 8888\n"

        probe_test = tmp_path / "test_probe.py"
        probe_test.write_text(
            "from vazus_core.verification.ast_pruner import __MUTANT_SENTINEL_8888__\n"
            "def test_sentinel():\n"
            "    assert __MUTANT_SENTINEL_8888__ == 8888\n",
            encoding="utf-8"
        )

        # 1. Base repository execution must fail because sentinel does not exist in C:\vazus
        score_base = evaluate_variant_pytest(str(probe_test), timeout=5)
        assert score_base == 0.0, "Base repository must fail probe test"

        # 2. Overlay execution must pass because sentinel is present in mutant overlay
        score_mutant = _evaluate_variant_in_overlay(base_file, mutant_code, str(probe_test), timeout=10)
        assert score_mutant > 0.0, "Mutant overlay must pass probe test and yield fitness > 0"

        # 3. Zero-Artifact Protocol verification
        leftovers = list(Path(tempfile.gettempdir()).glob("vazus_mutant_overlay_*"))
        assert len(leftovers) == 0, "Overlay must be purged (0 disk artifacts)"

    def test_mutant_functional_behavior_modification(self, tmp_path):
        """
        Empirical proof: pytest measures altered functional behavior inside the mutant.
        """
        base_file = r"C:\vazus\vazus_core\verification\ast_pruner.py"
        with open(base_file, "r", encoding="utf-8") as f:
            base_code = f.read()

        mutant_code = base_code + "\nASTPruner.prune_ast = staticmethod(lambda c, **kw: 'PRUNED_BY_MUTANT')\n"

        probe_test = tmp_path / "test_func_probe.py"
        probe_test.write_text(
            "from vazus_core.verification.ast_pruner import ASTPruner\n"
            "def test_behavior():\n"
            "    assert ASTPruner.prune_ast('def test(): pass') == 'PRUNED_BY_MUTANT'\n",
            encoding="utf-8"
        )

        score_base = evaluate_variant_pytest(str(probe_test), timeout=5)
        assert score_base == 0.0, "Base code must not match mutant behavior"

        score_mutant = _evaluate_variant_in_overlay(base_file, mutant_code, str(probe_test), timeout=10)
        assert score_mutant > 0.0, "Mutant behavior must be verified by pytest"

    def test_unmutated_sibling_modules_accessible(self, tmp_path):
        """
        Verifies namespace extension hook (`from pkgutil import extend_path`):
        Unmutated sibling modules in the same package and other vazus packages
        resolve seamlessly from the base repository.
        """
        base_file = r"C:\vazus\vazus_core\verification\ast_pruner.py"
        with open(base_file, "r", encoding="utf-8") as f:
            base_code = f.read()

        mutant_code = base_code + "\n__MUTANT_SIBLING_PROBE__ = True\n"

        probe_test = tmp_path / "test_sibling_probe.py"
        probe_test.write_text(
            "from vazus_core.verification.ast_pruner import __MUTANT_SIBLING_PROBE__, ASTPruner\n"
            "from vazus_core.verification.concordia_jury import ConcordiaJury\n"
            "from vazus_core.memory.db import get_db_connection\n"
            "def test_sibling_resolution():\n"
            "    assert __MUTANT_SIBLING_PROBE__ is True\n"
            "    assert ASTPruner is not None\n"
            "    assert ConcordiaJury is not None\n"
            "    assert callable(get_db_connection)\n",
            encoding="utf-8"
        )

        score_mutant = _evaluate_variant_in_overlay(base_file, mutant_code, str(probe_test), timeout=10)
        assert score_mutant > 0.0, "Sibling modules must resolve via extend_path"

    def test_syntax_error_mutant_handled_gracefully(self, tmp_path):
        """
        Fail-closed invariant: mutant with invalid Python syntax returns 0.0 fitness
        and cleans up temporary overlay without raising unhandled exceptions.
        """
        base_file = r"C:\vazus\vazus_core\verification\ast_pruner.py"
        broken_code = "def broken_syntax(:\n    pass\n"

        probe_test = tmp_path / "test_probe.py"
        probe_test.write_text(
            "from vazus_core.verification.ast_pruner import ASTPruner\n"
            "def test_import(): pass\n",
            encoding="utf-8"
        )

        score = _evaluate_variant_in_overlay(base_file, broken_code, str(probe_test), timeout=5)
        assert score == 0.0, "Syntax error must result in 0.0 fitness"

        leftovers = list(Path(tempfile.gettempdir()).glob("vazus_mutant_overlay_*"))
        assert len(leftovers) == 0, "Overlay directory must be cleaned up on syntax error"

    def test_assertion_failure_yields_zero_fitness(self, tmp_path):
        """
        Mutant that causes test assertion failure returns 0.0 fitness.
        """
        base_file = r"C:\vazus\vazus_core\verification\ast_pruner.py"
        with open(base_file, "r", encoding="utf-8") as f:
            base_code = f.read()

        mutant_code = base_code + "\n__VALUE__ = 111\n"
        probe_test = tmp_path / "test_fail.py"
        probe_test.write_text(
            "from vazus_core.verification.ast_pruner import __VALUE__\n"
            "def test_fail(): assert __VALUE__ == 999\n",
            encoding="utf-8"
        )

        score = _evaluate_variant_in_overlay(base_file, mutant_code, str(probe_test), timeout=5)
        assert score == 0.0, "Failed assertions must yield 0.0 fitness"

    def test_timeout_mutant_killed_cleanly(self, tmp_path):
        """
        Process termination invariant: mutant with infinite loop/sleep is killed
        within timeout and returns 0.0 with zero leaked processes or files.
        """
        base_file = r"C:\vazus\vazus_core\verification\ast_pruner.py"
        timeout_code = "import time\ntime.sleep(10)\n"

        probe_test = tmp_path / "test_timeout.py"
        probe_test.write_text(
            "from vazus_core.verification.ast_pruner import ASTPruner\n"
            "def test_dummy(): pass\n",
            encoding="utf-8"
        )

        score = _evaluate_variant_in_overlay(base_file, timeout_code, str(probe_test), timeout=1)
        assert score == 0.0, "Timed-out mutant must return 0.0"

        leftovers = list(Path(tempfile.gettempdir()).glob("vazus_mutant_overlay_*"))
        assert len(leftovers) == 0, "Overlay directory must be cleaned up on timeout"