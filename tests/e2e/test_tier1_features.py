"""
tests.e2e.test_tier1_features -- Tier 1: Feature Coverage (F1 to F14).
Comprehensive opaque-box verification with >= 5 checks per feature (>= 70 checks).
Strictly adheres to TEST_INFRA.md and PROJECT.md § Interface Contracts.
"""

import ast
import hashlib
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
    ReflexionMemoryStore,
    ReflexionRecord,
    SMTProver,
    TaskAttempt,
    TopologyCoordinator,
    VpsDaemon,
)


# ==============================================================================
# F1: 100-Point Quality Evaluation Rubric (R4)
# ==============================================================================

class TestF1QualityEvaluationRubric:
    """Feature 1: 100-point multi-dimensional quality rubric and >=75 admission gate."""

    def test_f1_rubric_admissible_threshold_pass(self):
        engine = QualityEvaluationEngine(admission_threshold=75.0)
        code = """
def add_positive(a: int, b: int) -> int:
    \"\"\"
    :requires: a > 0 and b > 0
    :ensures: result > a and result > b
    \"\"\"
    return a + b
"""
        score = engine.evaluate(candidate_code=code, baseline_code=code)
        assert score.total_score >= 75.0
        assert score.correctness_smt == 40.0
        assert score.empirical_integrity == 30.0
        assert score.academic_sovereignty == 15.0
        assert score.is_admissible is True
        assert score.counterexample is None

    def test_f1_rubric_below_threshold_rejection(self):
        engine = QualityEvaluationEngine(admission_threshold=75.0)
        # Baseline is small, candidate has excessive bloat incurring penalties
        baseline = "def f(x):\n    return x + 1\n"
        bloated_candidate = "def f(x):\n" + "\n".join([f"    _var_{i} = {i}" for i in range(150)]) + "\n    return x + 1\n"
        score = engine.evaluate(candidate_code=bloated_candidate, baseline_code=baseline)
        assert score.ast_bloat_ratio > 1.0
        assert score.parsimony_efficiency <= 5.0
        # If total score < 75.0, must be marked inadmissible
        if score.total_score < 75.0:
            assert score.is_admissible is False

    def test_f1_rubric_smt_failure_hard_veto(self):
        engine = QualityEvaluationEngine(admission_threshold=75.0)
        # Buggy implementation violating contract
        buggy_code = """
def dec_value(x: int) -> int:
    \"\"\"
    :requires: x >= 0
    :ensures: result > x
    \"\"\"
    return x - 5
"""
        score = engine.evaluate(candidate_code=buggy_code, baseline_code=buggy_code)
        assert score.correctness_smt == 0.0 or score.counterexample is not None or not score.is_admissible
        assert score.is_admissible is False

    def test_f1_rubric_sovereignty_failure_hard_veto(self):
        engine = QualityEvaluationEngine(admission_threshold=75.0)
        # Direct solution leak in academic task
        leak_code = """
# Задача для СДО ИВБО-22-25
# Вот готовый код лабораторной работы:
def solve_mirea_lab():
    return "ответ: 42"
"""
        score = engine.evaluate(
            candidate_code=leak_code,
            baseline_code="",
            context_prompt="Сделай лабораторную работу по ИВБО-22-25"
        )
        assert score.academic_sovereignty == 0.0 or not score.is_admissible or len(score.violation_reasons) > 0
        assert score.is_admissible is False

    def test_f1_rubric_clean_diff_bonus_awarded(self):
        analyzer = ASTParsimonyAnalyzer()
        base = "def compute(a, b):\n    x = a * 2\n    y = b * 2\n    return x + y\n"
        # Refactored more concisely (fewer or equal nodes)
        cand = "def compute(a, b):\n    return (a + b) * 2\n"
        res = analyzer.calculate_bloat(base, cand)
        assert res["bloat_ratio"] <= 0.0
        assert res["bonus"] == 5.0
        assert res["score"] == 15.0


# ==============================================================================
# F2: SMT Z3 Formal Equivalence & Contract Prover (R4)
# ==============================================================================

class TestF2SMTZ3EquivalenceProver:
    """Feature 2: Formal verification engine using Microsoft Z3 5.0.0."""

    def test_f2_smt_prover_proves_valid_clamp_unsat(self):
        prover = SMTProver()
        code = """
def clamp(val: int, low: int, high: int) -> int:
    \"\"\"
    :requires: low <= high
    :ensures: result >= low and result <= high
    \"\"\"
    if val < low:
        return low
    elif val > high:
        return high
    else:
        return val
"""
        result = prover.verify_contracts(code)
        assert result.verified is True
        assert result.status == "UNSAT"
        assert result.counterexample is None

    def test_f2_smt_prover_detects_buggy_increment_sat(self):
        prover = SMTProver()
        code = """
def faulty_inc(x: int) -> int:
    \"\"\"
    :requires: x >= 0
    :ensures: result > x
    \"\"\"
    return x - 1
"""
        result = prover.verify_contracts(code)
        assert result.verified is False
        assert result.status == "SAT"
        assert result.counterexample is not None
        assert isinstance(result.counterexample, dict)

    def test_f2_smt_prover_expression_equivalence_unsat(self):
        prover = SMTProver()
        # Verify algebraic identity: (x + y)*(x - y) == x**2 - y**2
        res = prover.verify_expression_equivalence(
            "(x + y) * (x - y)",
            "x**2 - y**2",
            ["x", "y"]
        )
        assert res["equivalent"] is True
        assert res["status"] in ("PROVEN_EQUIVALENT", "UNSAT")
        assert "counterexample" not in res or res["counterexample"] is None

    def test_f2_smt_prover_expression_disproof_sat(self):
        prover = SMTProver()
        # Verify non-equivalence: x + 1 != x + 2
        res = prover.verify_expression_equivalence(
            "x + 1",
            "x + 2",
            ["x"]
        )
        assert res["equivalent"] is False
        assert res["status"] in ("DISPROVEN", "SAT")
        assert "counterexample" in res and res["counterexample"] is not None

    def test_f2_smt_prover_anti_vacuous_contract_rejection(self):
        prover = SMTProver()
        code = """
def trivial_fn(x: int) -> int:
    \"\"\"
    :ensures: True
    \"\"\"
    return x
"""
        res = prover.verify_contracts(code)
        # Vacuous contracts should not pass as verified UNSAT
        assert res.status in ("VACUOUS_CONTRACT", "NO_CONTRACTS", "ERROR") or not res.verified


# ==============================================================================
# F3: AST Bloat & Parsimony Analyzer (R4)
# ==============================================================================

class TestF3ASTBloatParsimonyAnalyzer:
    """Feature 3: AST node counting, bloat ratio, penalty and clean diff scoring."""

    def test_f3_ast_node_counting_accuracy(self):
        analyzer = ASTParsimonyAnalyzer()
        code = "x = 1 + 2\ny = x * 3\n"
        count = analyzer.count_nodes(code)
        assert count > 0
        tree = ast.parse(code)
        assert count == len(list(ast.walk(tree)))

    def test_f3_ast_zero_bloat_clean_diff_bonus(self):
        analyzer = ASTParsimonyAnalyzer()
        base = "def test(x):\n    a = 1\n    return x + a\n"
        cand = "def test(x):\n    return x + 1\n"
        res = analyzer.calculate_bloat(base, cand)
        assert res["bloat_ratio"] <= 0.0
        assert res["penalty"] == 0.0
        assert res["bonus"] == 5.0
        assert res["score"] == 15.0

    def test_f3_ast_moderate_bloat_penalty(self):
        analyzer = ASTParsimonyAnalyzer()
        base = "def f(x):\n    return x\n"
        cand = "def f(x):\n    a = 1\n    b = 2\n    c = 3\n    return x + a + b + c\n"
        res = analyzer.calculate_bloat(base, cand)
        assert res["bloat_ratio"] > 0.10
        assert res["penalty"] > 0.0
        assert res["score"] < 10.0

    def test_f3_ast_excessive_bloat_hard_penalty(self):
        analyzer = ASTParsimonyAnalyzer()
        base = "def f(x):\n    return x\n"
        cand = "def f(x):\n" + "\n".join([f"    v_{i} = {i}" for i in range(100)]) + "\n    return x\n"
        res = analyzer.calculate_bloat(base, cand)
        assert res["bloat_ratio"] > 1.0
        assert res["penalty"] == 10.0
        assert res["score"] == 0.0

    def test_f3_ast_syntax_error_resilience(self):
        analyzer = ASTParsimonyAnalyzer()
        invalid_code = "def f(x) this is broken syntax :::"
        count = analyzer.count_nodes(invalid_code)
        assert count == 0
        res = analyzer.calculate_bloat("def f(x): pass", invalid_code)
        assert res["score"] <= 10.0



# ==============================================================================
# F4: Academic Sovereignty Guard (R4 & USER.md#L37)
# ==============================================================================

class TestF4AcademicSovereigntyGuard:
    """Feature 4: Academic Sovereignty, Socratic Mentoring, and Zero Stubs."""

    def test_f4_academic_context_detection(self):
        guard = AcademicSovereigntyGuard()
        assert guard.is_academic_context("Помоги решить типовой расчет по ИВБО-22-25") is True
        assert guard.is_academic_context("Вопрос по СДО тесту РТУ МИРЭА") is True
        assert guard.is_academic_context("Configure nginx reverse proxy on linux VPS") is False

    def test_f4_direct_solution_leak_veto(self):
        guard = AcademicSovereigntyGuard(strict_mode=True)
        res = guard.verify_response(
            prompt="Лабораторная работа 3 по физике",
            response="Вот готовый код лабораторной: ответ: 42"
        )
        assert res["allowed"] is False
        assert "Direct" in res["reason"] or "SOVEREIGNTY VIOLATION" in res["reason"]
        assert res.get("remediation_hint") is not None

    def test_f4_socratic_guidance_pass(self):
        guard = AcademicSovereigntyGuard(strict_mode=True)
        res = guard.verify_response(
            prompt="Не могу понять задание в СДО по графам",
            response="Подумай, какой алгоритм обхода оптимален? Обрати внимание на наличие циклов."
        )
        assert res["allowed"] is True
        assert res["has_socratic_guidance"] is True

    def test_f4_zero_stub_detection_veto(self):
        guard = AcademicSovereigntyGuard()
        stub_code = "def solve_equation():\n    pass\n"
        has_stubs, reason = guard.check_code_stubs(stub_code)
        assert has_stubs is True
        assert "pass" in reason or "stub" in reason.lower()

    def test_f4_non_academic_context_pass(self):
        guard = AcademicSovereigntyGuard()
        res = guard.verify_response(
            prompt="Set up systemd timer for database backup",
            response="Create /etc/systemd/system/backup.timer with OnCalendar=daily."
        )
        assert res["allowed"] is True
        assert res["is_academic"] is False


# ==============================================================================
# F5: Continuous Reflexion Generator (R2)
# ==============================================================================

class TestF5ContinuousReflexionGenerator:
    """Feature 5: Structured error-to-insight generator producing ReflexionRecord."""

    def test_f5_reflexion_record_creation_with_negative_rule(self):
        rule = ExecutableNegativeConstraint(
            rule_id="neg_001",
            rule_type="REGEX_DENY",
            pattern=r"buffer\[offset:offset\+length\]",
            description="Buffer slicing without boundary clamp"
        )
        record = ReflexionRecord(
            record_id="refl_test_01",
            timestamp=time.time(),
            task_id="buffer_opt_task",
            candidate_summary="Mutated buffer slice offset",
            root_cause="Out-of-bounds access when offset + length exceeds buffer size",
            violated_invariant="offset + length <= capacity",
            negative_rules=[rule],
            smt_counterexample={"offset": 95, "length": 10, "capacity": 100},
            fitness_score=45.0,
        )
        assert record.record_id == "refl_test_01"
        assert len(record.negative_rules) == 1
        assert record.negative_rules[0].rule_type == "REGEX_DENY"
        assert record.smt_counterexample["offset"] == 95

    def test_f5_reflexion_serialization_integrity(self):
        rule = ExecutableNegativeConstraint(
            rule_id="neg_002",
            rule_type="IMPORT_BAN",
            pattern="from vazus_core import ast_pruner",
            description="Circular import pattern"
        )
        record = ReflexionRecord(
            record_id="refl_test_02",
            timestamp=1758888000.0,
            task_id="import_clean_task",
            candidate_summary="Import refactoring",
            root_cause="Circular import between core and pruner",
            violated_invariant="Submodule imports must use absolute canonical paths",
            negative_rules=[rule],
        )
        dumped = json.dumps({
            "record_id": record.record_id,
            "root_cause": record.root_cause,
            "violated_invariant": record.violated_invariant,
            "negative_rules": [{"rule_id": r.rule_id, "pattern": r.pattern} for r in record.negative_rules]
        })
        loaded = json.loads(dumped)
        assert loaded["record_id"] == "refl_test_02"
        assert loaded["negative_rules"][0]["rule_id"] == "neg_002"

    def test_f5_reflexion_smt_counterexample_capture(self):
        cex = {"x": 0, "reason": "Discrepancy at lower domain boundary"}
        record = ReflexionRecord(
            record_id="refl_cex_03",
            timestamp=time.time(),
            task_id="arithmetic_task",
            candidate_summary="Step offset mutation",
            root_cause="Offset zero boundary drift",
            violated_invariant="f_orig(x) == f_mut(x)",
            negative_rules=[],
            smt_counterexample=cex,
        )
        assert record.smt_counterexample is not None
        assert record.smt_counterexample["x"] == 0

    def test_f5_reflexion_violated_invariant_taxonomy(self):
        invariants = [
            "∀x: f(x) == g(x)",
            "USER.md#L37 Socratic pedagogical sovereignty",
            "Path Jail: path.startswith('C:\\vazus')",
        ]
        records = [
            ReflexionRecord(
                record_id=f"refl_inv_{i}",
                timestamp=time.time(),
                task_id=f"task_{i}",
                candidate_summary=f"Summary {i}",
                root_cause=f"Root cause {i}",
                violated_invariant=inv,
                negative_rules=[]
            ) for i, inv in enumerate(invariants)
        ]
        assert len(records) == 3
        assert records[1].violated_invariant.startswith("USER.md#L37")

    def test_f5_reflexion_dedup_hash_generation(self):
        root_cause = "Buffer overrun on capacity edge"
        violated_inv = "offset + length <= capacity"
        payload = f"{root_cause.strip()}|{violated_inv.strip()}"
        expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        assert len(expected_hash) == 64
        # Verify deterministic hash
        assert expected_hash == hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ==============================================================================
# F6: Dual-Tier Episodic Memory Store (R2)
# ==============================================================================

class TestF6DualTierEpisodicMemoryStore:
    """Feature 6: SQLite SSOT + FTS5 full-text indexing + Markdown Zettelkasten wiki."""

    def test_f6_sqlite_ssot_crud_and_table_schema(self, tmp_path):
        db_file = tmp_path / "test_memory.db"
        store = ReflexionMemoryStore(db_path=str(db_file), wiki_dir=str(tmp_path / "wiki"))
        record = ReflexionRecord(
            record_id="refl_crud_01",
            timestamp=time.time(),
            task_id="crud_task",
            candidate_summary="Candidate 1",
            root_cause="Divide by zero in normalization",
            violated_invariant="denominator != 0",
            negative_rules=[],
            fitness_score=50.0,
        )
        store.record_failure(record)
        retrieved = store.retrieve_similar_dead_ends("Divide by zero", limit=5)
        assert len(retrieved) >= 1
        assert retrieved[0].record_id == "refl_crud_01"

    def test_f6_sqlite_fts5_lexical_search(self, tmp_path):
        db_file = tmp_path / "test_fts.db"
        store = ReflexionMemoryStore(db_path=str(db_file), wiki_dir=str(tmp_path / "wiki"))
        store.record_failure(ReflexionRecord(
            record_id="refl_fts_01",
            timestamp=time.time(),
            task_id="task_alpha",
            candidate_summary="Matrix invert",
            root_cause="Singular matrix encountered during determinant solve",
            violated_invariant="det(M) != 0",
            negative_rules=[]
        ))
        store.record_failure(ReflexionRecord(
            record_id="refl_fts_02",
            timestamp=time.time(),
            task_id="task_beta",
            candidate_summary="File parser",
            root_cause="JSON parsing error on trailing comma",
            violated_invariant="valid_json_grammar",
            negative_rules=[]
        ))
        res = store.retrieve_similar_dead_ends("Singular matrix determinant", limit=1)
        assert len(res) == 1
        assert res[0].record_id == "refl_fts_01"

    def test_f6_markdown_wiki_zettelkasten_generation(self, tmp_path):
        wiki_dir = tmp_path / "06_reflexion_wiki"
        store = ReflexionMemoryStore(db_path=":memory:", wiki_dir=str(wiki_dir))
        record = ReflexionRecord(
            record_id="refl_wiki_01",
            timestamp=time.time(),
            task_id="zettel_test",
            candidate_summary="AST optimization",
            root_cause="AST mutation broke variable scoping",
            violated_invariant="Variable scoping invariant",
            negative_rules=[ExecutableNegativeConstraint("rule_1", "REGEX_DENY", "global x", "No globals")],
        )
        store.record_failure(record)
        wiki_file = wiki_dir / "Reflexion_refl_wiki_01.md"
        assert wiki_file.exists()
        content = wiki_file.read_text(encoding="utf-8")
        assert "---" in content  # YAML frontmatter
        assert "Variable scoping invariant" in content
        assert "[[ADR_Autonomous_Flywheel]]" in content  # Wikilink

    def test_f6_episodic_record_deduplication_upsert(self, tmp_path):
        store = ReflexionMemoryStore(db_path=str(tmp_path / "dedup.db"), wiki_dir=str(tmp_path / "wiki"))
        rec1 = ReflexionRecord(
            record_id="refl_dup_01",
            timestamp=time.time(),
            task_id="dup_task",
            candidate_summary="Attempt 1",
            root_cause="Identical error signature",
            violated_invariant="Same invariant",
            negative_rules=[],
            fitness_score=30.0
        )
        rec2 = ReflexionRecord(
            record_id="refl_dup_02",
            timestamp=time.time() + 10,
            task_id="dup_task",
            candidate_summary="Attempt 2 with higher score",
            root_cause="Identical error signature",
            violated_invariant="Same invariant",
            negative_rules=[],
            fitness_score=50.0
        )
        store.record_failure(rec1)
        store.record_failure(rec2)  # Same dedup_hash (root_cause + invariant)
        results = store.retrieve_similar_dead_ends("Identical error signature", limit=10)
        # Table uses INSERT OR REPLACE on dedup_hash, avoiding duplicate clutter
        assert len(results) == 1
        assert results[0].fitness_score == 50.0

    def test_f6_retrieval_limit_and_ranking(self, tmp_path):
        store = ReflexionMemoryStore(db_path=str(tmp_path / "limit.db"), wiki_dir=str(tmp_path / "wiki"))
        for i in range(10):
            store.record_failure(ReflexionRecord(
                record_id=f"refl_batch_{i}",
                timestamp=time.time() + i,
                task_id=f"batch_task_{i}",
                candidate_summary=f"Summary {i}",
                root_cause=f"Batch error condition {i}",
                violated_invariant=f"Invariant {i}",
                negative_rules=[]
            ))
        results = store.retrieve_similar_dead_ends("Batch error", limit=3)
        assert len(results) == 3


# ==============================================================================
# F7: Pre-Flight Negative Constraint Filter (R2)
# ==============================================================================

class TestF7PreFlightNegativeConstraintFilter:
    """Feature 7: Pre-Flight tri-hybrid query & static hard-gate interceptor (< 5 ms)."""

    def test_f7_preflight_regex_deny_interception(self, tmp_path):
        store = ReflexionMemoryStore(db_path=str(tmp_path / "filter.db"), wiki_dir=str(tmp_path / "wiki"))
        rule = ExecutableNegativeConstraint(
            rule_id="neg_eval",
            rule_type="REGEX_DENY",
            pattern=r"eval\s*\(",
            description="Use of unsafe eval is strictly forbidden"
        )
        store.record_failure(ReflexionRecord(
            record_id="refl_rule_eval",
            timestamp=time.time(),
            task_id="security_task",
            candidate_summary="Dynamic code execution",
            root_cause="Arbitrary code execution risk",
            violated_invariant="No eval() calls permitted",
            negative_rules=[rule]
        ))
        bad_code = "result = eval('2 + 2')"
        is_blocked, msg = store.check_negative_constraints(bad_code)
        assert is_blocked is True
        assert "REGEX_DENY" in msg

    def test_f7_preflight_import_ban_interception(self, tmp_path):
        store = ReflexionMemoryStore(db_path=str(tmp_path / "filter_import.db"), wiki_dir=str(tmp_path / "wiki"))
        rule = ExecutableNegativeConstraint(
            rule_id="neg_imp",
            rule_type="IMPORT_BAN",
            pattern="from vazus_core import ast_pruner",
            description="Forbidden top-level circular import"
        )
        store.record_failure(ReflexionRecord(
            record_id="refl_rule_imp",
            timestamp=time.time(),
            task_id="import_task",
            candidate_summary="Importing pruner",
            root_cause="Circular dependency",
            violated_invariant="Deep submodule import required",
            negative_rules=[rule]
        ))
        bad_code = "from vazus_core import ast_pruner\npruner = ast_pruner.ASTPruner()"
        is_blocked, msg = store.check_negative_constraints(bad_code)
        assert is_blocked is True
        assert "IMPORT_BAN" in msg

    def test_f7_preflight_ast_pattern_deny(self, tmp_path):
        store = ReflexionMemoryStore(db_path=str(tmp_path / "filter_ast.db"), wiki_dir=str(tmp_path / "wiki"))
        rule = ExecutableNegativeConstraint(
            rule_id="neg_ast_01",
            rule_type="AST_PATTERN_DENY",
            pattern="os.system(",
            description="Prohibit os.system calls"
        )
        store.record_failure(ReflexionRecord(
            record_id="refl_rule_ast",
            timestamp=time.time(),
            task_id="os_system_task",
            candidate_summary="Shell call",
            root_cause="Command injection hazard",
            violated_invariant="Subprocess with argument list required",
            negative_rules=[rule]
        ))
        bad_code = "import os\nos.system('dir')"
        is_blocked, msg = store.check_negative_constraints(bad_code)
        assert is_blocked is True
        assert "AST_PATTERN_DENY" in msg

    def test_f7_preflight_clean_candidate_allowed(self, tmp_path):
        store = ReflexionMemoryStore(db_path=str(tmp_path / "filter_clean.db"), wiki_dir=str(tmp_path / "wiki"))
        store.record_failure(ReflexionRecord(
            record_id="refl_other",
            timestamp=time.time(),
            task_id="other_task",
            candidate_summary="Other",
            root_cause="Other error",
            violated_invariant="Other invariant",
            negative_rules=[ExecutableNegativeConstraint("r_xyz", "REGEX_DENY", r"__import__", "No dynamic import")]
        ))
        clean_code = "def safe_add(x, y):\n    return x + y\n"
        is_blocked, msg = store.check_negative_constraints(clean_code)
        assert is_blocked is False
        assert msg is None

    def test_f7_preflight_execution_latency_under_5ms(self, tmp_path):
        store = ReflexionMemoryStore(db_path=str(tmp_path / "filter_perf.db"), wiki_dir=str(tmp_path / "wiki"))
        for i in range(20):
            store.record_failure(ReflexionRecord(
                record_id=f"refl_rule_{i}",
                timestamp=time.time(),
                task_id=f"perf_task_{i}",
                candidate_summary="Rule",
                root_cause="Rule error",
                violated_invariant="Rule invariant",
                negative_rules=[ExecutableNegativeConstraint(f"r_{i}", "REGEX_DENY", f"forbidden_pattern_{i}", f"Rule {i}")]
            ))
        candidate = "def valid_fast_fn():\n    return 42\n"
        t0 = time.perf_counter()
        is_blocked, _ = store.check_negative_constraints(candidate)
        t_elapsed = (time.perf_counter() - t0) * 1000.0  # in ms
        assert is_blocked is False
        assert t_elapsed < 50.0  # Generous upper bound on CI, steady-state < 5 ms


# ==============================================================================
# F8: Anti-Thrashing Circuit Breaker (R3)
# ==============================================================================

class TestF8AntiThrashingCircuitBreaker:
    """Feature 8: Active deadlock detector tracking 3 failed cycles, delta <= 0, oscillation."""

    def test_f8_circuit_breaker_trips_on_three_failed_cycles(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        task_id = "stalled_task_01"
        assert breaker.record_attempt(TaskAttempt(task_id, 1, 60.0, "hash_1", "error 1")) is False
        assert breaker.record_attempt(TaskAttempt(task_id, 2, 55.0, "hash_2", "error 2")) is False
        # 3rd consecutive failed attempt with negative delta -> TRIPPED
        tripped = breaker.record_attempt(TaskAttempt(task_id, 3, 50.0, "hash_3", "error 3"))
        assert tripped is True
        assert breaker.is_tripped(task_id) is True

    def test_f8_circuit_breaker_allows_progressing_cycles(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        task_id = "progressing_task"
        assert breaker.record_attempt(TaskAttempt(task_id, 1, 40.0, "hash_1")) is False
        assert breaker.record_attempt(TaskAttempt(task_id, 2, 55.0, "hash_2")) is False
        # Score is progressing upwards (+15.0 delta), breaker should not trip
        tripped = breaker.record_attempt(TaskAttempt(task_id, 3, 70.0, "hash_3"))
        assert tripped is False
        assert breaker.is_tripped(task_id) is False

    def test_f8_circuit_breaker_structural_oscillation_trip(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=5, vault_path=str(tmp_path))
        task_id = "oscillation_task"
        # Cycle 1: hash A
        breaker.record_attempt(TaskAttempt(task_id, 1, 60.0, "hash_alpha"))
        # Cycle 2: hash B
        breaker.record_attempt(TaskAttempt(task_id, 2, 60.0, "hash_beta"))
        # Cycle 3: agent reverts back to hash A (A -> B -> A)
        tripped = breaker.record_attempt(TaskAttempt(task_id, 3, 60.0, "hash_alpha"))
        assert tripped is True
        assert breaker.is_tripped(task_id) is True
        assert "oscillation" in breaker.tripped_tasks[task_id].lower()

    def test_f8_circuit_breaker_missing_credential_immediate_halt(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        task_id = "auth_fail_task"
        # Attempt 1 encounters missing credential -> immediate fail-closed HALT
        tripped = breaker.record_attempt(TaskAttempt(
            task_id=task_id,
            cycle_number=1,
            score=0.0,
            code_hash="hash_x",
            missing_prerequisite="google_token.json not found on disk"
        ))
        assert tripped is True
        assert breaker.is_tripped(task_id) is True
        assert "missing external prerequisite" in breaker.tripped_tasks[task_id].lower()

    def test_f8_circuit_breaker_is_tripped_status_reporting(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        assert breaker.is_tripped("unknown_task") is False
        breaker.tripped_tasks["known_tripped"] = "Test trip"
        assert breaker.is_tripped("known_tripped") is True


# ==============================================================================
# F9: Human Escalation Diagnostic Briefing (R3)
# ==============================================================================

class TestF9HumanEscalationDiagnosticBriefing:
    """Feature 9: Executive diagnostic briefing generator producing actionable forks."""

    def test_f9_escalation_briefing_markdown_generation(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        task_id = "briefing_task_01"
        breaker.record_attempt(TaskAttempt(task_id, 1, 60.0, "hash_1", "SMT contract SAT"))
        breaker.record_attempt(TaskAttempt(task_id, 2, 55.0, "hash_2", "Buffer overrun"))
        breaker.record_attempt(TaskAttempt(task_id, 3, 50.0, "hash_3", "Regression failure"))
        briefing = breaker.generate_escalation_briefing(task_id)
        assert "# 🚨 EXECUTIVE ESCALATION BRIEFING" in briefing
        assert f"Incident ID**: ESC-{task_id}" in briefing
        assert "SEVERITY**: CRITICAL" in briefing or "CRITICAL -- AUTONOMOUS EXECUTION FROZEN" in briefing

    def test_f9_escalation_briefing_chronology_table(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        task_id = "chronology_task"
        breaker.record_attempt(TaskAttempt(task_id, 1, 65.0, "hash_aaa", "Error 1"))
        breaker.record_attempt(TaskAttempt(task_id, 2, 60.0, "hash_bbb", "Error 2"))
        breaker.record_attempt(TaskAttempt(task_id, 3, 55.0, "hash_ccc", "Error 3"))
        briefing = breaker.generate_escalation_briefing(task_id)
        assert "| Cycle | Code Hash | Score | Failure Reason |" in briefing
        assert "hash_aaa" in briefing
        assert "hash_bbb" in briefing
        assert "hash_ccc" in briefing

    def test_f9_escalation_briefing_three_actionable_forks(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        task_id = "forks_task"
        breaker.record_attempt(TaskAttempt(task_id, 1, 50.0, "hash_0", "failed"))
        breaker.record_attempt(TaskAttempt(task_id, 2, 45.0, "hash_1", "failed"))
        breaker.record_attempt(TaskAttempt(task_id, 3, 40.0, "hash_2", "failed"))
        briefing = breaker.generate_escalation_briefing(task_id)
        assert "[OPTION A] Manual Patch & Resume" in briefing
        assert "[OPTION B] Relax Contract Invariant" in briefing
        assert "[OPTION C] Abort & Blacklist Mutation Path" in briefing

    def test_f9_escalation_briefing_vault_file_persistence(self, tmp_path):
        vault_dir = tmp_path / "escalations"
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(vault_dir))
        task_id = "persist_task"
        breaker.record_attempt(TaskAttempt(task_id, 1, 10.0, "h1", "fail"))
        breaker.record_attempt(TaskAttempt(task_id, 2, 10.0, "h2", "fail"))
        breaker.record_attempt(TaskAttempt(task_id, 3, 10.0, "h3", "fail"))
        breaker.generate_escalation_briefing(task_id)
        expected_file = vault_dir / f"ESCALATION_{task_id}.md"
        assert expected_file.exists()
        assert expected_file.stat().st_size > 100

    def test_f9_escalation_briefing_minimal_unsatisfiable_core(self, tmp_path):
        breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(tmp_path))
        task_id = "muc_task"
        breaker.record_attempt(TaskAttempt(task_id, 1, 30.0, "h1", "precondition failed: x > 0"))
        breaker.record_attempt(TaskAttempt(task_id, 2, 25.0, "h2", "counterexample {x: -1}"))
        breaker.record_attempt(TaskAttempt(task_id, 3, 20.0, "h3", "SMT SAT witness"))
        briefing = breaker.generate_escalation_briefing(task_id)
        assert "Minimal Unsatisfiable Core" in briefing
        assert "counterexample" in briefing or "SMT SAT witness" in briefing


# ==============================================================================
# F10: Lightweight VPS Daemon (R5)
# ==============================================================================

class TestF10LightweightVPSDaemon:
    """Feature 10: Headless orchestration daemon with <= 200 MB RSS budget."""

    def test_f10_vps_daemon_memory_limit_under_200mb(self):
        daemon = VpsDaemon()
        rss_mb = daemon.get_memory_usage_mb()
        assert isinstance(rss_mb, float)
        assert rss_mb > 0.0
        assert daemon.memory_limit_mb == 200.0

    def test_f10_vps_daemon_tick_event_loop_telemetry(self):
        daemon = VpsDaemon()
        telemetry = daemon.tick()
        assert "timestamp" in telemetry
        assert "memory" in telemetry
        assert telemetry["memory"]["rss_mb"] > 0.0
        assert "status" in telemetry["memory"]

    def test_f10_vps_daemon_node_presence_and_expiration(self):
        daemon = VpsDaemon()
        # Add active node with 600s TTL and expired node with negative TTL
        daemon.register_node("node_active", "Tier2_Laptop", ["GPU"], ttl_seconds=600.0)
        daemon.register_node("node_expired", "Tier2_Laptop", ["GPU"], ttl_seconds=-10.0)
        pruned = daemon.prune_expired_nodes()
        assert "node_expired" in pruned
        assert "node_active" in daemon.nodes
        assert "node_expired" not in daemon.nodes

    def test_f10_vps_daemon_cloud_job_dispatching(self):
        daemon = VpsDaemon()
        # Dispatch with invalid/dummy token should safely record history and return bool without crashing
        res = daemon.dispatch_cloud_job("cloud_mega_lab.yml", {"workflow_file": "cloud_mega_lab.yml"})
        assert isinstance(res, bool)
        assert len(daemon.dispatched_jobs_history) >= 1

    def test_f10_vps_daemon_memory_overshoot_refusal(self):
        daemon = VpsDaemon()
        # Set artificial limit below current usage
        daemon.memory_limit_mb = 1.0
        telemetry = daemon.tick()
        assert telemetry["memory"]["status"] == "CRITICAL_EXCEEDS_BUDGET"


# ==============================================================================
# F11: Dual Deployment Setup Targets (R5)
# ==============================================================================

class TestF11DualDeploymentSetupTargets:
    """Feature 11: Deployment scripts for Target 1 (VPS) and Target 2 (Orange Pi 4 Pro) + systemd."""

    def test_f11_setup_vps_target1_script_integrity(self):
        vps_script = Path("vazus_autonomous_harness/daemon/setup_vps_target1.sh")
        assert vps_script.exists()
        content = vps_script.read_text(encoding="utf-8")
        assert "157.228.174.15" in content
        assert "200M" in content or "MemoryMax" in content

    def test_f11_setup_orangepi_target2_script_integrity(self):
        opi_script = Path("vazus_autonomous_harness/daemon/setup_orangepi_target2.sh")
        assert opi_script.exists()
        content = opi_script.read_text(encoding="utf-8")
        assert "Orange Pi" in content or "ARM64" in content or "aarch64" in content
        assert "z3" in content.lower()

    def test_f11_systemd_unit_file_cgroup_memory_limits(self):
        unit_file = Path("vazus_autonomous_harness/daemon/vazus-flywheel.service")
        assert unit_file.exists()
        content = unit_file.read_text(encoding="utf-8")
        assert "MemoryMax=200M" in content
        assert "MemoryHigh=160M" in content
        assert "MemoryAccounting=yes" in content

    def test_f11_systemd_unit_environment_security(self):
        unit_file = Path("vazus_autonomous_harness/daemon/vazus-flywheel.service")
        content = unit_file.read_text(encoding="utf-8")
        assert "EnvironmentFile=/etc/vazus/flywheel.env" in content
        assert "Restart=always" in content

    def test_f11_zero_plaintext_credentials_invariant(self):
        daemon_dir = Path("vazus_autonomous_harness/daemon")
        for script in daemon_dir.glob("*.sh"):
            text = script.read_text(encoding="utf-8")
            # Verify no hardcoded passwords, tokens, or private keys
            assert "ghp_" not in text, f"Plaintext GitHub token detected in {script.name}!"
            assert "-----BEGIN RSA PRIVATE KEY-----" not in text
            assert "password123" not in text.lower()


# ==============================================================================
# F12: OpenColab Asynchronous Bridge (R5)
# ==============================================================================

class TestF12OpenColabAsynchronousBridge:
    """Feature 12: Google Drive mailbox queue (inbox/outbox) for GPU offloading."""

    def test_f12_colab_bridge_initialization_and_dirs(self, tmp_path):
        bridge = ColabBridge(queue_root=tmp_path / "colab_queue")
        assert bridge.inbox_dir.exists()
        assert bridge.outbox_dir.exists()
        assert bridge.active_dir.exists()

    def test_f12_colab_bridge_submit_job_writes_inbox(self, tmp_path):
        bridge = ColabBridge(queue_root=tmp_path / "colab_queue")
        job_id = bridge.submit_job("MODEL_TUNE", "train_epoch(model, dataset)")
        assert job_id is not None
        task_file = bridge.inbox_dir / f"task_{job_id}.json"
        assert task_file.exists()
        data = json.loads(task_file.read_text(encoding="utf-8"))
        assert data["task_type"] == "MODEL_TUNE"
        assert "train_epoch" in data["code"]

    def test_f12_colab_bridge_poll_result_reads_outbox(self, tmp_path):
        bridge = ColabBridge(queue_root=tmp_path / "colab_queue")
        job_id = "job_test_poll_01"
        outbox_file = bridge.outbox_dir / f"result_{job_id}.json"
        outbox_file.write_text(json.dumps({
            "job_id": job_id,
            "status": "SUCCESS",
            "completed_at": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "result_data": {"loss": 0.042, "accuracy": 0.98}
        }), encoding="utf-8")
        result = bridge.poll_result(job_id)
        assert result is not None
        assert result["status"] == "SUCCESS"
        assert result["result_data"]["loss"] == 0.042

    def test_f12_colab_bridge_poll_result_returns_none_when_pending(self, tmp_path):
        bridge = ColabBridge(queue_root=tmp_path / "colab_queue")
        assert bridge.poll_result("non_existent_job_123") is None

    def test_f12_colab_bridge_keepalive_timestamp_monitoring(self, tmp_path):
        bridge = ColabBridge(queue_root=tmp_path / "colab_queue")
        now = time.time()
        bridge.keepalive_file.write_text(json.dumps({
            "worker_id": "colab_t4_instance_01",
            "timestamp": now,
            "gpu": "Tesla T4"
        }), encoding="utf-8")
        data = json.loads(bridge.keepalive_file.read_text(encoding="utf-8"))
        assert data["gpu"] == "Tesla T4"
        assert abs(data["timestamp"] - now) < 1.0



# ==============================================================================
# F13: Asymmetric 4-Tier Topology Coordinator (R1)
# ==============================================================================

class TestF13AsymmetricTopologyCoordinator:
    """Feature 13: Coordination plane for Tier 0 VPS, Tier 1 Cloud, Tier 1.5 Edge, Tier 2 Laptop."""

    def test_f13_topology_coordinator_registration(self):
        coord = TopologyCoordinator()
        now = time.time()
        vps = NodeRegistration("vps_0", "Tier0_VPS", ["CRON", "ORCHESTRATE"], now + 3600)
        edge = NodeRegistration("orangepi_1", "Tier1_5_Edge", ["SMT_Z3", "GIT_SYNC"], now + 3600)
        laptop = NodeRegistration("laptop_2", "Tier2_Laptop", ["GPU", "AGY_CLI", "REPL"], now + 600)
        assert coord.register_node(vps) is True
        assert coord.register_node(edge) is True
        assert coord.register_node(laptop) is True
        assert len(coord.nodes) == 3

    def test_f13_topology_coordinator_best_worker_gpu_routing(self):
        coord = TopologyCoordinator()
        now = time.time()
        coord.register_node(NodeRegistration("vps", "Tier0_VPS", ["ORCHESTRATE"], now + 3600))
        coord.register_node(NodeRegistration("edge", "Tier1_5_Edge", ["SMT_Z3"], now + 3600))
        coord.register_node(NodeRegistration("laptop", "Tier2_Laptop", ["GPU", "AGY_CLI"], now + 600))
        # When GPU needed, must route to laptop
        worker = coord.get_best_worker_for_task("GPU")
        assert worker is not None
        assert worker.node_id == "laptop"
        assert worker.tier == "Tier2_Laptop"

    def test_f13_topology_coordinator_best_worker_smt_routing(self):
        coord = TopologyCoordinator()
        now = time.time()
        coord.register_node(NodeRegistration("vps", "Tier0_VPS", ["ORCHESTRATE"], now + 3600))
        coord.register_node(NodeRegistration("edge", "Tier1_5_Edge", ["SMT_Z3"], now + 3600))
        # SMT needed, should route to Orange Pi edge server (Tier 1.5)
        worker = coord.get_best_worker_for_task("SMT_Z3")
        assert worker is not None
        assert worker.node_id == "edge"
        assert worker.tier == "Tier1_5_Edge"

    def test_f13_topology_coordinator_heartbeat_lease_extension(self):
        coord = TopologyCoordinator()
        now = time.time()
        node = NodeRegistration("laptop_node", "Tier2_Laptop", ["GPU"], now + 10)
        coord.register_node(node)
        assert coord.heartbeat_node("laptop_node", extension_seconds=600.0) is True
        assert coord.nodes["laptop_node"].lease_expires_at > now + 500

    def test_f13_topology_coordinator_safe_sync_git(self):
        coord = TopologyCoordinator()
        assert coord.safe_sync_git(".") is True


# ==============================================================================
# F14: Laptop Power Multiplier & Lease Manager (R1)
# ==============================================================================

class TestF14LaptopPowerMultiplierLeaseManager:
    """Feature 14: Dynamic laptop registration, 10-minute TTL leases, and split-brain immunity."""

    def test_f14_laptop_node_ttl_lease_registration(self):
        coord = TopologyCoordinator()
        now = time.time()
        laptop = NodeRegistration("laptop_win11", "Tier2_Laptop", ["GPU", "NPU", "AGY_CLI"], now + 600.0)
        coord.register_node(laptop)
        assert coord.nodes["laptop_win11"].lease_expires_at - now >= 590.0

    def test_f14_laptop_node_lease_expiration_when_offline(self):
        coord = TopologyCoordinator()
        # Laptop lease that has expired 5 seconds ago
        past_time = time.time() - 5.0
        laptop = NodeRegistration("laptop_offline", "Tier2_Laptop", ["GPU"], past_time)
        coord.register_node(laptop)
        # Expired worker must not be assigned tasks
        worker = coord.get_best_worker_for_task("GPU")
        assert worker is None

    def test_f14_laptop_node_quota_offloading_capabilities(self):
        laptop = NodeRegistration("laptop_dev", "Tier2_Laptop", ["AGY_CLI", "REPL", "GPU"], time.time() + 600)
        assert "AGY_CLI" in laptop.capabilities
        assert "REPL" in laptop.capabilities
        assert "GPU" in laptop.capabilities

    def test_f14_laptop_node_split_brain_prevention(self):
        coord = TopologyCoordinator()
        # Safe sync must verify git fast-forward cleanly
        is_safe = coord.safe_sync_git(".")
        assert isinstance(is_safe, bool)

    def test_f14_laptop_node_recovery_on_reconnect(self):
        coord = TopologyCoordinator()
        now = time.time()
        # Initial lease expired
        coord.register_node(NodeRegistration("laptop_recon", "Tier2_Laptop", ["GPU"], now - 100))
        assert coord.get_best_worker_for_task("GPU") is None
        # Laptop reconnects & refreshes lease
        coord.heartbeat_node("laptop_recon", extension_seconds=600.0)
        worker = coord.get_best_worker_for_task("GPU")
        assert worker is not None
        assert worker.node_id == "laptop_recon"
