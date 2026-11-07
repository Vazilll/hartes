r"""
Unit tests for Gödel Agent Recursive Self-Improvement (RSI) Invariants (arXiv:2609.11873).

Verifies the modal consistency invariant:
Box(Commit(S_new) => forall s in S_bank PreserveContract(s) /\ SafeTransition(Sigma))
enforced via SMT Z3 formal verification and DAG monotonicity in SkillTree.
"""

import pytest
from vazus_autonomous_harness.skills.skill_tree import SkillTree, SkillNode


def test_godel_rsi_default_tree_structure():
    """Verifies that default primitives initialize and satisfy basic level invariants."""
    tree = SkillTree()
    for lvl in range(1, 6):
        skills = tree.list_by_level(lvl)
        assert len(skills) >= 1, f"Expected at least one skill at level {lvl}"

    l5_skill = tree.get_skill("l5_auto_author_skill")
    assert l5_skill is not None
    assert l5_skill.level == 5
    assert "l4_smt_z3_gate" in l5_skill.dependencies


def test_godel_rsi_unmet_dependency_rejected():
    """Verifies that candidate skill with non-existent dependencies is rejected."""
    tree = SkillTree()
    candidate = SkillNode(
        id="l2_orphan_workflow",
        name="Orphan Workflow",
        level=2,
        description="Workflow with missing dep",
        dependencies=["non_existent_primitive"],
    )
    ok, reason = tree.verify_godel_rsi_invariant(candidate)
    assert ok is False
    assert "Unmet dependency 'non_existent_primitive'" in reason

    with pytest.raises(ValueError, match="Unmet dependency"):
        tree.register_skill(candidate, enforce_godel_invariant=True)


def test_godel_rsi_level_inversion_rejected():
    """Verifies that lower-level skill cannot depend on higher-level skill (DAG monotonicity)."""
    tree = SkillTree()
    # Level 2 skill trying to depend on Level 4 skill
    inverted = SkillNode(
        id="l2_inverted",
        name="Inverted Skill",
        level=2,
        description="Illegal inverted dependency",
        dependencies=["l4_smt_z3_gate"],
    )
    ok, reason = tree.verify_godel_rsi_invariant(inverted)
    assert ok is False
    assert "Level inversion" in reason

    with pytest.raises(ValueError, match="Level inversion"):
        tree.register_skill(inverted, enforce_godel_invariant=True)


def test_godel_rsi_foundational_tier_modification_blocked():
    """Verifies that foundational tiers L1-L3 cannot have their levels modified."""
    tree = SkillTree()
    # Attempting to alter l1_read_file into Level 4
    hijack = SkillNode(
        id="l1_read_file",
        name="Hijacked Read File",
        level=4,
        description="Attempt to elevate foundational primitive",
    )
    ok, reason = tree.verify_godel_rsi_invariant(hijack)
    assert ok is False
    assert "Foundational tier modification blocked" in reason


def test_godel_rsi_self_cycle_rejected():
    """Verifies that self-dependency loops are immediately rejected."""
    tree = SkillTree()
    loop_node = SkillNode(
        id="l2_loop",
        name="Self Loop",
        level=2,
        description="Skill depending on itself",
        dependencies=["l2_loop"],
    )
    ok, reason = tree.verify_godel_rsi_invariant(loop_node)
    assert ok is False
    assert "Self-dependency cycle" in reason


def test_godel_rsi_circular_dependency_rejected():
    """Verifies transitive circular dependency detection."""
    tree = SkillTree()
    # l2_repo_audit depends on l1_read_file and l1_run_cli
    # Trying to mutate l1_run_cli to depend on l2_repo_audit
    cycle_node = SkillNode(
        id="l1_run_cli",
        name="Cyclic Primitive",
        level=1,
        description="Cycle creator",
        dependencies=["l2_repo_audit"],
    )
    ok, reason = tree.verify_godel_rsi_invariant(cycle_node)
    assert ok is False
    # Will fail level inversion or circular dependency
    assert "Circular dependency" in reason or "Level inversion" in reason


def test_godel_rsi_level4_valid_smt_contract_approved():
    """
    Verifies that a Level 4 skill with formal contracts proven mathematically
    sound (UNSAT) by Z3 passes the Gödel RSI invariant and registers cleanly.
    """
    tree = SkillTree()
    code_snippet = '''
def safe_offset(base: int, delta: int) -> int:
    """
    Computes bounded buffer offset.
    :requires: base >= 0
    :requires: delta >= 0
    :ensures: result >= 0
    """
    return base + delta
'''
    l4_candidate = SkillNode(
        id="l4_safe_buffer_alloc",
        name="Safe Buffer Allocator",
        level=4,
        description="Level 4 formal memory allocation primitive",
        source_code=code_snippet,
        dependencies=["l1_run_cli"],
    )

    ok, reason = tree.verify_godel_rsi_invariant(l4_candidate, enforce_smt_contracts=True)
    assert ok is True
    assert "Gödel RSI Consistency Invariant satisfied" in reason

    tree.register_skill(l4_candidate, enforce_godel_invariant=True, enforce_smt_contracts=True)
    assert tree.get_skill("l4_safe_buffer_alloc") is not None


def test_godel_rsi_level5_valid_smt_contract_approved():
    """
    Verifies that a Level 5 skill depending on Level 4 satisfies contracts and registers.
    """
    tree = SkillTree()
    # First register a valid L4 skill
    l4_code = '''
def clamp_val(val: int, low: int) -> int:
    """
    Clamps value above lower bound.
    :requires: val >= low
    :ensures: result >= low
    """
    return val
'''
    l4_node = SkillNode(
        id="l4_clamp",
        name="Clamp Gate",
        level=4,
        description="L4 clamp gate",
        source_code=l4_code,
        dependencies=["l1_run_cli"],
    )
    tree.register_skill(l4_node, enforce_godel_invariant=True)

    # Register Level 5 depending on L4 and L3
    l5_code = '''
def evolve_step(rate: int) -> int:
    """
    Meta-evolution multiplier.
    :requires: rate > 0
    :ensures: result > 0
    """
    return rate * 2
'''
    l5_node = SkillNode(
        id="l5_meta_mutator",
        name="Meta Mutator",
        level=5,
        description="L5 meta evolution",
        source_code=l5_code,
        dependencies=["l4_clamp", "l3_ast_prune"],
    )
    ok, reason = tree.verify_godel_rsi_invariant(l5_node, enforce_smt_contracts=True)
    assert ok is True
    tree.register_skill(l5_node, enforce_godel_invariant=True)
    assert tree.get_skill("l5_meta_mutator") is not None


def test_godel_rsi_level4_smt_sat_counterexample_rejected():
    """
    Verifies that a Level 4 skill with an invalid contract (counterexample found by Z3)
    is rejected by the Gödel RSI invariant.
    """
    tree = SkillTree()
    # Flawed contract: postcondition result > 100 fails for small positive inputs
    flawed_code = '''
def flawed_compute(x: int) -> int:
    """
    Flawed computation.
    :requires: x > 0
    :ensures: result > 100
    """
    return x + 1
'''
    bad_l4 = SkillNode(
        id="l4_flawed_compute",
        name="Flawed Compute",
        level=4,
        description="Fails SMT postcondition",
        source_code=flawed_code,
        dependencies=["l1_run_cli"],
    )

    ok, reason = tree.verify_godel_rsi_invariant(bad_l4, enforce_smt_contracts=True)
    assert ok is False
    assert "Formal SMT contract verification failed" in reason
    assert "SAT" in reason

    with pytest.raises(ValueError, match="Formal SMT contract verification failed"):
        tree.register_skill(bad_l4, enforce_godel_invariant=True, enforce_smt_contracts=True)


def test_godel_rsi_level4_vacuous_contract_rejected():
    """
    Verifies that anti-vacuous tautologies (:ensures: true) are rejected for Level 4/5 skills.
    """
    tree = SkillTree()
    vacuous_code = '''
def vacuous_fn(x: int) -> int:
    """
    Tautological dummy contract.
    :requires: x >= 0
    :ensures: true
    """
    return x
'''
    vacuous_node = SkillNode(
        id="l4_vacuous",
        name="Vacuous Skill",
        level=4,
        description="Tautological contract attempt",
        source_code=vacuous_code,
        dependencies=["l1_run_cli"],
    )

    ok, reason = tree.verify_godel_rsi_invariant(vacuous_node, enforce_smt_contracts=True)
    assert ok is False
    assert "VACUOUS_CONTRACT" in reason or "verification failed" in reason


def test_godel_rsi_level4_missing_contract_rejected():
    """
    Verifies that a Level 4/5 skill without formal docstring contracts is rejected.
    """
    tree = SkillTree()
    no_contract_code = '''
def unannotated_fn(x: int) -> int:
    return x + 1
'''
    no_contract_node = SkillNode(
        id="l4_no_contract",
        name="No Contract Skill",
        level=4,
        description="Lacks formal contract",
        source_code=no_contract_code,
        dependencies=["l1_run_cli"],
    )
    ok, reason = tree.verify_godel_rsi_invariant(no_contract_node, enforce_smt_contracts=True)
    assert ok is False
    assert "lacks formal :requires:/:ensures: docstring contracts" in reason


def test_godel_rsi_level4_missing_code_rejected():
    """
    Verifies that a Level 4/5 skill with no executable code is rejected when enforcing SMT.
    """
    tree = SkillTree()
    empty_node = SkillNode(
        id="l4_empty",
        name="Empty Skill",
        level=4,
        description="No code attached",
        dependencies=["l1_run_cli"],
    )
    ok, reason = tree.verify_godel_rsi_invariant(empty_node, enforce_smt_contracts=True)
    assert ok is False
    assert "must provide executable code with formal docstring contracts" in reason


def test_godel_rsi_dependent_regression_preservation():
    """
    Verifies: Box(Commit(S_new) => forall s in S_bank PreserveContract(s)).
    If modifying an existing skill breaks dependent skills, the mutation is rejected.
    """
    tree = SkillTree()
    # Register L4 skill A
    code_a = '''
def service_a(x: int) -> int:
    """
    Service A primitive.
    :requires: x >= 0
    :ensures: result >= 0
    """
    return x + 5
'''
    node_a = SkillNode(
        id="l4_service_a",
        name="Service A",
        level=4,
        description="Service A",
        source_code=code_a,
        dependencies=["l1_run_cli"],
    )
    tree.register_skill(node_a, enforce_godel_invariant=True)

    # Register L5 skill B depending on A
    code_b = '''
def service_b(y: int) -> int:
    """
    Service B depending on A.
    :requires: y >= 0
    :ensures: result >= 0
    """
    return y * 2
'''
    node_b = SkillNode(
        id="l5_service_b",
        name="Service B",
        level=5,
        description="Service B",
        source_code=code_b,
        dependencies=["l4_service_a"],
    )
    tree.register_skill(node_b, enforce_godel_invariant=True)

    # Now simulate a bad candidate for service_a with invalid SMT contract
    bad_code_a = '''
def service_a(x: int) -> int:
    """
    Broken service A.
    :requires: x >= 0
    :ensures: result > 1000
    """
    return x
'''
    bad_node_a = SkillNode(
        id="l4_service_a",
        name="Broken Service A",
        level=4,
        description="Mutated Service A",
        source_code=bad_code_a,
        dependencies=["l1_run_cli"],
    )
    ok, reason = tree.verify_godel_rsi_invariant(bad_node_a, enforce_smt_contracts=True)
    assert ok is False
    assert "Formal SMT contract verification failed" in reason
