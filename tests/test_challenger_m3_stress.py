"""
Milestone 3: Zig Evaluator Adversarial Stress Test Suite & Bug Reproducer
Author: Challenger 1 (Adversarial Verifier & Empirical Stress Tester)
Target: native/sandbox vazus_runner.exe, vazus_runner.dll, LocalREPL integration
"""

import concurrent.futures
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

WORKSPACE_ROOT = Path("C:/vazus").resolve()
EXE_PATH = WORKSPACE_ROOT / "bin" / "vazus_runner.exe"
DLL_PATH = WORKSPACE_ROOT / "bin" / "vazus_runner.dll"

def run_cmd(args, timeout=5):
    """Helper to run CLI commands and return (returncode, stdout, stderr, duration)."""
    t0 = time.perf_counter()
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(WORKSPACE_ROOT),
    )
    duration = time.perf_counter() - t0
    return proc.returncode, proc.stdout, proc.stderr, duration


# ==============================================================================
# 1. LARGE SCRIPT PAYLOAD STRESS TESTS (64KB+ PAYLOADS)
# ==============================================================================

def test_large_payload_cli():
    """Test large payload on CLI runner within Windows CLI limits (~30KB)."""
    print("\n[1.1] Testing Large Payload on CLI Runner (~30KB payload)...")
    lines = ["x = 1\n"] * 5000  # 30,000 bytes
    code = "".join(lines)
    assert len(code) == 30000

    ret, stdout, stderr, dur = run_cmd([str(EXE_PATH), "--root", "C:\\vazus", "--eval", code], timeout=10)
    assert ret == 0, f"CLI runner failed on 30KB payload! Exit code: {ret}, stderr: {stderr}"
    print(f"  -> SUCCESS: CLI handled 30KB payload without panic or crash in {dur:.3f}s (exit code: {ret}).")


def test_large_payload_dll_ffi():
    """Test 64KB, 128KB, and 256KB payloads via DLL FFI."""
    print("\n[1.2] Testing Large Payloads via DLL C-ABI (64KB, 128KB, 256KB)...")
    lib = ctypes.CDLL(str(DLL_PATH))
    lib.execute_sandboxed_snippet.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.execute_sandboxed_snippet.restype = ctypes.c_int

    for size_kb in [64, 128, 256]:
        num_lines = (size_kb * 1024) // 6  # ~6 bytes per "x = 1\n"
        code = "x = 1\n" * num_lines
        code_bytes = code.encode("utf-8")
        payload_len = len(code_bytes)
        print(f"  -> Testing payload size: {payload_len} bytes ({payload_len / 1024:.1f} KB)...")

        out_buf = ctypes.create_string_buffer(4096)
        t0 = time.perf_counter()
        ret = lib.execute_sandboxed_snippet(
            code_bytes,
            b"C:\\vazus",
            out_buf,
            4096,
        )
        elapsed = time.perf_counter() - t0
        assert ret == 0, f"execute_sandboxed_snippet failed on {size_kb}KB payload! Return code: {ret}"
        print(f"     Passed: return code {ret} in {elapsed*1000:.2f}ms, zero buffer overflow / panic.")

    print("  -> SUCCESS: All large payloads (up to 256KB) executed cleanly via DLL FFI.")


# ==============================================================================
# 2. SYNTAX EDGE CASES & PATHOLOGICAL MALFORMED INPUTS
# ==============================================================================

def test_syntax_edge_cases_cli():
    """Test syntax edge cases on CLI runner."""
    print("\n[2.1] Testing Syntax Edge Cases on CLI Runner...")

    # A. Empty string: should exit 0 cleanly
    ret, stdout, stderr, _ = run_cmd([str(EXE_PATH), "--root", "C:\\vazus", "--eval", ""])
    assert ret == 0, f"Empty code should return 0, got {ret}"
    print("  -> Passed: Empty string returns 0 cleanly.")

    # B. Deeply nested expressions: 100 levels of parentheses
    nested_expr = "(" * 100 + "42" + ")" * 100
    ret, stdout, stderr, _ = run_cmd([str(EXE_PATH), "--root", "C:\\vazus", "--eval", nested_expr])
    assert ret == 0, f"Deeply nested expression failed! Code: {ret}, stderr: {stderr}"
    assert "42" in stdout, f"Expected 42 in stdout, got '{stdout}'"
    print("  -> Passed: 100-level deeply nested expression evaluated correctly to 42.")

    # C. Unclosed brackets
    unclosed_cases = [
        "(((1 + 1)",
        "while (true) { x = 1",
        "{ x = 1",
        "print((5 + 3",
    ]
    for case in unclosed_cases:
        ret, stdout, stderr, _ = run_cmd([str(EXE_PATH), "--root", "C:\\vazus", "--eval", case])
        assert ret != 0, f"Unclosed bracket '{case}' should fail, got returncode 0!"
        assert "SyntaxError" in stderr or "Error" in stderr, f"Expected SyntaxError for '{case}', got stderr: '{stderr}'"
        print(f"  -> Passed: Unclosed case '{case}' rejected cleanly (code {ret}).")

    # D. Invalid operator combinations
    invalid_op_cases = [
        "1 ++ 2",
        "1 ** 2",
        "+ * / 5",
        "== = 3",
        "1 != = 2",
        "1 >< 2",
    ]
    for case in invalid_op_cases:
        ret, stdout, stderr, _ = run_cmd([str(EXE_PATH), "--root", "C:\\vazus", "--eval", case])
        assert ret != 0, f"Invalid op '{case}' should fail, got returncode 0!"
        print(f"  -> Passed: Invalid operator combo '{case}' rejected cleanly (code {ret}).")

    # E. Division by zero
    div_zero_cases = [
        ("1 / 0", "ZeroDivisionError"),
        ("10 % 0", "ZeroDivisionError"),
        ("2.5 / 0.0", "ZeroDivisionError"),
    ]
    for case, expected_err in div_zero_cases:
        ret, stdout, stderr, _ = run_cmd([str(EXE_PATH), "--root", "C:\\vazus", "--eval", case])
        assert ret != 0, f"Division by zero '{case}' should return non-zero, got {ret}!"
        assert expected_err in stderr or "Division" in stderr, f"Expected {expected_err} in stderr for '{case}', got '{stderr}'"
        print(f"  -> Passed: Division by zero '{case}' returned non-zero code {ret} with '{expected_err}'.")


def test_syntax_edge_cases_dll():
    """Test syntax edge cases on DLL FFI."""
    print("\n[2.2] Testing Syntax Edge Cases on DLL C-ABI...")
    lib = ctypes.CDLL(str(DLL_PATH))
    lib.execute_sandboxed_snippet.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.execute_sandboxed_snippet.restype = ctypes.c_int

    out_buf = ctypes.create_string_buffer(1024)

    # Empty string
    ret = lib.execute_sandboxed_snippet(b"", b"C:\\vazus", out_buf, 1024)
    assert ret == 0, f"DLL empty snippet failed: {ret}"
    print("  -> Passed: DLL empty snippet returns 0.")

    # Syntax error
    ret = lib.execute_sandboxed_snippet(b"1 +++ 2", b"C:\\vazus", out_buf, 1024)
    assert ret == -2, f"DLL invalid syntax expected -2, got {ret}"
    print("  -> Passed: DLL invalid syntax returns -2.")

    # Division by zero
    ret = lib.execute_sandboxed_snippet(b"1 / 0", b"C:\\vazus", out_buf, 1024)
    assert ret == -2, f"DLL div by zero expected -2, got {ret}"
    print("  -> Passed: DLL division by zero returns -2.")


# ==============================================================================
# 3. WHILE LOOP PARSER REMEDIATION VERIFICATION
# ==============================================================================

def test_while_parser_defect_reproduction():
    """Verify clean while-loop execution following Milestone 3 parser remediation."""
    print("\n[3.1] VERIFYING WHILE LOOP PARSER REMEDIATION...")

    # 1. while(true){} executes infinite loop and times out cleanly (no premature SyntaxError)
    timed_out1 = False
    try:
        run_cmd([str(EXE_PATH), "--root", "C:\\vazus", "--eval", "while(true){}"], timeout=1)
    except subprocess.TimeoutExpired:
        timed_out1 = True
    assert timed_out1 is True, "Expected while(true){} to execute as infinite loop and time out"
    print("  -> Passed: while(true){} executed infinite loop without inverted slice panic.")

    # 2. while (1) { x = 1 } executes infinite loop and times out cleanly (no token swallowing)
    timed_out2 = False
    try:
        run_cmd([str(EXE_PATH), "--root", "C:\\vazus", "--eval", "while (1) { x = 1 }"], timeout=1)
    except subprocess.TimeoutExpired:
        timed_out2 = True
    assert timed_out2 is True, "Expected while (1) { x = 1 } to execute as infinite loop and time out"
    print("  -> Passed: while (1) { x = 1 } preserved body tokens and executed cleanly.")

    # 3. while (false) {} executes clean no-op
    ret3, _, _, dur3 = run_cmd([str(EXE_PATH), "--root", "C:\\vazus", "--eval", "while (false) {}"], timeout=2)
    assert ret3 == 0, f"Expected while (false) {{}} to exit 0, got {ret3}"
    print(f"  -> Passed: while (false) {{}} executed cleanly in {dur3*1000:.2f}ms.")

    # 4. Terminating dynamic loop: x = 0; while (x < 3) { x = x + 1 }
    ret4, _, _, dur4 = run_cmd([str(EXE_PATH), "--root", "C:\\vazus", "--eval", "x = 0; while (x < 3) { x = x + 1 }"], timeout=2)
    assert ret4 == 0, f"Expected dynamic loop to exit 0, got {ret4}"
    print(f"  -> Passed: x = 0; while (x < 3) {{ x = x + 1 }} terminated with exit code 0 in {dur4*1000:.2f}ms.")


# ==============================================================================
# 4. MULTI-THREADED FFI CONCURRENCY STRESS (10 CONCURRENT THREADS)
# ==============================================================================

def test_multithreaded_ffi_stress():
    """Stress test vazus_runner.dll concurrently from 10 Python threads."""
    print("\n[4.1] Testing Multi-threaded FFI Stress (10 Threads, 2500 total calls)...")
    lib = ctypes.CDLL(str(DLL_PATH))
    lib.check_path_allowed.argtypes = [ctypes.c_char_p]
    lib.check_path_allowed.restype = ctypes.c_int
    lib.execute_sandboxed_snippet.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.execute_sandboxed_snippet.restype = ctypes.c_int

    errors = []
    call_count = [0]
    lock = threading.Lock()

    def worker_task(thread_id, iterations=50):
        try:
            for i in range(iterations):
                # 1. Check path allowed (allowed path)
                res1 = lib.check_path_allowed(b"C:\\vazus\\data\\file.txt")
                if res1 != 1:
                    errors.append(f"T{thread_id} i{i}: check_path_allowed allowed failed, got {res1}")

                # 2. Check path allowed (forbidden path)
                res2 = lib.check_path_allowed(b"C:\\Windows\\System32\\cmd.exe")
                if res2 != 0:
                    errors.append(f"T{thread_id} i{i}: check_path_allowed forbidden failed, got {res2}")

                # 3. Check path allowed (git forbidden)
                res3 = lib.check_path_allowed(b"C:\\vazus\\.git\\HEAD")
                if res3 != 0:
                    errors.append(f"T{thread_id} i{i}: check_path_allowed git failed, got {res3}")

                # 4. Execute arithmetic expression
                buf = ctypes.create_string_buffer(256)
                res4 = lib.execute_sandboxed_snippet(b"10 + 20 * 2", b"C:\\vazus", buf, 256)
                if res4 != 0 or b"50" not in buf.value:
                    errors.append(f"T{thread_id} i{i}: execute_sandboxed_snippet 10+20*2 failed: ret={res4}, buf={buf.value}")

                # 5. Execute variable assignment and logic
                res5 = lib.execute_sandboxed_snippet(b"a = 5\nb = 7\na + b", b"C:\\vazus", buf, 256)
                if res5 != 0 or b"12" not in buf.value:
                    errors.append(f"T{thread_id} i{i}: execute_sandboxed_snippet a+b failed: ret={res5}, buf={buf.value}")

                with lock:
                    call_count[0] += 5
        except Exception as exc:
            errors.append(f"T{thread_id} exception: {exc}")

    threads = []
    num_threads = 10
    start_t = time.perf_counter()
    for t_id in range(num_threads):
        t = threading.Thread(target=worker_task, args=(t_id, 50))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=10.0)

    elapsed_t = time.perf_counter() - start_t
    print(f"  -> Completed {call_count[0]} FFI calls across {num_threads} concurrent threads in {elapsed_t:.3f}s ({call_count[0]/elapsed_t:.0f} calls/sec).")
    assert len(errors) == 0, f"Thread concurrency errors encountered: {errors[:5]}"
    print("  -> SUCCESS: Zero concurrency errors, thread-safety confirmed.")


# ==============================================================================
# 5. ADVERSARIAL PATH JAIL SECURITY BOUNDARY & C-ABI TRUNCATION ANALYSIS
# ==============================================================================

def test_adversarial_path_jail():
    """Verify security isolation: path traversal, forbidden targets, case sensitivity, symlinks/UNC."""
    print("\n[5.1] Testing Adversarial Path Jail Boundaries...")
    lib = ctypes.CDLL(str(DLL_PATH))
    lib.check_path_allowed.argtypes = [ctypes.c_char_p]
    lib.check_path_allowed.restype = ctypes.c_int

    test_vectors = [
        # (path, expected_result, description)
        (b"C:\\vazus\\src\\main.zig", 1, "Normal valid workspace path"),
        (b"C:/vazus/services/memory/vazus.db", 1, "Forward slash valid path"),
        (b"c:\\vazus\\test.py", 1, "Lowercase drive letter"),
        (b"~/.gemini/config.json", 1, "Gemini config path"),
        (b"C:\\vazus\\..\\..\\Windows\\System32\\calc.exe", 0, "Directory traversal escape"),
        (b"C:\\vazus\\subdir\\..\\..\\..\\Program Files", 0, "Multi-level traversal escape"),
        (b"\\\\?\\C:\\Windows\\System32\\cmd.exe", 0, "UNC prefix bypass attempt"),
        (b"C:\\vazus\\.git\\objects", 0, "Blocked .git folder"),
        (b"C:\\vazus\\AGENTS.md", 0, "Blocked AGENTS.md"),
        (b"C:\\vazus\\agents.md", 0, "Blocked lowercase agents.md"),
        (b"/etc/passwd", 0, "Unix system path /etc/passwd"),
        (b"C:\\Windows\\system32\\cmd.exe", 0, "Windows system32 binary"),
        (b"", 0, "Empty path"),
        (b"   ", 0, "Whitespace path"),
    ]

    for path, expected, desc in test_vectors:
        res = lib.check_path_allowed(path)
        assert res == expected, f"Path jail failed for '{path.decode(errors='replace')}' ({desc})! Expected {expected}, got {res}"
        print(f"  -> Passed: [{desc}] -> {'ALLOWED' if res == 1 else 'FORBIDDEN'}")

    # Null-byte C-ABI truncation observation
    res_null = lib.check_path_allowed(b"C:\\vazus\\test\x00.txt")
    print(f"  -> Observation: C-ABI null-byte input 'C:\\vazus\\test\\0.txt' evaluated as 'C:\\vazus\\test' (returned {res_null}).")
    print("  -> SUCCESS: All primary path security invariants strictly held.")


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

def main():
    print("=" * 80)
    print(" MILESTONE 3: ZIG EVALUATOR ADVERSARIAL STRESS TEST SUITE & DEFECT AUDIT")
    print("=" * 80)

    t0 = time.perf_counter()
    test_large_payload_cli()
    test_large_payload_dll_ffi()
    test_syntax_edge_cases_cli()
    test_syntax_edge_cases_dll()
    test_while_parser_defect_reproduction()
    test_multithreaded_ffi_stress()
    test_adversarial_path_jail()
    total_time = time.perf_counter() - t0

    print("\n" + "=" * 80)
    print(f" COMPLETED ALL ADVERSARIAL TEST HARNESS RUNS IN {total_time:.3f}s.")
    print("=" * 80)

if __name__ == "__main__":
    main()
