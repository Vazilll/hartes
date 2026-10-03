"""
End-to-End integration test for the 5-Layer Code Intelligence Architecture in Vazus OS.
"""

import pytest
from vazus_core.engine.supergraph_bridge import SuperGraphBridge
from vazus_core.telemetry.dynamic_trace_collector import DynamicTraceCollector
from vazus_core.codemods.libcst_pruner import LibCSTPruner
from vazus_core.verification.smt_equivalence_prover import SMTEquivalenceProver
from vazus_core.verification.candidate_harvester import CandidateHarvester
from vazus_core.memory.whitelist_manager import WhitelistManager

def test_closed_loop_5layer_integration(tmp_path):
    # 1. Layer 1: Graph Sync
    test_db = tmp_path / "test_5layers.db"
    bridge = SuperGraphBridge(db_path=str(test_db))
    sync_ok = bridge.sync_ast_node(
        node_id="ast:test_module:sample_function",
        name="sample_function",
        node_type="Function",
        file_path="tests/sample.py",
        description="Sample test function"
    )
    assert sync_ok is True

    # 2. Layer 5: Whitelist protection check
    whitelist_mgr = WhitelistManager()
    assert whitelist_mgr.is_protected("__init__") is True
    assert whitelist_mgr.is_protected("get_db_connection") is True

    # 3. Layer 4: SMT Invariant Verification
    prover = SMTEquivalenceProver()
    equiv_res = prover.verify_expression_equivalence("x * 2", "x + x", ["x"])
    assert equiv_res["equivalent"] is True

    # 4. Layer 3: LibCST Surgical Pruning
    code = "def active(): return 1\ndef _dead(): return 0"
    clean_code, removed = LibCSTPruner.excise_dead_functions(code, {"_dead"})
    assert removed == 1
    assert "def _dead" not in clean_code
    assert "def active():" in clean_code

    # 5. Layer 2: Upstream Scanner & Candidate Harvester
    harvester = CandidateHarvester()
    whitelist = harvester.whitelist_mgr.get_whitelist()
    assert len(whitelist) > 0
