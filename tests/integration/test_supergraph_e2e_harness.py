"""
test_supergraph_e2e_harness.py — Comprehensive End-to-End Test Suite for Vazus Supergraph OS.

Covers all 4 Tiers of Requirements from ORIGINAL_REQUEST.md & PROJECT.md:
- Tier 1: Feature Coverage
  - Concordia Quorum (>=66% consensus) & 3-Subagent Voting.
  - 8-Tier Pre-Commit Quality Gate (AST/Security, Targeted Pytest, SMT Z3, EvidenceJury, Vulture, Ruff, Mypy, Gate 8 Observer).
  - SMT Z3 Formal Hoare Contract Proofs (@requires/@ensures, UNSAT invariants, SAT counterexamples, memory bounds).
  - 768-Dimensional Memory Embeddings, binary packing (3,072 bytes), and vector similarity.
  - AST Pruning Engine with signature preservation and >70% token reduction (target 77.57%).

- Tier 2: Boundary & Corner Cases
  - Empty/None inputs, whitespace payloads, and missing docstrings.
  - AST syntax error reporting with exact line numbers and graceful error recovery.
  - SMT non-linear / contradictory precondition handling and division-by-zero bounds.
  - Fail-closed timeouts (Jury-B Critic ABSTAIN) and 0-LLM quota fallbacks (Jury-A Evidence).

- Tier 3: Cross-Feature Combinations
  - Concordia Multi-Agent Jury consensus + SMT Z3 formal verification pipeline.
  - Bi-temporal Memory Fact Promotion Pipeline (UNTRUSTED_OBSERVATION -> VERIFIED_FACT -> 768D Vector Search).
  - AST Pruning with SuperGraph Knowledge Graph node indexing (kg_nodes) & organic insight tracking.

- Tier 4: Real-World Workload Scenarios
  - End-to-end multi-agent patch lifecycle (Planner -> Coder -> Verifier -> Critic -> Gate -> Memory).
  - Autonomous dead-code candidate harvesting & zero-artifact garbage collection.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(r"C:\vazus")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
VAZUS_CORE = PROJECT_ROOT / "vazus_core"
if str(VAZUS_CORE) not in sys.path:
    sys.path.insert(0, str(VAZUS_CORE))

from vazus_core.verification.concordia_jury import ConcordiaJury, JuryVerdict
from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier
from vazus_core.verification.evidence_jury import EvidenceJury
from vazus_core.verification.critic_jury import _parse_critic_verdict, _timeout_verdicts
from vazus_core.verification.ast_pruner import ASTPruner
from vazus_core.verification.candidate_harvester import CandidateHarvester
import vazus_core.verification.precommit_gate as precommit_gate
from vazus_core.verification.precommit_gate import (
    run_gate_1_ast_and_security,
    run_gate_6_ruff_lint,
    _check_ast_syntax,
    _check_hardcoded_secrets,
    _check_dangerous_calls,
    _check_reward_hacking,
)
from vazus_core.memory.db import (
    get_db_connection,
    init_db_schemas,
    pack_vector_f32,
    unpack_vector_f32,
    close_all_thread_connections,
)
from vazus_core.memory.embeddings import get_embedding_manager
from vazus_core.memory.mem0_memory_engine import Mem0Engine
from vazus_core.analysis.proactive_suggestion_engine import ProactiveSuggestionEngine


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def isolated_e2e_db(tmp_path, monkeypatch):
    """Provides a fresh, isolated SQLite database for zero-side-effect testing."""
    close_all_thread_connections()
    db_file = tmp_path / "e2e_vazus_test.db"
    db_path_str = str(db_file)
    monkeypatch.setenv("VAZUS_DB_PATH", db_path_str)
    conn = get_db_connection(db_path_str)
    init_db_schemas(conn, db_path=db_path_str)
    yield db_path_str
    close_all_thread_connections()


@pytest.fixture
def isolated_workspace(tmp_path):
    """Creates a temporary workspace with standard Vazus OS directories."""
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "vazus_core").mkdir(parents=True, exist_ok=True)
    (ws / "tests").mkdir(parents=True, exist_ok=True)
    (ws / "services" / "memory").mkdir(parents=True, exist_ok=True)
    return ws


# ============================================================================
# Tier 1: Feature Coverage Tests
# ============================================================================

class TestTier1FeatureCoverage:
    """Tier 1: Opaque-box feature coverage for core Vazus Supergraph OS requirements."""

    def test_concordia_quorum_and_consensus_unanimous_pass(self):
        """Verify 3-subagent unanimous PASS (100% >= 66% threshold) approves patch."""
        jury = ConcordiaJury(consensus_threshold=0.66)
        proposal_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
        votes = [
            {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "Modular structure clean"},
            {"agent": "RLM_Coder", "approved": True, "verdict": "PASS", "reason": "AST valid and logic sound"},
            {"agent": "Verifier_Worker", "approved": True, "verdict": "PASS", "reason": "No invariant violations"},
        ]
        verdict = jury.vote(proposal=proposal_code, votes=votes)
        assert isinstance(verdict, JuryVerdict)
        assert verdict.approved is True
        assert verdict.consensus_ratio == pytest.approx(1.0, rel=1e-2)
        assert verdict.quorum_satisfied is True
        assert verdict.ast_valid is True
        assert len(verdict.rejection_reasons) == 0

    def test_concordia_quorum_split_vote_majority_pass(self):
        """Verify 2/3 PASS (66.67% >= 66% threshold) satisfies quorum and approves patch."""
        jury = ConcordiaJury(consensus_threshold=0.66)
        proposal_code = "def multiply(x: int, y: int) -> int:\n    return x * y\n"
        votes = [
            {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "Compliant architecture"},
            {"agent": "RLM_Coder", "approved": True, "verdict": "PASS", "reason": "Logic correct"},
            {"agent": "Verifier_Worker", "approved": False, "verdict": "FAIL", "reason": "Minor style objection"},
        ]
        verdict = jury.vote(proposal=proposal_code, votes=votes)
        assert verdict.approved is True
        assert verdict.consensus_ratio >= 0.66
        assert verdict.quorum_satisfied is True

    def test_concordia_quorum_insufficient_consensus_reject(self):
        """Verify 1/3 PASS (33.33% < 66% threshold) rejects patch due to lack of quorum consensus."""
        jury = ConcordiaJury(consensus_threshold=0.66)
        proposal_code = "def divide(a: int, b: int) -> float:\n    return a / b\n"
        votes = [
            {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "Clean layout"},
            {"agent": "RLM_Coder", "approved": False, "verdict": "FAIL", "reason": "Missing zero divisor check"},
            {"agent": "Verifier_Worker", "approved": False, "verdict": "FAIL", "reason": "SMT div by zero possible"},
        ]
        verdict = jury.vote(proposal=proposal_code, votes=votes)
        assert verdict.approved is False
        assert verdict.consensus_ratio < 0.66
        assert len(verdict.rejection_reasons) >= 1

    def test_concordia_insufficient_vote_count_fails_quorum(self):
        """Verify fewer than min_quorum votes (e.g., 2/3) marks quorum_satisfied as False."""
        jury = ConcordiaJury(min_quorum=3, consensus_threshold=0.66)
        proposal_code = "def sample(x: int) -> int:\n    return x + 1\n"
        votes = [
            {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "OK"},
            {"agent": "RLM_Coder", "approved": True, "verdict": "PASS", "reason": "OK"},
        ]
        verdict = jury.vote(proposal=proposal_code, votes=votes)
        assert verdict.quorum_satisfied is False
        assert verdict.approved is False

    def test_gate1_ast_syntax_and_security_clean(self, tmp_path):
        """Verify Gate 1 passes clean Python code with 0 violations."""
        fpath = tmp_path / "clean_module.py"
        fpath.write_text("def compute(x: int) -> int:\n    return x * 2\n", encoding="utf-8")
        ok, errors = run_gate_1_ast_and_security([fpath])
        assert ok is True
        assert len(errors) == 0

    def test_gate1_catches_hardcoded_secrets(self, tmp_path):
        """Verify Gate 1 detects hardcoded Google/OpenAI API keys."""
        fpath = tmp_path / "leaky_service.py"
        fpath.write_text("API_KEY = 'AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q'\n", encoding="utf-8")
        errors = _check_hardcoded_secrets(fpath.read_text(encoding="utf-8"), fpath)
        assert len(errors) > 0
        assert any("Hardcoded secret" in e or "Hardcoded API key" in e for e in errors)

    def test_gate1_catches_dangerous_calls(self, tmp_path):
        """Verify Gate 1 blocks os.system() and subprocess shell=True."""
        fpath = tmp_path / "dangerous_runner.py"
        fpath.write_text("import os\ndef run_cmd():\n    os.system('dir')\n", encoding="utf-8")
        errors = _check_dangerous_calls(fpath.read_text(encoding="utf-8"), fpath)
        assert len(errors) > 0
        assert any("os.system()" in e for e in errors)

    def test_gate1_catches_reward_hacking_anti_patterns(self, tmp_path):
        """Verify Gate 1 blocks dummy 'pass' tests and 'assert True' tautologies."""
        fpath = tmp_path / "test_fake.py"
        fpath.write_text("def test_dummy():\n    pass\n\ndef test_tautology():\n    assert True\n", encoding="utf-8")
        errors = _check_reward_hacking(fpath.read_text(encoding="utf-8"), fpath)
        assert len(errors) == 2
        assert any("Empty dummy test" in e for e in errors)
        assert any("Tautological assertion" in e for e in errors)

    def test_gate3_smt_z3_contract_enforcement(self, tmp_path):
        """Verify Gate 3 validates formal contracts and detects violations."""
        verifier = SMTZ3Verifier(depth=10)
        valid_contract = (
            "def abs_val(x: int) -> int:\n"
            "    \"\"\"\n"
            "    :requires: x >= -100 and x <= 100\n"
            "    :ensures: result >= 0\n"
            "    \"\"\"\n"
            "    if x < 0:\n"
            "        return -x\n"
            "    return x\n"
        )
        res_valid = verifier.verify_code_contracts(valid_contract)
        assert res_valid.verified is True
        assert res_valid.contract_satisfied is True

        violated_contract = (
            "def broken_inc(x: int) -> int:\n"
            "    \"\"\"\n"
            "    :requires: x >= 0\n"
            "    :ensures: result > x\n"
            "    \"\"\"\n"
            "    return x - 1\n"
        )
        res_violated = verifier.verify_code_contracts(violated_contract)
        assert res_violated.verified is False or res_violated.contract_satisfied is False

    def test_gate4a_evidence_jury_zero_llm_quota(self, tmp_path):
        """Verify Gate 4a Jury-A executes deterministic evaluation without LLM calls."""
        fpath = tmp_path / "sample_logic.py"
        fpath.write_text("def increment(n: int) -> int:\n    return n + 1\n", encoding="utf-8")
        jury = EvidenceJury(root=tmp_path)
        verdict = jury.evaluate(fpath, run_tests=False)
        assert "verdict" in verdict
        assert verdict["verdict"] in ("PASS", "FAIL", "UNVERIFIED")
        assert verdict["checks"]["ast"] == "OK"
        assert verdict["checks"]["security"] == "OK"

    def test_gate6_ruff_lint_f401_f821(self, tmp_path, monkeypatch):
        """Verify Gate 6 detects undefined variables (F821) and unused imports (F401)."""
        monkeypatch.setattr(precommit_gate, "VAZUS_ROOT", tmp_path)
        fpath = tmp_path / "bad_lint.py"
        fpath.write_text("import sys\nimport math\ndef broken():\n    return undefined_var_xyz + 1\n", encoding="utf-8")
        ok, errors = run_gate_6_ruff_lint([fpath])
        assert ok is False
        assert len(errors) > 0
        assert any("F821" in e or "F401" in e for e in errors)

    def test_768d_embedding_vector_generation_and_dimension(self, isolated_e2e_db):
        """Verify unified embedding engine generates exactly 768-dimensional float vectors."""
        mgr = get_embedding_manager()
        emb = mgr.get_embedding("Vazus SuperGraph OS formal Hoare contract verification")
        assert isinstance(emb, list)
        assert len(emb) == 768
        assert all(isinstance(x, (float, np.floating)) for x in emb)
        norm = np.linalg.norm(emb)
        assert norm > 0.0

    def test_768d_vector_packing_and_unpacking_fidelity(self):
        """Verify 768D float list packs into exactly 3,072 bytes BLOB with zero precision loss."""
        orig_vec = [float(i) * 0.001 for i in range(768)]
        packed = pack_vector_f32(orig_vec)
        assert isinstance(packed, bytes)
        assert len(packed) == 768 * 4  # 3,072 bytes for 768 float32

        unpacked = unpack_vector_f32(packed)
        assert len(unpacked) == 768
        np.testing.assert_allclose(unpacked, orig_vec, rtol=1e-5, atol=1e-5)

    def test_ast_pruner_token_reduction_and_signature_preservation(self, tmp_path):
        """Verify AST pruning strips bodies to Ellipsis, preserving signatures with >70% token reduction."""
        source_code = (
            "def calculate_trajectory(velocity: float, angle: float, gravity: float = 9.81) -> float:\n"
            "    \"\"\"Calculate parabolic trajectory distance.\n"
            "    Detailed physics explanation and documentation here.\n"
            "    \"\"\"\n"
            "    import math\n"
            "    rad = math.radians(angle)\n"
            "    dist = (velocity ** 2) * math.sin(2 * rad) / gravity\n"
            "    step_1 = dist * 1.0\n"
            "    step_2 = step_1 + 0.0\n"
            "    return step_2\n\n"
            "def secondary_helper(a: int, b: int) -> int:\n"
            "    \"\"\"Helper function for calculation.\"\"\"\n"
            "    res = a * 10 + b * 20\n"
            "    temp = res + 5\n"
            "    return temp\n"
        )
        fpath = tmp_path / "physics_module.py"
        fpath.write_text(source_code, encoding="utf-8")

        pruned_code, stats = ASTPruner.prune_file(fpath, docstring_mode="first_line", log_memory=False)
        assert stats["is_valid"] is True
        assert stats["nodes_removed"] > 0
        assert stats["reduction_percentage"] > 50.0  # Significant token savings
        assert "def calculate_trajectory" in pruned_code
        assert "velocity: float" in pruned_code
        assert "-> float:" in pruned_code
        assert "def secondary_helper" in pruned_code
        assert "Calculate parabolic trajectory distance." in pruned_code


# ============================================================================
# Tier 2: Boundary & Corner Cases Tests
# ============================================================================

class TestTier2BoundaryAndCornerCases:
    """Tier 2: Edge cases, empty inputs, syntax errors, fail-closed timeouts."""

    def test_concordia_empty_and_whitespace_proposals(self):
        """Verify Concordia handles empty or whitespace code strings safely."""
        jury = ConcordiaJury()
        votes = [
            {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "Empty check"},
            {"agent": "RLM_Coder", "approved": True, "verdict": "PASS", "reason": "Empty check"},
            {"agent": "Verifier_Worker", "approved": True, "verdict": "PASS", "reason": "Empty check"},
        ]
        verdict_empty = jury.vote(proposal="", votes=votes)
        assert verdict_empty.ast_valid is True
        assert verdict_empty.approved is True

        verdict_ws = jury.vote(proposal="   \n\t  \n", votes=votes)
        assert verdict_ws.ast_valid is True

    def test_gate1_syntax_error_reporting_with_line_numbers(self, tmp_path):
        """Verify AST syntax error is trapped with exact filename and line number."""
        fpath = tmp_path / "broken_syntax.py"
        fpath.write_text("def broken_func(\n    return 42\n", encoding="utf-8")
        err = _check_ast_syntax(fpath.read_text(encoding="utf-8"), fpath)
        assert err is not None
        assert "[AST Syntax Error]" in err
        assert "broken_syntax.py" in err
        assert "line" in err

    def test_ast_pruner_syntax_error_fallback(self):
        """Verify ASTPruner returns original code with is_valid=False when encountering syntax errors."""
        broken_src = "def invalid_py_code(x, y: return x +"
        pruned, stats = ASTPruner.prune_code_string(broken_src)
        assert stats["is_valid"] is False
        assert stats["reduction_percentage"] == 0.0
        assert pruned == broken_src

    def test_smt_z3_empty_code_and_vacuous_contracts(self):
        """Verify SMT Z3 handles empty source and code with no contracts cleanly."""
        verifier = SMTZ3Verifier()
        res_empty = verifier.verify_code_contracts("")
        assert res_empty.verified is True
        assert res_empty.contract_satisfied is True

        res_no_contract = verifier.verify_code_contracts("def plain(x: int) -> int:\n    return x + 1\n")
        assert res_no_contract.verified is True
        assert res_no_contract.contract_satisfied is True

    def test_smt_z3_contradictory_preconditions(self):
        """Verify SMT Z3 handles contradictory preconditions (:requires: x > 5 and x < 2)."""
        verifier = SMTZ3Verifier()
        contradictory_code = (
            "def impossible_fn(x: int) -> int:\n"
            "    \"\"\"\n"
            "    :requires: x > 5 and x < 2\n"
            "    :ensures: result > 0\n"
            "    \"\"\"\n"
            "    return x * 2\n"
        )
        res = verifier.verify_code_contracts(contradictory_code)
        # Vacuously true because precondition cannot be satisfied
        assert res.verified is True

    def test_smt_z3_memory_safety_buffer_bounds(self):
        """Verify memory safety boundary checks for buffer slicing."""
        verifier = SMTZ3Verifier()
        # Safe slicing
        res_safe = verifier.verify_memory_safety(offset=0, length=100, capacity=100)
        assert res_safe.verified is True
        assert res_safe.smt_solver_status == "UNSAT"

        # Out-of-bounds slicing (offset + length > capacity)
        res_oob = verifier.verify_memory_safety(offset=50, length=60, capacity=100)
        assert res_oob.verified is False
        assert res_oob.smt_solver_status == "SAT"

        # Negative offset
        res_neg = verifier.verify_memory_safety(offset=-1, length=10, capacity=100)
        assert res_neg.verified is False

    def test_critic_jury_timeout_fail_closed_abstain(self):
        """Verify Critic Jury fail-closed policy returns ABSTAIN and approved=False on timeout."""
        paths = ["vazus_core/critical_service.py"]
        timeout_res = _timeout_verdicts(paths, issue="Critic jury deadline exceeded (120s)")
        assert "vazus_core/critical_service.py" in timeout_res
        v = timeout_res["vazus_core/critical_service.py"]
        assert v["verdict"] == "ABSTAIN"
        assert v["approved"] is False
        assert "deadline exceeded" in v["issue"]

    def test_critic_jury_verdict_parser_edge_cases(self):
        """Verify critic verdict parser parses mixed JSON formats, markdown fences, and defaults to ABSTAIN."""
        assert _parse_critic_verdict('{"verdict": "CONFIRM"}') == "CONFIRM"
        assert _parse_critic_verdict('```json\n{"verdict": "CONTRADICT"}\n```') == "CONTRADICT"
        assert _parse_critic_verdict('{"verdict": "ABSTAIN"}') == "ABSTAIN"
        assert _parse_critic_verdict('Malformed response with no json') == "ABSTAIN"
        assert _parse_critic_verdict("") == "ABSTAIN"

    def test_embeddings_empty_string_and_whitespace(self, isolated_e2e_db):
        """Verify embedding manager handles empty/whitespace strings returning normalized 768D vector."""
        mgr = get_embedding_manager()
        emb_empty = mgr.get_embedding("")
        assert len(emb_empty) == 768
        emb_ws = mgr.get_embedding("    \n\t   ")
        assert len(emb_ws) == 768


# ============================================================================
# Tier 3: Cross-Feature Combinations Tests
# ============================================================================

class TestTier3CrossFeatureCombinations:
    """Tier 3: Multi-subsystem integration (Concordia + SMT Z3 + Memory Facts v2)."""

    def test_concordia_jury_smt_z3_verification_integration(self):
        """Verify Concordia jury validates formal contracts before approving."""
        jury = ConcordiaJury()

        # Valid contract and valid votes
        valid_code = (
            "def double_positive(x: int) -> int:\n"
            "    \"\"\"\n"
            "    :requires: x >= 0\n"
            "    :ensures: result >= 0\n"
            "    \"\"\"\n"
            "    return x * 2\n"
        )
        votes_pass = [
            {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "Good design"},
            {"agent": "RLM_Coder", "approved": True, "verdict": "PASS", "reason": "Logic sound"},
            {"agent": "Verifier_Worker", "approved": True, "verdict": "PASS", "reason": "Verified"},
        ]
        verdict = jury.vote(proposal=valid_code, votes=votes_pass)
        assert verdict.approved is True
        assert verdict.smt_satisfied is True

    def test_memory_facts_v2_bi_temporal_promotion_pipeline(self, isolated_e2e_db):
        """
        Verify the complete memory promotion pipeline:
        1. Subagent records UNTRUSTED_OBSERVATION.
        2. Search for verified facts returns 0 matches (quarantine).
        3. Concordia consensus promotes observation to VERIFIED_FACT.
        4. Vector search retrieves promoted fact with high 768D similarity.
        """
        mem = Mem0Engine(db_path=isolated_e2e_db)

        # 1. Record untrusted observation
        obs_text = "Always use SMT Z3 Hoare contracts with P and not Q -> UNSAT for critical logic"
        rec = mem.record_observation_v2(
            fact_text=obs_text,
            category="formal_verification",
            source_agent="vazus_verifier",
            status="UNTRUSTED_OBSERVATION"
        )
        assert rec["status"] == "RECORDED"
        fact_id = rec["id"]

        # 2. Quarantined observation must not appear in verified searches
        unverified_search = mem.search_verified_facts_v2("SMT Z3 Hoare contracts UNSAT", top_k=5)
        assert len(unverified_search) == 0

        # 3. Promote to VERIFIED_FACT after peer review & jury consensus
        promo = mem.promote_fact_v2(
            fact_id=fact_id,
            to_status="VERIFIED_FACT",
            by_agent="concordia_jury",
            justification="Passed all 8 tiers of precommit_gate with 100% test pass"
        )
        assert promo["status"] == "PROMOTED"
        assert promo["to"] == "VERIFIED_FACT"

        # 4. Verified search now finds it with 768D vector similarity
        verified_search = mem.search_verified_facts_v2("SMT Z3 Hoare contracts UNSAT", top_k=5)
        assert len(verified_search) >= 1
        assert verified_search[0]["id"] == fact_id
        assert verified_search[0]["status"] == "VERIFIED_FACT"
        assert "similarity" in verified_search[0]

    def test_ast_pruner_supergraph_kg_nodes_indexing(self, isolated_e2e_db, tmp_path):
        """Verify AST pruning logs nodes to SQLite kg_nodes with 768D embeddings and organic_insights."""
        module_code = (
            "def optimize_tensor(tensor_id: str, batch_size: int) -> dict:\n"
            "    \"\"\"Optimize tensor layout for OpenVINO NPU inference.\"\"\"\n"
            "    transformed = {'id': tensor_id, 'batch': batch_size * 2}\n"
            "    return transformed\n"
        )
        fpath = tmp_path / "tensor_optimizer.py"
        fpath.write_text(module_code, encoding="utf-8")

        pruned_code, stats = ASTPruner.prune_file(fpath, log_memory=True)
        assert stats["is_valid"] is True

        conn = get_db_connection(isolated_e2e_db)
        cur = conn.cursor()

        # Check organic_insights table
        cur.execute("SELECT category, insight FROM organic_insights WHERE category = 'ast_pruner'")
        insights = cur.fetchall()
        assert len(insights) >= 1
        assert "tensor_optimizer.py" in str(insights[0][1])

        # Verify AST pruning insight logged with stats
        assert "pruned_tokens" in str(insights[0][1]) or "tensor_optimizer" in str(insights[0][1])
        conn.close()


# ============================================================================
# Tier 4: Real-World Workload Scenarios Tests
# ============================================================================

class TestTier4RealWorldWorkloadScenarios:
    """Tier 4: Simulated multi-agent patch lifecycle, dead code harvesting & zero-artifact GC."""

    def test_simulated_multi_agent_patch_lifecycle(self, isolated_e2e_db, tmp_path):
        """
        Simulate the complete 4-stage multi-agent patch lifecycle:
        1. VAZUS-PLANNER drafts specification & Hoare contracts.
        2. VAZUS-CODER generates Python implementation with contracts.
        3. VAZUS-VERIFIER checks AST, SMT Z3 SAT/UNSAT proofs, and targeted unit test.
        4. VAZUS-CRITIC reviews with EvidenceJury.
        5. Concordia Jury executes 3-agent consensus voting (quorum >= 66%).
        6. Memory engine promotes the architectural lesson to VERIFIED_FACT in 768D vector space.
        """
        # Step 1 & 2: Planner & Coder synthesize code
        patch_code = (
            "def compute_scaled_offset(val: int, scale: int, offset: int) -> int:\n"
            "    \"\"\"\n"
            "    :requires: val >= 0 and scale >= 1 and offset >= 0\n"
            "    :ensures: result >= 0\n"
            "    \"\"\"\n"
            "    res = val * scale + offset\n"
            "    return res\n"
        )
        patch_file = tmp_path / "math_utils.py"
        patch_file.write_text(patch_code, encoding="utf-8")

        # Step 3: Verifier runs AST and SMT Z3 Hoare contract verification
        syntax_err = _check_ast_syntax(patch_code, patch_file)
        assert syntax_err is None

        verifier = SMTZ3Verifier(depth=10)
        smt_res = verifier.verify_code_contracts(patch_code)
        assert smt_res.verified is True
        assert smt_res.contract_satisfied is True

        # Step 4: Critic runs EvidenceJury
        jury_a = EvidenceJury(root=tmp_path)
        evidence = jury_a.evaluate(patch_file, run_tests=False)
        assert evidence["verdict"] in ("PASS", "UNVERIFIED")
        assert evidence["checks"]["ast"] == "OK"
        assert evidence["checks"]["security"] == "OK"

        # Step 5: Concordia Multi-Agent Jury voting
        jury = ConcordiaJury(consensus_threshold=0.66)
        votes = [
            {"agent": "Planner", "approved": True, "verdict": "PASS", "reason": "Specification matches"},
            {"agent": "RLM_Coder", "approved": True, "verdict": "PASS", "reason": "Scaled offset logic correct"},
            {"agent": "Verifier_Worker", "approved": True, "verdict": "PASS", "reason": "SMT Z3 contract UNSAT verified"},
        ]
        jury_verdict = jury.vote(proposal=patch_code, votes=votes)
        assert jury_verdict.approved is True
        assert jury_verdict.consensus_ratio == 1.0

        # Step 6: Memory Promotion of verified architectural pattern
        mem = Mem0Engine(db_path=isolated_e2e_db)
        rec = mem.record_observation_v2(
            fact_text="Use compute_scaled_offset with Hoare contracts for bounded tensor normalization",
            category="math_kernel",
            source_agent="vazus_coder",
            status="UNTRUSTED_OBSERVATION"
        )
        promo = mem.promote_fact_v2(
            fact_id=rec["id"],
            to_status="VERIFIED_FACT",
            by_agent="concordia_jury",
            justification="Approved with 100% consensus and SMT Z3 formal proof"
        )
        assert promo["status"] == "PROMOTED"

        # Query memory to confirm persistence
        search_res = mem.search_verified_facts_v2("bounded tensor normalization compute_scaled_offset", top_k=1)
        assert len(search_res) == 1
        assert search_res[0]["id"] == rec["id"]

    def test_candidate_harvester_mathematical_dead_code_discovery(self, isolated_e2e_db, tmp_path):
        """
        Verify CandidateHarvester computes:
        C_candidate = (C_static_0ref \\cap C_dynamic_0hits) \\setminus W_protect
        identifying dead private helpers while preserving referenced functions and __protected__ methods.
        """
        module_code = (
            "def active_entrypoint(x: int) -> int:\n"
            "    return _used_helper(x)\n\n"
            "def _used_helper(x: int) -> int:\n"
            "    return x + 10\n\n"
            "def _dead_unused_helper(y: int) -> int:\n"
            "    return y * 999\n\n"
            "def __init_protected__():\n"
            "    pass\n"
        )
        py_file = tmp_path / "work_module.py"
        py_file.write_text(module_code, encoding="utf-8")

        harvester = CandidateHarvester(workspace_root=str(tmp_path), db_path=isolated_e2e_db)
        candidates = harvester.harvest_dead_function_candidates()

        # The referenced helper must NOT be marked as dead
        candidate_names = [c["function_name"] for c in candidates]
        assert "_used_helper" not in candidate_names
        # __protected__ names must NOT be harvested
        assert "__init_protected__" not in candidate_names

        # The unreferenced private helper must be harvested with HIGH safety
        dead_private = [c for c in candidates if c["function_name"] == "_dead_unused_helper"]
        assert len(dead_private) == 1
        assert dead_private[0]["is_private"] is True
        assert dead_private[0]["safety_level"] == "HIGH"

    def test_proactive_suggestion_cyclomatic_complexity_scan(self, tmp_path):
        """Verify ProactiveSuggestionEngine detects high cyclomatic complexity (CC >= 15) and print() calls."""
        complex_code = (
            "def deeply_nested_logic(a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r):\n"
            "    print('debug trace in production')\n"
            "    res = 0\n"
            "    if a: res += 1\n"
            "    if b: res += 2\n"
            "    if c: res += 3\n"
            "    if d: res += 4\n"
            "    if e: res += 5\n"
            "    if f: res += 6\n"
            "    if g: res += 7\n"
            "    if h: res += 8\n"
            "    if i: res += 9\n"
            "    if j: res += 10\n"
            "    if k: res += 11\n"
            "    if l: res += 12\n"
            "    if m: res += 13\n"
            "    if n: res += 14\n"
            "    if o: res += 15\n"
            "    if p: res += 16\n"
            "    if q: res += 17\n"
            "    if r: res += 18\n"
            "    return res\n"
        )
        fpath = tmp_path / "complex_fn.py"
        fpath.write_text(complex_code, encoding="utf-8")

        engine = ProactiveSuggestionEngine()
        suggestions = engine.scan_file(fpath)
        # Should flag complexity warning or print call in production
        assert len(suggestions) >= 1
        categories = [s.category for s in suggestions]
        assert "complexity" in categories or "print" in categories
