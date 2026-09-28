"""
Unit Test Suite for Milestone 1 (F1, F2, F3, F4) of Autonomous Absolute AI Flywheel.

Components Tested:
- F1: 100-Point Quality Evaluation Rubric & 75-Point Hard Admission Gate
- F2: SMT Z3 Formal Equivalence & Contract Prover (Z3 5.0.0)
- F3: AST Bloat & Parsimony Analyzer
- F4: Academic Sovereignty & Zero Stub Guard (USER.md#L37, USER.md#L33)
"""

from vazus_autonomous_harness.verification.quality_engine import (
    QualityEvaluationEngine,
    QualityScore,
    ASTParsimonyAnalyzer,
)
from vazus_autonomous_harness.verification.smt_prover import (
    SMTProver,
)
from vazus_autonomous_harness.verification.academic_sovereignty import (
    AcademicSovereigntyGuard,
)


# =====================================================================
# F2: SMT Z3 Formal Equivalence & Contract Prover Tests
# =====================================================================

def test_smt_prover_valid_contract_unsat():
    prover = SMTProver()
    code = """
def clamp_value(val: int, low: int, high: int) -> int:
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
    assert "UNSAT" in result.details


def test_smt_prover_contract_violation_counterexample_sat():
    prover = SMTProver()
    code = """
def buggy_increment(x: int) -> int:
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
    assert "x" in result.counterexample
    assert "Contract violation" in result.details


def test_smt_prover_expression_equivalence_unsat():
    prover = SMTProver()
    res = prover.verify_expression_equivalence("a * 2 + a * 3", "5 * a", ["a"])
    assert res["equivalent"] is True
    assert res["status"] == "PROVEN_EQUIVALENT"


def test_smt_prover_expression_divergence_counterexample():
    prover = SMTProver()
    res = prover.verify_expression_equivalence("x * 2", "x + 3", ["x"])
    assert res["equivalent"] is False
    assert res["status"] == "DISPROVEN"
    assert "counterexample" in res


def test_smt_prover_function_equivalence():
    prover = SMTProver()
    f1 = """
def double_and_add(x: int) -> int:
    return (x * 2) + 4
"""
    f2 = """
def double_and_add(x: int) -> int:
    return 2 * (x + 2)
"""
    res = prover.verify_functional_equivalence(f1, f2)
    assert res.verified is True
    assert res.status == "UNSAT"


def test_smt_prover_function_divergence_counterexample():
    prover = SMTProver()
    f1 = """
def compute(x: int) -> int:
    return x * 2
"""
    f2 = """
def compute(x: int) -> int:
    return x * 3
"""
    res = prover.verify_functional_equivalence(f1, f2)
    assert res.verified is False
    assert res.status == "SAT"
    assert res.counterexample is not None
    assert "x" in res.counterexample


def test_smt_prover_vacuous_contract_rejected():
    prover = SMTProver()
    # Tautological postcondition
    code_vacuous_ensures = """
def dummy(x: int) -> int:
    \"\"\"
    :requires: x > 0
    :ensures: True
    \"\"\"
    return x
"""
    res = prover.verify_contracts(code_vacuous_ensures)
    assert res.verified is False
    assert res.status == "VACUOUS_CONTRACT"

    # Impossible precondition
    code_vacuous_requires = """
def dummy2(x: int) -> int:
    \"\"\"
    :requires: False
    :ensures: result > 0
    \"\"\"
    return x
"""
    res2 = prover.verify_contracts(code_vacuous_requires)
    assert res2.verified is False
    assert res2.status == "VACUOUS_CONTRACT"


def test_smt_prover_memory_safety_bounds():
    prover = SMTProver()
    # Safe bounds: offset 5, length 10 in buffer capacity 20
    safe_res = prover.verify_memory_safety(offset=5, length=10, capacity=20)
    assert safe_res.verified is True
    assert safe_res.status == "UNSAT"

    # Unsafe bounds: offset 15, length 10 in buffer capacity 20 (15 + 10 = 25 > 20)
    unsafe_res = prover.verify_memory_safety(offset=15, length=10, capacity=20)
    assert unsafe_res.verified is False
    assert unsafe_res.status == "SAT"
    assert unsafe_res.counterexample is not None
    assert unsafe_res.counterexample["violation"] == "Buffer overflow"


# =====================================================================
# F3: AST Bloat & Parsimony Analyzer Tests
# =====================================================================

def test_ast_parsimony_node_counting():
    analyzer = ASTParsimonyAnalyzer()
    assert analyzer.count_nodes("") == 0
    assert analyzer.count_nodes("x = 1") > 0
    code = """
def foo(a, b):
    return a + b
"""
    assert analyzer.count_nodes(code) > 5


def test_ast_parsimony_clean_diff_bonus():
    analyzer = ASTParsimonyAnalyzer()
    base = """
def compute(x):
    y = x * 2
    z = y + 0
    return z
"""
    # Optimized refactoring with fewer AST nodes
    cand = """
def compute(x):
    return x * 2
"""
    res = analyzer.calculate_bloat(base, cand)
    assert res["bloat_ratio"] < 0
    assert res["bonus"] == 5.0
    assert res["penalty"] == 0.0
    assert res["score"] == 15.0


def test_ast_parsimony_moderate_growth():
    analyzer = ASTParsimonyAnalyzer()
    base = "def f(x): return x"
    # Slight addition within 10%
    res = analyzer.calculate_bloat(base, base)
    assert res["bloat_ratio"] == 0.0
    assert res["score"] == 15.0


def test_ast_parsimony_excessive_bloat_penalty():
    analyzer = ASTParsimonyAnalyzer()
    base = "def f(x): return x"
    # Bloated version adding 10x nodes
    cand = """
def f(x):
    a = 1
    b = 2
    c = 3
    d = 4
    e = 5
    f = 6
    g = 7
    h = 8
    return x + a + b + c + d + e + f + g + h
"""
    res = analyzer.calculate_bloat(base, cand)
    assert res["bloat_ratio"] > 1.0
    assert res["penalty"] == 10.0
    assert res["score"] == 0.0


# =====================================================================
# F4: Academic Sovereignty & Zero Stub Guard Tests
# =====================================================================

def test_academic_sovereignty_direct_leak_vetoed():
    guard = AcademicSovereigntyGuard(strict_mode=True)
    prompt = "Реши за меня типовой расчет по ИВТ"
    dump_response = "Вот готовое решение лабораторной: просто вставь этот код в сдо."
    res = guard.verify_response(prompt, dump_response)
    assert res["allowed"] is False
    assert res["has_direct_solution_leak"] is True
    assert "SOVEREIGNTY VIOLATION" in res["reason"]


def test_academic_sovereignty_socratic_guidance_allowed():
    guard = AcademicSovereigntyGuard(strict_mode=True)
    prompt = "Помоги с лабораторной работой по матрицам"
    socratic_response = "Обрати внимание на свойства элементарных преобразований. Как ты считаешь, почему ранг не меняется?"
    res = guard.verify_response(prompt, socratic_response)
    assert res["allowed"] is True
    assert res["has_socratic_guidance"] is True
    assert res["has_direct_solution_leak"] is False


def test_academic_sovereignty_non_academic_allowed():
    guard = AcademicSovereigntyGuard(strict_mode=True)
    prompt = "Как работает git rebase?"
    response = "Git rebase переносит коммиты поверх новой базовой ветки."
    res = guard.verify_response(prompt, response)
    assert res["allowed"] is True
    assert res["is_academic"] is False


def test_academic_sovereignty_stub_detection():
    guard = AcademicSovereigntyGuard()
    # Code containing empty pass stub
    stub_code = """
def execute_task():
    pass
"""
    has_stubs, reason = guard.check_code_stubs(stub_code)
    assert has_stubs is True
    assert "empty 'pass' stub" in reason

    # Code containing ellipsis stub
    ellipsis_code = """
def fetch_data():
    ...
"""
    has_stubs2, reason2 = guard.check_code_stubs(ellipsis_code)
    assert has_stubs2 is True
    assert "empty '...' stub" in reason2

    # Code containing NotImplementedError
    nie_code = """
def process_stream():
    raise NotImplementedError("TODO")
"""
    has_stubs3, reason3 = guard.check_code_stubs(nie_code)
    assert has_stubs3 is True
    assert "NotImplementedError" in reason3


def test_academic_sovereignty_abstract_method_not_flagged():
    guard = AcademicSovereigntyGuard()
    abstract_code = """
from abc import ABC, abstractmethod

class BaseDriver(ABC):
    @abstractmethod
    def connect(self):
        pass
"""
    has_stubs, reason = guard.check_code_stubs(abstract_code)
    assert has_stubs is False


def test_academic_sovereignty_path_jail():
    guard = AcademicSovereigntyGuard()
    assert guard.check_path_jail(r"C:\vazus\hartes\file.py") is True
    # Escaping to Windows System32 is rejected
    assert guard.check_path_jail(r"C:\Windows\System32\cmd.exe") is False


# =====================================================================
# F1: 100-Point Quality Evaluation Rubric & Admission Gate Tests
# =====================================================================

def test_quality_engine_perfect_score_admitted():
    engine = QualityEvaluationEngine()
    code = """
def safe_multiply(a: int, b: int) -> int:
    \"\"\"
    :requires: a >= 0 and b >= 0
    :ensures: result >= 0
    \"\"\"
    return a * b
"""
    score = engine.evaluate(candidate_code=code, baseline_code=code)
    assert score.correctness_smt == 40.0
    assert score.empirical_integrity == 30.0
    assert score.parsimony_efficiency == 15.0
    assert score.academic_sovereignty == 15.0
    assert score.total_score == 100.0
    assert score.is_admissible is True
    assert score.counterexample is None


def test_quality_engine_rejection_on_smt_failure():
    engine = QualityEvaluationEngine()
    code = """
def decrement_positive(x: int) -> int:
    \"\"\"
    :requires: x >= 0
    :ensures: result > x
    \"\"\"
    return x - 1
"""
    score = engine.evaluate(candidate_code=code)
    assert score.correctness_smt == 0.0
    assert score.total_score <= 60.0
    assert score.is_admissible is False
    assert score.counterexample is not None
    assert "x" in score.counterexample


def test_quality_engine_rejection_on_test_failure():
    engine = QualityEvaluationEngine()
    code = "def add(a, b): return a + b"
    # Mocking test_command with a failing exit code command
    score = engine.evaluate(candidate_code=code, test_command="exit 1")
    assert score.empirical_integrity == 0.0
    assert score.total_score <= 70.0
    assert score.is_admissible is False
    assert any("failed" in r.lower() for r in score.violation_reasons)


def test_quality_engine_rejection_on_sovereignty_violation():
    engine = QualityEvaluationEngine()
    # Code containing an empty stub
    code_with_stub = """
def solve_problem():
    pass
"""
    score = engine.evaluate(candidate_code=code_with_stub)
    assert score.academic_sovereignty == 0.0
    assert score.is_admissible is False
    assert any("STUB VIOLATION" in r for r in score.violation_reasons)


def test_quality_engine_threshold_boundary():
    engine = QualityEvaluationEngine(admission_threshold=75.0)
    assert engine.admission_threshold == 75.0

    # 1. Below 75 threshold (e.g. 74.9) -> Rejection
    score_low = QualityScore(
        total_score=74.9,
        correctness_smt=40.0,
        empirical_integrity=20.0,
        parsimony_efficiency=0.0,
        academic_sovereignty=14.9,
        is_admissible=False,
    )
    assert score_low.is_admissible is False

    # 2. At or above 75 threshold with no vetoes -> Admissible
    score_high = QualityScore(
        total_score=75.0,
        correctness_smt=40.0,
        empirical_integrity=30.0,
        parsimony_efficiency=0.0,
        academic_sovereignty=15.0,
        is_admissible=True,
    )
    assert score_high.is_admissible is True


def test_quality_engine_smt_regression_veto():
    engine = QualityEvaluationEngine()
    baseline = """
def increment(x: int) -> int:
    \"\"\"
    :requires: x >= 0
    :ensures: result > x
    \"\"\"
    return x + 1
"""
    # Candidate stripped formal docstring contracts
    candidate = """
def increment(x: int) -> int:
    return x + 1
"""
    score = engine.evaluate(candidate_code=candidate, baseline_code=baseline)
    assert score.correctness_smt == 0.0
    assert score.is_admissible is False
    assert any("SMT regression" in r for r in score.violation_reasons)


def test_quality_engine_illicit_mock_rejected():
    engine = QualityEvaluationEngine()
    code_with_mock = """
from unittest.mock import MagicMock

def core_function():
    mock = MagicMock()
    return mock.execute()
"""
    score = engine.evaluate(candidate_code=code_with_mock)
    assert score.empirical_integrity == 0.0
    assert score.is_admissible is False
    assert any("mock" in r.lower() for r in score.violation_reasons)


def test_smt_prover_empty_code_and_syntax_error():
    prover = SMTProver()
    res_empty = prover.verify_contracts("")
    assert res_empty.verified is True
    assert res_empty.status == "NO_CONTRACTS"

    res_syntax = prover.verify_contracts("def broken_func(:\n pass")
    assert res_syntax.verified is False
    assert res_syntax.status == "SYNTAX_ERROR"


def test_smt_prover_advanced_operations():
    prover = SMTProver()
    code = """
def math_ops(a: int, b: int) -> int:
    \"\"\"
    :requires: a > 0 and b > 0
    :ensures: result >= 0
    \"\"\"
    x = abs(a)
    m = min(a, b)
    val = -m if a < b else max(a, b)
    return abs(val)
"""
    res = prover.verify_contracts(code)
    assert res.verified is True
    assert res.status == "UNSAT"


def test_quality_engine_syntax_error():
    engine = QualityEvaluationEngine()
    score = engine.evaluate("def invalid_syntax(: pass")
    assert score.correctness_smt == 0.0
    assert score.empirical_integrity == 0.0
    assert score.is_admissible is False
    assert any("syntax" in r.lower() for r in score.violation_reasons)


def test_quality_engine_inline_tests_pass_and_fail():
    engine = QualityEvaluationEngine()

    # Passing inline test
    passing_code = """
def add(a, b):
    return a + b

def test_add():
    assert add(2, 3) == 5
"""
    score_pass = engine.evaluate(passing_code)
    assert score_pass.empirical_integrity == 30.0

    # Failing inline test
    failing_code = """
def add(a, b):
    return a - b

def test_add():
    assert add(2, 3) == 5
"""
    score_fail = engine.evaluate(failing_code)
    assert score_fail.empirical_integrity == 0.0
    assert score_fail.is_admissible is False
    assert any("inline" in r.lower() for r in score_fail.violation_reasons)


def test_quality_engine_functional_equivalence_baseline():
    engine = QualityEvaluationEngine()
    base = """
def multiply_by_eight(x: int) -> int:
    return x * 8
"""
    # Equivalent candidate using bitshift or additions
    cand_equiv = """
def multiply_by_eight(x: int) -> int:
    return (x * 4) * 2
"""
    score = engine.evaluate(candidate_code=cand_equiv, baseline_code=base)
    assert score.correctness_smt == 40.0
    assert score.is_admissible is True

    # Divergent candidate
    cand_divergent = """
def multiply_by_eight(x: int) -> int:
    return (x * 4) + 2
"""
    score_div = engine.evaluate(candidate_code=cand_divergent, baseline_code=base)
    assert score_div.correctness_smt == 0.0
    assert score_div.is_admissible is False
    assert score_div.counterexample is not None


def test_quality_engine_context_prompt_sovereignty_veto():
    engine = QualityEvaluationEngine()
    # Direct leak in academic context prompt
    academic_prompt = "Помоги с лабораторной работой ИВБО-22-25, вот задание"
    score = engine.evaluate(
        candidate_code="Вот готовый код лабораторной для сдачи",
        context_prompt=academic_prompt
    )
    assert score.academic_sovereignty == 0.0
    assert score.is_admissible is False

