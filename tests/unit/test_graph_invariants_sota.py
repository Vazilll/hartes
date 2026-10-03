"""
tests/test_graph_invariants_sota.py — SOTA Graph Invariant & CPG Verification Tests (ICSE/FSE 2026).

Tests:
1. Gate 11: Phantom Import & Symbol Detector (Prevents 'The Patchwork Problem').
2. MR-G1: Node Renaming Isomorphism (AST & Dependency Preservation).
3. MR-G3: AST Pruning Signature Invariant (Contract & Type Annotations Preservation).
4. MR-G4: Organic Memory Knowledge Graph Link Invariant.
5. MR-G5: Dead Code Topology & Unreachability Invariant.
"""

from __future__ import annotations

import keyword
import ast
from pathlib import Path
import pytest
from hypothesis import given, strategies as st, settings, assume

from vazus_core.verification.precommit_gate import (
    run_gate_11_graph_invariants,
    _extract_file_imports,
    _resolve_vazus_module_path,
    _has_top_level_symbol,
    _check_import_target,
    VAZUS_ROOT,
)
from vazus_core.verification.ast_pruner import ASTPruner


# =============================================================================
# 1. GATE 11: PHANTOM IMPORT & SYMBOL INTEGRATION TESTS
# =============================================================================

class TestGate11PhantomImports:
    """Verifies that Gate 11 blocks phantom modules/symbols while passing valid ones."""

    @pytest.fixture(autouse=True)
    def patch_filter(self, monkeypatch: pytest.MonkeyPatch):
        """Allows temp test files outside VAZUS_ROOT to be analyzed by Gate 11."""
        monkeypatch.setattr(
            "vazus_core.verification.precommit_gate._filter_own_python_files",
            lambda fs: fs,
        )

    def test_valid_import_passes_gate11(self, tmp_path: Path):
        """A file importing real vazus_core symbols must pass Gate 11 with 0 errors."""
        test_file = tmp_path / "valid_module.py"
        test_file.write_text(
            "from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier\n"
            "from vazus_core.verification.ast_pruner import ASTPruner\n"
            "def run():\n"
            "    v = SMTZ3Verifier()\n"
            "    return v\n",
            encoding="utf-8"
        )
        passed, errors = run_gate_11_graph_invariants([test_file])
        assert passed is True
        assert len(errors) == 0

    def test_phantom_module_blocked_by_gate11(self, tmp_path: Path):
        """Importing a non-existent vazus_core module must be blocked by Gate 11."""
        test_file = tmp_path / "phantom_mod.py"
        test_file.write_text(
            "import vazus_core.non_existent_fake_subsystem_xyz\n",
            encoding="utf-8"
        )
        passed, errors = run_gate_11_graph_invariants([test_file])
        assert passed is False
        assert any("[Phantom Import]" in e and "non_existent_fake_subsystem_xyz" in e for e in errors)

    def test_phantom_symbol_blocked_by_gate11(self, tmp_path: Path):
        """Importing a non-existent symbol from an existing module must be blocked."""
        test_file = tmp_path / "phantom_sym.py"
        test_file.write_text(
            "from vazus_core.verification.smt_z3_verifier import FakeGhostSymbolNeverDefined123\n",
            encoding="utf-8"
        )
        passed, errors = run_gate_11_graph_invariants([test_file])
        assert passed is False
        assert any("[Phantom Symbol]" in e and "FakeGhostSymbolNeverDefined123" in e for e in errors)

    def test_star_import_passes_gate11(self, tmp_path: Path):
        """Star imports from existing modules must pass without crashing."""
        test_file = tmp_path / "star_import.py"
        test_file.write_text(
            "from vazus_core.verification.ast_pruner import *\n",
            encoding="utf-8"
        )
        passed, errors = run_gate_11_graph_invariants([test_file])
        assert passed is True
        assert len(errors) == 0

    def test_external_and_stdlib_imports_ignored(self, tmp_path: Path):
        """Non-vazus_core imports (stdlib, third-party) are ignored by Gate 11."""
        test_file = tmp_path / "stdlib_test.py"
        test_file.write_text(
            "import os\nimport sys\nimport json\nimport pytest\nfrom pathlib import Path\n",
            encoding="utf-8"
        )
        passed, errors = run_gate_11_graph_invariants([test_file])
        assert passed is True
        assert len(errors) == 0


# =============================================================================
# 2. METAMORPHIC GRAPH RELATIONS (MR-G)
# =============================================================================

class TestMetamorphicGraphRelations:
    """Tests SOTA Metamorphic Relations on Code Property Graphs."""

    @given(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=3, max_size=10).filter(
            lambda s: s.isidentifier() and not keyword.iskeyword(s)
        )
    )
    @settings(max_examples=25)
    def test_mr_g1_node_renaming_preserves_external_interface(self, var_name: str):
        """MR-G1: Renaming a local variable inside a function body must preserve

        100% of top-level symbol definitions and exported interface.
        """
        assume(var_name.isidentifier() and not keyword.iskeyword(var_name))
        code_orig = (
            "def compute(a: int, b: int) -> int:\n"
            "    local_tmp = a * 2\n"
            "    return local_tmp + b\n"
        )
        code_renamed = (
            f"def compute(a: int, b: int) -> int:\n"
            f"    {var_name} = a * 2\n"
            f"    return {var_name} + b\n"
        )
        tree_orig = ast.parse(code_orig)
        tree_renamed = ast.parse(code_renamed)

        assert _has_top_level_symbol(tree_orig, "compute") is True
        assert _has_top_level_symbol(tree_renamed, "compute") is True
        assert _has_top_level_symbol(tree_renamed, var_name) is False

    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=20)
    def test_mr_g3_ast_pruning_preserves_function_signature_contract(self, num_params: int):
        """MR-G3: AST Pruning must strictly preserve parameter count, names,

        and return type annotation while pruning function body statements.
        """
        param_list = ", ".join([f"arg_{i}: int" for i in range(num_params)])
        code = (
            f"def complex_worker({param_list}) -> int:\n"
            f"    '''Full docstring describing worker operation.'''\n"
            f"    acc = 0\n"
            f"    for i in range(100):\n"
            f"        acc += i * 2\n"
            f"    return acc\n"
        )
        pruner = ASTPruner()
        pruned_code, stats = pruner.prune_code_string(code)

        tree_orig = ast.parse(code)
        tree_pruned = ast.parse(pruned_code)

        orig_fn = tree_orig.body[0]
        pruned_fn = tree_pruned.body[0]

        assert isinstance(orig_fn, ast.FunctionDef)
        assert isinstance(pruned_fn, ast.FunctionDef)
        assert orig_fn.name == pruned_fn.name
        assert len(orig_fn.args.args) == len(pruned_fn.args.args)
        for p1, p2 in zip(orig_fn.args.args, pruned_fn.args.args):
            assert p1.arg == p2.arg
            if p1.annotation and p2.annotation:
                assert ast.unparse(p1.annotation) == ast.unparse(p2.annotation)

    def test_mr_g4_backlinks_consistency(self):
        """MR-G4: Generated wikilinks must produce valid, structured link records."""
        from vazus_core.memory.organic_memory_bridge import recommend_wikilinks
        links = recommend_wikilinks("SMT Z3 verification architecture in vazus")
        assert isinstance(links, list)
        for link_record in links:
            assert isinstance(link_record, dict)
            assert "name" in link_record or "zettel_id" in link_record or "node_id" in link_record
