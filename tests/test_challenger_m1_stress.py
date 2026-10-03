"""
Adversarial Stress Testing & Speedup Verification Suite for Milestone 1 Iteration 3
Author: Challenger 1 (Adversarial Verifier)
"""

import ast
import concurrent.futures
import math
import os
import sys
import time

sys.path.insert(0, r"C:\vazus")

import vazus_native_ast
from vazus_core.verification.ast_pruner import ASTPruner, DocstringAndBodyPruner
import vazus_core.ast_pruner as ast_pruner_module

def run_pathological_input_tests():
    print("=" * 70)
    print("STAGE 1: PATHOLOGICAL INPUTS STRESS TEST")
    print("=" * 70)

    # 1.1 Deeply nested classes (15 levels)
    print("\n[1.1] Deeply Nested Classes (15 Levels):")
    nested_lines = []
    for lvl in range(15):
        indent = "    " * lvl
        nested_lines.append(f"{indent}class NestedLevel_{lvl}:")
        nested_lines.append(f'{indent}    """Docstring for level {lvl}."""')
        nested_lines.append(f"{indent}    level_attr_{lvl} = {lvl}")
    
    deepest_indent = "    " * 15
    nested_lines.append(f"{deepest_indent}def deepest_method(self, x: int, y: int = 100) -> int:")
    nested_lines.append(f'{deepest_indent}    """Deepest method in 15 levels."""')
    nested_lines.append(f"{deepest_indent}    intermediate = x * 2 + y")
    nested_lines.append(f"{deepest_indent}    return intermediate")

    nested_class_code = "\n".join(nested_lines) + "\n"
    pruned, stats = vazus_native_ast.prune_code_string(nested_class_code, "summary")
    
    assert stats["is_valid"] is True, f"15-level nested class failed validity: {stats}"
    assert "class NestedLevel_0:" in pruned
    assert "class NestedLevel_14:" in pruned
    assert "def deepest_method(self, x: int, y: int=100) -> int:" in pruned
    assert "return intermediate" in pruned
    assert "intermediate = x * 2 + y" not in pruned
    
    parsed = ast.parse(pruned)
    assert parsed is not None, "ast.parse failed on pruned 15-level class"
    print(f"  -> SUCCESS: 15-level nested class parsed cleanly by ast.parse. Pruned bytes: {len(pruned)} (orig: {len(nested_class_code)})")

    # 1.2 Multi-level Closures (6 levels of nested defs)
    print("\n[1.2] Multi-Level Closures (6 Nested Function Levels):")
    closure_lines = [
        "def outer_func(a: int) -> int:",
        '    """Outer docstring."""',
        "    def inner_1(b: int) -> int:",
        "        def inner_2(c: int) -> int:",
        "            def inner_3(d: int) -> int:",
        "                def inner_4(e: int) -> int:",
        "                    def inner_5(f: int) -> int:",
        "                        return 999",
        "                    return 888",
        "                return 777",
        "            return 666",
        "        return 555",
        "    outer_calc = a + 1",
        "    return a * 42",
    ]
    closure_code = "\n".join(closure_lines) + "\n"
    pruned_closure, closure_stats = vazus_native_ast.prune_code_string(closure_code, "summary")
    
    assert closure_stats["is_valid"] is True, f"Closure code failed validity: {closure_stats}"
    assert "return a * 42" in pruned_closure, f"Outer return missing! Got: {pruned_closure}"
    # Verify inner closure returns were not leaked or stolen as outer return
    assert "return 999" not in pruned_closure, "Inner return 999 leaked into outer function body"
    assert "return 888" not in pruned_closure, "Inner return 888 leaked into outer function body"
    parsed_closure = ast.parse(pruned_closure)
    assert parsed_closure is not None, "ast.parse failed on pruned closure"
    print(f"  -> SUCCESS: Multi-level closure pruned without return theft. Valid AST output.")

    # 1.3 Indentation Variations: 2-space vs 4-space vs mixed
    print("\n[1.3] Indentation Variations (2-Space, 4-Space, Mixed):")
    two_space_module = (
        "class TwoSpaceA:\n"
        "  def method_one(self, x: int):\n"
        '    """2-space doc."""\n'
        "    y = x + 10\n"
        "    return y\n"
        "  def method_two(self):\n"
        "    return 'two'\n"
        "\n"
        "class FourSpaceB:\n"
        "    def method_three(self, z: str = 'default'):\n"
        '        """4-space doc."""\n'
        "        temp = z.upper()\n"
        "        return temp\n"
        "\n"
        "def two_space_func(p: float):\n"
        "  return p * 3.14\n"
    )
    pruned_indent, indent_stats = vazus_native_ast.prune_code_string(two_space_module, "summary")
    assert indent_stats["is_valid"] is True, f"Indent test failed validity: {indent_stats}"
    assert "class TwoSpaceA:" in pruned_indent
    assert "def method_one" in pruned_indent
    assert "return y" in pruned_indent
    assert "class FourSpaceB:" in pruned_indent
    assert "def method_three" in pruned_indent
    assert "return temp" in pruned_indent
    assert "def two_space_func" in pruned_indent
    assert "return p * 3.14" in pruned_indent
    parsed_indent = ast.parse(pruned_indent)
    assert parsed_indent is not None, "ast.parse failed on mixed 2-space/4-space module"
    print(f"  -> SUCCESS: 2-space, 4-space, and mixed indentation handled and parses valid AST.")

    print("\nSTAGE 1 PASSED: All pathological input tests verified.")

def run_unicode_cyrillic_stress_tests():
    print("\n" + "=" * 70)
    print("STAGE 2: NON-ASCII, UNICODE & CYRILLIC STRESS TEST")
    print("=" * 70)

    test_cases = [
        (
            "Cyrillic Class, Methods, Comments & Docstrings",
            (
                "# Заголовочный комментарий на русском языке\n"
                "class ТестовыйКласс: # комментарий к классу\n"
                '    """Документация класса с описанием инвариантов."""\n'
                "    \n"
                "    def вычислить_сумму(self, первое_число: int, второе_число: int = 100) -> int: # коммент сигнатуры\n"
                '        """Вычисляет сумму двух аргументов.\n'
                '        :requires: первое_число > 0\n'
                '        :ensures: result > первое_число\n'
                '        Подробное описание работы алгоритма.\n'
                '        """\n'
                "        промежуточный_итог = первое_число + второе_число\n"
                "        return промежуточный_итог\n"
                "    \n"
                "    def _приватный_метод(self):\n"
                "        return -1\n"
                "    \n"
                "    def __специальный_метод__(self):\n"
                "        return 'dunder'\n"
            ),
            lambda p: (
                "class ТестовыйКласс:" in p
                and "def вычислить_сумму(self, первое_число: int, второе_число: int=100) -> int:" in p
                and "return промежуточный_итог" in p
                and "промежуточный_итог = первое_число + второе_число" not in p
                and "_приватный_метод" not in p
                and "__специальный_метод__" in p
                and ":requires: первое_число > 0" in p
            )
        ),
        (
            "Multi-language Unicode (CJK, Arabic, Greek, German)",
            (
                "# 混合测试: 中文, 日本語, العربية, Ελληνικά, Deutsch\n"
                "class 数据处理器:\n"
                '    """处理数据流."""\n'
                "    def 処理する(self, 入力: str = '初期値') -> str: # 日本語\n"
                "        return 入力\n"
                "\n"
                "def حساب_النتيجة(القيمة: int) -> int: # عربي\n"
                "    return القيمة * 2\n"
                "\n"
                "def υπολογισμός_π(α: float, β: float = 3.14159) -> float: # Greek\n"
                "    return α * β\n"
                "\n"
                "class GroßeDatenMenge: # German umlauts\n"
                "    def ausführen(self):\n"
                "        return 'fertig'\n"
            ),
            lambda p: (
                "class 数据处理器:" in p
                and "def 処理する(self, 入力: str='初期値') -> str:" in p
                and "def حساب_النتيجة(القيمة: int) -> int:" in p
                and "def υπολογισμός_π(α: float, β: float=3.14159) -> float:" in p
                and "class GroßeDatenMenge:" in p
            )
        ),
        (
            "Heavy Emoji and Symbols in Headers, Comments & String Defaults",
            (
                "# 🚀🚀🚀 HyperDrive System 🌟✨\n"
                "class КосмическийКорабль: # 🛸 НЛО\n"
                "    def запустить_двигатель(self, тяга: str = '🔥 100%') -> str: # 💥\n"
                '        """Запуск реактивного двигателя 🚀."""\n'
                "        лог = f'Старт с тягой {тяга}'\n"
                "        return лог\n"
            ),
            lambda p: (
                "class КосмическийКорабль:" in p
                and "def запустить_двигатель(self, тяга: str='🔥 100%') -> str:" in p
                and "return лог" in p
            )
        )
    ]

    for title, code, validator in test_cases:
        pruned, stats = vazus_native_ast.prune_code_string(code, "summary")
        assert stats["is_valid"] is True, f"Failed validity for '{title}': {stats}"
        assert validator(pruned), f"Validator failed for '{title}'. Pruned:\n{pruned}"
        parsed = ast.parse(pruned)
        assert parsed is not None, f"ast.parse failed on pruned code for '{title}'"
        print(f"  -> SUCCESS: {title} (UTF-8 integrity verified, ast.parse succeeded)")

    print("\nSTAGE 2 PASSED: Unicode, Cyrillic, and non-ASCII verified.")

def run_syntax_error_stress_tests():
    print("\n" + "=" * 70)
    print("STAGE 3: SYNTAX ERROR RESILIENCE (ZERO PANICS, is_valid: False)")
    print("=" * 70)

    malformed_inputs = [
        ("Incomplete function header", "def broken_func(:\n    pass\n"),
        ("Unclosed parenthesis", "def f(x, y: int:\n    return x + y"),
        ("Mismatched brackets", "x = [1, 2, (3, 4]"),
        ("Bare colon at top level", ":"),
        ("Missing colon in if", "if True pass\n"),
        ("Unterminated single quote", "x = 'unterminated string"),
        ("Unterminated double quote", '"unterminated string literal\n'),
        ("Unterminated triple quote", '"""unclosed triple docstring\nmore lines\n'),
        ("Invalid operators token stream", "1 + * 2\n"),
        ("Keyword as identifier without expression", "class class: def def:"),
        ("Bare keyword definition", "class : pass\n"),
        ("Missing function identifier", "def (x): pass\n"),
        ("Bare import statement", "import\n"),
        ("Incomplete return statement block", "def syntax_err(\n    return"),
        ("Invalid loop syntax", "for in range(10): pass\n"),
        ("Random punctuation operator sequence", "??? +++ %%% @@@\n"),
        ("Unclosed class header", "class Unclosed:\n    def foo(\n"),
        ("Raw binary garbage decoded as unicode", "def \uFFFD\u0000 invalid syntax (:"),
        ("Only whitespace and tabs", "   \t\n   \r\n   "),
        ("Completely empty string", ""),
    ]

    for label, bad_code in malformed_inputs:
        try:
            pruned, stats = vazus_native_ast.prune_code_string(bad_code, "summary")
            # For empty or whitespace strings, Tree-sitter or empty check might say valid or empty:
            if bad_code.strip() == "":
                assert stats["pruned_bytes"] == 0
                print(f"  -> Empty input: handled gracefully with 0 pruned bytes.")
            elif label == "Control characters / null byte":
                # Valid python syntax with null string
                print(f"  -> {label}: is_valid={stats['is_valid']} (no panic on control characters)")
            else:
                assert stats["is_valid"] is False, (
                    f"Expected is_valid=False for '{label}', got is_valid={stats['is_valid']}"
                )
                print(f"  -> {label}: is_valid=False (handled safely without panic)")
        except Exception as exc:
            raise AssertionError(f"PANIC or UNCAUGHT EXCEPTION on '{label}': {exc}")

    print("\nSTAGE 3 PASSED: All syntax errors caught with zero panics.")

def run_concurrency_stress_test():
    print("\n" + "=" * 70)
    print("STAGE 4: CONCURRENCY STRESS TEST (16 OS THREADS)")
    print("=" * 70)

    num_threads = 16
    calls_per_thread = 250
    total_calls = num_threads * calls_per_thread

    test_snippets = [
        "def worker_f1(a: int, b: int = 2) -> int:\n    \"\"\"Worker doc 1.\"\"\"\n    c = a + b\n    return c\n",
        "class WorkerClassA:\n    \"\"\"Class doc.\"\"\"\n    def method(self):\n        return 42\n",
        "def broken_syntax(:\n    pass\n",
        "class ТестовыйКласс:\n    def метод(self, x: int = 10):\n        return x * 2\n",
        "def closure():\n    def inner():\n        return 1\n    return 2\n",
    ]

    print(f"Launching {total_calls} concurrent calls across {num_threads} OS threads...")
    start_time = time.perf_counter()

    def worker_job(worker_id: int):
        results = []
        for i in range(calls_per_thread):
            snippet = test_snippets[(worker_id + i) % len(test_snippets)]
            pruned, stats = vazus_native_ast.prune_code_string(snippet, "summary")
            is_broken = "broken_syntax" in snippet
            if is_broken:
                assert stats["is_valid"] is False
            else:
                assert stats["is_valid"] is True
                assert len(pruned) > 0
            results.append(stats["is_valid"])
        return len(results)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_job, tid) for tid in range(num_threads)]
        completed_counts = [f.result() for f in concurrent.futures.as_completed(futures)]

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    assert len(completed_counts) == num_threads
    assert sum(completed_counts) == total_calls

    ops_per_sec = total_calls / (elapsed_ms / 1000.0)
    print(f"  -> Completed {total_calls} calls across {num_threads} threads in {elapsed_ms:.2f} ms ({ops_per_sec:.0f} ops/sec)")
    print(f"  -> Zero race conditions, zero deadlocks, zero thread-local crashes.")
    print("\nSTAGE 4 PASSED: 16-thread concurrency safety empirically confirmed.")

def run_speedup_benchmark():
    print("\n" + "=" * 70)
    print("STAGE 5: LATENCY SPEEDUP INDEPENDENT BENCHMARK (10,000-LINE MODULE)")
    print("=" * 70)

    # Construct synthetic 10,000-line Python module (2,000 functions * 5 lines = 10,000 lines)
    num_functions = 2000
    module_lines = []
    for i in range(num_functions):
        module_lines.append(f"def func_{i:04d}(param_x: int = {i}, param_y: str = 'val_{i}') -> int:")
        module_lines.append(f'    """Documentation for generated synthetic function {i}."""')
        module_lines.append(f"    local_var_{i} = param_x * 2 + len(param_y)")
        module_lines.append(f"    result_{i} = local_var_{i} % 1000")
        module_lines.append(f"    return result_{i}")
    
    synthetic_code = "\n".join(module_lines) + "\n"
    total_loc = len(synthetic_code.splitlines())
    code_bytes = len(synthetic_code.encode("utf-8"))
    print(f"Generated synthetic module: {total_loc:,} lines, {code_bytes / 1024:.2f} KB, {num_functions} functions.")

    # 1. Warm-up
    vazus_native_ast.prune_code_string("def warmup(): pass", "summary")

    # 2. Benchmark Native Rust Tree-Sitter Pruner (vazus_native_ast.prune_code_string)
    native_times = []
    for _ in range(3):
        t0 = time.perf_counter()
        native_pruned, native_stats = vazus_native_ast.prune_code_string(synthetic_code, "summary")
        t_native = (time.perf_counter() - t0) * 1000.0
        native_times.append(t_native)
    
    best_native_ms = min(native_times)
    avg_native_ms = sum(native_times) / len(native_times)

    # 3. Benchmark Top-level vazus_core.ast_pruner wrapper
    t0 = time.perf_counter()
    wrapper_pruned, wrapper_stats = ast_pruner_module.prune_code_string(synthetic_code, docstring_mode="summary")
    wrapper_ms = (time.perf_counter() - t0) * 1000.0

    # 4. Benchmark Pure Python AST Pruner (DocstringAndBodyPruner with ast.parse + ast.unparse)
    python_times = []
    for _ in range(3):
        t0 = time.perf_counter()
        py_tree = ast.parse(synthetic_code)
        transformer = DocstringAndBodyPruner(docstring_mode="summary")
        pruned_tree = transformer.visit(py_tree)
        ast.fix_missing_locations(pruned_tree)
        py_pruned_code = ast.unparse(pruned_tree)
        t_py = (time.perf_counter() - t0) * 1000.0
        python_times.append(t_py)
    
    best_py_ms = min(python_times)
    avg_py_ms = sum(python_times) / len(python_times)

    # Calculate speedup ratios
    speedup_best = best_py_ms / best_native_ms
    speedup_avg = avg_py_ms / avg_native_ms
    wrapper_speedup = avg_py_ms / wrapper_ms

    print(f"\nBenchmark Results:")
    print(f"  - Pure Python AST: min={best_py_ms:.2f} ms, avg={avg_py_ms:.2f} ms")
    print(f"  - Native Rust Tree-Sitter: min={best_native_ms:.2f} ms, avg={avg_native_ms:.2f} ms")
    print(f"  - Python Wrapper (ast_pruner): {wrapper_ms:.2f} ms")
    print(f"  - Native Speedup over Python AST: {speedup_avg:.2f}x (best: {speedup_best:.2f}x)")
    print(f"  - Wrapper Speedup over Python AST: {wrapper_speedup:.2f}x")
    print(f"  - Native Stats: is_valid={native_stats['is_valid']}, reduction={native_stats['reduction_percent']}%, pruned_bytes={native_stats['pruned_bytes']}")

    # Validation
    assert native_stats["is_valid"] is True, "Native pruner returned invalid AST on 10k LOC benchmark"
    assert "def func_0000" in native_pruned
    assert "def func_1999" in native_pruned
    assert "return result_0" in native_pruned
    assert "local_var_0" not in native_pruned

    # Verify requirement: >= 10.0x speedup
    print(f"\nVerification against Requirement R1 / Acceptance Criteria (Speedup >= 10.0x):")
    if speedup_avg >= 10.0:
        print(f"  [PASS] Speedup {speedup_avg:.2f}x EXCEEDS 10.0x requirement threshold!")
    else:
        print(f"  [FAIL] Speedup {speedup_avg:.2f}x BELOW 10.0x requirement threshold!")
    assert speedup_avg >= 10.0, f"Speedup {speedup_avg:.2f}x is below required 10.0x"

    print("\nSTAGE 5 PASSED: Latency speedup requirement independently verified.")

if __name__ == "__main__":
    print("STARTING EMPIRICAL CHALLENGER STRESS SUITE (MILESTONE 1 ITERATION 3)")
    print(f"Python interpreter: {sys.executable}")
    print(f"vazus_native_ast path: {vazus_native_ast.__file__}")

    run_pathological_input_tests()
    run_unicode_cyrillic_stress_tests()
    run_syntax_error_stress_tests()
    run_concurrency_stress_test()
    run_speedup_benchmark()

    print("\n" + "=" * 70)
    print("ALL 5 CHALLENGER STRESS SUITE STAGES PASSED CLEANLY (100% VERIFIED)!")
    print("=" * 70)
