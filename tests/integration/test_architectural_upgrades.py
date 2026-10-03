"""
tests/test_architectural_upgrades.py — Verification suite for Zero-Trust Subprocess REPL,
Git Worktree Sandbox, and Native SQLite-vec Storage (Qdrant-free).
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, "C:/vazus")

from vazus_core.subprocess_repl import ZeroTrustSubprocessREPL
from vazus_core.worktree_sandbox import AntigravityWorktreeSandbox
from vazus_core.embeddings import get_embedding_manager
from vazus_core.organic_memory_bridge import record_insight, search_memory


def test_zero_trust_subprocess_repl_execution():
    repl = ZeroTrustSubprocessREPL(timeout_seconds=5.0)
    res = repl.execute_code("a = 100\nb = 250\nans = a + b\nprint(f'Calculated: {ans}')")
    
    assert res.status == "SUCCESS"
    assert "Calculated: 350" in res.stdout
    assert res.locals.get("ans") == 350
    assert res.execution_time >= 0


def test_zero_trust_subprocess_repl_isolation():
    repl = ZeroTrustSubprocessREPL(timeout_seconds=5.0)
    # Test that environment does not leak sensitive keys
    res = repl.execute_code("import os\nkeys = [k for k in os.environ if 'API_KEY' in k]\nprint(f'Leaked: {keys}')")
    
    assert res.status == "SUCCESS"
    assert "Leaked: []" in res.stdout


def test_worktree_sandbox_lifecycle():
    sandbox = AntigravityWorktreeSandbox()
    with sandbox.create_sandbox(prefix="arch_test") as sb_path:
        assert sb_path.exists()
        assert (sb_path / ".git").exists() or (sb_path / "vazus_core").exists()
    # After exit, worktree directory must be cleaned up
    assert not sb_path.exists()


def test_native_sqlite_vector_search_and_insight_record(tmp_path):
    mgr = get_embedding_manager()
    results = mgr.search_unified_vector_space("AST code topology", top_k=3)
    assert isinstance(results, list)

    rec = record_insight(
        category="architectural_upgrade",
        insight="Verified native SQLite-vec storage without external Qdrant locks.",
        db_path=str(tmp_path / "test_arch.db")
    )
    assert rec["status"] == "SUCCESS"
    assert "node_id" in rec
