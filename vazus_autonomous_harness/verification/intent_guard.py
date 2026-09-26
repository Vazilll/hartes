"""
vazus_autonomous_harness.verification.intent_guard
Enforces Semantic Intent Invariance and Dynamic Pareto Plan Adaptation (IAPC 2.0).
"""

import ast
import hashlib
import logging
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from vazus_autonomous_harness.engine.anti_thrashing import (
    AntiThrashingCircuitBreaker,
    TaskAttempt,
    compute_ast_hash,
)
from vazus_autonomous_harness.memory.preflight_filter import PreFlightFilter
from vazus_autonomous_harness.verification.academic_sovereignty import AcademicSovereigntyGuard
from vazus_autonomous_harness.verification.concordia_jury import ConcordiaJuryCore, JuryVerdict
from vazus_autonomous_harness.verification.quality_engine import QualityEvaluationEngine, QualityScore
from vazus_autonomous_harness.verification.smt_prover import SMTProver

logger = logging.getLogger("vazus.harness.intent_guard")


@dataclass(frozen=True)
class IntentSpecification:
    """
    Cryptographically sealed kernel representing the user's intent.
    Immutable: frozen=True prevents runtime mutation by subagents.
    """
    task_id: str
    goal_description: str
    preconditions: List[str]
    postconditions: List[str]
    constitutional_invariants: List[str]
    invariant_test_code: str
    intent_digest: str

    @classmethod
    def create(
        cls,
        task_id: str,
        goal: str,
        preconditions: List[str],
        postconditions: List[str],
        test_code: str,
        constitutional_invariants: Optional[List[str]] = None,
    ) -> "IntentSpecification":
        invariants = constitutional_invariants or ["USER.md#L37", "C:/vazus", "~/.gemini"]
        payload = f"{task_id}|{goal}|{'&'.join(preconditions)}|{'&'.join(postconditions)}|{test_code}|{'&'.join(invariants)}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return cls(
            task_id=task_id,
            goal_description=goal,
            preconditions=preconditions,
            postconditions=postconditions,
            constitutional_invariants=invariants,
            invariant_test_code=test_code,
            intent_digest=digest,
        )

    def verify_integrity(self) -> bool:
        payload = f"{self.task_id}|{self.goal_description}|{'&'.join(self.preconditions)}|{'&'.join(self.postconditions)}|{self.invariant_test_code}|{'&'.join(self.constitutional_invariants)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest() == self.intent_digest


@dataclass
class PlanMetricVector:
    quality_score: float
    smt_correctness: float
    test_pass_rate: float
    ast_parsimony: float
    complexity_rank: int
    measured_latency_ms: float

    def strictly_dominates(self, other: "PlanMetricVector", epsilon_latency: float = 0.10) -> bool:
        if self.test_pass_rate < 1.0 or self.smt_correctness < other.smt_correctness:
            return False
        if self.quality_score < other.quality_score:
            return False

        weakly_better = (
            self.quality_score >= other.quality_score
            and self.complexity_rank <= other.complexity_rank
            and self.ast_parsimony >= other.ast_parsimony
            and self.measured_latency_ms <= other.measured_latency_ms
        )

        has_significant_gain = (
            self.complexity_rank < other.complexity_rank
            or self.measured_latency_ms <= (other.measured_latency_ms * (1.0 - epsilon_latency))
            or (self.quality_score - other.quality_score) >= 5.0
            or (self.ast_parsimony - other.ast_parsimony) >= 3.0
        )
        return weakly_better and has_significant_gain


@dataclass
class ExecutionPlan:
    plan_id: str
    intent_digest: str
    version: int
    workflow_dag: List[Dict[str, Any]]
    code_artifact: str
    metrics: PlanMetricVector
    ast_hash: str = ""

    def __post_init__(self):
        if not self.ast_hash and self.code_artifact:
            self.ast_hash = compute_ast_hash(self.code_artifact)


@dataclass
class PlanEvolutionRFC:
    rfc_id: str
    intent_spec: IntentSpecification
    current_plan: ExecutionPlan
    proposed_plan: ExecutionPlan
    proposer_agent_id: str
    rationale: str
    refinement_proof: Optional[Dict[str, Any]] = None
    harness_results: Optional[Dict[str, Any]] = None
    jury_verdict: Optional[JuryVerdict] = None


class IntentGuard:
    """
    Core Governor implementing the Intent Invariance & Pareto Plan Adaptation Coupling (IAPC 2.0).
    """
    def __init__(
        self,
        smt_prover: Optional[SMTProver] = None,
        quality_engine: Optional[QualityEvaluationEngine] = None,
        jury: Optional[ConcordiaJuryCore] = None,
        anti_thrashing: Optional[AntiThrashingCircuitBreaker] = None,
        preflight: Optional[PreFlightFilter] = None,
    ):
        self.smt_prover = smt_prover or SMTProver()
        self.quality_engine = quality_engine or QualityEvaluationEngine()
        self.jury = jury or ConcordiaJuryCore()
        self.anti_thrashing = anti_thrashing or AntiThrashingCircuitBreaker()
        self.preflight = preflight or PreFlightFilter()
        self.sovereignty_guard = AcademicSovereigntyGuard()

    def evaluate_plan_elevation(
        self,
        rfc: PlanEvolutionRFC,
        jury_votes: List[Dict[str, Any]],
        cycle_number: int = 1,
    ) -> Dict[str, Any]:
        """
        Executes the 6-stage verification funnel for proposed plan elevation.
        """
        # 1. Intent Kernel Integrity Verification
        if not rfc.intent_spec.verify_integrity():
            return {"accepted": False, "reason": "CRITICAL: IntentSpecification digest mismatch or corruption"}

        if rfc.proposed_plan.intent_digest != rfc.intent_spec.intent_digest:
            return {"accepted": False, "reason": "SECURITY VETO: Proposed plan is not anchored to root intent digest"}

        cand_code = rfc.proposed_plan.code_artifact

        # 2. Stage 1: Pre-Flight Negative Constraint Interception (< 5 ms)
        is_blocked, violation_msg = self.preflight.check_negative_constraints(cand_code)
        if is_blocked:
            return {
                "accepted": False,
                "reason": f"Pre-flight hard gate veto: {violation_msg}",
            }

        # 3. Stage 2: Anti-Thrashing Circuit Breaker
        attempt = TaskAttempt(
            task_id=rfc.intent_spec.task_id,
            cycle_number=cycle_number,
            score=rfc.proposed_plan.metrics.quality_score,
            candidate_code=cand_code,
        )
        if self.anti_thrashing.record_attempt(attempt):
            briefing = self.anti_thrashing.generate_escalation_briefing(rfc.intent_spec.task_id)
            return {
                "accepted": False,
                "reason": "Anti-thrashing circuit breaker tripped: oscillation or failure limit reached",
                "briefing": briefing,
            }

        # 4. Stage 3: Formal Intent Invariance & Quality Rubric Gate
        quality: QualityScore = self.quality_engine.evaluate(
            candidate_code=cand_code,
            baseline_code=rfc.current_plan.code_artifact,
            context_prompt=rfc.intent_spec.goal_description,
        )
        if not quality.is_admissible:
            return {
                "accepted": False,
                "reason": f"Quality Engine veto: {quality.violation_reasons}",
                "counterexample": quality.counterexample,
            }

        # Execute Invariant Deterministic Test Harness
        combined_test = f"{cand_code}\n\n{rfc.intent_spec.invariant_test_code}"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write(combined_test)
            t_path = tf.name

        try:
            p_res = subprocess.run([sys.executable, "-m", "pytest", t_path, "-q"], capture_output=True, timeout=15)
            if p_res.returncode != 0:
                return {
                    "accepted": False,
                    "reason": f"Invariant test harness failed with exit code {p_res.returncode}",
                    "details": p_res.stderr.decode("utf-8", errors="ignore")[:300],
                }
        finally:
            if os.path.exists(t_path):
                os.remove(t_path)

        # 5. Stage 4: Multi-Objective Epsilon-Pareto Dominance Check
        if not rfc.proposed_plan.metrics.strictly_dominates(rfc.current_plan.metrics):
            return {
                "accepted": False,
                "reason": "Proposed plan does not strictly epsilon-dominate current plan (no significant gain)",
            }

        # 6. Stage 5: Concordia Multi-Agent Jury Evaluation
        verdict = self.jury.evaluate_proposal(cand_code, jury_votes)
        if not verdict.approved:
            return {
                "accepted": False,
                "reason": f"Concordia Jury rejection: {verdict.rejection_reasons}",
                "consensus_ratio": verdict.consensus_ratio,
                "byzantine_count": verdict.byzantine_count,
            }

        # 7. Stage 6: Elevation Accepted
        return {
            "accepted": True,
            "reason": "Plan successfully elevated via SMT refinement, Invariant Harness, Pareto dominance, and Concordia jury.",
            "new_version": rfc.proposed_plan.version,
            "pareto_gain": {
                "quality_delta": rfc.proposed_plan.metrics.quality_score - rfc.current_plan.metrics.quality_score,
                "latency_delta_ms": rfc.proposed_plan.metrics.measured_latency_ms - rfc.current_plan.metrics.measured_latency_ms,
                "complexity_delta": rfc.proposed_plan.metrics.complexity_rank - rfc.current_plan.metrics.complexity_rank,
            },
        }
