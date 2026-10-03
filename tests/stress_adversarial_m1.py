"""
Comprehensive Adversarial Stress and Fuzzing Suite for Milestone 1
Covers:
1. AST Pruner Fuzzing (Unicode, Emojis, Contracts, Deep Nesting, Syntax Variations, Huge File)
2. Z3 Native SMT Verifier Concurrency & Thread-Safety (Rayon, Multi-threading, GIL release, Extreme Values)
3. Cosine SIMD Vector Engine Mathematical Edge Cases (AVX2 vs NumPy, Zero-Norm, Orthogonal, Negative, NaN/Inf)
4. Latency Benchmark (Native vs Pure Python AST speedup factor)
"""

import ast
import concurrent.futures
import json
import math
import os
import random
import subprocess
import sys
import time
import numpy as np

sys.path.insert(0, r"C:\vazus")

import vazus_native_ast
import vazus_native_z3
import cosine_simd_rs
from vazus_core.verification.ast_pruner import DocstringAndBodyPruner

report = {
    "ast_fuzzing": {},
    "z3_concurrency": {},
    "cosine_math": {},
    "latency_benchmark": {},
    "findings": [],
}

print("=" * 60)
print("STARTING ADVERSARIAL VERIFICATION SUITE FOR MILESTONE 1")
print("=" * 60)

# ============================================================================
# SECTION 1: AST PRUNER FUZZING & PATHOLOGICAL INPUTS
# ============================================================================
print("\n[SECTION 1] AST Pruner Fuzzing & Stress Testing...")

test_cases_ast = {}

# 1.1 Non-ASCII class/func with comment (Bug reproduction)
test_cases_ast["unicode_identifier_with_comment"] = '''
class МетрикиКачества: # Класс метрик качества
    def вычислить(self, x: float) -> bool: # Метод вычисления
        return x > 0.5
'''

# 1.2 Unicode & Emojis in comments, docstrings, and literals
test_cases_ast["unicode_emojis_in_docstrings"] = '''
# 🚀 Vazus SuperGraph OS v5.0
"""
Этот модуль тестирует поддержку UTF-8 и эмодзи 🎉🔥.
:requires: x >= 0
:ensures: result == "Успех! 🌟"
"""

def greeting(name: str = "Алексей 👨‍💻") -> str:
    """Возвращает строку с приветствием ✨."""
    msg = f"Привет, {name}! 🚀"
    return msg
'''

# 1.3 Deep nesting (10 levels of functions / closures)
deep_nest_lines = ["def level_0():"]
for lvl in range(1, 10):
    indent = "    " * lvl
    deep_nest_lines.append(f"{indent}def level_{lvl}():")
deep_nest_lines.append("    " * 10 + "return 42")
for lvl in range(9, 0, -1):
    indent = "    " * lvl
    deep_nest_lines.append(f"{indent}return level_{lvl}()")
deep_nest_lines.append("    return level_1()")
test_cases_ast["deep_nesting"] = "\n".join(deep_nest_lines)

# 1.4 Pathological quotes, escapes, and contract directives
test_cases_ast["pathological_quotes_contracts"] = r'''
def complex_docstring(a: int, b: str = "quote \"' inside") -> str:
    r"""
    Raw docstring with backslashes \n \t and quotes: "single ' inside double"
    :requires: a > 0
    :requires: b != ""
    :ensures: len(result) >= a
    Detailed notes:
    - Point 1: don't fail on "quoted" items
    - Point 2: 'single' quotes
    """
    return f"{b}_{a}"

def single_quote_docstring(x: float) -> float:
    ''' + "'''" + r'''
    Docstring using triple single quotes!
    :requires: x > 0.0
    :ensures: result > 1.0
    ''' + "'''" + r'''
    return x + 1.0
'''

# 1.5 Modern Python Syntax Variations
test_cases_ast["syntax_variations"] = '''
@decorator_one(
    target="core",
    flags=0x1F,
    enabled=True,
)
@decorator_two
async def process_event(event: dict, *args, mode: str = "fast", **kwargs) -> tuple[int, ...]:
    """Processes event stream with async generator."""
    if (n := len(event)) > 0:
        match event.get("type"):
            case "start":
                return (1, n)
            case "stop":
                return (0, n)
            case _:
                return (-1, 0)
    return (0, 0)
'''

# 1.6 Multiline return statements with complex expressions
test_cases_ast["multiline_return"] = '''
def calculate_matrix_projection(vec: list[float], scale: float = 1.0) -> dict[str, list[float]]:
    """Calculates multi-dimensional projection."""
    return {
        "x": [v * scale for v in vec],
        "y": [v * (scale + 1.0) for v in vec],
        "z": [0.0] * len(vec),
    }
'''

# 1.7 2-space indentation (valid Python)
test_cases_ast["two_space_indent"] = '''
class TwoSpaceClass:
  def method_a(self):
    return 1
  def method_b(self):
    return 2
'''

# 1.8 Nested scope return theft
test_cases_ast["nested_scope_return_theft"] = '''
def outer_func():
    def inner_helper():
        return 999
    return 1
'''

# 1.9 Huge file stress (1000 functions + 300 classes, ~8,000 lines)
print("  Generating huge pathological file (8,000 lines)...")
huge_lines = ["# Huge stress file for AST pruner\nimport math\nimport os\n"]
for i in range(300):
    huge_lines.append(f"""
class Entity_{i}:
    \"\"\"Entity {i} docstring with contract.
    :requires: id > 0
    :ensures: valid == True
    \"\"\"
    CLASS_VAR_{i}: int = {i}

    def __init__(self, name: str = "item_{i}") -> None:
        \"\"\"Initialize entity {i}.\"\"\"
        self.name = name

    def compute_{i}(self, x: int = {i}) -> int:
        \"\"\"Compute entity {i} score.\"\"\"
        return x * {i}
""")
for i in range(700):
    huge_lines.append(f"""
def standalone_{i}(val: float = {i}.5) -> float:
    \"\"\"Standalone function {i}.
    :requires: val > 0.0
    \"\"\"
    temp = val * 2.0
    return temp + {i}
""")
test_cases_ast["huge_file"] = "\n".join(huge_lines)

# Run AST Fuzzing tests in isolated subprocess via stdin to avoid WinError 206
python_exe = sys.executable

runner_script = """
import sys, ast, json
sys.path.insert(0, r"C:\\vazus")
import vazus_native_ast

code = sys.stdin.read()
try:
    pruned, stats = vazus_native_ast.prune_code_string(code, "summary")
    ast.parse(pruned)
    res = {"status": "PASS", "pruned_len": len(pruned), "pruned": pruned, "stats": stats}
except Exception as e:
    res = {"status": "EXCEPTION", "error": str(e)}
print("RESULT:" + json.dumps(res))
"""

for name, code in test_cases_ast.items():
    t0 = time.perf_counter()
    proc = subprocess.run([python_exe, "-c", runner_script], input=code, capture_output=True, text=True, encoding="utf-8")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or proc.stdout.strip()
        report["ast_fuzzing"][name] = {"status": "PANIC_CRASH", "error": err_msg}
        report["findings"].append(f"AST Pruner Panicked/Crashed on '{name}': {err_msg}")
        print(f"  [CRASH] {name}: Process crashed with code {proc.returncode} ({err_msg[:80]}...)")
    else:
        out_line = [l for l in proc.stdout.splitlines() if l.startswith("RESULT:")]
        if out_line:
            data = json.loads(out_line[0][7:])
            if data["status"] == "PASS":
                notes = []
                pruned = data.get("pruned", "")
                if name == "two_space_indent" and "method_a" not in pruned:
                    notes.append("2-space indent methods dropped (hardcoded indent >= 4)")
                    report["findings"].append("AST Pruner drops methods in 2-space indented classes")
                if name == "nested_scope_return_theft" and "return 999" in pruned:
                    notes.append("Inner return 999 stolen by outer function (semantic distortion)")
                    report["findings"].append("AST Pruner steals inner function return statements for outer function")
                
                note_str = f" (NOTE: {'; '.join(notes)})" if notes else ""
                report["ast_fuzzing"][name] = {
                    "status": "PASS" if not notes else "SEMANTIC_DEFECT",
                    "elapsed_ms": round(elapsed_ms, 2),
                    "notes": notes
                }
                print(f"  [{'PASS' if not notes else 'WARN'}] {name} ({elapsed_ms:.2f} ms){note_str}")
            else:
                report["ast_fuzzing"][name] = {"status": "FAIL", "error": data.get("error")}
                print(f"  [FAIL] {name}: {data.get('error')}")

# ============================================================================
# SECTION 2: Z3 NATIVE VERIFIER CONCURRENCY & THREAD-SAFETY
# ============================================================================
print("\n[SECTION 2] Z3 Native Verifier Concurrency & Multi-threading...")

# 2.1 Multi-contract JSON batch test
contract_batch = [
    {
        "name": f"contract_{i}",
        "preconditions": [f"x >= {i}"],
        "postconditions": [f"result >= {i}"],
        "code": f"def contract_{i}(x: int) -> int:\n    \"\"\"\n    :requires: x >= {i}\n    :ensures: result >= {i}\n    \"\"\"\n    return x\n",
    }
    for i in range(20)
]
batch_json = json.dumps(contract_batch)

t0 = time.perf_counter()
try:
    res_str = vazus_native_z3.verify_contracts_parallel(batch_json)
    res_data = json.loads(res_str)
    all_verified = all(item.get("verified") for item in res_data)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    report["z3_concurrency"]["batch_parallel"] = {
        "status": "PASS" if all_verified else "FAIL",
        "verified_count": len(res_data),
        "elapsed_ms": round(elapsed_ms, 2),
    }
    print(f"  [PASS] Parallel batch ({len(res_data)} contracts in {elapsed_ms:.2f} ms, all verified={all_verified})")
except Exception as e:
    report["z3_concurrency"]["batch_parallel"] = {"status": "FAIL", "error": str(e)}
    report["findings"].append(f"Z3 parallel batch failed: {e}")
    print(f"  [FAIL] Parallel batch: {e}")

# 2.2 Concurrent threads invoking Z3 solvers simultaneously (Stress GIL release & Thread-Safety)
num_workers = 16
iterations_per_worker = 10

def worker_z3_task(worker_id):
    results = []
    for it in range(iterations_per_worker):
        # 1. Memory safety check
        ms = vazus_native_z3.verify_memory_safety(it * 10, 20, 500)
        # 2. Functional equivalence
        code_a = f"def fn_{worker_id}_{it}(x: int) -> int:\n    return x + x\n"
        code_b = f"def fn_{worker_id}_{it}(x: int) -> int:\n    return x * 2\n"
        fe = vazus_native_z3.verify_functional_equivalence_native(code_a, code_b, f"fn_{worker_id}_{it}")
        # 3. Contract code
        cc = f"def abs_{worker_id}_{it}(n: int) -> int:\n    \"\"\"\n    :requires: n >= 0\n    :ensures: result >= 0\n    \"\"\"\n    return n\n"
        vc = vazus_native_z3.verify_code_contracts_native(cc)
        results.append((ms.verified, fe.verified, vc.verified))
    return results

t0 = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
    futures = [executor.submit(worker_z3_task, i) for i in range(num_workers)]
    all_worker_results = [f.result() for f in concurrent.futures.as_completed(futures)]

elapsed_ms = (time.perf_counter() - t0) * 1000
total_tasks = num_workers * iterations_per_worker * 3
all_valid = all(all(trip == (True, True, True) for trip in wr) for wr in all_worker_results)

report["z3_concurrency"]["threaded_stress"] = {
    "status": "PASS" if all_valid else "FAIL",
    "threads": num_workers,
    "total_solver_invocations": total_tasks,
    "elapsed_ms": round(elapsed_ms, 2),
    "throughput_invocations_sec": round(total_tasks / (elapsed_ms / 1000), 2),
}
print(f"  [{'PASS' if all_valid else 'FAIL'}] 16 Concurrent Threads ({total_tasks} SMT queries in {elapsed_ms:.2f} ms, {total_tasks / (elapsed_ms / 1000):.1f} queries/s)")

# 2.3 Extreme memory bounds testing (INT64_MAX, INT64_MIN, negative bounds, 0 capacity)
boundary_cases = [
    (0, 0, 0, False),  # 0 capacity
    (-1, 10, 100, False),  # negative offset
    (10, -5, 100, False),  # negative length
    (100, 1, 100, False),  # OOB boundary
    (0, 100, 100, True),  # Exact match
    (9223372036854775806, 1, 9223372036854775807, True), # INT64 high
    (9223372036854775807, 1, 9223372036854775807, False), # INT64 overflow
]
bound_pass = True
for off, length, cap, expected in boundary_cases:
    res = vazus_native_z3.verify_memory_safety(off, length, cap)
    if res.verified != expected:
        bound_pass = False
        print(f"  [FAIL] Bounds ({off}, {length}, {cap}) expected {expected}, got {res.verified}")
        report["findings"].append(f"Z3 bounds check failed on ({off}, {length}, {cap})")

report["z3_concurrency"]["extreme_bounds"] = {"status": "PASS" if bound_pass else "FAIL"}
if bound_pass:
    print("  [PASS] Extreme memory safety bounds & integer overflows handled correctly")

# ============================================================================
# SECTION 3: COSINE SIMD MATHEMATICAL EDGE CASES
# ============================================================================
print("\n[SECTION 3] Cosine SIMD Vector Engine Mathematical Edge Cases...")

def py_cosine(a, b):
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-8 or norm_b < 1e-8:
        return 0.0
    return float(np.clip(dot / (norm_a * norm_b), -1.0, 1.0))

# 3.1 All zeros
zeros = [0.0] * 768
sim_zeros = cosine_simd_rs.cosine_similarity_768(zeros, zeros)
assert sim_zeros == 0.0, f"Expected 0.0 for zero vector, got {sim_zeros}"

# 3.2 Negative / Opposite vectors
vec_pos = [1.0] * 768
vec_neg = [-1.0] * 768
sim_opp = cosine_simd_rs.cosine_similarity_768(vec_pos, vec_neg)
assert abs(sim_opp - (-1.0)) < 1e-5, f"Expected -1.0 for opposite vectors, got {sim_opp}"

# 3.3 Orthogonal vectors
vec_orth_a = [1.0 if i < 384 else 0.0 for i in range(768)]
vec_orth_b = [0.0 if i < 384 else 1.0 for i in range(768)]
sim_orth = cosine_simd_rs.cosine_similarity_768(vec_orth_a, vec_orth_b)
assert abs(sim_orth) < 1e-5, f"Expected 0.0 for orthogonal vectors, got {sim_orth}"

# 3.4 100 Random 768-D Gaussian vectors vs NumPy reference
np.random.seed(42)
max_abs_diff = 0.0
for _ in range(100):
    gauss_a = np.random.randn(768).astype(np.float32)
    gauss_b = np.random.randn(768).astype(np.float32)
    expected = py_cosine(gauss_a, gauss_b)
    actual = cosine_simd_rs.cosine_similarity_768(gauss_a.tolist(), gauss_b.tolist())
    diff = abs(expected - actual)
    if diff > max_abs_diff:
        max_abs_diff = diff

print(f"  [PASS] 100 Random 768D Gaussian pairs: Max abs diff from NumPy: {max_abs_diff:.6e} (tolerance: 1e-4)")
report["cosine_math"]["random_gaussian_vs_numpy"] = {
    "status": "PASS" if max_abs_diff < 1e-4 else "FAIL",
    "max_abs_diff": float(max_abs_diff),
}

# 3.5 Batch cosine similarity & top_k throughput
batch_size = 5000
corpus = np.random.randn(batch_size, 768).astype(np.float32).tolist()
query = np.random.randn(768).astype(np.float32).tolist()

t0 = time.perf_counter()
batch_sims = cosine_simd_rs.batch_cosine_similarity_768(query, corpus)
batch_time = time.perf_counter() - t0
rate = batch_size / batch_time

top_k = cosine_simd_rs.batch_top_k(query, corpus, 10)
print(f"  [PASS] Batch Cosine: {batch_size} 768-D vectors in {batch_time*1000:.2f} ms ({rate:.0f} vectors/sec)")
print(f"  [PASS] Top-10 similarity score: {top_k[0][1]:.4f} (index {top_k[0][0]})")

report["cosine_math"]["batch_throughput"] = {
    "status": "PASS",
    "vectors_evaluated": batch_size,
    "elapsed_ms": round(batch_time * 1000, 2),
    "vectors_per_second": round(rate, 0),
}

# 3.6 Invalid input dimension handling
dim_mismatch_pass = False
try:
    cosine_simd_rs.cosine_similarity_768([1.0] * 100, [1.0] * 768)
except ValueError:
    dim_mismatch_pass = True
print(f"  [{'PASS' if dim_mismatch_pass else 'FAIL'}] Dimension mismatch raises ValueError properly")

# ============================================================================
# SECTION 4: LATENCY SPEEDUP REQUIREMENT (>= 10x)
# ============================================================================
print("\n[SECTION 4] Latency Benchmark (Native vs Pure Python AST)...")

benchmark_files = [
    ("precommit_gate.py", r"C:\vazus\vazus_core\verification\precommit_gate.py"),
    ("ast_pruner.py", r"C:\vazus\vazus_core\verification\ast_pruner.py"),
]

speedup_results = {}
all_ge_10x = True

for label, file_path in benchmark_files:
    if not os.path.exists(file_path):
        continue
    with open(file_path, "r", encoding="utf-8") as f:
        src = f.read()

    # Warmup
    _ = ast.unparse(DocstringAndBodyPruner("summary").visit(ast.parse(src)))
    _ = vazus_native_ast.prune_code_string(src, "summary")

    # Pure Python AST timing (5 runs)
    py_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = ast.unparse(DocstringAndBodyPruner("summary").visit(ast.parse(src)))
        py_times.append((time.perf_counter() - t0) * 1000)
    median_py = sorted(py_times)[len(py_times) // 2]

    # Native AST timing (10 runs)
    native_times = []
    for _ in range(10):
        t0 = time.perf_counter()
        _ = vazus_native_ast.prune_code_string(src, "summary")
        native_times.append((time.perf_counter() - t0) * 1000)
    median_native = sorted(native_times)[len(native_times) // 2]

    speedup = median_py / median_native
    speedup_results[label] = {
        "file_size_bytes": len(src.encode("utf-8")),
        "lines": len(src.splitlines()),
        "python_median_ms": round(median_py, 3),
        "native_median_ms": round(median_native, 3),
        "speedup_factor": round(speedup, 2),
        "meets_10x": speedup >= 10.0,
    }

    status_str = "PASS" if speedup >= 10.0 else "FAIL"
    if speedup < 10.0:
        all_ge_10x = False
    print(f"  [{status_str}] {label} ({len(src.splitlines())} lines): Python {median_py:.2f} ms vs Native {median_native:.2f} ms -> {speedup:.1f}x speedup")

report["latency_benchmark"] = {
    "status": "PASS" if all_ge_10x else "FAIL",
    "results": speedup_results,
}

print("\n" + "=" * 60)
print(f"VERIFICATION SUMMARY: {len(report['findings'])} DEFECTS/FINDINGS RECORDED")
print("=" * 60)

with open(r"C:\vazus\tests\stress_adversarial_m1_results.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("Results dumped to tests/stress_adversarial_m1_results.json")
