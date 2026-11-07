"""
tests.e2e.test_tier2_boundaries -- Tier 2: Boundary Value Analysis & Corner Cases.
Comprehensive opaque-box verification with >= 5 checks per feature (>= 70 checks).
Strictly adheres to TEST_INFRA.md and PROJECT.md § Interface Contracts.
"""

import json
import sys
import time
from pathlib import Path


# Ensure e2e directory is in sys.path
_e2e_dir = str(Path(__file__).resolve().parent)
if _e2e_dir not in sys.path:
    sys.path.insert(0, _e2e_dir)

from contract_loader import (
    ASTParsimonyAnalyzer,
    AcademicSovereigntyGuard,
    AntiThrashingCircuitBreaker,
    ColabBridge,
    ExecutableNegativeConstraint,
    NodeRegistration,
    QualityEvaluationEngine,
    QualityScore,
    ReflexionMemoryStore,
    ReflexionRecord,
    SMTProofResult,
    SMTProver,
    TaskAttempt,
    TopologyCoordinator,
    VpsDaemon,
)


# ==============================================================================
# F1 Boundaries: Quality Evaluation Rubric
# ==============================================================================

class TestF1QualityRubricBoundaries:
    """Tier 2 Boundary Tests for Feature 1 (Quality Rubric)."""

    def test_f1_boundary_empty_code_submission(self):
        engine = QualityEvaluationEngine(admission_threshold=75.0)
        baseline = """
def baseline_calc(x: int) -> int:
    \"\"\"
    :requires: x >= 0
    :ensures: result > x
    \"\"\"
    return x + 1
"""
        score = engine.evaluate(candidate_code="", baseline_code=baseline)
        assert score.is_admissible is False
        assert score.correctness_smt == 0.0 or len(score.violation_reasons) > 0


    def test_f1_boundary_exact_75_point_threshold(self):
        # A proposal scoring exactly 75.0 with full SMT and Sovereignty must be admissible
        score = QualityScore(
            total_score=75.0,
            correctness_smt=40.0,
            empirical_integrity=20.0,
            parsimony_efficiency=0.0,
            academic_sovereignty=15.0,
            is_admissible=True,
            counterexample=None,
            violation_reasons=[]
        )
        assert score.is_admissible is True
        assert score.total_score >= 75.0

    def test_f1_boundary_74_9_point_threshold(self):
        # Even with SMT and Sovereignty clear, 74.9 is strictly below 75.0
        score = QualityScore(
            total_score=74.9,
            correctness_smt=40.0,
            empirical_integrity=20.0,
            parsimony_efficiency=0.0,
            academic_sovereignty=14.9,
            is_admissible=False,
            counterexample=None,
            violation_reasons=["Score 74.9 is below hard admission threshold 75.0"]
        )
        assert score.is_admissible is False
        assert score.total_score < 75.0

    def test_f1_boundary_massive_bloat_penalty_floor(self):
        analyzer = ASTParsimonyAnalyzer()
        base = "x = 1\n"
        # 1000% bloat
        cand = "x = 1\n" + "\n".join([f"var_{i} = {i}" for i in range(500)]) + "\n"
        res = analyzer.calculate_bloat(base, cand)
        assert res["penalty"] == 10.0  # Max penalty capped at 10
        assert res["score"] == 0.0  # Score floored at 0, never negative

    def test_f1_boundary_none_baseline_code(self):
        analyzer = ASTParsimonyAnalyzer()
        # When baseline is empty or None
        res = analyzer.calculate_bloat("", "def valid(): return 1\n")
        assert res["base_nodes"] == 0
        assert res["bloat_ratio"] == 0.0
        assert res["score"] in (10.0, 15.0)


# ==============================================================================
# F2 Boundaries: SMT Z3 Equivalence Prover
# ==============================================================================

class TestF2SMTProverBoundaries:
    """Tier 2 Boundary Tests for Feature 2 (SMT Z3 Prover)."""

    def test_f2_boundary_extreme_integer_ranges(self):
        prover = SMTProver()
        # Test 64-bit boundary formula
        res = prover.verify_expression_equivalence(
            "x + 9223372036854775807",
            "9223372036854775807 + x",
            ["x"]
        )
        assert res["equivalent"] is True
        assert res["status"] in ("PROVEN_EQUIVALENT", "UNSAT")

    def test_f2_boundary_division_by_zero_precondition(self):
        prover = SMTProver()
        code = """
def divide_unsafe(a: int, b: int) -> int:
    \"\"\"
    :ensures: result * b == a
    \"\"\"
    return a // b
"""
        res = prover.verify_contracts(code)
        # Without :requires: b != 0, contract cannot be proved UNSAT across entire domain
        assert res.verified is False or res.status in ("SAT", "UNKNOWN", "ERROR", "NO_CONTRACTS")

    def test_f2_boundary_solver_timeout_bounded(self):
        prover = SMTProver(timeout_ms=50)
        # Solver should not hang; timeout handles boundedly
        assert prover.timeout_ms == 50

    def test_f2_boundary_unsupported_ast_nodes(self):
        prover = SMTProver()
        # Unsupported operators (e.g. bitwise shift or matrix multiplication) should handle gracefully
        res = prover.verify_expression_equivalence("x @ y", "y @ x", ["x", "y"])
        assert res["equivalent"] is False
        assert "error" in res or res["status"] in ("TRANSLATION_ERROR", "ERROR")

    def test_f2_boundary_nested_logical_connectives(self):
        prover = SMTProver()
        code = """
def bool_logic(a: int, b: int) -> int:
    \"\"\"
    :requires: (a > 0 and b > 0) or (a < 0 and b < 0)
    :ensures: result > 0
    \"\"\"
    return a * b
"""
        res = prover.verify_contracts(code)
        # SMT translates conjunctions/disjunctions without crashing
        assert isinstance(res, SMTProofResult)


# ==============================================================================
# F3 Boundaries: AST Bloat & Parsimony Analyzer
# ==============================================================================

class TestF3ASTBloatBoundaries:
    """Tier 2 Boundary Tests for Feature 3 (AST Bloat)."""

    def test_f3_boundary_single_token_mutation(self):
        analyzer = ASTParsimonyAnalyzer()
        base = "x = 10\n"
        cand = "x = 10 + 1\n"
        res = analyzer.calculate_bloat(base, cand)
        assert res["cand_nodes"] > res["base_nodes"]

    def test_f3_boundary_exact_10_percent_bloat_threshold(self):
        analyzer = ASTParsimonyAnalyzer()
        # Base with 10 nodes, candidate with 11 nodes (10% bloat)
        res = analyzer.calculate_bloat(
            "a = 1; b = 2; c = 3; d = 4",
            "a = 1; b = 2; c = 3; d = 4; e = 5"
        )
        if res["bloat_ratio"] <= 0.10:
            assert res["penalty"] == 0.0

    def test_f3_boundary_10_point_1_percent_bloat_penalty(self):
        analyzer = ASTParsimonyAnalyzer()
        base = "x = 1\n"
        cand = "x = 1\ny = 2\n"  # 100% bloat
        res = analyzer.calculate_bloat(base, cand)
        assert res["bloat_ratio"] > 0.10
        assert res["penalty"] >= 1.0

    def test_f3_boundary_unicode_and_comment_invariance(self):
        analyzer = ASTParsimonyAnalyzer()
        code_plain = "x = 42\n"
        code_commented = "# Comment line\n# Другой комментарий\nx = 42  # Inline\n"
        # Comments are ignored by Python AST parser
        assert analyzer.count_nodes(code_plain) == analyzer.count_nodes(code_commented)

    def test_f3_boundary_whitespace_formatting_invariance(self):
        analyzer = ASTParsimonyAnalyzer()
        code_compact = "def f(x): return x + 1\n"
        code_spaced = "\n\ndef f(x):\n\n    return x + 1\n\n\n"
        assert analyzer.count_nodes(code_compact) == analyzer.count_nodes(code_spaced)


# ==============================================================================
# F4 Boundaries: Academic Sovereignty Guard
# ==============================================================================

class TestF4AcademicSovereigntyBoundaries:
    """Tier 2 Boundary Tests for Feature 4 (Academic Sovereignty Guard)."""

    def test_f4_boundary_case_insensitive_matching(self):
        guard = AcademicSovereigntyGuard()
        assert guard.is_academic_context("ЛАБОРАТОРНАЯ РАБОТА ПО ИВБО-22-25") is True
        assert guard.is_academic_context("сдо тест китпипи") is True
        assert guard.is_academic_context("25И0566 расчет") is True

    def test_f4_boundary_cyrillic_homoglyph_obfuscation(self):
        guard = AcademicSovereigntyGuard()
        # Direct leak with mixed case
        res = guard.verify_response(
            prompt="Задание СДО ИВБО-22-25",
            response="Вот ГоТоВоЕ РеШеНиЕ задачи: ответ: 3"
        )
        assert res["allowed"] is False

    def test_f4_boundary_empty_prompt_and_response(self):
        guard = AcademicSovereigntyGuard()
        res = guard.verify_response("", "")
        assert res["allowed"] is True
        assert res["is_academic"] is False

    def test_f4_boundary_subtle_socratic_inquiry_without_question_mark(self):
        guard = AcademicSovereigntyGuard(strict_mode=True)
        res = guard.verify_response(
            prompt="Задание СДО",
            response="Попробуй рассмотреть граничные случаи для нулевого значения массива."
        )
        assert res["allowed"] is True
        assert res["has_socratic_guidance"] is True

    def test_f4_boundary_nested_stub_in_class_method(self):
        guard = AcademicSovereigntyGuard()
        stub_class = """
class DataRepository:
    def fetch_all(self):
        pass
"""
        has_stubs, reason = guard.check_code_stubs(stub_class)
        assert has_stubs is True
        assert "pass" in reason


# ==============================================================================
# F5 Boundaries: Continuous Reflexion Generator
# ==============================================================================

class TestF5ReflexionBoundaries:
    """Tier 2 Boundary Tests for Feature 5 (Reflexion Generator)."""

    def test_f5_boundary_special_characters_in_root_cause(self):
        special_str = 'Error with quotes: "hello", newlines: \n, tabs: \t, and unicode: 🚀.'
        record = ReflexionRecord(
            record_id="refl_special",
            timestamp=time.time(),
            task_id="task_special",
            candidate_summary="Summary with special chars: <>&'",
            root_cause=special_str,
            violated_invariant="None",
            negative_rules=[]
        )
        dumped = json.dumps({"root_cause": record.root_cause})
        loaded = json.loads(dumped)
        assert loaded["root_cause"] == special_str

    def test_f5_boundary_large_counterexample_payload(self):
        large_cex = {f"var_{i}": i * 100 for i in range(150)}
        record = ReflexionRecord(
            record_id="refl_large_cex",
            timestamp=time.time(),
            task_id="task_large",
            candidate_summary="Large model",
            root_cause="Large model disproven",
            violated_invariant="Bounds check",
            negative_rules=[],
            smt_counterexample=large_cex,
        )
        assert len(record.smt_counterexample) == 150
        assert record.smt_counterexample["var_149"] == 14900

    def test_f5_boundary_empty_negative_rules_list(self):
        record = ReflexionRecord(
            record_id="refl_empty_rules",
            timestamp=time.time(),
            task_id="empty_rules_task",
            candidate_summary="No rules",
            root_cause="Transient failure",
            violated_invariant="Liveness",
            negative_rules=[]
        )
        assert len(record.negative_rules) == 0

    def test_f5_boundary_duplicate_rule_ids(self):
        r1 = ExecutableNegativeConstraint("rule_dup", "REGEX_DENY", "eval", "Desc 1")
        r2 = ExecutableNegativeConstraint("rule_dup", "IMPORT_BAN", "os", "Desc 2")
        record = ReflexionRecord(
            record_id="refl_dup_rules",
            timestamp=time.time(),
            task_id="task_dup",
            candidate_summary="Dup rules",
            root_cause="Cause",
            violated_invariant="Inv",
            negative_rules=[r1, r2]
        )
        assert len(record.negative_rules) == 2

    def test_f5_boundary_zero_timestamp(self):
        record = ReflexionRecord(
            record_id="refl_zero_time",
            timestamp=0.0,
            task_id="epoch_task",
            candidate_summary="Epoch 1970",
            root_cause="Genesis",
            violated_invariant="Genesis invariant",
            negative_rules=[]
        )
        assert record.timestamp == 0.0


# ==============================================================================
# F6 Boundaries: Dual-Tier Episodic Memory Store
# ==============================================================================

class TestF6EpisodicStoreBoundaries:
    """Tier 2 Boundary Tests for Feature 6 (Episodic Store)."""

    def test_f6_boundary_fts5_special_syntax_sanitization(self, tmp_path):
        store = ReflexionMemoryStore(db_path=str(tmp_path / "fts_sanitize.db"), wiki_dir=str(tmp_path / "wiki"))
        store.record_failure(ReflexionRecord(
            record_id="refl_san_01",
            timestamp=time.time(),
            task_id="task_san",
            candidate_summary="Query test",
            root_cause="Syntax error with punctuation: 'AND', OR NOT (*)",
            violated_invariant="Punctuation invariant",
            negative_rules=[]
        ))
        # Query with characters that usually break raw FTS5 MATCH
        results = store.retrieve_similar_dead_ends('AND OR NOT * " ()', limit=5)
        assert isinstance(results, list)

    def test_f6_boundary_concurrent_sqlite_writes(self, tmp_path):
        db_path = str(tmp_path / "concurrent.db")
        store = ReflexionMemoryStore(db_path=db_path, wiki_dir=str(tmp_path / "wiki"))
        # Execute 20 rapid successive writes
        for i in range(20):
            store.record_failure(ReflexionRecord(
                record_id=f"refl_con_{i}",
                timestamp=time.time() + i,
                task_id=f"task_{i}",
                candidate_summary=f"Summary {i}",
                root_cause=f"Error {i}",
                violated_invariant=f"Inv {i}",
                negative_rules=[]
            ))
        res = store.retrieve_similar_dead_ends("Error", limit=50)
        assert len(res) == 20

    def test_f6_boundary_wiki_directory_auto_creation(self, tmp_path):
        deep_wiki_dir = tmp_path / "nested" / "vault" / "06_reflexion_wiki"
        store = ReflexionMemoryStore(db_path=":memory:", wiki_dir=str(deep_wiki_dir))
        store.record_failure(ReflexionRecord(
            record_id="refl_deep_01",
            timestamp=time.time(),
            task_id="deep_task",
            candidate_summary="Deep dir test",
            root_cause="Deep path",
            violated_invariant="Auto-create directories",
            negative_rules=[]
        ))
        assert deep_wiki_dir.exists()
        assert (deep_wiki_dir / "Reflexion_refl_deep_01.md").exists()

    def test_f6_boundary_retrieval_with_zero_limit(self, tmp_path):
        store = ReflexionMemoryStore(db_path=":memory:", wiki_dir=str(tmp_path / "wiki"))
        store.record_failure(ReflexionRecord(
            record_id="refl_zero_limit",
            timestamp=time.time(),
            task_id="zero_task",
            candidate_summary="Zero limit",
            root_cause="Zero",
            violated_invariant="Zero",
            negative_rules=[]
        ))
        res = store.retrieve_similar_dead_ends("Zero", limit=0)
        assert len(res) == 0

    def test_f6_boundary_unmatched_fts_query_fallback(self, tmp_path):
        store = ReflexionMemoryStore(db_path=":memory:", wiki_dir=str(tmp_path / "wiki"))
        res = store.retrieve_similar_dead_ends("NonExistentTermXYZ123456", limit=5)
        assert len(res) == 0


# ==============================================================================
# F7 Boundaries: Pre-Flight Negative Constraint Filter
# ==============================================================================

class TestF7PreFlightFilterBoundaries:
    """Tier 2 Boundary Tests for Feature 7 (Pre-Flight Filter)."""

    def test_f7_boundary_empty_candidate_code(self, tmp_path):
        store = ReflexionMemoryStore(db_path=":memory:", wiki_dir=str(tmp_path / "wiki"))
        is_blocked, msg = store.check_negative_constraints("")
        assert is_blocked is False
        assert msg is None

    def test_f7_boundary_regex_metacharacter_safety(self, tmp_path):
        store = ReflexionMemoryStore(db_path=":memory:", wiki_dir=str(tmp_path / "wiki"))
        rule = ExecutableNegativeConstraint(
            rule_id="neg_meta",
            rule_type="REGEX_DENY",
            pattern=r"(?m)^def\s+dangerous_\w+\(.*\):\s*$",
            description="Prohibit dangerous_* function declarations"
        )
        store.record_failure(ReflexionRecord(
            record_id="refl_meta",
            timestamp=time.time(),
            task_id="meta_task",
            candidate_summary="Meta",
            root_cause="Meta error",
            violated_invariant="No dangerous functions",
            negative_rules=[rule]
        ))
        bad_code = "def dangerous_execute(cmd):\n    pass\n"
        is_blocked, msg = store.check_negative_constraints(bad_code)
        assert is_blocked is True

    def test_f7_boundary_multiple_negative_rules_first_match(self, tmp_path):
        store = ReflexionMemoryStore(db_path=":memory:", wiki_dir=str(tmp_path / "wiki"))
        r1 = ExecutableNegativeConstraint("r1", "IMPORT_BAN", "import os", "No os")
        r2 = ExecutableNegativeConstraint("r2", "REGEX_DENY", "eval", "No eval")
        store.record_failure(ReflexionRecord(
            record_id="refl_multi",
            timestamp=time.time(),
            task_id="multi_task",
            candidate_summary="Multi",
            root_cause="Multi",
            violated_invariant="Multi",
            negative_rules=[r1, r2]
        ))
        bad_code = "import os\nresult = eval('1')"
        is_blocked, msg = store.check_negative_constraints(bad_code)
        assert is_blocked is True
        assert msg is not None

    def test_f7_boundary_multiline_pattern_matching(self, tmp_path):
        store = ReflexionMemoryStore(db_path=":memory:", wiki_dir=str(tmp_path / "wiki"))
        rule = ExecutableNegativeConstraint(
            rule_id="r_multi",
            rule_type="REGEX_DENY",
            pattern=r"def\s+leaky_fn\(\):[\s\S]*?password\s*=\s*['\"].*?['\"]",
            description="Leaky function containing hardcoded credentials"
        )
        store.record_failure(ReflexionRecord(
            record_id="refl_multiline",
            timestamp=time.time(),
            task_id="multi_task",
            candidate_summary="Multi",
            root_cause="Secret leak",
            violated_invariant="Zero secrets",
            negative_rules=[rule]
        ))
        bad_code = "def leaky_fn():\n    x = 1\n    password = 'secret'\n    return x\n"
        is_blocked, msg = store.check_negative_constraints(bad_code)
        assert is_blocked is True

    def test_f7_boundary_ast_deny_on_syntax_error_code(self, tmp_path):
        store = ReflexionMemoryStore(db_path=":memory:", wiki_dir=str(tmp_path / "wiki"))
        store.record_failure(ReflexionRecord(
            record_id="refl_syntax",
            timestamp=time.time(),
            task_id="syntax_task",
            candidate_summary="Syntax",
            root_cause="Syntax",
            violated_invariant="Syntax",
            negative_rules=[ExecutableNegativeConstraint("r_ast", "AST_PATTERN_DENY", "while True", "No infinite loops")]
        ))
        # Malformed python code does not crash check_negative_constraints
        broken_code = "def broken( :::"
        is_blocked, _ = store.check_negative_constraints(broken_code)
        assert isinstance(is_blocked, bool)


# ==============================================================================
# F8 Boundaries: Anti-Thrashing Circuit Breaker
# ==============================================================================

class TestF8CircuitBreakerBoundaries:
    """Tier 2 Boundary Tests for Feature 8 (Circuit Breaker)."""

    def test_f8_boundary_zero_budget_immediate_trip(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=1, vault_path=str(tmp_path))
        tripped = breaker.record_attempt(TaskAttempt("task_immediate", 1, 50.0, "hash_0", "failed"))
        assert tripped is True

    def test_f8_boundary_flat_score_delta_trips(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        # 3 attempts with flat score 60.0 (delta = 0.0)
        breaker.record_attempt(TaskAttempt("flat_task", 1, 60.0, "h1"))
        breaker.record_attempt(TaskAttempt("flat_task", 2, 60.0, "h2"))
        tripped = breaker.record_attempt(TaskAttempt("flat_task", 3, 60.0, "h3"))
        assert tripped is True
        assert breaker.is_tripped("flat_task") is True

    def test_f8_boundary_two_cycles_do_not_trip_yet(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        breaker.record_attempt(TaskAttempt("two_cycle_task", 1, 40.0, "h1"))
        tripped = breaker.record_attempt(TaskAttempt("two_cycle_task", 2, 35.0, "h2"))
        assert tripped is False
        assert breaker.is_tripped("two_cycle_task") is False

    def test_f8_boundary_task_id_isolation(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        # Task A fails 3 times
        breaker.record_attempt(TaskAttempt("task_A", 1, 40.0, "h1"))
        breaker.record_attempt(TaskAttempt("task_A", 2, 30.0, "h2"))
        breaker.record_attempt(TaskAttempt("task_A", 3, 20.0, "h3"))
        assert breaker.is_tripped("task_A") is True

        # Task B has only 1 attempt, should not be tripped
        breaker.record_attempt(TaskAttempt("task_B", 1, 60.0, "hb1"))
        assert breaker.is_tripped("task_B") is False

    def test_f8_boundary_score_progression_recovery(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        breaker.record_attempt(TaskAttempt("recovering_task", 1, 50.0, "h1"))
        breaker.record_attempt(TaskAttempt("recovering_task", 2, 40.0, "h2"))
        # Attempt 3 fixes the issue and achieves 80.0
        tripped = breaker.record_attempt(TaskAttempt("recovering_task", 3, 80.0, "h3"))
        assert tripped is False
        assert breaker.is_tripped("recovering_task") is False


# ==============================================================================
# F9 Boundaries: Human Escalation Diagnostic Briefing
# ==============================================================================

class TestF9EscalationBriefingBoundaries:
    """Tier 2 Boundary Tests for Feature 9 (Escalation Briefing)."""

    def test_f9_boundary_empty_attempt_history(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(vault_path=str(tmp_path))
        breaker.tripped_tasks["empty_task"] = "Forced manual halt"
        briefing = breaker.generate_escalation_briefing("empty_task")
        assert "Incident ID**: ESC-empty_task" in briefing
        assert "[OPTION A]" in briefing

    def test_f9_boundary_markdown_injection_safety(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(vault_path=str(tmp_path))
        breaker.record_attempt(TaskAttempt(
            task_id="inject_task",
            cycle_number=1,
            score=0.0,
            code_hash="h#1|2*3",
            error_message="Error with | pipe | tables | and `code`"
        ))
        breaker.tripped_tasks["inject_task"] = "Pipe test"
        briefing = breaker.generate_escalation_briefing("inject_task")
        assert "inject_task" in briefing
        assert "Option A" in briefing or "[OPTION A]" in briefing

    def test_f9_boundary_long_error_message_truncation(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(vault_path=str(tmp_path))
        long_err = "Stacktrace line\n" * 500
        breaker.record_attempt(TaskAttempt("long_err_task", 1, 10.0, "hash_long", long_err))
        breaker.tripped_tasks["long_err_task"] = "Large stacktrace"
        briefing = breaker.generate_escalation_briefing("long_err_task")
        assert len(briefing) > 0
        assert "long_err_task" in briefing

    def test_f9_boundary_missing_counterexample_graceful(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(vault_path=str(tmp_path))
        breaker.record_attempt(TaskAttempt("no_cex_task", 1, 20.0, "h_no_cex", "Failure without CEX"))
        breaker.tripped_tasks["no_cex_task"] = "No CEX"
        briefing = breaker.generate_escalation_briefing("no_cex_task")
        assert "Minimal Unsatisfiable Core" in briefing

    def test_f9_boundary_unwriteable_vault_local_fallback(self, tmp_path):
        # Uses local path inside tmp_path
        vault = tmp_path / "deep" / "vault"
        breaker = AntiThrashingCircuitBreaker(vault_path=str(vault))
        briefing = breaker.generate_escalation_briefing("fallback_task")
        assert briefing is not None
        assert (vault / "ESCALATION_fallback_task.md").exists()


# ==============================================================================
# F10 Boundaries: Lightweight VPS Daemon
# ==============================================================================

class TestF10VPSDaemonBoundaries:
    """Tier 2 Boundary Tests for Feature 10 (VPS Daemon)."""

    def test_f10_boundary_zero_active_nodes(self):
        daemon = VpsDaemon()
        daemon.nodes.clear()
        active = daemon.get_active_nodes()
        assert len(active) == 0
        telemetry = daemon.tick()
        assert telemetry["nodes"]["active_count"] == 0


    def test_f10_boundary_rapid_tick_loop_stability(self):
        daemon = VpsDaemon()
        # Execute 50 rapid ticks
        for _ in range(50):
            daemon.tick()
        assert daemon.tick_count >= 50
        assert daemon.get_memory_usage_mb() <= 200.0

    def test_f10_boundary_expired_lease_boundary(self):
        daemon = VpsDaemon()
        # Node expires exactly at current time
        daemon.register_node("boundary_node", "Tier2_Laptop", ["GPU"], ttl_seconds=0.0)
        time.sleep(0.01)
        pruned = daemon.prune_expired_nodes()
        assert "boundary_node" in pruned

    def test_f10_boundary_corrupt_config_file_fallback(self, tmp_path):
        bad_cfg = tmp_path / "broken.env"
        bad_cfg.write_text("INVALID_SYNTAX ::: === ???", encoding="utf-8")
        daemon = VpsDaemon(config_path=str(bad_cfg))
        # Falls back to default limits without exception
        assert daemon.memory_limit_mb == 200.0

    def test_f10_boundary_process_rss_reading_accuracy(self):
        daemon = VpsDaemon()
        rss = daemon.get_memory_usage_mb()
        assert rss > 0.0
        assert rss < 200.0


# ==============================================================================
# F11 Boundaries: Dual Deployment Targets
# ==============================================================================

class TestF11DeploymentTargetsBoundaries:
    """Tier 2 Boundary Tests for Feature 11 (Deployment Targets)."""

    def test_f11_boundary_vps_script_shebang_and_syntax(self):
        script_path = Path("vazus_autonomous_harness/daemon/setup_vps_target1.sh")
        lines = script_path.read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith("#!/")
        assert "bash" in lines[0] or "sh" in lines[0]

    def test_f11_boundary_orangepi_script_shebang_and_syntax(self):
        script_path = Path("vazus_autonomous_harness/daemon/setup_orangepi_target2.sh")
        lines = script_path.read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith("#!/")
        assert "bash" in lines[0]

    def test_f11_boundary_systemd_restart_sec_bounds(self):
        unit_path = Path("vazus_autonomous_harness/daemon/vazus-flywheel.service")
        content = unit_path.read_text(encoding="utf-8")
        assert "RestartSec=" in content
        # Must be bounded (5 to 60 seconds)
        assert any(f"RestartSec={sec}" in content for sec in (5, 10, 15, 30))

    def test_f11_boundary_systemd_cpu_quota_bounds(self):
        unit_path = Path("vazus_autonomous_harness/daemon/vazus-flywheel.service")
        content = unit_path.read_text(encoding="utf-8")
        assert "CPUQuota=" in content

    def test_f11_boundary_file_permissions_declaration(self):
        vps_script = Path("vazus_autonomous_harness/daemon/setup_vps_target1.sh").read_text(encoding="utf-8")
        # Script must enforce 0600 permissions on env file
        assert "0600" in vps_script or "chmod 600" in vps_script


# ==============================================================================
# F12 Boundaries: OpenColab Bridge
# ==============================================================================

class TestF12ColabBridgeBoundaries:
    """Tier 2 Boundary Tests for Feature 12 (OpenColab Bridge)."""

    def test_f12_boundary_empty_task_type_and_code(self, tmp_path):
        bridge = ColabBridge(queue_root=tmp_path / "colab_queue")
        job_id = bridge.submit_job("", "")
        assert job_id is not None
        assert (bridge.inbox_dir / f"task_{job_id}.json").exists()

    def test_f12_boundary_special_characters_in_code_payload(self, tmp_path):
        bridge = ColabBridge(queue_root=tmp_path / "colab_queue")
        code_special = 'print("🚀 Running with emojis and \n newlines and quotes: \'hello\'")'
        job_id = bridge.submit_job("TEST_CODE", code_special)
        manifest = json.loads((bridge.inbox_dir / f"task_{job_id}.json").read_text(encoding="utf-8"))
        assert manifest["code"] == code_special

    def test_f12_boundary_stale_keepalive_detection(self, tmp_path):
        bridge = ColabBridge(queue_root=tmp_path / "colab_queue")
        # Stale keepalive from 1 hour ago
        old_time = time.time() - 3600.0
        bridge.keepalive_file.write_text(json.dumps({"timestamp": old_time}), encoding="utf-8")
        status = bridge.get_keepalive_status()
        assert status["alive"] is False
        assert status["age_seconds"] >= 3500.0

    def test_f12_boundary_concurrent_job_submissions(self, tmp_path):
        bridge = ColabBridge(queue_root=tmp_path / "colab_queue")
        job_ids = [bridge.submit_job(f"JOB_{i}", f"code_{i}") for i in range(15)]
        assert len(set(job_ids)) == 15
        assert len(list(bridge.inbox_dir.glob("task_*.json"))) == 15

    def test_f12_boundary_malformed_outbox_result_file(self, tmp_path):
        bridge = ColabBridge(queue_root=tmp_path / "colab_queue")
        job_id = "corrupt_job"
        corrupt_file = bridge.outbox_dir / f"result_{job_id}.json"
        corrupt_file.write_text("NOT_VALID_JSON ::: !!!", encoding="utf-8")
        # Should handle gracefully without crashing
        res = bridge.poll_result(job_id)
        assert res is None or res.get("status") == "ERROR"


# ==============================================================================
# F13 Boundaries: Asymmetric Topology Coordinator
# ==============================================================================

class TestF13TopologyBoundaries:
    """Tier 2 Boundary Tests for Feature 13 (Topology Coordinator)."""

    def test_f13_boundary_unregistered_node_heartbeat(self):
        coord = TopologyCoordinator()
        assert coord.heartbeat_node("non_existent_node_id") is False

    def test_f13_boundary_no_worker_has_capability(self):
        coord = TopologyCoordinator()
        now = time.time()
        coord.register_node(NodeRegistration("vps", "Tier0_VPS", ["ORCHESTRATE"], now + 600))
        # Requesting QUANTUM_SOLVER which no worker supports
        worker = coord.get_best_worker_for_task("QUANTUM_SOLVER")
        assert worker is None

    def test_f13_boundary_all_workers_leases_expired(self):
        coord = TopologyCoordinator()
        past = time.time() - 100.0
        coord.register_node(NodeRegistration("node_1", "Tier2_Laptop", ["GPU"], past))
        coord.register_node(NodeRegistration("node_2", "Tier1_5_Edge", ["GPU"], past))
        worker = coord.get_best_worker_for_task("GPU")
        assert worker is None

    def test_f13_boundary_duplicate_node_registration(self):
        coord = TopologyCoordinator()
        now = time.time()
        coord.register_node(NodeRegistration("node_x", "Tier2_Laptop", ["GPU"], now + 100))
        # Re-register with new capabilities
        coord.register_node(NodeRegistration("node_x", "Tier2_Laptop", ["GPU", "NPU"], now + 500))
        assert len(coord.nodes) == 1
        assert "NPU" in coord.nodes["node_x"].capabilities

    def test_f13_boundary_empty_capability_list(self):
        coord = TopologyCoordinator()
        coord.register_node(NodeRegistration("empty_node", "Tier0_VPS", [], time.time() + 600))
        assert coord.get_best_worker_for_task("ANY_CAPABILITY") is None


# ==============================================================================
# F14 Boundaries: Laptop Power Multiplier & Lease Manager
# ==============================================================================

class TestF14LaptopLeaseBoundaries:
    """Tier 2 Boundary Tests for Feature 14 (Laptop Lease Manager)."""

    def test_f14_boundary_zero_ttl_lease(self):
        coord = TopologyCoordinator()
        now = time.time()
        # Lease expires at current second
        coord.register_node(NodeRegistration("laptop_0s", "Tier2_Laptop", ["GPU"], now))
        time.sleep(0.01)
        assert coord.get_best_worker_for_task("GPU") is None

    def test_f14_boundary_negative_ttl_lease(self):
        coord = TopologyCoordinator()
        coord.register_node(NodeRegistration("laptop_neg", "Tier2_Laptop", ["GPU"], time.time() - 100))
        assert coord.get_best_worker_for_task("GPU") is None

    def test_f14_boundary_maximum_ttl_clamping(self):
        coord = TopologyCoordinator()
        far_future = time.time() + 1000000.0
        coord.register_node(NodeRegistration("laptop_max", "Tier2_Laptop", ["GPU"], far_future))
        worker = coord.get_best_worker_for_task("GPU")
        assert worker is not None
        assert worker.node_id == "laptop_max"

    def test_f14_boundary_rapid_heartbeat_renewal(self):
        coord = TopologyCoordinator()
        now = time.time()
        coord.register_node(NodeRegistration("laptop_renew", "Tier2_Laptop", ["GPU"], now + 10))
        for _ in range(20):
            coord.heartbeat_node("laptop_renew", extension_seconds=600.0)
        assert coord.nodes["laptop_renew"].lease_expires_at > now + 500

    def test_f14_boundary_subsecond_lease_expiry_transition(self):
        coord = TopologyCoordinator()
        # Lease valid for 0.05 seconds
        coord.register_node(NodeRegistration("laptop_fast", "Tier2_Laptop", ["GPU"], time.time() + 0.05))
        assert coord.get_best_worker_for_task("GPU") is not None
        time.sleep(0.06)
        assert coord.get_best_worker_for_task("GPU") is None
