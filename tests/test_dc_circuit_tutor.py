"""
Unit Test Suite for Milestone 7 (F19): Semester 3 DC Circuit Socratic Tutor.

Tests:
- Circuit parameters for Variant 6 (Hex D35E): R, E, nodes, branches.
- Strict USER.md#L37 Pedagogical Sovereignty: ZERO unearned solutions or direct answers leaked.
- Validation across all steps: topology, Kirchhoff laws, MKT, MUP, currents, power balance, potential diagram.
- Socratic hint generator across all error types.
- Oral defense questions and reasoning verification.
- Compliance with AcademicSovereigntyGuard.
- NO MOCKS: All tests use genuine math, electrical laws, and dataclasses.
"""

import pytest

from vazus_autonomous_harness.academic.dc_circuit_tutor import (
    DEFAULT_VARIANT_6_E,
    DEFAULT_VARIANT_6_R,
    VARIANT_6_BRANCHES_COUNT,
    VARIANT_6_HEX,
    VARIANT_6_INDEPENDENT_LOOPS,
    VARIANT_6_INDEPENDENT_NODES,
    VARIANT_6_NODES,
    DCCircuitSocraticTutor,
)
from vazus_autonomous_harness.verification.academic_sovereignty import (
    AcademicSovereigntyGuard,
)


def test_tutor_initialization_variant_6():
    tutor = DCCircuitSocraticTutor(variant=6)
    assert tutor.variant == 6
    assert tutor.hex_code == VARIANT_6_HEX
    assert tutor.R == DEFAULT_VARIANT_6_R
    assert tutor.E == DEFAULT_VARIANT_6_E
    assert tutor.nodes == VARIANT_6_NODES
    assert tutor.branches_count == VARIANT_6_BRANCHES_COUNT
    assert tutor.independent_nodes == VARIANT_6_INDEPENDENT_NODES
    assert tutor.independent_loops == VARIANT_6_INDEPENDENT_LOOPS

    params = tutor.get_circuit_parameters()
    assert params["variant"] == 6
    assert params["hex_code"] == "D35E"
    assert params["nodes_count"] == 4
    assert params["branches_count"] == 6
    assert params["resistances_ohm"]["R1"] == 64.0
    assert params["resistances_ohm"]["R2"] == 98.0
    assert params["resistances_ohm"]["R3"] == 30.0
    assert params["resistances_ohm"]["R4"] == 48.0
    assert params["resistances_ohm"]["R5"] == 58.0
    assert params["resistances_ohm"]["R6"] == 65.0
    assert params["emf_sources_v"]["E3"] == 25.0
    assert params["emf_sources_v"]["E6"] == 30.0


def test_pedagogical_sovereignty_guard_zero_solution_leak():
    """Verifies that all hints and checks strictly comply with USER.md#L37."""
    guard = AcademicSovereigntyGuard(strict_mode=True)
    tutor = DCCircuitSocraticTutor(variant=6)

    steps = [
        "topology",
        "kirchhoff_1",
        "kirchhoff_2",
        "mkt",
        "mup",
        "currents",
        "power_balance",
        "potential_diagram",
    ]
    error_types = ["general", "sign_error", "resistance", "emf", "reference", "imbalance", "equation"]

    # Check hints for all combinations
    for step in steps:
        for err in error_types:
            hint = tutor.generate_socratic_hint(step, err)
            # Must contain a question mark
            assert "?" in hint, f"Hint for {step}/{err} lacks question mark"
            # Verify via AcademicSovereigntyGuard
            check = guard.verify_response("типовой расчет электротехника дз 1 вариант 6", hint)
            assert check["allowed"] is True, f"Guard rejected hint for {step}/{err}: {check['reason']}"
            assert check["has_direct_solution_leak"] is False
            assert check["has_socratic_guidance"] is True


def test_check_student_step_topology():
    tutor = DCCircuitSocraticTutor(variant=6)

    # 1. Correct topology
    ok, msg = tutor.check_student_step("topology", {
        "nodes": 4,
        "branches": 6,
        "kcl_equations": 3,
        "kvl_equations": 3,
    })
    assert ok is True
    assert "?" in msg

    # 2. Incorrect node count
    ok, msg = tutor.check_student_step("topology", {"nodes": 5})
    assert ok is False
    assert "узл" in msg.lower()
    assert "?" in msg

    # 3. Incorrect branch count
    ok, msg = tutor.check_student_step("topology", {"branches": 7})
    assert ok is False
    assert "ветв" in msg.lower()
    assert "?" in msg

    # 4. Incorrect KCL equations count (e.g. 4 instead of n-1=3)
    ok, msg = tutor.check_student_step("topology", {"kcl_equations": 4})
    assert ok is False
    assert "первому закону" in msg.lower() or "n - 1" in msg
    assert "?" in msg


def test_check_student_step_kirchhoff_1():
    tutor = DCCircuitSocraticTutor(variant=6)

    # Correct node equations:
    # Node a: -I1 - I4 - I6 = 0
    # Node b: +I1 + I2 + I3 = 0
    # Node c: -I3 + I5 + I6 = 0
    ok, msg = tutor.check_student_step("kirchhoff_1", {
        "node_a": [-1, 0, 0, -1, 0, -1],
        "node_b": [1, 1, 1, 0, 0, 0],
        "node_c": [0, 0, -1, 0, 1, 1],
    })
    assert ok is True
    assert "?" in msg

    # Incorrect signs at node a (mixed signs)
    ok, msg = tutor.check_student_step("kirchhoff_1", {
        "node_a": [-1, 0, 0, 1, 0, -1],
    })
    assert ok is False
    assert "узл" in msg.lower() and "a" in msg.lower()
    assert "?" in msg

    # Extraneous branch in node b
    ok, msg = tutor.check_student_step("kirchhoff_1", {
        "node_b": [1, 1, 1, 1, 0, 0],
    })
    assert ok is False
    assert "узел b" in msg.lower()
    assert "?" in msg


def test_check_student_step_kirchhoff_2():
    tutor = DCCircuitSocraticTutor(variant=6)

    # Correct loop EMFs:
    # Loop 1: 0 V
    # Loop 2: -25 V (or 25 V if opposite loop orientation)
    # Loop 3: -30 V (or 30 V)
    ok, msg = tutor.check_student_step("kirchhoff_2", {
        "loop1_emf": 0.0,
        "loop2_emf": -25.0,
        "loop3_emf": -30.0,
    })
    assert ok is True
    assert "?" in msg

    # Incorrect Loop 1 EMF (there are no EMF sources in loop 1)
    ok, msg = tutor.check_student_step("kirchhoff_2", {
        "loop1_emf": 15.0,
    })
    assert ok is False
    assert "первый" in msg.lower()
    assert "?" in msg

    # Incorrect Loop 2 EMF
    ok, msg = tutor.check_student_step("kirchhoff_2", {
        "loop2_emf": 10.0,
    })
    assert ok is False
    assert "2-м контуре" in msg.lower() or "e3" in msg.lower()
    assert "?" in msg


def test_check_student_step_mkt():
    tutor = DCCircuitSocraticTutor(variant=6)

    # Loop resistances:
    # R11 = R1 + R2 + R4 = 64 + 98 + 48 = 210
    # R22 = R2 + R3 + R5 = 98 + 30 + 58 = 186
    # R33 = R4 + R5 + R6 = 48 + 58 + 65 = 171
    ok, msg = tutor.check_student_step("mkt", {
        "R11": 210.0,
        "R22": 186.0,
        "R33": 171.0,
    })
    assert ok is True
    assert "?" in msg

    # Mistake in R11
    ok, msg = tutor.check_student_step("mkt", {
        "R11": 200.0,
    })
    assert ok is False
    assert "r11" in msg.lower() or "контур 1" in msg.lower()
    assert "?" in msg

    # Mistake in R22
    ok, msg = tutor.check_student_step("mkt", {
        "R22": 190.0,
    })
    assert ok is False
    assert "контур 2" in msg.lower() or "r22" in msg.lower()
    assert "?" in msg


def test_check_student_step_mup():
    tutor = DCCircuitSocraticTutor(variant=6)

    # Valid base node d with 0.0 V
    ok, msg = tutor.check_student_step("mup", {
        "reference_node": "d",
        "reference_potential": 0.0,
    })
    assert ok is True
    assert "?" in msg

    # Invalid non-zero reference potential
    ok, msg = tutor.check_student_step("mup", {
        "reference_node": "d",
        "reference_potential": 5.0,
    })
    assert ok is False
    assert "0" in msg
    assert "?" in msg


def test_check_student_step_branch_currents():
    tutor = DCCircuitSocraticTutor(variant=6)

    # Ground truth values:
    # I1 ~ -0.2762 A, I2 ~ -0.1251 A, I3 ~ 0.4012 A,
    # I4 ~ -0.1129 A, I5 ~ 0.0122 A, I6 ~ 0.3891 A
    valid_student_currents = {
        "I1": -0.276,
        "I2": -0.125,
        "I3": 0.401,
        "I4": -0.113,
        "I5": 0.012,
        "I6": 0.389,
    }
    ok, msg = tutor.check_student_step("currents", valid_student_currents)
    assert ok is True
    assert "?" in msg
    # Must not leak answer values in message
    assert "готовое решение" not in msg.lower()

    # Incomplete inputs
    ok, msg = tutor.check_student_step("currents", {"I1": -0.276, "I2": -0.125})
    assert ok is False
    assert "2 из 6" in msg
    assert "?" in msg

    # Inverted signs on branch 1 and branch 3
    flawed_currents = {
        "I1": +0.276,
        "I2": -0.125,
        "I3": -0.401,
        "I4": -0.113,
        "I5": 0.012,
        "I6": 0.389,
    }
    ok, msg = tutor.check_student_step("currents", flawed_currents)
    assert ok is False
    assert "ветвь 1" in msg
    assert "?" in msg


def test_check_student_step_power_balance():
    tutor = DCCircuitSocraticTutor(variant=6)

    # Accurate power balance (~21.70 W)
    ok, msg = tutor.check_student_step("power_balance", {
        "P_consumed": 21.702,
        "P_generated": 21.702,
    })
    assert ok is True
    assert "?" in msg

    # Severe power mismatch (> 1%)
    ok, msg = tutor.check_student_step("power_balance", {
        "P_consumed": 21.70,
        "P_generated": 25.00,
    })
    assert ok is False
    assert "погрешность" in msg.lower() or "1%" in msg.lower()
    assert "?" in msg

    # Negative power input
    ok, msg = tutor.check_student_step("power_balance", {
        "P_consumed": -10.0,
        "P_generated": 21.70,
    })
    assert ok is False
    assert "отрицательной" in msg.lower()
    assert "?" in msg


def test_check_student_step_potential_diagram():
    tutor = DCCircuitSocraticTutor(variant=6)

    ok, msg = tutor.check_student_step("potential_diagram", {
        "contour": "b - c (E3) - a - c (E6) - d",
    })
    assert ok is True
    assert "?" in msg

    # Contour missing E6
    ok, msg = tutor.check_student_step("potential_diagram", {
        "contour": "a - b - d - a",
    })
    assert ok is False
    assert "e3" in msg.lower() or "e6" in msg.lower()
    assert "?" in msg


def test_oral_defense_questions():
    guard = AcademicSovereigntyGuard(strict_mode=True)
    tutor = DCCircuitSocraticTutor(variant=6)
    questions = tutor.get_oral_defense_questions()

    assert len(questions) == 4
    for q in questions:
        assert "question" in q
        assert "socratic_prompt" in q
        assert "?" in q["socratic_prompt"]

        # Verify compliance with AcademicSovereigntyGuard
        check = guard.verify_response(q["question"], q["socratic_prompt"])
        assert check["allowed"] is True
        assert check["has_direct_solution_leak"] is False


def test_unknown_step_name_graceful_handling():
    tutor = DCCircuitSocraticTutor(variant=6)
    ok, msg = tutor.check_student_step("quantum_teleportation", {})
    assert ok is False
    assert "неизвестный этап" in msg.lower()
    assert "?" in msg
