"""
Unit tests for IntentGuard (IAPC 2.0: Intent Invariance & Dynamic Pareto Plan Adaptation).
"""

import pytest
from vazus_autonomous_harness.verification.intent_guard import (
    IntentSpecification,
    PlanMetricVector,
    ExecutionPlan,
    PlanEvolutionRFC,
    IntentGuard,
)


def test_intent_specification_integrity_and_hashing():
    spec = IntentSpecification.create(
        task_id="task_calc_sum",
        goal="Calculate sum of two integers",
        preconditions=["x >= 0", "y >= 0"],
        postconditions=["result == x + y"],
        test_code="def test_sum():\n    assert add(2, 3) == 5\n    assert add(0, 0) == 0",
    )
    assert spec.verify_integrity() is True
    assert len(spec.intent_digest) == 64


def test_plan_metric_vector_pareto_dominance():
    base_m = PlanMetricVector(
        quality_score=80.0,
        smt_correctness=40.0,
        test_pass_rate=1.0,
        ast_parsimony=10.0,
        complexity_rank=5,  # O(N^2)
        measured_latency_ms=100.0,
    )

    # Strictly superior candidate: drops complexity to O(N), latency down 50%
    superior_m = PlanMetricVector(
        quality_score=90.0,
        smt_correctness=40.0,
        test_pass_rate=1.0,
        ast_parsimony=12.0,
        complexity_rank=3,  # O(N)
        measured_latency_ms=50.0,
    )
    assert superior_m.strictly_dominates(base_m) is True

    # Inferior candidate: fails tests
    inferior_m = PlanMetricVector(
        quality_score=95.0,
        smt_correctness=40.0,
        test_pass_rate=0.8,
        ast_parsimony=15.0,
        complexity_rank=1,
        measured_latency_ms=10.0,
    )
    assert inferior_m.strictly_dominates(base_m) is False


def test_intent_guard_elevation_lifecycle():
    guard = IntentGuard()
    spec = IntentSpecification.create(
        task_id="task_add_fast",
        goal="Calculate integer sum efficiently",
        preconditions=["isinstance(a, int)", "isinstance(b, int)"],
        postconditions=["result == a + b"],
        test_code="def test_add_op():\n    assert add(10, 20) == 30\n",
    )

    base_code = "def add(a: int, b: int) -> int:\n    '''\n    :requires: True\n    :ensures: result == a + b\n    '''\n    return a + b\n"
    better_code = "def add(a: int, b: int) -> int:\n    '''\n    :requires: True\n    :ensures: result == a + b\n    '''\n    return a + b  # Optimized\n"

    p_curr = ExecutionPlan(
        plan_id="p1",
        intent_digest=spec.intent_digest,
        version=1,
        workflow_dag=[],
        code_artifact=base_code,
        metrics=PlanMetricVector(
            quality_score=80.0,
            smt_correctness=40.0,
            test_pass_rate=1.0,
            ast_parsimony=10.0,
            complexity_rank=3,
            measured_latency_ms=100.0,
        ),
    )

    p_new = ExecutionPlan(
        plan_id="p2",
        intent_digest=spec.intent_digest,
        version=2,
        workflow_dag=[],
        code_artifact=better_code,
        metrics=PlanMetricVector(
            quality_score=88.0,
            smt_correctness=40.0,
            test_pass_rate=1.0,
            ast_parsimony=12.0,
            complexity_rank=3,
            measured_latency_ms=70.0,
        ),
    )

    rfc = PlanEvolutionRFC(
        rfc_id="rfc_001",
        intent_spec=spec,
        current_plan=p_curr,
        proposed_plan=p_new,
        proposer_agent_id="vazus-coder",
        rationale="Reduced latency and improved quality score",
    )

    votes = [
        {"agent": "vazus-planner", "verdict": "PASS", "approved": True, "confidence": 0.9, "reason": "Architecture conforms"},
        {"agent": "vazus-coder", "verdict": "PASS", "approved": True, "confidence": 0.9, "reason": "Logic verified and optimal"},
        {"agent": "vazus-verifier", "verdict": "PASS", "approved": True, "confidence": 0.9, "reason": "SMT proofs hold"},
    ]

    res = guard.evaluate_plan_elevation(rfc, votes)
    # The evaluation passes intent integrity, anti-thrashing, quality, and jury
    assert res["accepted"] is True
    assert res["new_version"] == 2
    assert res["pareto_gain"]["quality_delta"] == 8.0
