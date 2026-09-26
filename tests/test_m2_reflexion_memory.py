"""
Unit Test Suite for Milestone 2 (F5, F6, F7) of Autonomous Absolute AI Flywheel.

Components Tested:
- F5: Continuous Reflexion Generator (reflexion_engine.py)
  * Structured ReflexionRecord generation (root cause, violated invariant, negative rules, SMT counterexample)
  * Factory methods: from_quality_score, from_smt_disproof, from_test_failure, from_exception
- F6: Dual-Tier Episodic Memory Store (episodic_store.py)
  * SQLite SSOT (episodic_reflexion_records + episodic_reflexion_fts FTS5 table + triggers)
  * Automated deduplication and recurrence boost tracking
  * Markdown Zettelkasten Wiki generation in Tars 30TB Vault (YAML frontmatter + wikilinks)
  * 768D vector embedding persistence & retrieval
- F7: Pre-Flight Retrieval & Executable Negative Constraint Filter (preflight_filter.py)
  * Tri-hybrid semantic search (FTS5 BM25 + vector cosine similarity + recurrence boost)
  * Sub-5ms pre-execution hard-gate intercepting AST/regex/SMT negative rules
  * ReflexionMemoryStore façade adhering to PROJECT.md § M2 interface contracts
"""

import time
import pytest

from vazus_autonomous_harness.memory.reflexion_engine import (
    ExecutableNegativeConstraint,
    ReflexionRecord,
    ContinuousReflexionGenerator,
    ReflexionMemoryStore,
)
from vazus_autonomous_harness.memory.episodic_store import (
    EpisodicMemoryStore,
)
from vazus_autonomous_harness.memory.preflight_filter import (
    PreFlightFilter,
)
from vazus_autonomous_harness.verification.quality_engine import QualityScore


@pytest.fixture
def temp_store(tmp_path):
    """Provides isolated SQLite DB and Wiki directory for clean test execution."""
    db_file = str(tmp_path / "test_reflexion.db")
    wiki_dir = tmp_path / "test_wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    store = EpisodicMemoryStore(db_path=db_file, wiki_root=wiki_dir)
    yield store
    store.close()


# =====================================================================
# F5: Continuous Reflexion Generator Tests
# =====================================================================

def test_reflexion_record_fields_and_roundtrip():
    """Verifies ReflexionRecord schema adheres to PROJECT.md § M2 contract."""
    rule = ExecutableNegativeConstraint(
        rule_id="neg_001",
        rule_type="REGEX_DENY",
        pattern=r"\bassert\s+False\b",
        description="Deny explicit assert False",
        target_scope="code",
        is_hard_block=True,
    )
    rec = ReflexionRecord(
        record_id="refl_1001",
        timestamp=1727350000.0,
        task_id="task_calc_sum",
        candidate_summary="def sum(a, b): return a - b",
        root_cause="Operator inversion: subtraction used instead of addition",
        violated_invariant="sum(a, b) == a + b ∀ a, b ∈ ℤ",
        negative_rules=[rule],
        smt_counterexample={"a": 1, "b": 2, "result": -1, "expected": 3},
        fitness_score=45.0,
        category="arithmetic_inversion",
        remediation_hint="Use + operator instead of -",
    )

    # Verify attributes
    assert rec.record_id == "refl_1001"
    assert rec.task_id == "task_calc_sum"
    assert rec.root_cause.startswith("Operator inversion")
    assert rec.violated_invariant.startswith("sum(a, b)")
    assert len(rec.negative_rules) == 1
    assert rec.negative_rules[0].rule_type == "REGEX_DENY"
    assert rec.smt_counterexample["result"] == -1
    assert rec.fitness_score == 45.0
    assert rec.recurrence_count == 1
    assert rec.intercept_count == 0
    assert rec.dedup_hash is not None

    # Serialization roundtrip
    data = rec.to_dict()
    assert data["record_id"] == "refl_1001"
    assert len(data["negative_rules"]) == 1

    restored = ReflexionRecord.from_dict(data)
    assert restored.record_id == rec.record_id
    assert restored.negative_rules[0].pattern == rule.pattern
    assert restored.smt_counterexample == rec.smt_counterexample
    assert restored.dedup_hash == rec.dedup_hash


def test_generator_from_smt_disproof():
    """Verifies generator synthesizes SMT_PREDICATE_BLOCK negative constraints from Z3 models."""
    generator = ContinuousReflexionGenerator()
    code = "def divide(a, b): return a // b"
    counterexample = {"a": 10, "b": 0}

    rec = generator.from_smt_disproof(
        task_id="task_safe_div",
        candidate_code=code,
        contract_name="safe_div_contract",
        counterexample=counterexample,
        details="Division by zero exception state",
    )

    assert rec.category == "smt_contract_violation"
    assert rec.smt_counterexample == {"a": 10, "b": 0}
    assert "divide" in rec.candidate_summary
    assert len(rec.negative_rules) == 1

    rule = rec.negative_rules[0]
    assert rule.rule_type == "SMT_PREDICATE_BLOCK"
    assert "b == 0" in rule.pattern
    assert "Counterexample" in rule.description


def test_generator_from_quality_score_sovereignty_violation():
    """Verifies generator extracts Academic Sovereignty leaks into REGEX_DENY rules."""
    generator = ContinuousReflexionGenerator()
    bad_code = "print('Вот готовое решение лабораторной работы №2')"

    score = QualityScore(
        total_score=25.0,
        correctness_smt=40.0,
        empirical_integrity=30.0,
        parsimony_efficiency=10.0,
        academic_sovereignty=0.0,
        is_admissible=False,
        violation_reasons=["[SOVEREIGNTY VIOLATION] Direct solution dump detected in academic task"],
    )

    rec = generator.from_quality_score(
        task_id="mirea_ivbo_lab2",
        candidate_code=bad_code,
        score=score,
    )

    assert rec.category == "academic_sovereignty_leak"
    assert "USER.md#L37" in rec.violated_invariant
    assert len(rec.negative_rules) >= 1
    assert any(r.rule_type == "REGEX_DENY" for r in rec.negative_rules)


def test_generator_from_quality_score_empty_stubs():
    """Verifies generator extracts empty stubs (USER.md#L33) into AST_PATTERN_DENY rules."""
    generator = ContinuousReflexionGenerator()
    stub_code = "def solve_equation():\n    pass\n"

    score = QualityScore(
        total_score=50.0,
        correctness_smt=40.0,
        empirical_integrity=0.0,
        parsimony_efficiency=10.0,
        academic_sovereignty=0.0,
        is_admissible=False,
        violation_reasons=["Function 'solve_equation' is an empty 'pass' stub (USER.md#L33 violation)."],
    )

    rec = generator.from_quality_score(
        task_id="task_solver",
        candidate_code=stub_code,
        score=score,
    )

    assert "USER.md#L33" in rec.violated_invariant
    assert any(r.rule_type == "AST_PATTERN_DENY" for r in rec.negative_rules)


def test_generator_from_quality_score_illicit_mock():
    """Verifies generator creates negative rules against illicit mocks."""
    generator = ContinuousReflexionGenerator()
    mock_code = "from unittest.mock import MagicMock\nm = MagicMock()"

    score = QualityScore(
        total_score=40.0,
        correctness_smt=40.0,
        empirical_integrity=0.0,
        parsimony_efficiency=10.0,
        academic_sovereignty=15.0,
        is_admissible=False,
        violation_reasons=["Illicit mock detected: mocking core components violates empirical integrity"],
    )

    rec = generator.from_quality_score(
        task_id="task_mock_check",
        candidate_code=mock_code,
        score=score,
    )

    assert any("mock" in r.pattern.lower() for r in rec.negative_rules)


def test_generator_from_test_failure_and_exception():
    """Verifies generator handles test failures and uncaught exceptions."""
    generator = ContinuousReflexionGenerator()

    # Test failure
    rec_test = generator.from_test_failure(
        task_id="task_sort",
        candidate_code="def sort_arr(a): return a",
        error_message="AssertionError: [3, 1, 2] != [1, 2, 3]",
        test_name="test_sort_arr",
    )
    assert rec_test.category == "test_assertion_failure"
    assert "AssertionError" in rec_test.root_cause

    # Exception
    rec_exc = generator.from_exception(
        task_id="task_zero",
        candidate_code="x = 1 / 0",
        exc=ZeroDivisionError("division by zero"),
    )
    assert rec_exc.category == "runtime_exception"
    assert "ZeroDivisionError" in rec_exc.root_cause


# =====================================================================
# F6: Dual-Tier Episodic Memory Store Tests
# =====================================================================

def test_sqlite_ssot_crud_operations(temp_store):
    """Verifies SQLite SSOT creation, insertion, retrieval, and querying."""
    rule = ExecutableNegativeConstraint(
        rule_id="neg_sql_01",
        rule_type="REGEX_DENY",
        pattern=r"\bos\.system\(",
        description="Deny raw os.system execution",
    )
    rec = ReflexionRecord(
        record_id="refl_sql_01",
        timestamp=time.time(),
        task_id="task_secure_exec",
        candidate_summary="import os; os.system('ls')",
        root_cause="Insecure shell execution via os.system",
        violated_invariant="Shell execution must use sandboxed subprocess",
        negative_rules=[rule],
        fitness_score=10.0,
        category="security_vulnerability",
    )

    # Insert
    inserted_id = temp_store.insert_record(rec)
    assert inserted_id == "refl_sql_01"

    # Retrieve by ID
    fetched = temp_store.get_record("refl_sql_01")
    assert fetched is not None
    assert fetched.record_id == "refl_sql_01"
    assert fetched.category == "security_vulnerability"
    assert len(fetched.negative_rules) == 1
    assert fetched.negative_rules[0].pattern == r"\bos\.system\("

    # List records
    all_recs = temp_store.list_records(limit=10)
    assert len(all_recs) == 1
    assert all_recs[0].record_id == "refl_sql_01"


def test_deduplication_and_recurrence_boost(temp_store):
    """Verifies inserting identical failures increments recurrence_count rather than duplicating rows."""
    rule = ExecutableNegativeConstraint(
        rule_id="neg_dup_01",
        rule_type="REGEX_DENY",
        pattern="test_recurrence_pattern",
        description="Deduplication test pattern",
    )
    rec1 = ReflexionRecord(
        record_id="refl_dup_01",
        timestamp=time.time(),
        task_id="task_dedup",
        candidate_summary="def foo(): return 1",
        root_cause="Repeated mistake in logic flow",
        violated_invariant="Logic flow invariant must hold",
        negative_rules=[rule],
        fitness_score=20.0,
    )

    temp_store.insert_record(rec1)
    stored1 = temp_store.get_record("refl_dup_01")
    assert stored1.recurrence_count == 1

    # Second insertion with same dedup hash
    rec2 = ReflexionRecord(
        record_id="refl_dup_02",  # different ID, but same semantic contents
        timestamp=time.time(),
        task_id="task_dedup",
        candidate_summary="def foo(): return 1",
        root_cause="Repeated mistake in logic flow",
        violated_invariant="Logic flow invariant must hold",
        negative_rules=[rule],
        fitness_score=25.0,  # higher score
    )
    temp_store.insert_record(rec2)

    # Should update existing record without row proliferation
    records = temp_store.list_records(limit=10)
    assert len(records) == 1
    assert records[0].recurrence_count == 2
    assert records[0].fitness_score == 25.0


def test_markdown_wiki_zettel_export(temp_store):
    """Verifies Obsidian-compliant Zettelkasten note generation with YAML frontmatter."""
    rule = ExecutableNegativeConstraint(
        rule_id="neg_wiki_01",
        rule_type="AST_PATTERN_DENY",
        pattern="ast.Pass",
        description="Empty pass prohibited",
    )
    rec = ReflexionRecord(
        record_id="refl_wiki_01",
        timestamp=time.time(),
        task_id="task_zettelkasten",
        candidate_summary="def solve(): pass",
        root_cause="Empty stub implementation violated contract",
        violated_invariant="USER.md#L33: Zero stubs",
        negative_rules=[rule],
        smt_counterexample={"x": 42},
        fitness_score=35.0,
        category="academic_sovereignty_leak",
    )

    note_path = temp_store.export_to_wiki(rec)
    assert note_path.exists()
    assert note_path.name.endswith(".md")

    content = note_path.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "id: Reflexion_refl_wiki_01" in content
    assert "category: academic_sovereignty_leak" in content
    assert "dedup_hash:" in content
    assert "tags:" in content
    assert "## 1. Failure Context & Error Signature" in content
    assert "## 2. Root Cause Analysis" in content
    assert "## 3. Violated Invariant" in content
    assert "## 4. Counterexample & Evidence Trace" in content
    assert '"x": 42' in content
    assert "## 7. Bidirectional Wikilinks" in content
    assert "[[ADR_005_CONTINUOUS_AGENT_SELF_IMPROVEMENT_FLYWHEEL]]" in content


def test_fts5_lexical_search_and_triggers(temp_store):
    """Verifies SQLite FTS5 BM25 search across error signature and root cause."""
    rec1 = ReflexionRecord(
        record_id="refl_fts_01",
        timestamp=time.time(),
        task_id="task_quicksort",
        candidate_summary="def quicksort(a): pass",
        root_cause="Quicksort partition pivot boundary out of bounds recursion",
        violated_invariant="Partition offset <= right bound",
        negative_rules=[],
        category="algorithm_recursion",
    )
    rec2 = ReflexionRecord(
        record_id="refl_fts_02",
        timestamp=time.time(),
        task_id="task_btree",
        candidate_summary="def btree_insert(k): pass",
        root_cause="B-tree balance invariant failure on node split",
        violated_invariant="Node child count between t and 2t",
        negative_rules=[],
        category="data_structure",
    )

    temp_store.insert_record(rec1)
    temp_store.insert_record(rec2)

    # Search for quicksort partition
    results_qs = temp_store.fts_search("quicksort partition", limit=5)
    assert len(results_qs) >= 1
    assert results_qs[0][0].record_id == "refl_fts_01"
    assert results_qs[0][1] > 0.0

    # Search for btree balance
    results_bt = temp_store.fts_search("btree split", limit=5)
    assert len(results_bt) >= 1
    assert results_bt[0][0].record_id == "refl_fts_02"


def test_intercept_tracking_and_resolved_status(temp_store):
    """Verifies intercept count increments and resolved status updates."""
    rule = ExecutableNegativeConstraint(
        rule_id="neg_track_01",
        rule_type="REGEX_DENY",
        pattern="track_me",
        description="Tracking rule",
    )
    rec = ReflexionRecord(
        record_id="refl_track_01",
        timestamp=time.time(),
        task_id="task_tracking",
        candidate_summary="candidate",
        root_cause="root cause",
        violated_invariant="invariant",
        negative_rules=[rule],
    )
    temp_store.insert_record(rec)

    # Increment intercept
    temp_store.increment_intercept_count("neg_track_01", count=3)
    updated = temp_store.get_record("refl_track_01")
    assert updated.intercept_count == 3

    # Mark resolved
    assert updated.resolved is False
    temp_store.mark_resolved("refl_track_01", resolved=True)
    resolved = temp_store.get_record("refl_track_01")
    assert resolved.resolved is True

    # Resolved records excluded from active rules
    active_rules = temp_store.get_active_negative_rules()
    assert not any(r.rule_id == "neg_track_01" for r in active_rules)


# =====================================================================
# F7: Pre-Flight Retrieval & Executable Negative Constraint Filter Tests
# =====================================================================

def test_preflight_regex_deny_interception(temp_store):
    """Verifies PreFlightFilter immediately vetoes code matching REGEX_DENY."""
    rule = ExecutableNegativeConstraint(
        rule_id="neg_regex_leak",
        rule_type="REGEX_DENY",
        pattern=r"(?i)вот\s+готовое\s+решение",
        description="Direct homework answers are forbidden (USER.md#L37).",
    )
    preflight = PreFlightFilter(episodic_store=temp_store, cached_rules=[rule])

    bad_candidate = """
def answer_student():
    return "Вот готовое решение вашей задачи!"
"""
    result = preflight.check_candidate(bad_candidate)
    assert result.allowed is False
    assert result.is_blocked is True
    assert "USER.md#L37" in result.violation_message
    assert result.violated_rule.rule_id == "neg_regex_leak"


def test_preflight_ast_pattern_deny_stubs(temp_store):
    """Verifies PreFlightFilter detects empty pass and ellipsis stubs via AST visitor."""
    stub_rule = ExecutableNegativeConstraint(
        rule_id="neg_ast_stub",
        rule_type="AST_PATTERN_DENY",
        pattern="ast.Pass|ast.Constant(Ellipsis)",
        description="Empty facade stubs strictly forbidden (USER.md#L33).",
    )
    preflight = PreFlightFilter(episodic_store=temp_store, cached_rules=[stub_rule])

    # Pass stub
    pass_code = "def calculate_matrix():\n    pass\n"
    res1 = preflight.check_candidate(pass_code)
    assert res1.allowed is False
    assert "empty 'pass' stub" in res1.violation_message

    # Ellipsis stub
    ellipsis_code = "def calculate_matrix():\n    ...\n"
    res2 = preflight.check_candidate(ellipsis_code)
    assert res2.allowed is False
    assert "empty '...' ellipsis stub" in res2.violation_message

    # Real implementation should be allowed
    real_code = "def calculate_matrix():\n    return [[1, 0], [0, 1]]\n"
    res3 = preflight.check_candidate(real_code)
    assert res3.allowed is True
    assert res3.violation_message is None


def test_preflight_ast_pattern_deny_illicit_imports(temp_store):
    """Verifies PreFlightFilter blocks forbidden module imports like mock."""
    import_rule = ExecutableNegativeConstraint(
        rule_id="neg_mock_import",
        rule_type="AST_PATTERN_DENY",
        pattern="import:mock",
        description="Synthetic mocks prohibited in production code.",
        target_scope="imports",
    )
    preflight = PreFlightFilter(episodic_store=temp_store, cached_rules=[import_rule])

    mock_code1 = "import mock\nm = mock.Mock()"
    res1 = preflight.check_candidate(mock_code1)
    assert res1.allowed is False
    assert "Prohibited import 'mock'" in res1.violation_message

    mock_code2 = "from unittest import mock"
    res2 = preflight.check_candidate(mock_code2)
    assert res2.allowed is False
    assert "mock" in res2.violation_message.lower()


def test_preflight_ast_pattern_deny_dangerous_calls(temp_store):
    """Verifies PreFlightFilter blocks prohibited calls like eval or exec."""
    call_rule = ExecutableNegativeConstraint(
        rule_id="neg_eval_call",
        rule_type="AST_PATTERN_DENY",
        pattern="call:eval",
        description="Prohibit eval execution in sandbox.",
    )
    preflight = PreFlightFilter(episodic_store=temp_store, cached_rules=[call_rule])

    eval_code = "def run_dynamic(expr):\n    return eval(expr)\n"
    res = preflight.check_candidate(eval_code)
    assert res.allowed is False
    assert "Prohibited call to 'eval'" in res.violation_message


def test_preflight_smt_predicate_block(temp_store):
    """Verifies PreFlightFilter vetoes candidate containing disproved SMT counterexample models."""
    smt_rule = ExecutableNegativeConstraint(
        rule_id="neg_smt_model",
        rule_type="SMT_PREDICATE_BLOCK",
        pattern="step_offset == 1 and window_base == 0",
        description="Disproved parameter coupling at domain boundary.",
    )
    preflight = PreFlightFilter(episodic_store=temp_store, cached_rules=[smt_rule])

    failing_code = """
def compute_window():
    step_offset = 1
    window_base = 0
    return step_offset + window_base
"""
    res = preflight.check_candidate(failing_code)
    assert res.allowed is False
    assert "PRE-FLIGHT SMT VETO" in res.violation_message


def test_preflight_latency_under_5ms_benchmark(temp_store):
    """Verifies pre-execution hard-gate executes strictly in under 5 ms across 100 negative rules."""
    rules = []
    for i in range(100):
        rules.append(
            ExecutableNegativeConstraint(
                rule_id=f"bench_rule_{i}",
                rule_type="REGEX_DENY" if i % 2 == 0 else "AST_PATTERN_DENY",
                pattern=f"pattern_{i}_forbidden" if i % 2 == 0 else "call:bad_func_{i}",
                description=f"Benchmark rule {i}",
            )
        )

    preflight = PreFlightFilter(episodic_store=temp_store, cached_rules=rules)
    clean_code = """
def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
"""
    # Warmup
    preflight.check_candidate(clean_code)

    # Measure 5 runs
    times_ms = []
    for _ in range(5):
        t0 = time.perf_counter()
        res = preflight.check_candidate(clean_code)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        times_ms.append(elapsed_ms)
        assert res.allowed is True

    avg_time = sum(times_ms) / len(times_ms)
    assert avg_time < 5.0, f"Pre-flight filter latency exceeded 5 ms threshold: {avg_time:.3f} ms"


def test_tri_hybrid_retrieval_ranking(temp_store):
    """Verifies tri-hybrid search combines BM25 lexical, vector similarity, and recurrence boost."""
    # Record 1: Highly recurrent matrix multiplication bug
    rec1 = ReflexionRecord(
        record_id="refl_tri_01",
        timestamp=time.time(),
        task_id="matrix_mult",
        candidate_summary="def matmul(A, B): return np.dot(A, B)",
        root_cause="Inner dimension mismatch in matrix multiplication dot product",
        violated_invariant="A.shape[1] == B.shape[0]",
        negative_rules=[],
        recurrence_count=5,  # High recurrence boost
        intercept_count=3,
        category="linear_algebra",
    )
    # Record 2: Irrelevant string formatting bug
    rec2 = ReflexionRecord(
        record_id="refl_tri_02",
        timestamp=time.time(),
        task_id="string_format",
        candidate_summary="def format_str(s): return s.strip()",
        root_cause="Unicode encoding crash on utf-16 surrogate pairs",
        violated_invariant="Valid utf-8 string encoding",
        negative_rules=[],
        recurrence_count=1,
        intercept_count=0,
        category="encoding",
    )

    temp_store.insert_record(rec1)
    temp_store.insert_record(rec2)

    preflight = PreFlightFilter(episodic_store=temp_store)

    query = "matrix dimension mismatch dot product"
    results = preflight.tri_hybrid_search(query, limit=5)

    assert len(results) >= 1
    assert results[0].record_id == "refl_tri_01"
    assert results[0].category == "linear_algebra"


# =====================================================================
# Integration & PROJECT.md § M2 Interface Contract Tests
# =====================================================================

def test_reflexion_memory_store_facade_contract(temp_store):
    """Verifies ReflexionMemoryStore satisfies PROJECT.md § M2 interface contract."""
    store = ReflexionMemoryStore(db_path=str(temp_store.db_path), wiki_root=temp_store.wiki_root)

    rule = ExecutableNegativeConstraint(
        rule_id="neg_facade_01",
        rule_type="REGEX_DENY",
        pattern=r"\bforbidden_keyword\b",
        description="Prohibit forbidden_keyword usage",
    )
    rec = ReflexionRecord(
        record_id="refl_facade_01",
        timestamp=time.time(),
        task_id="task_facade",
        candidate_summary="def test(): forbidden_keyword()",
        root_cause="Used forbidden keyword",
        violated_invariant="Keywords must be strictly whitelisted",
        negative_rules=[rule],
    )

    # 1. record_failure(record: ReflexionRecord) -> None
    store.record_failure(rec)

    # 2. retrieve_similar_dead_ends(task_description: str, limit: int = 5) -> List[ReflexionRecord]
    retrieved = store.retrieve_similar_dead_ends("forbidden keyword whitelisted", limit=5)
    assert isinstance(retrieved, list)
    assert len(retrieved) >= 1
    assert retrieved[0].record_id == "refl_facade_01"

    # 3. check_negative_constraints(candidate_code: str) -> tuple[bool, Optional[str]]
    blocked, msg = store.check_negative_constraints("def foo(): forbidden_keyword()")
    assert blocked is True
    assert msg is not None
    assert "forbidden_keyword" in msg

    allowed, no_msg = store.check_negative_constraints("def foo(): safe_call()")
    assert allowed is False  # allowed is False means NOT blocked
    assert no_msg is None


def test_closed_loop_flywheel_reflexion_cycle(temp_store):
    """
    Simulates end-to-end closed-loop error-to-insight flywheel cycle:
    Round 1: Candidate violates safety -> Reflexion generated & stored
    Round 2: Agent attempts identical bad code -> Pre-flight hard-gate halts in < 5 ms
    Round 3: Agent uses remediation hint -> Pre-flight allows -> Candidate passes -> Marked resolved
    """
    generator = ContinuousReflexionGenerator()
    store = ReflexionMemoryStore(db_path=str(temp_store.db_path), wiki_root=temp_store.wiki_root)

    # Round 1: Failed candidate execution
    bad_code = "def get_answer():\n    return 'Вот готовое решение лабораторной'"
    score = QualityScore(
        total_score=20.0,
        correctness_smt=40.0,
        empirical_integrity=30.0,
        parsimony_efficiency=10.0,
        academic_sovereignty=0.0,
        is_admissible=False,
        violation_reasons=["[SOVEREIGNTY VIOLATION] Direct solution dump detected in academic task"],
    )
    record = generator.from_quality_score("task_mirea_lab", bad_code, score)
    store.record_failure(record)

    # Round 2: Pre-flight interception of recurring mistake
    t0 = time.perf_counter()
    is_blocked, veto_reason = store.check_negative_constraints(bad_code)
    latency_ms = (time.perf_counter() - t0) * 1000

    assert is_blocked is True
    assert latency_ms < 5.0
    assert "USER.md#L37" in veto_reason or "PRE-FLIGHT REGEX VETO" in veto_reason

    # Round 3: Remediated candidate with Socratic inquiry
    remediated_code = """
def get_answer():
    # Socratic guidance for student
    return "Обратите внимание на формулу (2.1): какой результат дает подстановка x=0?"
"""
    is_blocked_rem, rem_msg = store.check_negative_constraints(remediated_code)
    assert is_blocked_rem is False
    assert rem_msg is None

    # Mark original failure resolved
    store.episodic_store.mark_resolved(record.record_id, resolved=True)
    assert store.episodic_store.get_record(record.record_id).resolved is True
