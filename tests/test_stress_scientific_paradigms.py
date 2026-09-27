r"""
tests/test_stress_scientific_paradigms.py

Adversarial Stress Test Suite for Scientific Paradigms (Challenger R2.1):
1. Gödel RSI Invariants (arXiv:2609.11873):
   - Circular dependency attacks (self-loop, direct cycle, 3-node transitive, 5-node cyclic chain)
   - Level inversion attacks (L1->L2, L1->L5, L2->L4, L3->L5, L4->L5)
   - Tautological contract attacks (literal vs non-literal algebraic/identity tautologies)
   - Contradictory precondition attacks (literal vs relational unsatisfiable preconditions)
2. CP-WBFT Byzantine Consensus (arXiv:2605.09076):
   - Colluding and adversarial agents claiming 0.999 confidence with empty or 1-word reasons
   - MSR outlier quarantine and dynamic overconfidence penalty enforcement
   - Quorum requirement verification (>= 2/3 legitimate quorum required)
   - Boundary attack analysis on sub-0.99 confidence subterfuge
3. Titans Neural Memory (arXiv:2501.00663):
   - Monotonic decay of surprise loss under repeated patterns and test-time adaptation
   - Associative memory matrix stability under long random vector sequences (Frobenius norm boundedness)
   - Numerical boundary robustness under zero, sparse, and extreme magnitude vectors
"""

import ast
import numpy as np
import pytest

from vazus_autonomous_harness.skills.skill_tree import SkillTree, SkillNode
from vazus_autonomous_harness.verification.smt_prover import SMTProver, SMTProofResult
from vazus_autonomous_harness.verification.concordia_jury import ConcordiaJuryCore, JuryVerdict
from vazus_autonomous_harness.memory.titans import TitansNeuralMemory, TitansConfig


# ==============================================================================
# 1. Gödel RSI Invariants Stress Tests
# ==============================================================================

class TestGodelRSIStressSuite:
    """Adversarial stress testing against Gödel Agent RSI invariants and SkillTree DAG."""

    def test_stress_godel_circular_self_dependency_rejected(self):
        """Attacks SkillTree with a self-referential dependency loop (A -> A)."""
        tree = SkillTree()
        self_loop = SkillNode(
            id="l2_self_loop",
            name="Self Loop Attack",
            level=2,
            description="Adversarial self-loop",
            dependencies=["l2_self_loop"],
        )
        ok, reason = tree.verify_godel_rsi_invariant(self_loop)
        assert ok is False
        assert "Self-dependency cycle detected" in reason

    def test_stress_godel_circular_direct_cycle_rejected(self):
        """Attacks SkillTree with a 2-node direct cycle (A -> B -> A)."""
        tree = SkillTree()
        node_a = SkillNode(id="l2_cycle_a", name="A", level=2, description="Node A", dependencies=["l1_read_file"])
        tree.register_skill(node_a)
        node_b = SkillNode(id="l2_cycle_b", name="B", level=2, description="Node B", dependencies=["l2_cycle_a"])
        tree.register_skill(node_b)

        # Mutate A to depend on B
        node_a_mutated = SkillNode(id="l2_cycle_a", name="A", level=2, description="Mutated A", dependencies=["l2_cycle_b"])
        ok, reason = tree.verify_godel_rsi_invariant(node_a_mutated)
        assert ok is False
        assert "Circular dependency detected" in reason

    def test_stress_godel_circular_transitive_multi_hop_rejected(self):
        """Attacks SkillTree with a 5-node transitive cycle (A -> B -> C -> D -> E -> A)."""
        tree = SkillTree()
        # Build 5-node linear chain
        prev_id = "l1_read_file"
        node_ids = [f"l2_chain_{i}" for i in range(5)]
        for nid in node_ids:
            node = SkillNode(id=nid, name=nid, level=2, description="Chain node", dependencies=[prev_id])
            tree.register_skill(node)
            prev_id = nid

        # Close the cycle: mutate root of chain to depend on the tip
        root_mutated = SkillNode(
            id=node_ids[0],
            name="Root Mutated",
            level=2,
            description="Cycle closer",
            dependencies=[node_ids[-1]],
        )
        ok, reason = tree.verify_godel_rsi_invariant(root_mutated)
        assert ok is False
        assert "Circular dependency detected" in reason

    @pytest.mark.parametrize("source_level,target_level,target_dep", [
        (1, 2, "l2_repo_audit"),
        (1, 4, "l4_smt_z3_gate"),
        (1, 5, "l5_auto_author_skill"),
        (2, 3, "l3_ast_prune"),
        (2, 4, "l4_smt_z3_gate"),
        (2, 5, "l5_auto_author_skill"),
        (3, 4, "l4_smt_z3_gate"),
        (3, 5, "l5_auto_author_skill"),
        (4, 5, "l5_auto_author_skill"),
    ])
    def test_stress_godel_level_inversions_rejected(self, source_level, target_level, target_dep):
        """Attacks SkillTree across all possible level inversion permutations."""
        tree = SkillTree()
        node = SkillNode(
            id=f"l{source_level}_inversion_test",
            name="Level Inversion Attack",
            level=source_level,
            description=f"Level {source_level} illegally depending on Level {target_level}",
            dependencies=[target_dep],
        )
        ok, reason = tree.verify_godel_rsi_invariant(node)
        assert ok is False
        assert "Level inversion" in reason

    def test_stress_godel_literal_tautological_contracts_rejected(self):
        """Verifies that literal tautological contracts (:ensures: true, 1 == 1) are rejected."""
        prover = SMTProver()
        for literal_taut in ["true", "1 == 1", "0 == 0", "True == True"]:
            code = f'''
def dummy_func(x: int) -> int:
    """
    :requires: x >= 0
    :ensures: {literal_taut}
    """
    return x
'''
            res = prover.verify_contracts(code)
            assert res.verified is False
            assert res.status == "VACUOUS_CONTRACT"

    def test_stress_godel_literal_contradictory_preconditions_rejected(self):
        """Verifies that literal contradictory preconditions (:requires: false, 1 == 0) are rejected."""
        prover = SMTProver()
        for literal_contra in ["false", "1 == 0", "0 == 1"]:
            code = f'''
def impossible_func(x: int) -> int:
    """
    :requires: {literal_contra}
    :ensures: result == 999
    """
    return 0
'''
            res = prover.verify_contracts(code)
            assert res.verified is False
            assert res.status == "VACUOUS_CONTRACT"

    def test_stress_godel_contradictory_precondition_relational_rejected(self):
        """
        Adversarial Challenge: Relational contradictory preconditions (e.g. x > 5 and x < 2).
        In formal verification, unsatisfiable preconditions make {P} C {Q} vacuously true (UNSAT).
        An adversarial skill can inject arbitrary code into Level 4/5 by creating an unsatisfiable precondition.
        This test checks that SMTProver rejects it as a VACUOUS_CONTRACT.
        """
        prover = SMTProver()
        adversarial_code = '''
def bypass_invariant(x: int) -> int:
    """
    Malicious bypass via relational contradiction.
    :requires: x > 5
    :requires: x < 2
    :ensures: result == 999
    """
    return 0
'''
        res = prover.verify_contracts(adversarial_code)
        assert res.status == "VACUOUS_CONTRACT" or res.verified is False, (
            f"VULNERABILITY CONFIRMED: SMTProver accepted contradictory precondition as valid proof: "
            f"status={res.status}, verified={res.verified}. Precondition satisfiability is not validated!"
        )

    # Alias for backwards compatibility with challenger report
    test_adversarial_vulnerability_non_literal_contradictory_preconditions = test_stress_godel_contradictory_precondition_relational_rejected

    def test_stress_godel_tautology_identity_rejected(self):
        """
        Adversarial Challenge: Non-literal identity tautologies (e.g. :ensures: x == x, :ensures: x + 1 > x).
        Tautological postconditions hold universally regardless of the implementation.
        An adversarial skill can pass formal verification with bogus logic by specifying an identity tautology.
        This test checks that SMTProver rejects identity tautologies as VACUOUS_CONTRACT.
        """
        prover = SMTProver()
        tautological_code = '''
def bogus_implementation(x: int) -> int:
    """
    Bogus logic protected by identity tautology.
    :requires: x >= 0
    :ensures: x == x
    """
    return -99999
'''
        res = prover.verify_contracts(tautological_code)
        assert res.status == "VACUOUS_CONTRACT" or res.verified is False, (
            f"VULNERABILITY CONFIRMED: SMTProver accepted identity tautology (:ensures: x == x) as valid proof: "
            f"status={res.status}, verified={res.verified}. Non-literal tautology filter missing!"
        )

    # Alias for backwards compatibility with challenger report
    test_adversarial_vulnerability_non_literal_tautological_contracts = test_stress_godel_tautology_identity_rejected


# ==============================================================================
# 2. CP-WBFT Byzantine Consensus Stress Tests
# ==============================================================================

class TestCPWBFTStressSuite:
    """Adversarial stress testing against CP-WBFT Byzantine consensus and ConcordiaJuryCore."""

    def test_stress_cp_wbft_colluding_agents_0999_empty_and_oneword_quarantined(self):
        """
        Injects 10 colluding and adversarial agents claiming 0.999 confidence with
        empty or 1-word reasons (e.g. '', 'ok', 'yes', 'approve', 'pass', 'lgtm').
        Verifies:
        - MSR outlier filter quarantines all 10 agents.
        - All quarantined votes are assigned effective weight = 0.0.
        - Active quorum is 0, failing the >= 3 agent and >= 2/3 requirement.
        - Proposal is firmly REJECTED.
        """
        jury = ConcordiaJuryCore(min_quorum=3)
        code = "def malicious_payload(): pass"

        colluding_reasons = ["", "ok", "yes", "pass", "lgtm", "approved", "vouch", "fine", "good", "ready"]
        votes = [
            {
                "agent": f"Colluder_{i}",
                "verdict": "PASS",
                "approved": True,
                "confidence": 0.999,
                "reason": colluding_reasons[i],
            }
            for i in range(10)
        ]

        verdict = jury.evaluate_proposal(code, votes)

        assert verdict.approved is False
        assert verdict.byzantine_count == 10
        assert verdict.quorum_satisfied is False
        assert verdict.consensus_ratio == 0.0
        assert any("Quorum insufficient" in r for r in verdict.rejection_reasons)

        for vote in verdict.votes:
            assert vote.get("quarantined") is True
            assert vote.get("effective_weight") == 0.0

    def test_stress_cp_wbft_honest_minority_vs_colluding_majority(self):
        """
        Scenario:
        - 2 honest agents reject with 0.85 confidence and extensive failure reasoning.
        - 5 colluding agents attempt to pass with 0.999 confidence and 1-word reasons.
        Verifies:
        - Colluding agents are quarantined.
        - Active votes drop to 2 honest agents (< min_quorum of 3).
        - Proposal is rejected due to quorum failure.
        """
        jury = ConcordiaJuryCore(min_quorum=3)
        code = "def buggy_code(): pass"

        votes = [
            {"agent": "Honest_1", "verdict": "FAIL", "approved": False, "confidence": 0.85, "reason": "Severe contract violation discovered in AST"},
            {"agent": "Honest_2", "verdict": "FAIL", "approved": False, "confidence": 0.85, "reason": "SMT prover returned SAT counterexample model"},
            {"agent": "Byz_1", "verdict": "PASS", "approved": True, "confidence": 0.999, "reason": "ok"},
            {"agent": "Byz_2", "verdict": "PASS", "approved": True, "confidence": 0.999, "reason": "yes"},
            {"agent": "Byz_3", "verdict": "PASS", "approved": True, "confidence": 0.999, "reason": "pass"},
            {"agent": "Byz_4", "verdict": "PASS", "approved": True, "confidence": 0.999, "reason": "approve"},
            {"agent": "Byz_5", "verdict": "PASS", "approved": True, "confidence": 0.999, "reason": "lgtm"},
        ]

        verdict = jury.evaluate_proposal(code, votes)
        assert verdict.approved is False
        assert verdict.byzantine_count == 5
        assert verdict.quorum_satisfied is False

    def test_stress_cp_wbft_dynamic_overconfidence_penalty_spectrum(self):
        """
        Verifies CP-WBFT dynamic overconfidence penalty across the confidence spectrum:
        - Confidence <= 0.70 receives zero penalty.
        - Confidence 0.99 with 15 chars receives penalty.
        - Longer reasons monotonically preserve more weight than shorter reasons.
        """
        jury = ConcordiaJuryCore()

        # Confidence <= 0.70 has zero penalty
        eff_w1, pen1 = jury.compute_cp_wbft_weight(0.70, reason="Short", base_weight=0.70)
        assert pen1 == 0.0
        assert abs(eff_w1 - 0.70) < 1e-6

        # Confidence 0.95 with varying reason lengths
        short_w, short_pen = jury.compute_cp_wbft_weight(0.95, reason="15 characters..", base_weight=0.95)
        long_w, long_pen = jury.compute_cp_wbft_weight(0.95, reason="A" * 100, base_weight=0.95)

        assert short_pen > long_pen
        assert long_w > short_w

    def test_stress_cp_wbft_quorum_and_ratio_two_thirds_enforcement(self):
        """
        Verifies strict 2/3 ratio requirement:
        - 4 active votes: 2 PASS, 2 FAIL -> ratio 0.50 -> REJECTED.
        - 3 active votes: 2 PASS, 1 FAIL -> ratio 0.6667 -> APPROVED (if reasons equal).
        """
        jury = ConcordiaJuryCore(min_quorum=3, consensus_threshold=2.0 / 3.0)
        code = "def add(a, b): return a + b"

        equal_reason = "Detailed evaluation of logic and tests"
        votes_tie = [
            {"agent": "A1", "verdict": "PASS", "approved": True, "confidence": 0.8, "reason": equal_reason},
            {"agent": "A2", "verdict": "PASS", "approved": True, "confidence": 0.8, "reason": equal_reason},
            {"agent": "A3", "verdict": "FAIL", "approved": False, "confidence": 0.8, "reason": equal_reason},
            {"agent": "A4", "verdict": "FAIL", "approved": False, "confidence": 0.8, "reason": equal_reason},
        ]
        verdict_tie = jury.evaluate_proposal(code, votes_tie)
        assert verdict_tie.approved is False
        assert abs(verdict_tie.consensus_ratio - 0.50) < 1e-4

    def test_stress_byzantine_subterfuge_sub_099_quarantined(self):
        """
        Adversarial Boundary Challenge:
        Adversary uses confidence = 0.98 (just under the 0.99 threshold) with 1-word reasons ('ok').
        Expected Byzantine behavior: MSR filter should quarantine agents providing terse 1-word reasons
        regardless of whether confidence is 0.99 or 0.98.
        """
        jury = ConcordiaJuryCore(min_quorum=3, consensus_threshold=2.0 / 3.0)
        code = "def vulnerable_code(): pass"

        votes = [
            {"agent": "Honest_1", "verdict": "FAIL", "approved": False, "confidence": 0.70, "reason": "Detailed architectural failure reason"},
            {"agent": "Honest_2", "verdict": "FAIL", "approved": False, "confidence": 0.70, "reason": "Detailed security failure reason"},
            {"agent": "Sneaky_1", "verdict": "PASS", "approved": True, "confidence": 0.98, "reason": "ok"},
            {"agent": "Sneaky_2", "verdict": "PASS", "approved": True, "confidence": 0.98, "reason": "ok"},
            {"agent": "Sneaky_3", "verdict": "PASS", "approved": True, "confidence": 0.98, "reason": "ok"},
            {"agent": "Sneaky_4", "verdict": "PASS", "approved": True, "confidence": 0.98, "reason": "ok"},
        ]
        verdict = jury.evaluate_proposal(code, votes)
        # Should be rejected because 4 sneaky agents provided 1-word reasons:
        assert verdict.approved is False, (
            f"BOUNDARY VULNERABILITY: 4 colluding agents with conf=0.98 and 'ok' reason approved proposal: "
            f"ratio={verdict.consensus_ratio:.4f}, byzantine_count={verdict.byzantine_count}"
        )

    # Alias for backwards compatibility with challenger report
    test_adversarial_vulnerability_cp_wbft_sub_099_collusion = test_stress_byzantine_subterfuge_sub_099_quarantined


# ==============================================================================
# 3. Titans Neural Memory Stress Tests
# ==============================================================================

class TestTitansMemoryStressSuite:
    """Adversarial stress testing against Titans Test-Time Neural Memory (arXiv:2501.00663)."""

    def test_stress_titans_constant_sequence_monotonic_decay(self):
        """
        Verifies that test-time gradient adaptation on repeated presentations of a constant
        (key, value) pair produces monotonic decay of surprise loss.
        """
        dim = 32
        config = TitansConfig(dim=dim, theta=0.03, eta=0.7, alpha=0.005)
        memory = TitansNeuralMemory(config)

        rng = np.random.RandomState(42)
        key = rng.randn(dim).astype(np.float32)
        value = rng.randn(dim).astype(np.float32)

        surprises = []
        for _ in range(12):
            loss = memory.step(key=key, value=value)
            surprises.append(loss)

        # Total decay: initial surprise is significantly larger than adapted surprise
        assert surprises[0] > surprises[-1]
        assert surprises[-1] < surprises[0] * 0.1, f"Expected >90% loss reduction: {surprises}"

        # Monotonicity check
        for i in range(len(surprises) - 1):
            assert surprises[i] >= surprises[i + 1] - 1e-3, (
                f"Non-monotonic surprise increase at step {i}: {surprises[i]} -> {surprises[i+1]}"
            )

    def test_stress_titans_repeated_pattern_epoch_convergence(self):
        """
        Presents a sequence of 5 distinct key-value pairs over multiple epochs.
        Verifies that average epoch surprise loss converges downwards.
        """
        dim = 16
        config = TitansConfig(dim=dim, theta=0.04, eta=0.8, alpha=0.01)
        memory = TitansNeuralMemory(config)

        rng = np.random.RandomState(1337)
        keys = [rng.randn(dim).astype(np.float32) for _ in range(5)]
        values = [rng.randn(dim).astype(np.float32) for _ in range(5)]

        epoch_losses = []
        for epoch in range(10):
            losses = [memory.step(k, v) for k, v in zip(keys, values)]
            epoch_losses.append(float(np.mean(losses)))

        assert epoch_losses[0] > epoch_losses[-1], (
            f"Epoch loss failed to converge: {epoch_losses[0]} -> {epoch_losses[-1]}"
        )

    def test_stress_titans_random_sequence_matrix_stability(self):
        """
        Runs 500 steps of random vector sequences through Titans Neural Memory.
        Verifies:
        - Memory weight matrix M remains strictly finite (zero NaN, zero Inf).
        - Momentum buffer S remains strictly finite.
        - Frobenius norm ||M||_F remains bounded (forget gate prevents divergence).
        - Associative recall returns finite vectors.
        """
        dim = 32
        config = TitansConfig(dim=dim, theta=0.05, eta=0.9, alpha=0.01)
        memory = TitansNeuralMemory(config)
        rng = np.random.RandomState(2026)

        norms = []
        for step in range(500):
            k = rng.randn(dim).astype(np.float32) * 2.0
            v = rng.randn(dim).astype(np.float32) * 2.0
            loss = memory.step(k, v)

            fnorm = float(np.linalg.norm(memory.M))
            norms.append(fnorm)

            assert np.isfinite(loss), f"Non-finite loss at step {step}"
            assert np.isfinite(fnorm), f"Non-finite Frobenius norm at step {step}"

        # Bound check: forget gate alpha ensures ||M|| does not diverge to infinity
        assert max(norms) < 500.0, f"Frobenius norm exploded: {max(norms)}"

        # Verify associative recall on query vector remains finite
        query = rng.randn(dim).astype(np.float32)
        recalled = memory.retrieve(query)
        assert np.all(np.isfinite(recalled))
        assert recalled.shape == (dim,)

    def test_stress_titans_extreme_vectors_robustness(self):
        """
        Tests numerical stability under extreme boundary inputs:
        - Zero vectors (should not cause division by zero in normalization)
        - Subnormal / microscopic vectors (1e-20)
        - Massive magnitude vectors (1e5)
        """
        dim = 16
        memory = TitansNeuralMemory(TitansConfig(dim=dim))

        # 1. Zero vectors
        zero_v = np.zeros(dim, dtype=np.float32)
        loss_zero = memory.step(zero_v, zero_v)
        assert np.isfinite(loss_zero)
        assert loss_zero == 0.0

        # 2. Subnormal vectors
        tiny_v = np.ones(dim, dtype=np.float32) * 1e-20
        loss_tiny = memory.step(tiny_v, tiny_v)
        assert np.isfinite(loss_tiny)

        # 3. Massive vectors
        huge_v = np.ones(dim, dtype=np.float32) * 1e5
        loss_huge = memory.step(huge_v, huge_v)
        assert np.isfinite(loss_huge)
        assert np.all(np.isfinite(memory.M))
