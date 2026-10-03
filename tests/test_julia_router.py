"""
tests/test_julia_router.py
==========================
Comprehensive verification test suite for Julia System-1 Decision Router
accelerated on Intel AI Boost NPU with Jev-style typed decision primitives
(Choice, Score, Noul, Tool Routing) and RLCD probability calibration.
"""

import pytest
from vazus_core.integrations.julia_router import (
    JuliaRouter,
    RoutingDecision,
    ChoiceDecision,
    ScoreDecision,
    NoulDecision,
    ToolRoutingDecision,
    RLCDCalibrator,
    CANONICAL_DOMAINS,
)


@pytest.fixture(scope="module")
def shared_router() -> JuliaRouter:
    return JuliaRouter(offline_fallback=True)


def test_julia_router_initialization(shared_router: JuliaRouter):
    assert shared_router is not None
    assert len(shared_router.domains) == len(CANONICAL_DOMAINS)
    if shared_router.classifier:
        assert shared_router.classifier.active_device in ("NPU", "GPU", "CPU", None)


def test_julia_router_academic_route(shared_router: JuliaRouter):
    decision = shared_router.route("Срочно проверь задолженности по матанализу и график пересдач")
    assert isinstance(decision, RoutingDecision)
    assert decision.domain in ("academic", "vazus-academic-debt-navigator")
    assert decision.confidence >= 0.50
    assert decision.latency_ms < 250.0


def test_julia_router_coding_route(shared_router: JuliaRouter):
    decision = shared_router.route("Сделай рефакторинг функции ast_prune и прогони pytest")
    assert isinstance(decision, RoutingDecision)
    assert decision.domain in ("code", "testing", "refactor")
    assert isinstance(decision.requires_cloud_reasoning, bool)


def test_julia_router_choice_primitive(shared_router: JuliaRouter):
    options = ["web_search", "run_pytest", "query_database"]
    decision = shared_router.route_choice("Прогони тесты pytest для vazus_core", options)
    assert isinstance(decision, ChoiceDecision)
    assert decision.selected in options
    assert decision.selected == "run_pytest"
    assert decision.confidence > 0.0
    assert sum(decision.probabilities.values()) == pytest.approx(1.0, abs=1e-3)
    assert decision.margin >= 0.0


def test_julia_router_score_primitive(shared_router: JuliaRouter):
    rubric = "Code compilation and test pass status"
    score_res = shared_router.route_score("Function syntax error and broken tests", rubric)
    assert isinstance(score_res, ScoreDecision)
    assert 0.0 <= score_res.normalized_score <= 1.0
    assert 0.0 <= score_res.score <= 1.0
    assert score_res.confidence > 0.0


def test_julia_router_noul_primitive(shared_router: JuliaRouter):
    context = "All 42 unit tests passed with exit code 0"
    hypothesis = "The test suite succeeded without errors"
    noul_res = shared_router.route_noul(hypothesis, context, threshold=0.5)
    assert isinstance(noul_res, NoulDecision)
    assert isinstance(noul_res.passed, bool)
    assert 0.0 <= noul_res.probability <= 1.0


def test_julia_router_tool_dispatch(shared_router: JuliaRouter):
    tool_res = shared_router.route_tool("Запусти pytest и проверь ast деревья")
    assert isinstance(tool_res, ToolRoutingDecision)
    assert tool_res.domain == "code"
    assert tool_res.selected_tool in ("cbm", "vazus_ast_prune", "code-quality", "pytest_runner", "vazus_smt_z3_verify")
    assert tool_res.confidence > 0.0


def test_rlcd_calibrator():
    calibrator = RLCDCalibrator(temperature=1.2)
    logits = [2.0, 1.0, 0.1]
    probs = calibrator.temperature_scale(logits)
    assert len(probs) == 3
    assert sum(probs) == pytest.approx(1.0, abs=1e-5)
    assert probs[0] > probs[1] > probs[2]

    # Test Brier Score
    brier = RLCDCalibrator.brier_score([1.0, 0.0, 0.0], [1, 0, 0])
    assert brier == 0.0

    brier_imperfect = RLCDCalibrator.brier_score([0.8, 0.1, 0.1], [1, 0, 0])
    assert brier_imperfect > 0.0


def test_julia_router_skill_matching_and_progression(shared_router: JuliaRouter):
    # Match existing academic skill in competency tree
    skill_res = shared_router.route_skill("Помоги с пределами и интегралами по матанализу")
    assert skill_res.requires_new_skill is False
    assert skill_res.selected_skill == "mirea-rt1-calculus"
    assert "mirea" in skill_res.prerequisites
    assert "academic_verification" in skill_res.next_in_tree

    # Match financial skill
    fin_res = shared_router.route_skill("Проверь баланс карты тинькофф")
    assert fin_res.requires_new_skill is False
    assert fin_res.selected_skill == "tinkoff_finance_manager"
    assert "npd_tax_tracker" in fin_res.next_in_tree


def test_julia_router_skill_gap_detection(shared_router: JuliaRouter):
    # Unhandled intent with no existing skill in tree
    gap_res = shared_router.route_skill("Спроектируй гидропонную установку с датчиками pH", gap_threshold=0.45)
    assert gap_res.requires_new_skill is True
    assert gap_res.selected_skill is None
    assert gap_res.suggested_skill_name is not None
    assert "vazus_author_skill" in gap_res.authoring_prompt


def test_julia_router_routine_action_dispatch(shared_router: JuliaRouter):
    # Routine test execution reflex
    act_test = shared_router.route_routine_action("Запусти тесты")
    assert act_test.is_routine is True
    assert act_test.action_type == "run_command"
    assert "pytest" in act_test.suggested_command

    # Routine OCR reflex
    act_ocr = shared_router.route_routine_action("Прочитай буфер обмена через ocr")
    assert act_ocr.is_routine is True
    assert act_ocr.action_type == "run_command"
    assert "clip_ocr.py" in act_ocr.suggested_command

    # Non-routine query
    act_non_routine = shared_router.route_routine_action("В чем смысл жизни и устройство вселенной?")
    assert act_non_routine.is_routine is False
    assert act_non_routine.action_type == "none"

