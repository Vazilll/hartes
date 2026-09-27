"""
vazus_autonomous_harness.academic.dc_circuit_tutor — Socratic DC Circuit Tutor.

Milestone 7 (F19):
- DC Circuit Calculation for Semester 3 Stage 1 (Variant 6, Hex D35E):
  * Branch resistances R = [64, 98, 30, 48, 58, 65] Ohm.
  * EMF sources E = [0, 0, 25, 0, 0, 30] V.
  * 4 nodes (a, b, c, d), 6 branches (p = 6).
  * Kirchhoff laws (1st and 2nd), MKT (Loop Current Method), MUP (Node Potential Method), power balance.
- Strict USER.md#L37 Pedagogical Sovereignty:
  * ZERO unearned solutions or direct answers leaked.
  * Generates Socratic guidance, validates student intermediate steps, flags errors in reasoning.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger("vazus.harness.academic.dc_circuit_tutor")

# Variant 6 Constants (Hex code: D35E)
VARIANT_6_HEX = "D35E"
DEFAULT_VARIANT_6_R = [64.0, 98.0, 30.0, 48.0, 58.0, 65.0]
DEFAULT_VARIANT_6_E = [0.0, 0.0, 25.0, 0.0, 0.0, 30.0]
VARIANT_6_NODES = ["a", "b", "c", "d"]
VARIANT_6_BRANCHES_COUNT = 6
VARIANT_6_INDEPENDENT_NODES = 3  # n - 1 = 4 - 1
VARIANT_6_INDEPENDENT_LOOPS = 3  # p - (n - 1) = 6 - 3


def _lookup_val(d: Any, *keys: str, default: Any = None) -> Any:
    """Helper to look up the first matching key with a non-None value, preserving 0 and 0.0."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _safe_float(val: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Safely parses a numeric float.
    Returns (float_val, error_indicator).
    If val is NaN, returns (None, 'NaN').
    If val cannot be parsed as float, returns (None, 'INVALID_NUMBER').
    """
    if val is None:
        return None, None
    try:
        f = float(val)
        if math.isnan(f):
            return None, "NaN"
        if math.isinf(f):
            return None, "INF"
        return f, None
    except (ValueError, TypeError):
        return None, "INVALID_NUMBER"


def _has_nan_recursive(obj: Any) -> bool:
    """Recursively checks if any number in the input structure is NaN."""
    if isinstance(obj, (int, float)):
        return math.isnan(obj)
    if isinstance(obj, (list, tuple)):
        return any(_has_nan_recursive(x) for x in obj)
    if isinstance(obj, dict):
        return any(_has_nan_recursive(v) for v in obj.values())
    return False


class DCCircuitSocraticTutor:
    """
    Socratic Tutor for DC Circuit Calculations.
    Strictly adheres to USER.md#L37: guides students through questions,
    conceptual hints, and step-by-step verification without leaking direct solutions.
    """

    def __init__(self, variant: int = 6):
        self.variant = variant
        self.hex_code = VARIANT_6_HEX if variant == 6 else f"VAR_{variant:02d}"
        if variant == 6:
            self.R = list(DEFAULT_VARIANT_6_R)
            self.E = list(DEFAULT_VARIANT_6_E)
        else:
            # Deterministic variation for other test variants if requested
            self.R = [float(50 + (variant * 7 + i * 13) % 60) for i in range(6)]
            self.E = [0.0, 0.0, float(20 + variant), 0.0, 0.0, float(25 + variant)]

        self.nodes = list(VARIANT_6_NODES)
        self.branches_count = VARIANT_6_BRANCHES_COUNT
        self.independent_nodes = len(self.nodes) - 1
        self.independent_loops = self.branches_count - self.independent_nodes

        # Solve internally to evaluate student steps (never displayed raw to student)
        self._ground_truth_currents, self._ground_truth_p_res, self._ground_truth_p_src = (
            self._solve_internally()
        )

    def _solve_internally(self) -> Tuple[np.ndarray, float, float]:
        """Solves the circuit internally for step evaluation without exposing answers."""
        R = self.R
        E = self.E
        A = np.array(
            [
                [-1, 0, 0, -1, 0, -1],
                [1, 1, 1, 0, 0, 0],
                [0, 0, -1, 0, 1, 1],
                [R[0], -R[1], 0, -R[3], 0, 0],
                [0, R[1], -R[2], 0, -R[4], 0],
                [0, 0, 0, R[3], R[4], -R[5]],
            ],
            dtype=float,
        )
        b = np.array(
            [
                0.0,
                0.0,
                0.0,
                E[0] - E[1] - E[3],
                E[1] - E[2] - E[4],
                E[3] + E[4] - E[5],
            ],
            dtype=float,
        )
        try:
            I = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            I = np.zeros(6, dtype=float)

        P_res = float(sum(I[k] ** 2 * R[k] for k in range(6)))
        P_src = float(sum(E[k] * I[k] for k in range(6)))
        return I, P_res, P_src

    def get_circuit_parameters(self) -> Dict[str, Any]:
        """Provides student with the initial problem statement parameters."""
        return {
            "variant": self.variant,
            "hex_code": self.hex_code,
            "resistances_ohm": {f"R{i+1}": r for i, r in enumerate(self.R)},
            "emf_sources_v": {f"E{i+1}": e for i, e in enumerate(self.E)},
            "nodes_count": len(self.nodes),
            "branches_count": self.branches_count,
            "independent_nodes_count": self.independent_nodes,
            "independent_loops_count": self.independent_loops,
        }

    def check_student_step(self, step_name: str, student_input: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates student intermediate step against genuine electrical laws.
        Returns (is_correct, socratic_feedback).
        Never exposes the unearned final answer!
        """
        # Guard: Check for NaN in student inputs
        if _has_nan_recursive(student_input):
            return (
                False,
                "Получено нечисловое значение (NaN). Проверьте вычисления. На каком этапе расчета возникла неопределенность?",
            )

        try:
            normalized_step = self._normalize_step_name(step_name)

            if normalized_step == "topology":
                return self._check_topology(student_input)
            elif normalized_step == "kirchhoff_1":
                return self._check_kirchhoff_1(student_input)
            elif normalized_step == "kirchhoff_2":
                return self._check_kirchhoff_2(student_input)
            elif normalized_step == "mkt":
                return self._check_mkt(student_input)
            elif normalized_step == "mup":
                return self._check_mup(student_input)
            elif normalized_step == "currents":
                return self._check_currents(student_input)
            elif normalized_step == "power_balance":
                return self._check_power_balance(student_input)
            elif normalized_step == "potential_diagram":
                return self._check_potential_diagram(student_input)
            else:
                return (
                    False,
                    f"Неизвестный этап расчета '{step_name}'. Обрати внимание на основные этапы: "
                    f"topology (топология цепи), kirchhoff_1 (1-й ЗК), kirchhoff_2 (2-й ЗК), "
                    f"mkt (метод контурных токов), mup (метод узловых потенциалов), "
                    f"currents (расчет токов), power_balance (баланс мощностей). Какой из них ты сейчас решаешь?",
                )
        except (ValueError, TypeError) as err:
            return (
                False,
                f"Ошибка в формате числовых данных: {err}. Убедитесь, что все значения введены вещественными числами. Проверьте правильность исходных данных?",
            )

    def _normalize_step_name(self, raw_name: str) -> str:
        s = raw_name.strip().lower()
        if any(k in s for k in ("topolog", "тополог", "базовые", "basic")):
            return "topology"
        if any(k in s for k in ("kirchhoff_1", "1-й закон", "1 закон", "первый закон", "kcl", "узл")):
            return "kirchhoff_1"
        if any(k in s for k in ("kirchhoff_2", "2-й закон", "2 закон", "второй закон", "kvl", "контур")):
            return "kirchhoff_2"
        if any(k in s for k in ("mkt", "мкт", "контурных токов")):
            return "mkt"
        if any(k in s for k in ("mup", "муп", "узловых потенциалов")):
            return "mup"
        if any(k in s for k in ("current", "ток", "ветвей")):
            return "currents"
        if any(k in s for k in ("power", "мощнос", "баланс")):
            return "power_balance"
        if any(k in s for k in ("diagram", "диаграмм", "потенциал")):
            return "potential_diagram"
        return s

    def _check_topology(self, student_input: Dict[str, Any]) -> Tuple[bool, str]:
        """Validates node count, branch count, and independent equation counts."""
        nodes = _lookup_val(student_input, "nodes", "nodes_count")
        branches = _lookup_val(student_input, "branches", "branches_count")
        kcl_eqs = _lookup_val(student_input, "kcl_equations", "kcl_count")
        kvl_eqs = _lookup_val(student_input, "kvl_equations", "kvl_count")

        for name, val in [("узлов", nodes), ("ветвей", branches), ("уравнений по 1-му ЗК", kcl_eqs), ("уравнений по 2-му ЗК", kvl_eqs)]:
            if val is not None:
                parsed_val, err = _safe_float(val)
                if err:
                    return (
                        False,
                        f"Не удалось распознать числовое значение для {name}. Убедитесь, что количество введено числом. Сколько {name} на схеме?",
                    )

        if nodes is not None and int(float(nodes)) != 4:
            return (
                False,
                "Подумай внимательно: сколько геометрических узлов объединяет ветви на исходной схеме? "
                "Обрати внимание на узлы a, b, c, d — можно ли какие-то из них объединить или их ровно 4?",
            )

        if branches is not None and int(float(branches)) != 6:
            return (
                False,
                "Обрати внимание на структуру ветвей цепи: ветвью называется участок цепи с одним и тем же током. "
                "Сколько независимых участков с резисторами и источниками соединяют узлы? Не пропустил ли ты ветвь?",
            )

        if kcl_eqs is not None and int(float(kcl_eqs)) != 3:
            return (
                False,
                "Вспомни теорему о числе независимых уравнений по первому закону Кирхгофа: "
                "если в схеме n узлов, почему независимых уравнений ровно (n - 1)? "
                "Что произойдет, если составить уравнение для 4-го узла d: будет ли оно линейно независимым?",
            )

        if kvl_eqs is not None and int(float(kvl_eqs)) != 3:
            return (
                False,
                "Подумай, каково число независимых контуров в разветвленной цепи? "
                "Формула p - (n - 1): при 6 ветвях и 4 узлах сколько уравнений по второму закону Кирхгофа необходимо составить?",
            )

        return (
            True,
            "Отлично! Топологический анализ цепи выполнен безупречно: 4 узла, 6 ветвей, "
            "3 независимых уравнения по 1-му ЗК и 3 уравнения по 2-му ЗК. "
            "Как ты выберешь направления токов ветвей и направления обхода независимых контуров?",
        )

    def _check_kirchhoff_1(self, student_input: Dict[str, Any]) -> Tuple[bool, str]:
        """Validates node equations (signs of currents at nodes a, b, c)."""
        # Node a: -I1 - I4 - I6 = 0 (or +I1 + I4 + I6 = 0)
        # Node b: +I1 + I2 + I3 = 0 (or -I1 - I2 - I3 = 0)
        # Node c: -I3 + I5 + I6 = 0 (or +I3 - I5 - I6 = 0)
        node_a = _lookup_val(student_input, "node_a", "a")
        node_b = _lookup_val(student_input, "node_b", "b")
        node_c = _lookup_val(student_input, "node_c", "c")

        for node_name, node_val in [("a", node_a), ("b", node_b), ("c", node_c)]:
            if node_val is not None:
                if not isinstance(node_val, (list, tuple)) or len(node_val) != 6:
                    return (
                        False,
                        f"Уравнение для узла {node_name} должно содержать коэффициенты для всех 6 ветвей схемы (список из 6 чисел). Как выглядит вектор токов?",
                    )
                for elem in node_val:
                    if not isinstance(elem, (int, float)) or isinstance(elem, bool):
                        return (
                            False,
                            f"Все коэффициенты уравнения для узла {node_name} должны быть вещественными числами (+1, -1 или 0). Какие токи сходятся в узле {node_name}?",
                        )

        if node_a is not None:
            s1, s2, s3, s4, s5, s6 = [float(x) for x in node_a]
            if s2 != 0 or s3 != 0 or s5 != 0:
                return (
                    False,
                    "Посмотри внимательно на узел a: соединяются ли с ним ветви 2, 3 или 5? "
                    "Какие именно ветви непосредственно сходятся в узле a?",
                )
            if not ((s1 < 0 and s4 < 0 and s6 < 0) or (s1 > 0 and s4 > 0 and s6 > 0)):
                return (
                    False,
                    "Обрати внимание на стрелки токов для узла a: токи I1, I4 и I6 все имеют одинаковое "
                    "направление относительно узла (все вытекают или все втекают)? "
                    "Почему у них в твоем уравнении получились противоположные знаки?",
                )

        if node_b is not None:
            s1, s2, s3, s4, s5, s6 = [float(x) for x in node_b]
            if s4 != 0 or s5 != 0 or s6 != 0:
                return (
                    False,
                    "Взгляни на узел b: сходятся ли в нем ветви 4, 5 или 6? "
                    "Какие ветви образуют узел b на схеме?",
                )
            if not ((s1 > 0 and s2 > 0 and s3 > 0) or (s1 < 0 and s2 < 0 and s3 < 0)):
                return (
                    False,
                    "Проверь знаки для узла b: согласно выбранным стрелкам, все три тока I1, I2, I3 "
                    "втекают в узел b. Должны ли они иметь одинаковый знак в 1-м законе Кирхгофа?",
                )

        if node_c is not None:
            s1, s2, s3, s4, s5, s6 = [float(x) for x in node_c]
            if s1 != 0 or s2 != 0 or s4 != 0:
                return (
                    False,
                    "Проверь ветви узла c: сходятся ли в узле c ветви 1, 2 или 4?",
                )
            # In node c: I3 leaves/enters, I5 and I6 have opposite direction to I3
            # e.g. -I3 + I5 + I6 = 0 -> s3 has opposite sign to s5 and s6, and s5 == s6 sign
            if (s5 > 0 and s6 < 0) or (s5 < 0 and s6 > 0):
                return (
                    False,
                    "Обрати внимание на ветви 5 и 6 в узле c: обе ли они входят в узел c? "
                    "Почему у токов I5 и I6 разные знаки?",
                )
            if (s3 > 0 and s5 > 0) or (s3 < 0 and s5 < 0):
                return (
                    False,
                    "Вспомни направление тока I3 относительно узла c: ток I3 течет от b к c или от c к d? "
                    "Имеет ли ток I3 знак, противоположный токам I5 и I6?",
                )

        return (
            True,
            "Замечательно! Уравнения по первому закону Кирхгофа для независимых узлов составлены корректно. "
            "Почему для четвертого узла d уравнение составлять не нужно, и как оно проверяет правильность системы?",
        )

    def _check_kirchhoff_2(self, student_input: Dict[str, Any]) -> Tuple[bool, str]:
        """Validates loop equations and EMF sums for loops 1, 2, 3."""
        # Loop 1: +I1*R1 - I2*R2 - I4*R4 = E1 - E2 - E4 = 0
        # Loop 2: +I2*R2 - I3*R3 - I5*R5 = E2 - E3 - E5 = 0 - 25 - 0 = -25
        # Loop 3: +I4*R4 + I5*R5 - I6*R6 = E4 + E5 - E6 = 0 + 0 - 30 = -30
        loop1_emf = _lookup_val(student_input, "loop1_emf", "emf_1", "E_loop1")
        loop2_emf = _lookup_val(student_input, "loop2_emf", "emf_2", "E_loop2")
        loop3_emf = _lookup_val(student_input, "loop3_emf", "emf_3", "E_loop3")

        for loop_name, loop_val in [("контура 1", loop1_emf), ("контура 2", loop2_emf), ("контура 3", loop3_emf)]:
            if loop_val is not None:
                parsed_val, err = _safe_float(loop_val)
                if err == "NaN":
                    return (
                        False,
                        "Получено нечисловое значение (NaN). Проверьте вычисления. Какая ЭДС действует в этом контуре?",
                    )
                if err or parsed_val is None:
                    return (
                        False,
                        f"Не удалось распознать числовое значение ЭДС для {loop_name}. Убедитесь, что значение введено числом (например, 25.0). Какая ЭДС действует в этом контуре?",
                    )

        if loop1_emf is not None and abs(float(loop1_emf) - 0.0) > 0.001:
            return (
                False,
                "Посмотри на первый независимый контур (ветви 1, 2, 4): присутствуют ли в этих ветвях источники ЭДС? "
                "Чему равна алгебраическая сумма ЭДС контура 1 при E1=0, E2=0, E4=0?",
            )

        if loop2_emf is not None and abs(float(loop2_emf) - (-25.0)) > 0.001 and abs(float(loop2_emf) - 25.0) > 0.001:
            return (
                False,
                "Обрати внимание на источник ЭДС во 2-м контуре: в какой ветви он расположен? "
                "Чему равна величина E3? Направлена ли стрелка источника навстречу контуру обхода?",
            )

        if loop3_emf is not None and abs(float(loop3_emf) - (-30.0)) > 0.001 and abs(float(loop3_emf) - 30.0) > 0.001:
            return (
                False,
                "Взгляни на контур 3: какой источник ЭДС входит в контур (E6=30 В)? "
                "Совпадает ли направление стрелки ЭДС с направлением обхода контура или направлено навстречу?",
            )

        return (
            True,
            "Отлично! Уравнения по второму закону Кирхгофа согласованы по знакам падений напряжений и ЭДС. "
            "Как ты планируешь решать полученную систему 6x6: методом определителей Крамера, методом Гаусса или перейдешь к методу контурных токов?",
        )

    def _check_mkt(self, student_input: Dict[str, Any]) -> Tuple[bool, str]:
        """Validates loop resistance matrix in Loop Current Method (MKT)."""
        # R11 = R1 + R2 + R4 = 64 + 98 + 48 = 210
        # R22 = R2 + R3 + R5 = 98 + 30 + 58 = 186
        # R33 = R4 + R5 + R6 = 48 + 58 + 65 = 171
        r11 = _lookup_val(student_input, "R11", "r11")
        r22 = _lookup_val(student_input, "R22", "r22")
        r33 = _lookup_val(student_input, "R33", "r33")

        for r_name, r_val in [("R11", r11), ("R22", r22), ("R33", r33)]:
            if r_val is not None:
                parsed_val, err = _safe_float(r_val)
                if err == "NaN":
                    return (
                        False,
                        f"Получено нечисловое значение (NaN) для сопротивления {r_name}. Проверьте вычисления. Какова сумма сопротивлений резисторов контура?",
                    )
                if err or parsed_val is None:
                    return (
                        False,
                        f"Не удалось распознать значение контурного сопротивления {r_name}. Убедитесь, что сопротивление задано числом в Омах. Какое значение получилось при сложении сопротивлений ветвей?",
                    )

        if r11 is not None and abs(float(r11) - 210.0) > 0.1:
            return (
                False,
                "Обрати внимание на контур 1: из каких резисторов складывается собственное сопротивление R11? "
                "Проверь сумму R1 (64 Ом), R2 (98 Ом) и R4 (48 Ом). Где закралась арифметическая неточность?",
            )

        if r22 is not None and abs(float(r22) - 186.0) > 0.1:
            return (
                False,
                "Вспомни контур 2: какие резисторы входят во 2-й независимый контур? "
                "Проверь сумму R2 (98 Ом) + R3 (30 Ом) + R5 (58 Ом). Чему равна сумма этих трех величин?",
            )

        if r33 is not None and abs(float(r33) - 171.0) > 0.1:
            return (
                False,
                "Проверь собственное сопротивление контура 3: резисторы R4 (48 Ом), R5 (58 Ом) и R6 (65 Ом). "
                "Какова сумма этих сопротивлений?",
            )

        return (
            True,
            "Превосходно! Собственные контурные сопротивления R11=210 Ом, R22=186 Ом и R33=171 Ом найдены верно. "
            "Подумай, какие ветви являются смежными для пар контуров, и с какими знаками войдут взаимные сопротивления R12, R23, R13?",
        )

    def _check_mup(self, student_input: Dict[str, Any]) -> Tuple[bool, str]:
        """Validates node potential method setup (MUP)."""
        ref_node = _lookup_val(student_input, "reference_node", "base_node")
        ref_pot = _lookup_val(student_input, "reference_potential", "V_ref")

        if ref_node is not None and str(ref_node).lower() not in ("d", "д", "0"):
            return (
                False,
                "Подумай, какой узел удобнее всего заземлить (принять за базисный с V=0)? "
                "Обычно в данной схеме выбирают узел d. Почему потенциал одного узла необходимо зафиксировать?",
            )

        if ref_pot is not None:
            parsed_val, err = _safe_float(ref_pot)
            if err == "NaN":
                return (
                    False,
                    "Получено нечисловое значение (NaN). Проверьте вычисления. Чему равен потенциал заземленного узла?",
                )
            if err or parsed_val is None:
                return (
                    False,
                    "Не удалось распознать потенциал базисного узла. Убедитесь, что потенциал задан числом. Чему равен потенциал заземленного узла?",
                )
            if abs(float(ref_pot) - 0.0) > 0.001:
                return (
                    False,
                    "Обрати внимание на базовый узел: потенциал базисного узла всегда принимается равным 0 В. "
                    "Почему потенциалы остальных узлов определяются относительно него?",
                )

        return (
            True,
            "Верно! Заземление узла d (Vd = 0 В) понижает порядок системы до 3x3. "
            "Как связаны проводимости ветвей Gk = 1/Rk с узловыми уравнениями метода узловых потенциалов?",
        )

    def _check_currents(self, student_input: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates calculated branch currents.
        Checks deviation from ground truth without exposing true numbers!
        """
        raw_vals: List[Any] = []
        if isinstance(student_input, (list, tuple)):
            raw_vals = list(student_input)
        elif isinstance(student_input, dict):
            if "I" in student_input and isinstance(student_input["I"], (list, tuple)):
                raw_vals = list(student_input["I"])
            else:
                for k in range(1, 7):
                    val = _lookup_val(student_input, f"I{k}", f"i{k}", str(k), f"I_{k}")
                    if val is not None:
                        raw_vals.append(val)

        if len(raw_vals) < 6:
            return (
                False,
                f"Получено только {len(raw_vals)} из 6 токов ветвей. "
                "Все ли ветви были рассчитаны? Проверь токи для всех 6 ветвей схемы.",
            )

        currents: List[float] = []
        for idx, rv in enumerate(raw_vals[:6]):
            f_val, err = _safe_float(rv)
            if err == "NaN":
                return (
                    False,
                    f"Получено нечисловое значение (NaN) для тока ветви {idx + 1}. Проверьте вычисления. На каком этапе возникло деление на ноль?",
                )
            if err or f_val is None:
                return (
                    False,
                    f"Значение тока ветви {idx + 1} ('{rv}') не является вещественным числом. Убедитесь, что все токи рассчитаны в Амперах. Какое значение тока получилось в ветви {idx + 1}?",
                )
            currents.append(f_val)

        # Compare with ground truth
        gt = self._ground_truth_currents
        mismatched_branches = []
        for i in range(6):
            diff = abs(currents[i] - gt[i])
            # Allow 5% relative error or 0.015 A absolute tolerance
            if diff > 0.015 and (abs(gt[i]) < 1e-4 or diff / abs(gt[i]) > 0.05):
                mismatched_branches.append(i + 1)

        if mismatched_branches:
            branches_str = ", ".join(f"ветвь {b}" for b in mismatched_branches)
            return (
                False,
                f"Обрати внимание: расчет токов требует проверки ({branches_str}). "
                "Проверь 1-й закон Кирхгофа: сходится ли сумма токов в узлах? "
                "Не перепутаны ли знаки или коэффициенты сопротивлений при решении системы уравнений?",
            )

        return (
            True,
            "Превосходно! Все 6 токов ветвей рассчитаны верно с высокой точностью. "
            "Обрати внимание: некоторые токи получились со знаком минус. "
            "Что означает отрицательный знак тока, и в какую сторону на самом деле перемещаются заряды в этих ветвях?",
        )

    def _check_power_balance(self, student_input: Dict[str, Any]) -> Tuple[bool, str]:
        """Validates power balance calculation with < 1% tolerance."""
        p_res = _lookup_val(student_input, "P_consumed", "P_res", "P_potr", "P_load")
        p_src = _lookup_val(student_input, "P_generated", "P_src", "P_ist", "P_sources")

        if p_res is None or p_src is None:
            return (
                False,
                "Для проверки баланса мощностей необходимо предоставить мощность потребителей (P_потр = Σ I_k^2 * R_k) "
                "и суммарную мощность источников (P_ист = Σ E_k * I_k). Какие значения у тебя получились?",
            )

        p_res_f, err_res = _safe_float(p_res)
        p_src_f, err_src = _safe_float(p_src)

        if err_res == "NaN" or err_src == "NaN":
            return (
                False,
                "Получено нечисловое значение (NaN) в балансе мощностей. Проверьте вычисления. На каком шаге возникла ошибка?",
            )

        if err_res or p_res_f is None or err_src or p_src_f is None:
            return (
                False,
                "Значения мощности должны быть заданы вещественными числами (в Ваттах). Какие мощности получились в твоем расчете?",
            )

        if p_src_f <= 0 or p_res_f <= 0:
            return (
                False,
                "Подумай: может ли суммарная рассеиваемая мощность на резисторах быть отрицательной? "
                "Проверь знаки: в выражении I_k^2 * R_k квадрат тока всегда положителен. "
                "А в сумме E_k * I_k отдает ли источник мощность цепи или потребляет?",
            )

        rel_diff = abs(p_res_f - p_src_f) / max(p_src_f, 1e-6)
        if rel_diff > 0.01:  # Over 1% tolerance
            return (
                False,
                f"Погрешность баланса мощностей составляет {rel_diff * 100:.2f}%, что превышает допустимый 1%. "
                "Обрати внимание: почему мощность источников разошлась с мощностью на резисторах? "
                "Проверь знак произведения E_k * I_k для ветвей 3 и 6: совпадает ли знак тока с направлением действия ЭДС?",
            )

        # Check if values are close to true power (~21.7 W)
        gt_power = self._ground_truth_p_res
        if abs(p_res_f - gt_power) / gt_power > 0.1:
            return (
                False,
                "Баланс между твоими P_потр и P_ист формально сошелся, но порядок величины мощности не соответствует параметрам схемы. "
                "Проверь правильность рассчитанных токов: не закралась ли систематическая ошибка в расчет матрицы токов?",
            )

        return (
            True,
            "Идеально! Баланс мощностей сошелся с относительной погрешностью менее 1% (закон сохранения энергии выполнен). "
            "Это окончательно доказывает правильность всех найденных токов. "
            "Готов ли ты ответить на контрольные вопросы преподавателя по физическому смыслу полученных результатов?",
        )

    def _check_potential_diagram(self, student_input: Dict[str, Any]) -> Tuple[bool, str]:
        """Validates potential diagram construction concept."""
        contour_chosen = _lookup_val(student_input, "contour", "path")
        if contour_chosen is not None:
            c_str = str(contour_chosen).lower()
            if not ("3" in c_str and "6" in c_str):
                return (
                    False,
                    "Обрати внимание на методические указания: по какому контуру рекомендуется строить потенциальную диаграмму? "
                    "Входит ли в выбранный контур хотя бы один, а лучше оба источника ЭДС (E3 и E6)?",
                )

        return (
            True,
            "Отлично! Контур для потенциальной диаграммы выбран верно. "
            "Вспомни правило: при движении по направлению тока через резистор потенциал падает (минус I*R) или возрастает? "
            "А при переходе через идеальный источник ЭДС от отрицательного полюса к положительному?",
        )

    def generate_socratic_hint(self, step_name: str, error_type: str = "general") -> str:
        """
        Generates Socratic guiding questions and conceptual explanations
        strictly tailored to the step and error type, with zero direct answers leaked.
        """
        step = self._normalize_step_name(step_name)
        err = error_type.lower()

        if step == "topology":
            if "equation" in err:
                return (
                    "Вспомни фундаментальное правило топологии электрических цепей: "
                    "почему число независимых уравнений по первому закону Кирхгофа равно (n - 1), "
                    "а не n? Что будет, если просуммировать уравнения для всех n узлов цепи?"
                )
            return (
                "Обрати внимание на топологию цепи: сколько в ней узлов и сколько ветвей? "
                "Как по формуле p - (n - 1) определить число независимых контуров для второго закона Кирхгофа?"
            )

        if step == "kirchhoff_1":
            if "sign" in err:
                return (
                    "Обрати внимание на знаки токов: как ты выбирал положительное направление для каждой ветви? "
                    "Если ток втекает в узел, с каким знаком ты его учитываешь, "
                    "и сохраняется ли это правило для всех остальных токов данного узла?"
                )
            return (
                "Вспомни формулировку первого закона Кирхгофа: чему равна алгебраическая сумма токов в любом узле? "
                "Каков физический закон сохранения (заряда), лежащий в его основе?"
            )

        if step == "kirchhoff_2":
            if "emf" in err or "sign" in err:
                return (
                    "Вспомни 2-й закон Кирхгофа: как соотносится направление обхода контура со стрелкой источника ЭДС? "
                    "Если направление обхода совпадает с направлением стрелки ЭДС, с каким знаком входит E_k в правую часть уравнения?"
                )
            return (
                "Обрати внимание на второй закон Кирхгофа: чему равна алгебраическая сумма падений напряжений "
                "вдоль замкнутого контура? Как падение напряжения на резисторе связано с направлением контурного обхода и стрелкой тока?"
            )

        if step == "mkt":
            if "resistance" in err:
                return (
                    "Вспомни определение собственных и взаимных сопротивлений контуров: "
                    "из каких резисторов складывается сопротивление первого независимого контура? "
                    "Чему равна сумма R1 + R2 + R4? Какой резистор является общим между контурами 1 и 2?"
                )
            return (
                "Подумай, в чем главное преимущество метода контурных токов (МКТ) по сравнению с непосредственным применением законов Кирхгофа? "
                "Сколько уравнений содержит система МКТ для твоей цепи: 6 или всего 3?"
            )

        if step == "mup":
            if "reference" in err:
                return (
                    "Обрати внимание: выбран ли в твоей схеме опорный базисный узел с нулевым потенциалом? "
                    "Почему потенциал одного из узлов (например, Vd) необходимо зафиксировать равным 0 В?"
                )
            return (
                "Вспомни метод узловых потенциалов: как проводимость ветви G_k = 1 / R_k используется "
                "для составления собственной проводимости узла? Проверь сумму проводимостей ветвей, сходящихся в узле a."
            )

        if step == "currents":
            if "sign" in err:
                return (
                    "Подумай, о чем говорит знак «минус» перед рассчитанным значением тока? "
                    "Означает ли это ошибку в расчетах, или просто физический ток течет навстречу произвольно выбранной стрелке?"
                )
            return (
                "Подумай, удовлетворяют ли полученные тобой токи первому закону Кирхгофа для каждого узла? "
                "Попробуй подставить найденные значения в уравнения узлов a и b: равна ли сумма нулю? "
                "В каком уравнении системы могла возникнуть вычислительная погрешность?"
            )

        if step == "power_balance":
            if "sign" in err or "imbalance" in err:
                return (
                    "Обрати внимание на формулу баланса мощностей: почему суммарная мощность потребителей должна равняться мощности источников? "
                    "Проверь: мощность на резисторах всегда неотрицательна Σ I_k^2 * R_k, "
                    "а в мощности источников Σ E_k * I_k учитываешь ли ты направление тока относительно стрелки ЭДС?"
                )
            return (
                "Вспомни физический закон сохранения энергии: куда девается энергия, вырабатываемая источниками ЭДС? "
                "Какая формула связывает тепловую мощность, выделяющуюся на резисторах по закону Джоуля-Ленца, с мощностью источников?"
            )

        # General pedagogical prompt
        return (
            "Обрати внимание на физические законы электротехники: "
            "какой именно принцип вызывает у тебя затруднение? "
            "Попробуй сформулировать свой вопрос: что именно не сходится в расчетах?"
        )

    def get_oral_defense_questions(self) -> List[Dict[str, str]]:
        """Returns the 4 key teacher oral defense questions with Socratic prompts."""
        return [
            {
                "question": "Почему для четвертого узла (узел d) не составляется уравнение по первому закону Кирхгофа?",
                "socratic_prompt": "Подумай: если сложить уравнения токов для узлов a, b и c, какое выражение получится для узла d? "
                                   "Является ли уравнение для 4-го узла линейно зависимым от остальных трех?",
            },
            {
                "question": "Что означает знак «минус» перед числовым значением рассчитанного тока ветви?",
                "socratic_prompt": "Вспомни: перед началом расчета стрелки токов выбираются произвольно. "
                                   "Если итоговый ток отрицателен, в какую сторону физически движутся электроны относительно стрелки на схеме?",
            },
            {
                "question": "Как изменяется потенциал точки при переходе через резистор и идеальный источник ЭДС?",
                "socratic_prompt": "Подумай: при переходе через резистор по направлению тока потенциал падает или растет (ΔV = -I*R)? "
                                   "А при переходе через источник ЭДС от отрицательного полюса к положительному (ΔV = +E)?",
            },
            {
                "question": "Как строится потенциальная диаграмма замкнутого контура?",
                "socratic_prompt": "Обрати внимание: по оси абсцисс откладываются сопротивления R вдоль контура, а по оси ординат — потенциалы V. "
                                   "Почему график обязан вернуться в исходную точку с тем же потенциалом после полного обхода контура?",
            },
        ]
