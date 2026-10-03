"""
Empirical Adversarial Recheck Harness for Milestone 1 (Rust Native Engine Remediation)
Author: Challenger 2 Recheck
Covers all 5 adversarial dimensions and pathological edge cases:
1. UTF-8 comments before '#' (no panics, no aborts)
2. Syntax error strings (dynamically returns is_valid: False)
3. Nested classes & closures (preserves bodies, 2-space indents, no return theft)
4. Memory safety bounds checks (i64::MAX overflow rejected)
5. Cosine SIMD extreme vectors (1e15 vectors return 1.0 without overflow)
"""

import sys
import os
import math

sys.path.insert(0, r"C:\vazus")

import vazus_native_ast
import vazus_native_z3
import cosine_simd_rs
from vazus_core.verification.ast_pruner import ASTPruner

def test_utf8_comments():
    print("=== ADVERSARIAL TEST 1: UTF-8 COMMENTS BEFORE # ===")
    utf8_inputs = [
        "class МетрикиКачества: # коммент\n    pass\n",
        "def вычислить_метрику(): # комментарий функции\n    return 42\n",
        "def 日本語関数(x: int): # 日本語コメント\n    return x\n",
        "# 🎉 Эмодзи комментарий\nclass ЭмодзиКласс: # 🚀 ракета\n    def метод(self): # ✨ искра\n        return 'ok'\n",
        "class Mixed_Тест_123: # comment with non-ascii chars: öäüß\n    pass\n",
        "def foo(x: str = 'значение'): # коммент после параметра\n    return x\n",
        "x = 100 # комментарий\n",
    ]
    for i, code in enumerate(utf8_inputs):
        pruned, stats = vazus_native_ast.prune_code_string(code, "summary")
        assert stats["is_valid"] is True, f"Failed validity on case {i}"
        print(f"  Case {i}: is_valid={stats['is_valid']}, pruned_len={len(pruned)}")
    print("TEST 1: PASSED (Zero panics, zero aborts)\n")

def test_syntax_errors():
    print("=== ADVERSARIAL TEST 2: SYNTAX ERROR STRINGS ===")
    syntax_err_inputs = [
        "def broken_func(:\n    pass\n",
        "class Unclosed:\n    def foo(\n",
        "def (x): pass\n",
        "class : pass\n",
        "if True pass\n",
        "for in range(10): pass\n",
        "1 + * 2\n",
        "import\n",
        '"unterminated string literal\n',
        "??? +++ %%% @@@\n",
        "def syntax_err(\n    return",
    ]
    for i, code in enumerate(syntax_err_inputs):
        pruned, stats = vazus_native_ast.prune_code_string(code, "summary")
        assert stats["is_valid"] is False, f"Expected is_valid=False for case {i} ({code!r}), got {stats['is_valid']}"
        # Also verify fallback via ASTPruner
        fallback_pruned, fallback_stats = ASTPruner.prune_code_string(code, "summary")
        assert fallback_stats["is_valid"] is False, f"Fallback failed for case {i}"
        print(f"  Syntax Error {i}: native is_valid={stats['is_valid']}, fallback is_valid={fallback_stats['is_valid']}")
    print("TEST 2: PASSED (Dynamically returns is_valid: False)\n")

def test_nested_classes_and_closures():
    print("=== ADVERSARIAL TEST 3: NESTED CLASSES AND CLOSURES ===")
    # 3.1 Closure return stealing
    closure_code = (
        "def outer():\n"
        "    def inner():\n"
        "        return 999\n"
        "    return 1\n"
    )
    pruned, stats = vazus_native_ast.prune_code_string(closure_code, "summary")
    assert "return 1" in pruned, f"Outer return missing or stolen! Got:\n{pruned}"
    assert "return 999" not in pruned, f"Inner return 999 was stolen by outer! Got:\n{pruned}"
    print("  3.1 Closure return stealing: PASSED (Outer retained return 1, inner return 999 omitted)")

    # 3.2 Multi-level closure
    multi_closure = (
        "def level1():\n"
        "    def level2():\n"
        "        def level3():\n"
        "            return 333\n"
        "        return 222\n"
        "    return 111\n"
    )
    pruned, stats = vazus_native_ast.prune_code_string(multi_closure, "summary")
    assert "return 111" in pruned, f"Multi-level outer return stolen! Got:\n{pruned}"
    print("  3.2 Multi-level closure: PASSED")

    # 3.3 2-space indentation preservation
    two_space_code = (
        "class TwoSpaceClass:\n"
        "  def method_a(self):\n"
        "    return 1\n"
        "  def method_b(self):\n"
        "    return 2\n"
    )
    pruned, stats = vazus_native_ast.prune_code_string(two_space_code, "summary")
    assert "def method_a" in pruned, f"method_a lost in 2-space class! Got:\n{pruned}"
    assert "def method_b" in pruned, f"method_b lost in 2-space class! Got:\n{pruned}"
    print("  3.3 2-space indentation: PASSED (Methods retained)")

    # 3.4 Nested class inside class
    nested_class_code = (
        "class OuterClass:\n"
        "    class InnerClass:\n"
        "        def inner_method(self):\n"
        "            return 42\n"
        "    def outer_method(self):\n"
        "        return 100\n"
    )
    pruned, stats = vazus_native_ast.prune_code_string(nested_class_code, "summary")
    assert "class InnerClass" in pruned, f"InnerClass lost! Got:\n{pruned}"
    assert "def inner_method" in pruned, f"inner_method lost! Got:\n{pruned}"
    assert "def outer_method" in pruned, f"outer_method lost! Got:\n{pruned}"
    print("  3.4 Nested class: PASSED (InnerClass and methods retained)")

    # 3.5 Outer function with no return, inner function with return
    no_outer_return = (
        "def outer_no_ret():\n"
        "    def helper():\n"
        "        return 'helper_val'\n"
        "    x = 10\n"
    )
    pruned, stats = vazus_native_ast.prune_code_string(no_outer_return, "summary")
    assert "return" not in pruned, f"Outer function without return got a stolen return statement! Got:\n{pruned}"
    print("  3.5 Outer without return: PASSED (No stolen return)")
    print("TEST 3: PASSED\n")

def test_memory_safety_bounds():
    print("=== ADVERSARIAL TEST 4: MEMORY SAFETY BOUNDS CHECKS ===")
    I64_MAX = 9223372036854775807

    # Must reject offset=i64::MAX, length=1, capacity=i64::MAX
    res_overflow = vazus_native_z3.verify_memory_safety(I64_MAX, 1, I64_MAX)
    assert res_overflow.verified is False, f"Expected verified=False on overflow, got {res_overflow.verified}"
    assert res_overflow.solver_status == "SAT", f"Expected SAT, got {res_overflow.solver_status}"
    assert res_overflow.smt_solver_status == "SAT", f"Expected SAT, got {res_overflow.smt_solver_status}"
    print(f"  4.1 Overflow bound (i64::MAX, 1, i64::MAX): verified={res_overflow.verified}, status={res_overflow.solver_status}")

    # Valid boundary check right below overflow
    res_valid_max = vazus_native_z3.verify_memory_safety(I64_MAX - 1, 1, I64_MAX)
    assert res_valid_max.verified is True, f"Expected verified=True, got {res_valid_max.verified}"
    print(f"  4.2 Max valid bound (i64::MAX - 1, 1, i64::MAX): verified={res_valid_max.verified}")

    # Length overflow: 1 + i64::MAX
    res_overflow_2 = vazus_native_z3.verify_memory_safety(1, I64_MAX, I64_MAX)
    assert res_overflow_2.verified is False, f"Expected verified=False, got {res_overflow_2.verified}"
    print(f"  4.3 Length overflow (1, i64::MAX, i64::MAX): verified={res_overflow_2.verified}")

    # Negative offset
    res_negative_off = vazus_native_z3.verify_memory_safety(-1, 10, 100)
    assert res_negative_off.verified is False, "Expected verified=False for negative offset"
    print(f"  4.4 Negative offset (-1, 10, 100): verified={res_negative_off.verified}")

    # Negative length
    res_negative_len = vazus_native_z3.verify_memory_safety(0, -5, 100)
    assert res_negative_len.verified is False, "Expected verified=False for negative length"
    print(f"  4.5 Negative length (0, -5, 100): verified={res_negative_len.verified}")

    # Negative capacity
    res_negative_cap = vazus_native_z3.verify_memory_safety(0, 10, -100)
    assert res_negative_cap.verified is False, "Expected verified=False for negative capacity"
    print(f"  4.6 Negative capacity (0, 10, -100): verified={res_negative_cap.verified}")

    # Exceeding capacity
    res_oob = vazus_native_z3.verify_memory_safety(50, 60, 100)
    assert res_oob.verified is False, "Expected verified=False for out of bounds"
    print(f"  4.7 OOB access (50, 60, 100): verified={res_oob.verified}")
    print("TEST 4: PASSED (All boundary and overflow attacks rejected)\n")

def test_cosine_simd():
    print("=== ADVERSARIAL TEST 5: COSINE SIMD EXTREME VECTORS ===")
    large_val = 1e15
    vec_large_a = [large_val] * 768
    vec_large_b = [large_val] * 768
    sim_large = cosine_simd_rs.cosine_similarity_768(vec_large_a, vec_large_b)
    assert abs(sim_large - 1.0) < 1e-5, f"Expected 1.0, got {sim_large}"
    print(f"  5.1 Extreme vectors (1e15) identical: similarity = {sim_large}")

    vec_large_neg = [-large_val] * 768
    sim_large_neg = cosine_simd_rs.cosine_similarity_768(vec_large_a, vec_large_neg)
    assert abs(sim_large_neg - (-1.0)) < 1e-5, f"Expected -1.0, got {sim_large_neg}"
    print(f"  5.2 Extreme vectors (1e15) opposite: similarity = {sim_large_neg}")

    vec_large_orth_a = [large_val if i < 384 else 0.0 for i in range(768)]
    vec_large_orth_b = [0.0 if i < 384 else large_val for i in range(768)]
    sim_large_orth = cosine_simd_rs.cosine_similarity_768(vec_large_orth_a, vec_large_orth_b)
    assert abs(sim_large_orth) < 1e-5, f"Expected 0.0, got {sim_large_orth}"
    print(f"  5.3 Extreme vectors (1e15) orthogonal: similarity = {sim_large_orth}")

    # Cross scale comparison (1e15 vs 1.0)
    vec_ones = [1.0] * 768
    sim_cross = cosine_simd_rs.cosine_similarity_768(vec_large_a, vec_ones)
    assert abs(sim_cross - 1.0) < 1e-5, f"Expected 1.0, got {sim_cross}"
    print(f"  5.4 Cross scale (1e15 vs 1.0): similarity = {sim_cross}")

    # Vectors below epsilon norm threshold (1e-8) are zero-norm degenerate vectors -> return 0.0
    small_val = 1e-15
    vec_small_a = [small_val] * 768
    vec_small_b = [small_val] * 768
    sim_small = cosine_simd_rs.cosine_similarity_768(vec_small_a, vec_small_b)
    assert sim_small == 0.0, f"Expected 0.0 for degenerate sub-epsilon vectors, got {sim_small}"
    print(f"  5.5 Degenerate vectors (1e-15 < 1e-8 epsilon): similarity = {sim_small} (correctly zero-normed)")
    print("TEST 5: PASSED (Extreme vectors computed without overflow/NaN)\n")

if __name__ == "__main__":
    test_utf8_comments()
    test_syntax_errors()
    test_nested_classes_and_closures()
    test_memory_safety_bounds()
    test_cosine_simd()
    print("=" * 60)
    print("ALL 5 ADVERSARIAL DIMENSIONS EMPIRICALLY CONFIRMED AND PASSED!")
    print("=" * 60)
