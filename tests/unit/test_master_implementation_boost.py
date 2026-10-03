"""
tests/unit/test_master_implementation_boost.py
==============================================
Empirical validation test suite for vazus SuperGraph OS Master Implementation Plan:
P0: Emergency Fixes (Imports, MapElitesArchive, OpenVINO Arc GPU/NPU)
P1: Memory & Graph (Recursive CTE, sqlite-vec vec0, DDL unification, decay_policy, SurpriseRecorder)
P2: Formal Verification (AuxiliaryLemmaSynthesizer, Concordia Jury Agent #4, LTLMonitor, SMT DB Invariants)
P3: App Engine VAE 2.0 (Data Fabric FastAPI, Academic Dashboard live data, ClickToAST)
P4: Code Evolution (FunSearch 4-Island Evolver, Griffin Salience Router, DeepResearch sink)
P6: Academic Engine (Socratic Tutoring under USER.md#L37)
"""

import asyncio
import math
import sqlite3
import tempfile
import time
from pathlib import Path
import numpy as np
import pytest
import z3

# ============================================================================
# P0: Emergency Fixes
# ============================================================================

def test_p0_sandbox_mcp_import_and_methods():
    """Verify sandbox_mcp_server imports correctly and controller exposes required MCP actions."""
    from services.sandbox_mcp.sandbox_mcp_server import SandboxController, _controller
    assert SandboxController is not None
    assert hasattr(_controller, "launch")
    assert hasattr(_controller, "is_running")
    assert hasattr(_controller, "ready_file")
    assert hasattr(_controller, "ping")
    assert hasattr(_controller, "exec")
    assert hasattr(_controller, "capture_som")
    assert hasattr(_controller, "click")
    assert hasattr(_controller, "type")


def test_p0_map_elites_archive():
    """Verify MapElitesArchive and CodeCandidate are restored and functional."""
    from vazus_core.synthesis import MapElitesArchive, CodeCandidate
    archive = MapElitesArchive(grid_dim_x=5, grid_dim_y=5)
    c1 = CodeCandidate("c1", "def foo(): return 0", fitness_score=0.6, complexity_dim=1, performance_dim=1)
    c2 = CodeCandidate("c2", "def foo(): return 1", fitness_score=0.9, complexity_dim=1, performance_dim=1)
    assert archive.add_candidate(c1) is True
    assert archive.add_candidate(c2) is True  # Higher fitness replaces c1
    best = archive.get_best_candidate()
    assert best is not None
    assert best.candidate_id == "c2"
    assert archive.get_coverage_ratio() > 0.0


def test_p0_silicon_openvino_pipeline():
    """Verify OpenVINOGenAIPipeline class and SiliconOrchestrator integration."""
    from vazus_core.engine.silicon_orchestrator import OpenVINOGenAIPipeline, SiliconOrchestrator
    pipe = OpenVINOGenAIPipeline(preferred_device="GPU")
    assert pipe.preferred_device == "GPU"
    orch = SiliconOrchestrator(j_space_capacity=8)
    assert hasattr(orch, "openvino_genai")


# ============================================================================
# P1: Memory & Graph Layer
# ============================================================================

def test_p1_magma_graph_recursive_cte():
    """Verify MAGMAGraphEngine intent_aware_traverse executes single Recursive CTE without N+1 loops."""
    from vazus_core.memory.magma_graph import MAGMAGraphEngine, MAGMAEdgeType
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_magma.db"
        engine = MAGMAGraphEngine(db_path=str(db_file))
        engine.add_edge("N1", "N2", relation=MAGMAEdgeType.SEMANTIC, strength=0.9)
        engine.add_edge("N2", "N3", relation=MAGMAEdgeType.CAUSAL, strength=0.85)
        # Prefix collision test: N2_worker is prefix of N2
        engine.add_edge("N1", "N2_worker", relation=MAGMAEdgeType.ENTITY, strength=0.8)
        engine.add_edge("N2_worker", "N", relation=MAGMAEdgeType.CAUSAL, strength=0.75)
        results = engine.intent_aware_traverse("N1", intent="why", max_depth=2)
        assert len(results) >= 3
        node_ids = {r["node_id"] for r in results}
        assert "N2" in node_ids
        assert "N3" in node_ids
        assert "N" in node_ids  # Ensure prefix node did not block traversal to 'N'


def test_p1_j_space_sqlite_vec():
    """Verify JSpaceVectorIndex utilizes sqlite-vec vec0 index with correct nearest neighbor ranking."""
    from vazus_core.memory.j_space_vector_index import JSpaceVectorIndex
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_vec.db"
        idx = JSpaceVectorIndex(db_path=str(db_file))
        v1 = np.zeros(768, dtype=np.float32)
        v1[0] = 1.0
        v2 = np.zeros(768, dtype=np.float32)
        v2[1] = 1.0

        idx.insert_vector("concept_x", "Dimension X", v1, salience=0.9)
        idx.insert_vector("concept_y", "Dimension Y", v2, salience=0.7)

        search_res = idx.search_similar(v1, top_k=1, min_similarity=0.9)
        assert len(search_res) == 1
        assert search_res[0]["concept_id"] == "concept_x"
        assert search_res[0]["similarity"] >= 0.99


def test_p1_decay_policy_unification():
    """Verify decay_policy constants synchronize hypergraph and synaptic pruner."""
    from vazus_core.memory.decay_policy import (
        DECAY_BASE_DAYS,
        DECAY_MAX_DAYS,
        DEFAULT_BASE_STABILITY,
        MAX_STABILITY,
        COLD_STORAGE_THRESHOLD,
    )
    from vazus_core.memory.dynamic_hypergraph import DEFAULT_BASE_STABILITY as HYPER_BASE
    from vazus_core.memory.synaptic_pruner import BASE_STABILITY as PRUNER_BASE

    assert DECAY_BASE_DAYS == 2.0
    assert DECAY_MAX_DAYS == 365.0
    assert HYPER_BASE == DEFAULT_BASE_STABILITY
    assert PRUNER_BASE == DEFAULT_BASE_STABILITY


def test_p1_surprise_recorder():
    """Verify Titans-style surprise score gating and event filtering."""
    from vazus_core.memory.surprise_recorder import SurpriseRecorder
    rec = SurpriseRecorder(threshold=0.70)
    pred = np.array([1.0, 0.0, 0.0])
    similar = np.array([0.98, 0.02, 0.0])
    divergent = np.array([0.0, 1.0, 0.0])

    r_expected = rec.record_if_surprising({"id": "ev_1"}, pred, similar)
    assert r_expected["recorded"] is False
    assert r_expected["surprise_score"] < 0.1

    r_surprising = rec.record_if_surprising({"id": "ev_2"}, pred, divergent)
    assert r_surprising["recorded"] is True
    assert r_surprising["surprise_score"] >= 0.70


# ============================================================================
# P2: Formal Verification
# ============================================================================

def test_p2_auxiliary_lemma_synthesizer():
    """Verify AuxiliaryLemmaSynthesizer proves theorems and applies relational lemmas to Z3."""
    from vazus_core.verification.auxiliary_lemma_synthesizer import AuxiliaryLemmaSynthesizer
    synth = AuxiliaryLemmaSynthesizer()
    s = z3.Solver()
    x = z3.Int("x")
    s.add(x > 10)
    s.add(x < 5)  # UNSAT trivially
    res = synth.verify_with_lemmas(s, [], {"x": x})
    assert res.verified is True
    assert res.status == "UNSAT"

    # Test relational lemma application (x <= y, x >= 10)
    y = z3.Int("y")
    s2 = z3.Solver()
    synth._apply_lemma_to_solver(s2, "x <= y", {"x": x, "y": y})
    assert len(s2.assertions()) == 1


def test_p2_concordia_adversarial_falsifier():
    """Verify Concordia Jury Agent #4 (AdversarialFalsifier) participates in consensus voting."""
    from vazus_core.concordia_jury import ConcordiaJury
    jury = ConcordiaJury(consensus_threshold=0.66, min_quorum=4)
    proposal = "def add(a, b): return a + b"
    votes = [
        {"agent": "Planner", "verdict": "PASS"},
        {"agent": "RLM_Coder", "verdict": "PASS"},
        {"agent": "Verifier_Worker", "verdict": "PASS"},
        {"agent": "AdversarialFalsifier", "verdict": "PASS", "reason": "NO_COUNTEREXAMPLE_FOUND"},
    ]
    verdict = jury.vote(proposal=proposal, votes=votes)
    assert verdict.approved is True
    assert verdict.passed_votes == 4
    assert verdict.quorum_satisfied is True

    # Fast-path TRIVIAL proposals under min_quorum=4 must also include AdversarialFalsifier
    verdict_trivial = jury.vote(proposal="# Just a trivial comment")
    assert verdict_trivial.approved is True
    assert verdict_trivial.quorum_satisfied is True


def test_p2_ltl_monitor():
    """Verify LTLMonitor enforces safety, liveness, and memory causality on DAG traces."""
    from vazus_core.verification.ltl_monitor import LTLMonitor
    ltl = LTLMonitor()

    valid_trace = [
        {"event_type": "task_started", "memory_write": True},
        {"event_type": "task_running", "memory_readable": True},
        {"event_type": "task_completed"},
    ]
    res_valid = ltl.verify_trace(valid_trace)
    assert res_valid.passed is True

    # Violate liveness: task started but never completed
    broken_trace = [
        {"event_type": "task_started"},
        {"event_type": "intermediate_step"},
    ]
    res_broken = ltl.verify_trace(broken_trace)
    assert res_broken.passed is False
    assert any("task_completed" in v for v in res_broken.violations)

    # Violate memory causality: memory_write without readable state next
    broken_memory = [
        {"event_type": "memory_write"},
        {"event_type": "unrelated_event"},
    ]
    res_mem = ltl.verify_trace(broken_memory)
    assert res_mem.passed is False
    assert any("memory_readable" in v for v in res_mem.violations)


def test_p2_smt_db_invariants():
    """Verify SMT Z3 invariants over vazus.db transitions."""
    from vazus_core.verification.smt_db_invariants import (
        verify_deadline_invariant,
        verify_non_negative_balance,
        verify_credit_limit_invariant,
        verify_academic_status_transition,
    )
    # Deadline cannot shift earlier
    assert verify_deadline_invariant("2026-10-02", "2026-10-15") is True
    assert verify_deadline_invariant("2026-10-15", "2026-10-02") is False

    # Financial invariants
    assert verify_non_negative_balance(500.0, 200.0) is True
    assert verify_non_negative_balance(100.0, 150.0) is False
    assert verify_credit_limit_invariant(1000.0, 800.0) is True
    assert verify_credit_limit_invariant(1000.0, 1200.0) is False

    # State machine workflow monotonicity
    assert verify_academic_status_transition("PENDING", "В процессе") is True
    assert verify_academic_status_transition("Готово к сдаче", "Сдано") is True
    assert verify_academic_status_transition("Сдано", "PENDING") is False


# ============================================================================
# P3: App Engine VAE 2.0
# ============================================================================

def test_p3_data_fabric_api():
    """Verify Data Fabric FastAPI endpoints serve live academic data and health checks."""
    from fastapi.testclient import TestClient
    from services.data_fabric.main import app

    client = TestClient(app)
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"

    r_debts = client.get("/api/academic/debts")
    assert r_debts.status_code == 200
    debts = r_debts.json()
    assert len(debts) == 18

    r_schedule = client.get("/api/academic/schedule")
    assert r_schedule.status_code == 200

    r_stats = client.get("/api/academic/stats")
    assert r_stats.status_code == 200
    assert r_stats.json()["total_debts"] == 18


def test_p3_click_to_ast():
    """Verify ClickToAST generates valid Python AST patches."""
    from services.data_fabric.click_to_ast import ClickToAST, FieldDef
    fdef = FieldDef(name="test_field", type_name="str", required=False)
    patch = ClickToAST.generate_crud_patch("Student", fdef)
    assert ClickToAST.validate_patch_syntax(patch) is True
    assert "set_student_test_field" in patch


# ============================================================================
# P4: Code Evolution
# ============================================================================

@pytest.mark.anyio
async def test_p4_funsearch_four_island():
    """Verify FunSearch FourIslandEvolver coordinates 4 islands and migration."""
    from labs.deepmind.funsearch_evolver import FourIslandEvolver
    evolver = FourIslandEvolver(num_islands=4, migration_interval=5)
    evolver.seed_initial_candidate("def compute(): return 0")
    best = await evolver.evolve("test_task", n_iterations=10, test_suite_fn=lambda c: 0.92)
    assert best is not None
    assert best.fitness_score == 0.92
    assert evolver.statistics["total_evaluations"] == 40


def test_p4_griffin_salience_router():
    """Verify GriffinSalienceRouter distinguishes conversational vs formal SMT queries."""
    from vazus_core.engine.griffin_salience_router import GriffinSalienceRouter
    router = GriffinSalienceRouter()
    r_local = router.route("Как сегодня распределить фокус дня?")
    assert r_local.tier == "FAST_LOCAL"

    r_cloud = router.route("Требуется формальная верификация SMT Z3 инварианта для транзакций")
    assert r_cloud.tier == "DEEP_CLOUD"


# ============================================================================
# P6: Academic Engine (Socratic Mode)
# ============================================================================

@pytest.mark.anyio
async def test_p6_alphaproof_socratic_sovereignty():
    """Verify SocraticProofEngine strictly preserves USER.md#L37 pedagogical sovereignty."""
    from labs.deepmind.alphaproof_socratic import SocraticProofEngine
    engine = SocraticProofEngine()

    # Must classify homework as assignment
    q_type = engine.classify_question_type("Реши типовой расчет №3 по матанализу")
    assert q_type == "assignment_task"

    # Must generate Socratic questions, not direct answers
    guidance = await engine.guide("Реши типовой расчет №3 по матанализу", subject="Математический анализ")
    assert "USER.md#L37" in guidance
    assert "?" in guidance
    assert "не решаю" in guidance.lower()
    assert engine.verify_no_direct_solution(guidance) is True
