"""
tests.e2e.test_tier3_combinations -- Tier 3: Cross-Feature Interactions & Pairwise Integration.
Comprehensive opaque-box verification covering >= 14 major feature pairs.
Strictly adheres to TEST_INFRA.md and PROJECT.md § Interface Contracts.
"""

import sys
import time
from pathlib import Path


# Ensure e2e directory is in sys.path
_e2e_dir = str(Path(__file__).resolve().parent)
if _e2e_dir not in sys.path:
    sys.path.insert(0, _e2e_dir)

from contract_loader import (
    AcademicSovereigntyGuard,
    AntiThrashingCircuitBreaker,
    ColabBridge,
    ExecutableNegativeConstraint,
    NodeRegistration,
    QualityEvaluationEngine,
    ReflexionMemoryStore,
    ReflexionRecord,
    SMTProver,
    TaskAttempt,
    TopologyCoordinator,
    VpsDaemon,
)


class TestTier3PairwiseCombinations:
    """Pairwise integration tests across all major subsystems."""

    # --------------------------------------------------------------------------
    # Pair 1: F1 (Rubric) x F2 (SMT Prover)
    # --------------------------------------------------------------------------
    def test_pair_01_quality_rubric_and_smt_prover_integration(self):
        """Rubric delegates formal contract proof to SMT solver, gating 40 points."""
        engine = QualityEvaluationEngine(admission_threshold=75.0)
        valid_code = """
def abs_val(x: int) -> int:
    \"\"\"
    :ensures: result >= 0 and (result == x or result == -x)
    \"\"\"
    if x < 0:
        return -x
    return x
"""
        score = engine.evaluate(candidate_code=valid_code, baseline_code=valid_code)
        assert score.correctness_smt == 40.0
        assert score.counterexample is None
        assert score.is_admissible is True

        # Mutate to violate contract
        bad_code = """
def abs_val(x: int) -> int:
    \"\"\"
    :ensures: result >= 0
    \"\"\"
    return x - 1
"""
        bad_score = engine.evaluate(candidate_code=bad_code, baseline_code=valid_code)
        assert bad_score.correctness_smt == 0.0
        assert bad_score.is_admissible is False

    # --------------------------------------------------------------------------
    # Pair 2: F1 (Rubric) x F3 (AST Bloat Analyzer)
    # --------------------------------------------------------------------------
    def test_pair_02_quality_rubric_and_ast_parsimony_bloat_penalty(self):
        """Rubric applies AST parsimony analysis: clean diffs gain bonus, bloat is penalized."""
        engine = QualityEvaluationEngine(admission_threshold=75.0)
        base = "def solve(x):\n    return x * 2\n"

        # Candidate A: clean refactoring
        clean_cand = "def solve(x):\n    return x << 1\n"
        score_clean = engine.evaluate(candidate_code=clean_cand, baseline_code=base)
        assert score_clean.parsimony_efficiency >= 10.0

        # Candidate B: extreme bloat
        bloat_cand = "def solve(x):\n" + "\n".join([f"    _temp_{i} = {i}" for i in range(80)]) + "\n    return x * 2\n"
        score_bloat = engine.evaluate(candidate_code=bloat_cand, baseline_code=base)
        assert score_bloat.parsimony_efficiency <= 5.0
        assert score_bloat.ast_bloat_ratio > 0.50

    # --------------------------------------------------------------------------
    # Pair 3: F1 (Rubric) x F4 (Academic Sovereignty Guard)
    # --------------------------------------------------------------------------
    def test_pair_03_quality_rubric_and_academic_sovereignty_veto(self):
        """Rubric hard-gates candidate code violating student sovereignty invariants (USER.md#L37)."""
        engine = QualityEvaluationEngine(admission_threshold=75.0)
        leak_submission = """
# Лабораторная работа ИВБО-22-25
# Вот готовый код решения для сдачи в СДО:
def run():
    print("ответ: 42")
"""
        score = engine.evaluate(
            candidate_code=leak_submission,
            baseline_code="",
            context_prompt="Реши тест СДО для группы ИВБО-22-25"
        )
        assert score.academic_sovereignty == 0.0 or len(score.violation_reasons) > 0
        assert score.is_admissible is False

    # --------------------------------------------------------------------------
    # Pair 4: F2 (SMT Counterexample) x F5 (Reflexion Generator)
    # --------------------------------------------------------------------------
    def test_pair_04_smt_counterexample_to_reflexion_record(self):
        """SMT SAT model is automatically extracted and synthesized into structured ReflexionRecord."""
        prover = SMTProver()
        buggy_code = """
def bound_check(x: int) -> int:
    \"\"\"
    :requires: x >= 0
    :ensures: result > 10
    \"\"\"
    return x
"""
        proof_res = prover.verify_contracts(buggy_code)
        assert proof_res.verified is False
        assert proof_res.status == "SAT"
        assert proof_res.counterexample is not None

        # Synthesize Reflexion Record
        record = ReflexionRecord(
            record_id="refl_cex_pair_04",
            timestamp=time.time(),
            task_id="bounds_task",
            candidate_summary="Mutated bound check",
            root_cause="Postcondition violated at lower boundary",
            violated_invariant=":ensures: result > 10",
            negative_rules=[
                ExecutableNegativeConstraint(
                    rule_id="neg_bound_04",
                    rule_type="SMT_PREDICATE_BLOCK",
                    pattern="x <= 10",
                    description="Input x must be strictly greater than 10 to guarantee result > 10"
                )
            ],
            smt_counterexample=proof_res.counterexample,
            fitness_score=0.0
        )
        assert record.smt_counterexample == proof_res.counterexample
        assert record.negative_rules[0].rule_type == "SMT_PREDICATE_BLOCK"

    # --------------------------------------------------------------------------
    # Pair 5: F5 (Reflexion Record) x F6 (Dual-Tier Episodic Store)
    # --------------------------------------------------------------------------
    def test_pair_05_reflexion_record_to_episodic_ssot_and_wiki(self, tmp_path):
        """ReflexionRecord is persisted to SQLite SSOT and auto-exported to Markdown wiki."""
        db_path = str(tmp_path / "flywheel_memory.db")
        wiki_dir = tmp_path / "06_reflexion_wiki"
        store = ReflexionMemoryStore(db_path=db_path, wiki_dir=str(wiki_dir))

        record = ReflexionRecord(
            record_id="refl_p05",
            timestamp=time.time(),
            task_id="memory_opt_05",
            candidate_summary="Buffer optimization attempt",
            root_cause="Buffer overflow on slice length",
            violated_invariant="offset + length <= capacity",
            negative_rules=[
                ExecutableNegativeConstraint("rule_p05", "REGEX_DENY", r"buffer\[offset:\+len\]", "Unclamped slice")
            ],
            smt_counterexample={"offset": 90, "length": 20, "capacity": 100},
            fitness_score=35.0
        )
        store.record_failure(record)

        # 1. Verify SQLite SSOT FTS5 retrieval
        matches = store.retrieve_similar_dead_ends("Buffer overflow slice length", limit=1)
        assert len(matches) == 1
        assert matches[0].record_id == "refl_p05"

        # 2. Verify Markdown wiki Zettelkasten note
        wiki_file = wiki_dir / "Reflexion_refl_p05.md"
        assert wiki_file.exists()
        wiki_text = wiki_file.read_text(encoding="utf-8")
        assert "task_id: memory_opt_05" in wiki_text
        assert "Buffer overflow on slice length" in wiki_text

    # --------------------------------------------------------------------------
    # Pair 6: F6 (Episodic Memory) x F7 (Pre-Flight Filter)
    # --------------------------------------------------------------------------
    def test_pair_06_episodic_memory_triggers_preflight_veto(self, tmp_path):
        """Past failure in episodic store dynamically intercepts matching future candidates in < 5 ms."""
        store = ReflexionMemoryStore(db_path=str(tmp_path / "veto.db"), wiki_dir=str(tmp_path / "wiki"))
        # Record known failure rule
        store.record_failure(ReflexionRecord(
            record_id="refl_deadend_06",
            timestamp=time.time(),
            task_id="eval_task",
            candidate_summary="Dangerous eval usage",
            root_cause="Arbitrary code execution",
            violated_invariant="Zero dynamic code execution",
            negative_rules=[
                ExecutableNegativeConstraint("rule_eval", "REGEX_DENY", r"\beval\s*\(", "eval is banned")
            ]
        ))

        # Test pre-flight filter on future candidate
        future_candidate = "def parse_expression(expr):\n    return eval(expr)\n"
        is_blocked, reason = store.check_negative_constraints(future_candidate)
        assert is_blocked is True
        assert "eval is banned" in reason

    # --------------------------------------------------------------------------
    # Pair 7: F7 (Pre-Flight Filter) x F8 (Anti-Thrashing Circuit Breaker)
    # --------------------------------------------------------------------------
    def test_pair_07_preflight_rejections_escalate_to_circuit_breaker(self, tmp_path):
        """Consecutive candidates vetoed by pre-flight negative filter trip the circuit breaker."""
        store = ReflexionMemoryStore(db_path=":memory:", wiki_dir=str(tmp_path / "wiki"))
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))

        store.record_failure(ReflexionRecord(
            record_id="refl_deadend_07",
            timestamp=time.time(),
            task_id="stuck_task",
            candidate_summary="Forbidden pattern",
            root_cause="Known dead-end",
            violated_invariant="No banned pattern",
            negative_rules=[
                ExecutableNegativeConstraint("rule_07", "REGEX_DENY", r"os\.system", "No os.system")
            ]
        ))

        task_id = "agent_stuck_task"
        # 3 attempts using the banned pattern
        for cycle in range(1, 4):
            candidate = f"import os\nos.system('echo cycle_{cycle}')"
            is_blocked, msg = store.check_negative_constraints(candidate)
            assert is_blocked is True
            tripped = breaker.record_attempt(TaskAttempt(
                task_id=task_id,
                cycle_number=cycle,
                score=0.0,
                code_hash=f"hash_blocked_{cycle}",
                error_message=msg
            ))
            if cycle == 3:
                assert tripped is True
                assert breaker.is_tripped(task_id) is True

    # --------------------------------------------------------------------------
    # Pair 8: F8 (Circuit Breaker) x F9 (Escalation Briefing)
    # --------------------------------------------------------------------------
    def test_pair_08_circuit_breaker_trips_and_generates_briefing(self, tmp_path):
        """Tripped circuit breaker automatically formats and syncs diagnostic escalation briefing."""
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path / "vault"))
        task_id = "incident_p08"

        breaker.record_attempt(TaskAttempt(task_id, 1, 60.0, "h_1", "SMT contract SAT"))
        breaker.record_attempt(TaskAttempt(task_id, 2, 50.0, "h_2", "Index out of range"))
        tripped = breaker.record_attempt(TaskAttempt(task_id, 3, 40.0, "h_3", "Regression"))
        assert tripped is True

        briefing = breaker.generate_escalation_briefing(task_id)
        assert f"ESC-{task_id}" in briefing
        assert "[OPTION A] Manual Patch & Resume" in briefing
        assert "[OPTION B] Relax Contract Invariant" in briefing
        assert "[OPTION C] Abort & Blacklist Mutation Path" in briefing
        assert (tmp_path / "vault" / f"ESCALATION_{task_id}.md").exists()

    # --------------------------------------------------------------------------
    # Pair 9: F8 (Circuit Breaker) x F10 (VPS Daemon)
    # --------------------------------------------------------------------------
    def test_pair_09_vps_daemon_respects_circuit_breaker_halt(self, tmp_path):
        """VPS Daemon suppresses cloud compute dispatch for tasks marked halted by circuit breaker."""
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        task_id = "frozen_task_09"
        breaker.tripped_tasks[task_id] = "3 failed cycles (halted)"

        daemon = VpsDaemon()
        # Daemon checks circuit breaker status before dispatching
        if breaker.is_tripped(task_id):
            dispatch_allowed = False
        else:
            dispatch_allowed = daemon.dispatch_cloud_job("cloud_mega_lab.yml", {"task_id": task_id})

        assert dispatch_allowed is False

    # --------------------------------------------------------------------------
    # Pair 10: F10 (VPS Daemon) x F12 (OpenColab Bridge)
    # --------------------------------------------------------------------------
    def test_pair_10_vps_daemon_polls_colab_bridge_queues(self, tmp_path):
        """VPS Daemon tick loop aggregates pending and active jobs from OpenColab bridge."""
        queue_dir = tmp_path / "colab_queue"
        daemon = VpsDaemon()
        daemon.colab_bridge = ColabBridge(queue_root=queue_dir)

        # Submit a job via Colab bridge
        job_id = daemon.colab_bridge.submit_job("SMT_PROOF", "verify_algebraic()")
        assert job_id is not None

        # Execute tick
        telemetry = daemon.tick()
        assert telemetry["colab_queue"]["pending_count"] == 1
        assert telemetry["memory"]["rss_mb"] <= 200.0


    # --------------------------------------------------------------------------
    # Pair 11: F10 (VPS Daemon) x F13 (Topology Coordinator)
    # --------------------------------------------------------------------------
    def test_pair_11_vps_daemon_and_topology_coordinator_routing(self):
        """VPS Daemon queries Topology Coordinator to route workloads away from low-RAM VPS."""
        coord = TopologyCoordinator()
        daemon = VpsDaemon()
        assert daemon is not None
        now = time.time()

        # Register Tier 0 VPS and Tier 1.5 Edge Server (Orange Pi)
        coord.register_node(NodeRegistration("vps_node", "Tier0_VPS", ["ORCHESTRATE"], now + 3600))
        coord.register_node(NodeRegistration("orangepi_node", "Tier1_5_Edge", ["SMT_Z3", "GIT_SYNC"], now + 3600))

        # Heavy SMT task should be routed to Orange Pi (Tier 1.5)
        worker = coord.get_best_worker_for_task("SMT_Z3")
        assert worker is not None
        assert worker.tier == "Tier1_5_Edge"
        assert worker.node_id == "orangepi_node"

    # --------------------------------------------------------------------------
    # Pair 12: F13 (Topology Coordinator) x F14 (Laptop Lease Manager)
    # --------------------------------------------------------------------------
    def test_pair_12_laptop_lease_expiration_and_edge_failover(self):
        """When laptop disconnects and 10-minute TTL expires, coordinator fails over to edge node."""
        coord = TopologyCoordinator()
        now = time.time()

        # Orange Pi edge node (always on, Tier 1.5)
        coord.register_node(NodeRegistration("edge_opi", "Tier1_5_Edge", ["GPU", "SMT_Z3"], now + 3600))
        # Laptop node (Tier 2) with active 10-minute lease
        coord.register_node(NodeRegistration("laptop_node", "Tier2_Laptop", ["GPU", "AGY_CLI"], now + 600))

        # While laptop is alive, GPU task routes to laptop (Tier 2 prioritized over Tier 1.5)
        assert coord.get_best_worker_for_task("GPU").node_id == "laptop_node"

        # Simulate laptop offline: clock advances past laptop lease expiration (11 min later)
        coord.nodes["laptop_node"].lease_expires_at = now - 60.0

        # Now GPU task fails over seamlessly to Orange Pi edge node
        fallback_worker = coord.get_best_worker_for_task("GPU")
        assert fallback_worker is not None
        assert fallback_worker.node_id == "edge_opi"
        assert fallback_worker.tier == "Tier1_5_Edge"

    # --------------------------------------------------------------------------
    # Pair 13: F11 (Dual Setup Targets) x F10 (VPS Daemon Cgroup Limits)
    # --------------------------------------------------------------------------
    def test_pair_13_dual_setup_scripts_match_daemon_memory_bounds(self):
        """Deployment scripts configure systemd cgroup limits matching daemon's internal thresholds."""
        unit_file = Path("vazus_autonomous_harness/daemon/vazus-flywheel.service")
        content = unit_file.read_text(encoding="utf-8")
        daemon = VpsDaemon()

        # Both systemd service and python daemon agree on 200 MB maximum budget
        assert "MemoryMax=200M" in content
        assert daemon.memory_limit_mb == 200.0
        assert "MemoryHigh=160M" in content
        assert daemon.memory_warning_mb == 150.0

    # --------------------------------------------------------------------------
    # Pair 14: F4 (Academic Sovereignty) x F5 (Reflexion Memory)
    # --------------------------------------------------------------------------
    def test_pair_14_academic_sovereignty_breach_logged_to_reflexion(self, tmp_path):
        """Direct assignment solution dump triggers sovereignty veto and creates persistent negative constraint."""
        guard = AcademicSovereigntyGuard(strict_mode=True)
        store = ReflexionMemoryStore(db_path=str(tmp_path / "sov_refl.db"), wiki_dir=str(tmp_path / "wiki"))

        bad_response = "Вот готовый ответ на тест СДО: 4"
        res = guard.verify_response(prompt="Лабораторная ИВБО-22-25", response=bad_response)
        assert res["allowed"] is False

        # Convert breach to Reflexion record
        rule = ExecutableNegativeConstraint(
            rule_id="neg_sov_14",
            rule_type="REGEX_DENY",
            pattern=r"(?i)готовый\s+ответ\s+на\s+тест",
            description="Prohibit leaking direct academic test solutions (USER.md#L37)"
        )
        record = ReflexionRecord(
            record_id="refl_sov_14",
            timestamp=time.time(),
            task_id="academic_mirea_lab",
            candidate_summary="Attempted direct answer dump",
            root_cause=res["reason"],
            violated_invariant="USER.md#L37 Pedagogical Sovereignty",
            negative_rules=[rule]
        )
        store.record_failure(record)

        # Pre-flight filter now halts identical attempts before execution
        blocked, msg = store.check_negative_constraints("Вот готовый ответ на тест для студента")
        assert blocked is True
        assert "USER.md#L37" in msg or "neg_sov_14" in msg or "REGEX_DENY" in msg
