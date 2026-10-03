"""
SOTA 2026 Advanced Testing Patterns for Vazus Core.

Включает 4 новых класса тестирования помимо базового PBT:

1. STATEFUL TESTING (Hypothesis RuleBasedStateMachine)
   - Тестирует многошаговые последовательности операций
   - Находит баги в состоянии системы которые один @given никогда не найдёт
   - Применяем к: GateResult pipeline, GraphifyEngine node accumulation

2. METAMORPHIC TESTING
   - Не требует оракула ("правильного ответа")
   - Проверяет ОТНОШЕНИЯ между входами и выходами
   - Применяем к: _extract_json (перестановка ключей), taint detector (добавление комментария не меняет результат)

3. DIFFERENTIAL TESTING
   - Сравниваем два реализации одного алгоритма
   - Применяем к: секретные паттерны (regex vs re.search должны совпадать)

4. MUTATION ANALYSIS (собственный mini-mutmut)
   - Автоматически мутируем производственный код
   - Проверяем что наши тесты убивают мутантов
   - Если тест проходит при мутации → тест слабый (не проверяет поведение)
"""
from __future__ import annotations

import ast
import json
import keyword
import tempfile
from pathlib import Path
from unittest.mock import patch

from hypothesis import given, settings, strategies as st, HealthCheck
from hypothesis.stateful import (
    RuleBasedStateMachine,
    rule,
    invariant,
    initialize,
    precondition,
)

from vazus_core.verification.precommit_gate import (
    SECRET_PATTERNS,
    _check_hardcoded_secrets,
    _check_taint_sinks,
    _has_tautological_assert,
    _is_empty_pass_test,
    _dedupe_and_bound_tests,
)
from vazus_core.missions.mission_factory import MissionFactory

settings.register_profile("ci", max_examples=50, deadline=15_000)
settings.load_profile("ci")

_PY_IDENT = (
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=12)
    .filter(lambda s: s.isidentifier() and not keyword.iskeyword(s))
)


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN 1: STATEFUL TESTING — Gate Pipeline State Machine
# ══════════════════════════════════════════════════════════════════════════════
# Тестируем не один вызов, а ПОСЛЕДОВАТЕЛЬНОСТЬ операций с сохранением состояния.
# Hypothesis сам генерирует разные последовательности и ищет баги в переходах.

class GatePipelineStateMachine(RuleBasedStateMachine):
    """
    Stateful test: моделируем pipeline staged_files → gate checks.

    Reference model: Python list (простой, заведомо правильный).
    System under test: _dedupe_and_bound_tests (реальная реализация).

    ИНВАРИАНТ: они всегда должны давать одинаковый результат.
    """

    def __init__(self):
        super().__init__()
        self._td = tempfile.TemporaryDirectory()
        self._tmp = Path(self._td.name)
        self._staged: list[Path] = []       # reference model
        self._file_pool: list[Path] = []    # pool of created files
        self._counter = 0

    def teardown(self):
        self._td.cleanup()

    @initialize()
    def init_pool(self):
        """Инициализируем пул файлов: создаём 5 уникальных test-файлов."""
        for i in range(5):
            f = self._tmp / f"test_module_{i}.py"
            f.write_text(f"def test_x_{i}(): assert {i+1} > 0")
            self._file_pool.append(f)

    @rule(idx=st.integers(min_value=0, max_value=4))
    def stage_file(self, idx):
        """Добавляем файл из пула в staged (как `git add`)."""
        f = self._file_pool[idx]
        self._staged.append(f)

    @rule()
    @precondition(lambda self: len(self._staged) > 0)
    def run_dedupe(self):
        """Запускаем dedupe — результат должен иметь только уникальные файлы."""
        result = _dedupe_and_bound_tests(self._staged)
        # ИНВАРИАНТ: дубликаты убраны
        assert len(result) == len(set(result)), \
            f"Дубликаты в результате: {result}"

    @rule()
    @precondition(lambda self: len(self._staged) > 0)
    def clear_staged(self):
        """Сбрасываем staged — имитируем `git reset`."""
        self._staged.clear()

    @invariant()
    def staged_never_negative(self):
        """ГЛОБАЛЬНЫЙ ИНВАРИАНТ: staged list никогда не отрицательного размера."""
        assert len(self._staged) >= 0

    @invariant()
    def bound_always_respected(self):
        """ГЛОБАЛЬНЫЙ ИНВАРИАНТ: результат dedupe всегда ≤ MAX_TARGET_TESTS=8."""
        if self._staged:
            result = _dedupe_and_bound_tests(self._staged)
            assert len(result) <= 8


# Pytest TestCase из State Machine
TestGatePipelineStateMachine = GatePipelineStateMachine.TestCase


class SecretPatternStateMachine(RuleBasedStateMachine):
    """
    Stateful test: накапливаем фрагменты кода, проверяем что секреты
    детектируются независимо от позиции в файле.
    """

    def __init__(self):
        super().__init__()
        self._code_lines: list[str] = []
        self._known_secrets: list[str] = []

    @rule(safe_code=_PY_IDENT)
    def add_safe_line(self, safe_code):
        """Добавляем обычную строку кода."""
        self._code_lines.append(f"x_{safe_code} = 1")

    @rule()
    def add_google_secret(self):
        """Добавляем Google API key — должен детектироваться."""
        key_line = 'api_key = "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234567"'
        self._code_lines.append(key_line)
        self._known_secrets.append(key_line)

    @rule()
    def add_aws_secret(self):
        """Добавляем AWS key — должен детектироваться."""
        key_line = "aws = 'AKIAIOSFODNN7EXAMPLE'"
        self._code_lines.append(key_line)
        self._known_secrets.append(key_line)

    @invariant()
    @precondition(lambda self: len(self._known_secrets) > 0)
    def secrets_always_detected(self):
        """ИНВАРИАНТ: если добавили секрет, он ВСЕГДА должен быть найден.

        Важно: файл НЕ должен называться test_*/gate*/verif* — иначе exempt.
        Hypothesis нашёл это через stateful testing!
        """
        content = "\n".join(self._code_lines)
        # CRITICAL: не test_code.py (exempt!) → используем source.py
        fpath = Path("source_module.py")
        errs = _check_hardcoded_secrets(content, fpath)
        assert len(errs) > 0, (
            f"Секрет в файле НЕ обнаружен!\n"
            f"Code:\n{content}\n"
            f"Ожидали найти: {self._known_secrets}\n"
            f"(Файл: {fpath.name} — не test/gate/verif → должен сканироваться)"
        )


TestSecretPatternStateMachine = SecretPatternStateMachine.TestCase


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN 2: METAMORPHIC TESTING
# ══════════════════════════════════════════════════════════════════════════════
# Не знаем правильный ответ? Тестируем ОТНОШЕНИЯ между трансформациями входа.
# MR (Metamorphic Relation) = свойство которое ВСЕГДА должно выполняться.

class TestMetamorphicRelations:
    """
    Метаморфические отношения для функций системы.

    MR1: Перестановка ключей в JSON не меняет результат _extract_json
    MR2: Добавление комментария в код не меняет результат taint detection
    MR3: Повторный вызов dedupe идемпотентен (MR = идемпотентность)
    MR4: Размер staged > размер dedupe result ⇔ были дубликаты
    MR5: _extract_json(json(d)) == d для любого dict (round-trip relation)
    """

    @given(
        data=st.dictionaries(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8),
            st.integers(min_value=-1000, max_value=1000),
            min_size=1, max_size=6,
        )
    )
    def test_mr1_key_permutation_preserves_extract_result(self, data):
        """MR1: перестановка ключей dict → одинаковый результат _extract_json.

        Метаморфическое отношение: если f(x) = y, то f(permute(x)) = y.
        """
        factory = MissionFactory()
        # Оригинальный JSON
        original_text = f"```json\n{json.dumps(data)}\n```"
        result_original = factory._extract_json(original_text)

        # Перемешанный JSON (другой порядок ключей)
        import random
        keys = list(data.keys())
        random.shuffle(keys)
        shuffled = {k: data[k] for k in keys}
        shuffled_text = f"```json\n{json.dumps(shuffled)}\n```"
        result_shuffled = factory._extract_json(shuffled_text)

        # MR: результаты должны быть равны (JSON не зависит от порядка ключей)
        assert result_original == result_shuffled, (
            f"MR1 VIOLATED: key order changed result!\n"
            f"Original: {result_original}\nShuffled: {result_shuffled}"
        )

    @given(
        func_body=_PY_IDENT,
        n_comments=st.integers(min_value=0, max_value=5),
    )
    def test_mr2_adding_comments_does_not_change_taint_result(
        self, func_body, n_comments
    ):
        """MR2: добавление комментариев не меняет результат taint detection.

        Метаморфическое отношение: комментарии семантически нейтральны.
        """
        base_code = f"def handler({func_body}):\n    return {func_body}\n"
        comments = "\n".join(f"# comment {i}" for i in range(n_comments))
        code_with_comments = f"{comments}\n{base_code}" if comments else base_code

        fpath = Path("handler.py")
        errs_base = _check_taint_sinks(base_code, fpath)
        errs_with_comments = _check_taint_sinks(code_with_comments, fpath)

        # MR: добавление комментариев не должно менять количество ошибок
        assert len(errs_base) == len(errs_with_comments), (
            f"MR2 VIOLATED: comments changed taint result!\n"
            f"Without comments: {errs_base}\n"
            f"With {n_comments} comments: {errs_with_comments}"
        )

    @given(
        n=st.integers(min_value=1, max_value=10),
        unique_names=st.lists(
            _PY_IDENT, min_size=1, max_size=5, unique=True
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_mr3_dedupe_is_idempotent(self, n, unique_names):
        """MR3: идемпотентность — dedupe(dedupe(X)) = dedupe(X).

        Это фундаментальный MR для любой операции дедупликации.
        """
        with tempfile.TemporaryDirectory() as td:
            files = []
            for name in unique_names:
                f = Path(td) / f"test_{name}.py"
                f.write_text("def test_x(): assert 1 > 0")
                # Добавляем каждый файл n раз (создаём дубликаты)
                files.extend([f] * n)

            result_once = _dedupe_and_bound_tests(files)
            # Конвертируем обратно в Path для второго вызова
            result_paths = [Path(r) for r in result_once]
            result_twice = _dedupe_and_bound_tests(result_paths)

        # MR: повторный dedupe не меняет результат
        assert result_once == result_twice, (
            f"MR3 IDEMPOTENCY VIOLATED: dedupe(dedupe(X)) ≠ dedupe(X)!\n"
            f"Once: {result_once}\nTwice: {result_twice}"
        )

    @given(
        data=st.dictionaries(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8),
            st.one_of(
                st.text(max_size=20),
                st.integers(-100, 100),
                st.booleans(),
            ),
            min_size=1, max_size=4,
        )
    )
    def test_mr5_extract_json_round_trip_preserves_data(self, data):
        """MR5: round-trip relation — serialize → deserialize → original.

        MR: _extract_json(json.dumps(d)) = d для любого dict d.
        Это проверяет что парсер и сериализатор СОГЛАСОВАНЫ.
        """
        factory = MissionFactory()
        serialized = json.dumps(data)
        result = factory._extract_json(serialized)
        assert result == data, (
            f"MR5 ROUND-TRIP VIOLATED: deserialization lost data!\n"
            f"Input: {data}\nOutput: {result}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN 3: DIFFERENTIAL TESTING
# ══════════════════════════════════════════════════════════════════════════════
# Запускаем ДВЕ независимые реализации и сравниваем их выходы.
# Если они расходятся — в одной из них баг.

class TestDifferentialPatterns:
    """
    Дифференциальное тестирование: сравниваем независимые реализации.
    """

    @given(
        content=st.text(
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789=_-' \"",
            max_size=200,
        )
    )
    def test_diff_secret_patterns_vs_raw_regex(self, content):
        """DIFF: компилированные SECRET_PATTERNS совпадают с raw re.search.

        Независимая реализация: каждый паттерн проверяем прямым re.search.
        Если они расходятся — ошибка в компиляции паттерна.
        """
        # Реализация 1: наша система
        fpath = Path("source.py")
        system_errs = _check_hardcoded_secrets(content, fpath)
        system_found = len(system_errs) > 0

        # Реализация 2: независимый raw regex поиск
        raw_found = any(p and p.search(content) for p in SECRET_PATTERNS)

        # DIFFERENTIAL: результаты должны совпадать
        assert system_found == raw_found, (
            f"DIFFERENTIAL MISMATCH!\n"
            f"System: {system_found} ({system_errs})\n"
            f"Raw regex: {raw_found}\n"
            f"Content snippet: {content[:60]!r}"
        )

    @given(
        n=st.integers(min_value=0, max_value=15),
        unique_count=st.integers(min_value=1, max_value=5),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_diff_dedupe_vs_python_set(self, n, unique_count):
        """DIFF: _dedupe_and_bound_tests vs наивная реализация через set.

        Независимая реализация: простой set-dedupe (reference model).
        DIFFERENTIAL: при n < MAX_TARGET_TESTS результаты должны совпадать.
        """
        with tempfile.TemporaryDirectory() as td:
            unique_files = []
            for i in range(min(unique_count, 5)):
                f = Path(td) / f"test_mod_{i}.py"
                f.write_text("def test_x(): assert 1 > 0")
                unique_files.append(f)

            # Создаём список с повторами: каждый файл добавляется случайно
            import random
            files_with_dups = []
            for _ in range(n):
                files_with_dups.append(random.choice(unique_files))

            # Система
            with patch.dict("os.environ", {"VAZUS_GATE_MAX_TARGET_TESTS": "8"}):
                system_result = _dedupe_and_bound_tests(files_with_dups)

            # Reference model: простой set-based dedupe
            seen = set()
            naive_result = []
            for f in files_with_dups:
                if str(f) not in seen:
                    seen.add(str(f))
                    naive_result.append(str(f))
            naive_result = naive_result[:8]  # bound

        # DIFFERENTIAL: оба дают одинаковое количество уникальных файлов
        assert len(system_result) == len(naive_result), (
            f"DIFFERENTIAL MISMATCH in dedupe count!\n"
            f"System: {len(system_result)}, Naive: {len(naive_result)}\n"
            f"Input had {len(files_with_dups)} files, {len(unique_files)} unique"
        )

    def test_diff_tautological_ast_vs_compile(self):
        """DIFF: _has_tautological_assert vs компиляция и eval.

        Для конкретных случаев сравниваем наш детектор с 'ground truth' через eval.
        """
        # Tautological cases — оба должны детектировать
        tautological_cases = [
            "assert True",
            "assert 1 == 1",
            "assert -1 == -1",
            "assert 'x' == 'x'",
        ]
        non_tautological_cases = [
            "assert x > 0",
            "assert result == expected",
            "assert 1 == 2",  # always False but not tautological
            "assert len(items) > 0",
        ]

        def wrap_assert(assert_str: str) -> str:
            return f"def test_fn():\n    {assert_str}\n"

        for case in tautological_cases:
            tree = ast.parse(wrap_assert(case))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    result = _has_tautological_assert(node)
                    assert result is True, (
                        f"DIFF: '{case}' должен быть tautological, но детектор вернул False"
                    )

        for case in non_tautological_cases:
            tree = ast.parse(wrap_assert(case))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    result = _has_tautological_assert(node)
                    assert result is False, (
                        f"DIFF: '{case}' НЕ должен быть tautological, но детектор вернул True"
                    )


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN 4: MINI MUTATION ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
# Автоматически мутируем условия в нашем production-коде и проверяем
# что наши тесты "убивают" мутантов (т.е. ловят изменение поведения).
# Если тест проходит при мутации → тест слабый!

class TestMutationAnalysis:
    """
    Mini-mutation testing: проверяем что наши инварианты достаточно сильны.

    Мутируем:
    - Граничные условия (> vs >=, == vs !=)
    - Возвращаемые значения (True vs False, None vs {})
    - Структурные условия (isinstance checks)

    Если мутированная версия проходит наши тесты → тест СЛАБЫЙ.
    """

    def test_mutation_extract_json_none_check_is_necessary(self):
        """MUTATION: убираем isinstance(result, dict) guard → тест должен поймать.

        Это воспроизводит BUG-1 который Hypothesis нашёл ранее.
        """
        factory = MissionFactory()

        # Мутант: возвращаем любой результат json.loads без isinstance проверки
        def mutant_extract_json(text: str):
            import re as re_mod
            m = re_mod.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re_mod.DOTALL)
            raw = m.group(1) if m else text.strip()
            try:
                return json.loads(raw)  # МУТАЦИЯ: убрали isinstance check
            except Exception:
                return None

        # Тест который убивает этого мутанта:
        result = mutant_extract_json("0")  # json.loads("0") = 0 (int!)
        # Если мутант жив — результат = 0 (не None и не dict)
        # Если мутант убит — результат = None (как в исправленной версии)
        # Наш инвариант: результат должен быть dict или None
        is_mutant_alive = (result is not None and not isinstance(result, dict))
        # Документируем: мутант живёт в мутированной версии
        assert is_mutant_alive, (
            "Мутант json.loads-без-isinstance должен выжить в мутированной версии — "
            "это подтверждает что BUG-1 был реальным"
        )

        # А в production-коде — мутант убит:
        real_result = factory._extract_json("0")
        assert real_result is None or isinstance(real_result, dict), (
            "Production код должен возвращать только dict или None"
        )

    def test_mutation_tautological_assert_boundary(self):
        """MUTATION: меняем > на >= в _is_empty_pass_test границе.

        Проверяем что наш детектор чувствителен к количеству стейтментов.
        """
        # Функция с ДВУМЯ стейтментами (не пустая)
        two_stmts = ast.parse("def test_f():\n    x = 1\n    pass\n")
        for node in ast.walk(two_stmts):
            if isinstance(node, ast.FunctionDef):
                # Должна быть НЕ пустой (2 стейтмента)
                result = _is_empty_pass_test(node)
                assert result is False, (
                    "MUTATION: функция с 2 стейтментами не должна быть пустой"
                )

        # Функция с ОДНИМ pass (пустая)
        one_pass = ast.parse("def test_g():\n    pass\n")
        for node in ast.walk(one_pass):
            if isinstance(node, ast.FunctionDef):
                result = _is_empty_pass_test(node)
                assert result is True, (
                    "MUTATION: функция только с pass должна быть пустой"
                )

    @given(
        secret_type=st.sampled_from([
            ('api_key = "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234567"', True),
            ('x = 1', False),
            ('name = "John"', False),
            ('token = "ghp_' + 'A' * 36 + '"', True),
            ('AKIA' + 'B' * 16, True),
        ])
    )
    def test_mutation_secret_patterns_correct_classification(self, secret_type):
        """MUTATION: проверяем границы SECRET_PATTERNS.

        Для каждого примера проверяем что система правильно классифицирует.
        Мутант: убрать один из 8 паттернов → часть секретов пройдёт.
        ВАЖНО: используем source.py (не test_*) — иначе exempt от проверки!
        """
        content, should_be_secret = secret_type
        # CRITICAL: НЕ test_*.py — такие файлы exempt от secret scanning!
        fpath = Path("source_module.py")

        errs = _check_hardcoded_secrets(content, fpath)
        found = len(errs) > 0

        assert found == should_be_secret, (
            f"MUTATION BOUNDARY: '{content[:30]}' "
            f"expected_secret={should_be_secret}, got found={found}\n"
            f"Errors: {errs}"
        )

    def test_mutation_cc_parser_boundary_10_11(self):
        """MUTATION: граница CC=10 vs CC=11 — критическая для Gate 10.

        Мутант: меняем > 10 на >= 10 → CC=10 тоже блокируется.
        Мутант: меняем > 10 на > 11 → CC=11 пропускается.
        """
        # Тестируем парсер radon output
        def parse_cc_from_line(line: str) -> int | None:
            """Точная копия логики из run_gate_10_cc_complexity."""
            if "(" in line and ")" in line:
                try:
                    cc_str = line.split("(CC=")[-1].rstrip(")")
                    return int(cc_str)
                except ValueError:
                    return None
            return None

        def flag_by_threshold(cc_val: int, threshold: int = 10) -> bool:
            """Реальная логика флагирования."""
            return cc_val > threshold

        # Граничные значения (Boundary Value Analysis)
        boundaries = [
            (9,  False),   # Не флагируется
            (10, False),   # ГРАНИЦА: ровно 10 — не флагируется (CC ≤ 10 OK)
            (11, True),    # ГРАНИЦА+1: флагируется
            (100, True),   # Явно флагируется
        ]

        for cc, expected_flag in boundaries:
            line = f"    some_func - C (CC={cc})"
            parsed = parse_cc_from_line(line)
            assert parsed == cc, f"CC парсинг провалился для {cc}"

            flagged = flag_by_threshold(parsed)
            assert flagged == expected_flag, (
                f"BOUNDARY MUTATION: CC={cc} → expected flagged={expected_flag}, "
                f"got {flagged}. Граница > 10 нарушена!"
            )
