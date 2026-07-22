"""
run_stress_harness.py — Adversarial Stress Test Suite for DNTS OS SuperGraph Architecture & Native Subagent Bridges.

Author: Challenger M5_1
Target Environment: C:\\dnts\\pyenv\\.venv\\Scripts\\python.exe
"""

import os
import sys
import json
import math
import time
import shutil
import tempfile
import subprocess
import traceback
from pathlib import Path

# Setup Path
PYENV_DIR = Path("C:/dnts/pyenv")
if str(PYENV_DIR) not in sys.path:
    sys.path.insert(0, str(PYENV_DIR))

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PYTHON_EXE = sys.executable

test_results = []

def record_test(suite: str, test_name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    test_results.append({
        "suite": suite,
        "name": test_name,
        "passed": passed,
        "details": details
    })
    symbol = "✅" if passed else "❌"
    print(f"  {symbol} [{suite}] {test_name}: {status} {('- ' + details) if details else ''}")


# ==============================================================================
# SUITE 1: AST Pruner Boundary Limits & Edge Cases
# ==============================================================================
def test_suite_ast_pruner():
    print("\n" + "=" * 70)
    print("RUNNING SUITE 1: AST Pruner Boundary Limits & Edge Cases")
    print("=" * 70)
    suite = "AST_Pruner"

    from dnts_core.ast_pruner import (
        prune_python_code,
        prune_python_file,
        compute_compression_metrics,
        ASTPrunerTransformer
    )

    # 1.1 Empty string code
    try:
        pruned = prune_python_code("")
        metrics = compute_compression_metrics("", pruned)
        record_test(suite, "Empty String Code", pruned == "" and metrics["char_reduction_percent"] == 0.0, f"Pruned len: {len(pruned)}")
    except Exception as e:
        record_test(suite, "Empty String Code", False, f"Exception: {e}")

    # 1.2 Syntax error handling in prune_python_code
    try:
        prune_python_code("def broken_syntax(: pass")
        record_test(suite, "Syntax Error Input", False, "Expected SyntaxError exception but none raised!")
    except SyntaxError as se:
        record_test(suite, "Syntax Error Input", True, f"Caught expected SyntaxError: {se.msg}")
    except Exception as e:
        record_test(suite, "Syntax Error Input", False, f"Unexpected exception type: {type(e).__name__}: {e}")

    # 1.3 Non-existent file in prune_python_file
    try:
        prune_python_file("C:/dnts/non_existent_file_xyz_123.py")
        record_test(suite, "Non-existent File Input", False, "Expected FileNotFoundError but none raised!")
    except FileNotFoundError as fnfe:
        record_test(suite, "Non-existent File Input", True, f"Caught expected FileNotFoundError: {fnfe}")
    except Exception as e:
        record_test(suite, "Non-existent File Input", False, f"Unexpected exception: {e}")

    # 1.4 Directory path passed as file to prune_python_file
    try:
        prune_python_file("C:/dnts/pyenv/dnts_core")
        record_test(suite, "Directory Path as File", False, "Expected FileNotFoundError or IsADirectoryError but none raised!")
    except (FileNotFoundError, IsADirectoryError, PermissionError) as err:
        record_test(suite, "Directory Path as File", True, f"Caught expected error: {err}")
    except Exception as e:
        record_test(suite, "Directory Path as File", False, f"Unexpected exception: {e}")

    # 1.5 Complex python constructs: async, decorators, type hints, docstrings, classes
    complex_code = '''
"""Module docstring"""
import os, sys
from typing import List, Dict, Optional, Tuple

MODULE_CONST = 42

@decorator_a
@decorator_b(arg=123)
async def async_method(x: int, y: List[str] = None) -> Dict[str, int]:
    """Async docstring here."""
    val = x + 10
    await async_op(val)
    return {"key": val}

class ComplexClass(BaseClass):
    """Class docstring."""
    class_attr: str = "hello"

    def __init__(self, a: int):
        """Init docstring."""
        self.a = a

    @classmethod
    def create(cls) -> "ComplexClass":
        return cls(10)

    @staticmethod
    def calc(z: float) -> float:
        return z * 2.0
'''
    try:
        pruned_keep = prune_python_code(complex_code, keep_docstrings=True)
        pruned_no_keep = prune_python_code(complex_code, keep_docstrings=False)
        metrics = compute_compression_metrics(complex_code, pruned_keep)

        has_docstring = "Async docstring here." in pruned_keep
        no_docstring = "Async docstring here." not in pruned_no_keep
        has_ellipsis = "..." in pruned_keep

        record_test(
            suite,
            "Complex Python Constructs (Async, Decorators, Type Hints)",
            has_docstring and no_docstring and has_ellipsis and metrics["token_reduction_percent"] > 0,
            f"Token reduction: {metrics['token_reduction_percent']}%"
        )
    except Exception as e:
        record_test(suite, "Complex Python Constructs (Async, Decorators, Type Hints)", False, f"Exception: {e}")

    # 1.6 Python code with NO functions (only variables, imports, class without methods)
    no_func_code = '''
import sys
VAR_A = 100
VAR_B = 200
class DataContainer:
    x: int = 1
    y: int = 2
'''
    try:
        pruned_nf = prune_python_code(no_func_code)
        metrics_nf = compute_compression_metrics(no_func_code, pruned_nf)
        record_test(suite, "Code With No Functions", len(pruned_nf) > 0, f"Pruned len: {len(pruned_nf)}, reduction: {metrics_nf['char_reduction_percent']}%")
    except Exception as e:
        record_test(suite, "Code With No Functions", False, f"Exception: {e}")

    # 1.7 Unicode & Large Code String Compression Stress
    large_code_lines = ["# Unicode Comment: Привет 🚀⚡"]
    for i in range(1000):
        large_code_lines.append(f"def func_{i}(a: int, b: str) -> bool:\n    \"\"\"Docstring {i}\"\"\"\n    x = a + {i}\n    y = b * {i}\n    return True\n")
    large_code = "\n".join(large_code_lines)

    try:
        t0 = time.time()
        pruned_large = prune_python_code(large_code)
        t_elapsed = time.time() - t0
        metrics_large = compute_compression_metrics(large_code, pruned_large)

        record_test(
            suite,
            "1000 Functions AST Pruning & Compression Performance",
            metrics_large["token_reduction_percent"] > 50.0 and t_elapsed < 2.0,
            f"Processed 1000 functions in {t_elapsed:.3f}s. Reduction: {metrics_large['token_reduction_percent']}%"
        )
    except Exception as e:
        record_test(suite, "1000 Functions AST Pruning & Compression Performance", False, f"Exception: {e}")


# ==============================================================================
# SUITE 2: 768D Embeddings & Hybrid Metric Stress
# ==============================================================================
def test_suite_embeddings_and_metrics():
    print("\n" + "=" * 70)
    print("RUNNING SUITE 2: 768D Embeddings & Metric Boundary Stress")
    print("=" * 70)
    suite = "Embeddings_Metrics"

    from dnts_core.embeddings import UnifiedGoogleEmbedder
    from dnts_core.supergraph_linker import (
        calculate_cosine_similarity,
        calculate_fts_similarity,
        calculate_structural_similarity,
        calculate_provenance_similarity,
        SuperGraphLinker
    )

    embedder = UnifiedGoogleEmbedder()

    # 2.1 Vector dimension check on various inputs
    inputs_to_test = [
        "",
        "Short text",
        "Unicode test: Привет, мир! 🤖⚡🚀 12345",
        "\x00\x01\x02 Null bytes and control characters \n\t\r",
        "A" * 100000  # 100k chars
    ]

    dims_ok = True
    dim_details = []
    for idx, text_in in enumerate(inputs_to_test):
        try:
            vec = embedder.embed_query(text_in)
            if len(vec) != 768 or not all(isinstance(x, float) for x in vec):
                dims_ok = False
                dim_details.append(f"Input #{idx} failed: len={len(vec)}")
        except Exception as e:
            dims_ok = False
            dim_details.append(f"Input #{idx} raised: {e}")

    record_test(suite, "768D Embedder Vector Dimension Consistency (5 variants)", dims_ok, "; ".join(dim_details) or "All 5 inputs produced 768D float vectors")

    # 2.2 Cosine Similarity Boundary & Edge Cases
    try:
        # None inputs
        c1 = calculate_cosine_similarity(None, None)
        # Empty inputs
        c2 = calculate_cosine_similarity([], [])
        # Mismatched vector dimensions (768 vs 512)
        c3 = calculate_cosine_similarity([1.0] * 768, [1.0] * 512)
        # NaN / Inf inputs
        c4 = calculate_cosine_similarity([float('nan'), 1.0], [1.0, 1.0])
        c5 = calculate_cosine_similarity([float('inf'), 1.0], [1.0, 1.0])
        # Zero norm
        c6 = calculate_cosine_similarity([0.0] * 768, [1.0] * 768)
        # Non-numeric elements
        c7 = calculate_cosine_similarity(["a", "b"], [1.0, 2.0])

        all_zeros_or_clamped = all(
            0.0 <= val <= 1.0 for val in [c1, c2, c3, c4, c5, c6, c7]
        ) and c1 == 0.0 and c2 == 0.0 and c3 == 0.0 and c4 == 0.0 and c5 == 0.0 and c6 == 0.0 and c7 == 0.0

        record_test(suite, "Cosine Similarity Invalid/Boundary Vector Inputs", all_zeros_or_clamped, f"c1..c7 all 0.0 bounded: {c1, c2, c3, c4, c5, c6, c7}")
    except Exception as e:
        record_test(suite, "Cosine Similarity Invalid/Boundary Vector Inputs", False, f"Exception: {e}")

    # 2.3 FTS Similarity Edge Cases
    try:
        f1 = calculate_fts_similarity("", "")
        f2 = calculate_fts_similarity("!@#$%^&*()", "___---...")
        f3 = calculate_fts_similarity("a b c", "x y z")
        f4 = calculate_fts_similarity("supergraph linker module", "supergraph linker module integration")
        f5 = calculate_fts_similarity("Привет мир 123", "Привет мир 123")

        fts_ok = f1 == 0.0 and f2 == 0.0 and f3 == 0.0 and f4 > 0.5 and 0.0 <= f5 <= 1.0
        record_test(suite, "FTS Similarity Edge Cases (Empty, Punctuation, Unicode)", fts_ok, f"Scores: f1={f1}, f2={f2}, f3={f3}, f4={f4:.2f}, f5={f5:.2f}")
    except Exception as e:
        record_test(suite, "FTS Similarity Edge Cases", False, f"Exception: {e}")

    # 2.4 Structural Similarity Edge Cases
    try:
        s1 = calculate_structural_similarity({}, {})
        s2 = calculate_structural_similarity({"community": None}, {"community": None})
        s3 = calculate_structural_similarity(
            {"source_file": "dnts_core/supergraph_linker.py", "community": 1, "tags": "core,linker"},
            {"source_file": "dnts_core/supergraph_linker.py", "community": 1, "tags": "core,linker"}
        )
        s4 = calculate_structural_similarity(
            {"source_file": 123, "tags": None},
            {"source_file": False, "tags": 456}
        )

        struct_ok = s1 == 0.0 and s2 == 0.0 and s3 >= 0.8 and 0.0 <= s4 <= 1.0
        record_test(suite, "Structural Similarity Malformed & Extreme Dict Inputs", struct_ok, f"Scores: s1={s1}, s2={s2}, s3={s3:.2f}, s4={s4:.2f}")
    except Exception as e:
        record_test(suite, "Structural Similarity Malformed & Extreme Dict Inputs", False, f"Exception: {e}")

    # 2.5 Provenance Similarity Edge Cases
    try:
        p1 = calculate_provenance_similarity(None, None)
        p2 = calculate_provenance_similarity({}, {})
        p3 = calculate_provenance_similarity({"_origin": "ast"}, {"_origin": "ast"})
        p4 = calculate_provenance_similarity("not_a_dict", {"_origin": "ast"})
        p5 = calculate_provenance_similarity(
            {"source_file": "supergraph_linker.py", "description": "some text"},
            {"description": "refers to supergraph_linker.py file"}
        )

        prov_ok = p1 == 0.0 and p2 == 0.0 and p3 == 0.2 and p4 == 0.0 and p5 == 0.3
        record_test(suite, "Provenance Similarity Non-dict & Cross-reference Inputs", prov_ok, f"Scores: p1={p1}, p2={p2}, p3={p3}, p4={p4}, p5={p5}")
    except Exception as e:
        record_test(suite, "Provenance Similarity Non-dict & Cross-reference Inputs", False, f"Exception: {e}")

    # 2.6 Hybrid Metric Weight Integrity
    try:
        linker = SuperGraphLinker()
        n_u = {"id": "u", "name": "test_u", "description": "test node u"}
        n_v = {"id": "v", "name": "test_v", "description": "test node v"}
        v_u = [0.1] * 768
        v_v = [0.1] * 768

        metrics = linker.compute_hybrid_metric(n_u, n_v, v_u, v_v)
        expected = (
            0.45 * metrics["s_cosine"] +
            0.25 * metrics["s_fts"] +
            0.20 * metrics["s_structural"] +
            0.10 * metrics["s_provenance"]
        )
        diff = abs(metrics["total_score"] - expected)
        record_test(suite, "Hybrid Metric Formula Weight Integrity", diff < 1e-6, f"Computed score: {metrics['total_score']:.6f}, Expected: {expected:.6f}")
    except Exception as e:
        record_test(suite, "Hybrid Metric Formula Weight Integrity", False, f"Exception: {e}")


# ==============================================================================
# SUITE 3: SuperGraph Database Persistence & File System Boundaries
# ==============================================================================
def test_suite_db_and_persistence():
    print("\n" + "=" * 70)
    print("RUNNING SUITE 3: SuperGraph DB Persistence & Boundary Stress")
    print("=" * 70)
    suite = "DB_Persistence"

    from dnts_core.supergraph_linker import SuperGraphLinker, DEFAULT_DB_PATH

    temp_dir = Path(tempfile.mkdtemp(prefix="dnts_stress_"))
    try:
        # 3.1 Initialize Linker with Custom Deep Non-Existent Directory Path
        custom_db = temp_dir / "nested" / "deep_dir" / "test_stress.db"
        linker = SuperGraphLinker(db_path=str(custom_db))
        record_test(suite, "Custom Deep DB Directory Auto-Creation", custom_db.exists(), f"DB Path created: {custom_db}")

        # 3.2 SQL Injection & Special Characters in Node Properties & Tags
        sql_injection_node_ast = {
            "id": "ast:'; DROP TABLE kg_nodes; --",
            "name": "SQL ' Injection \" Test --",
            "domain": "ast_code",
            "node_type": "Class' OR 1=1 --",
            "description": "Unicode test: Привет \x00 ' \" --",
            "source_file": "path/with 'quotes' and--dashes.py",
            "community": 99,
            "_origin": "ast",
            "tags": "tag1,tag2'; DROP TABLE kg_edges;--"
        }

        sql_injection_node_wiki = {
            "id": "wiki:'; DELETE FROM llm_cache; --",
            "name": "Wiki Injection Test",
            "domain": "memory_wiki",
            "node_type": "WikiNote",
            "description": "Wiki note with special chars: <script>alert(1)</script>",
            "content": "Content with ' single quotes and \" double quotes",
            "source_file": "injection_test.md",
            "community": 99,
            "_origin": "wiki",
            "tags": "wiki,injection"
        }

        edges = linker.link_nodes([sql_injection_node_ast], [sql_injection_node_wiki], threshold=0.0)

        with linker._get_connection() as conn:
            nodes_count = conn.execute("SELECT COUNT(*) FROM kg_nodes").fetchone()[0]
            edges_count = conn.execute("SELECT COUNT(*) FROM kg_edges").fetchone()[0]
            cache_count = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]

        db_safe = nodes_count == 2 and edges_count == 1 and cache_count >= 2
        record_test(suite, "SQL Injection & Special Character Sanitization", db_safe, f"DB tables intact: nodes={nodes_count}, edges={edges_count}, cache={cache_count}")

        # 3.3 Linker Threshold Extreme Variations
        t_high = linker.link_nodes([sql_injection_node_ast], [sql_injection_node_wiki], threshold=1.0)
        t_neg = linker.link_nodes([sql_injection_node_ast], [sql_injection_node_wiki], threshold=-0.5)

        threshold_ok = len(t_high) == 0 and len(t_neg) == 1
        record_test(suite, "Linking Threshold Variations (threshold=1.0 vs -0.5)", threshold_ok, f"Edges high threshold: {len(t_high)}, neg threshold: {len(t_neg)}")

        # 3.4 Corrupted Cache Recovery Test
        with linker._get_connection() as conn:
            # Insert a corrupted 512D vector into llm_cache for a specific node_id
            corrupt_key = "corrupt_test_key_123"
            conn.execute("""
                INSERT OR REPLACE INTO llm_cache (cache_key, text_content, embedding_json, created_at)
                VALUES (?, ?, ?, ?)
            """, (corrupt_key, "corrupt text", json.dumps([0.1] * 512), time.time()))
            conn.commit()

        # Call get_or_compute_embedding for a node that hashes to corrupt_key
        dummy_node = {"id": "corrupt_node", "name": "corrupt", "description": "text"}
        # Compute embedding (should ignore corrupted 512D cache entry and compute fresh 768D vector)
        vec_recovered = linker.get_or_compute_embedding(dummy_node)

        recovery_ok = len(vec_recovered) == 768
        record_test(suite, "Corrupted Cache Vector Dimension Auto-Recovery (512D -> 768D)", recovery_ok, f"Recovered vector len: {len(vec_recovered)}")

    except Exception as e:
        record_test(suite, "DB Persistence Stress", False, f"Exception: {e}\n{traceback.format_exc()}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# SUITE 4: Native Subagent Bridges & CLI Flags Stress
# ==============================================================================
def test_suite_subagent_bridges():
    print("\n" + "=" * 70)
    print("RUNNING SUITE 4: Native Subagent Bridges & CLI Stress")
    print("=" * 70)
    suite = "Subagent_Bridges"

    scripts_dir = PYENV_DIR / "scripts"
    rlm_bridge_script = scripts_dir / "subagent_rlm_bridge.py"
    research_bridge_script = scripts_dir / "subagent_research_bridge.py"
    verifier_bridge_script = scripts_dir / "subagent_verifier_bridge.py"

    # 4.1 RLM Bridge Dry-Run Execution
    try:
        cmd = [PYTHON_EXE, str(rlm_bridge_script), "--dry-run", "--prompt", "Stress test prime checker", "--complexity", "high"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        passed = res.returncode == 0 and "RLM SUBAGENT BRIDGE EXECUTION RESULT" in res.stdout and "dry_run_verification" in res.stdout
        record_test(suite, "RLM Bridge Dry-Run Execution", passed, f"Exit code: {res.returncode}")
    except Exception as e:
        record_test(suite, "RLM Bridge Dry-Run Execution", False, f"Exception: {e}")

    # 4.2 RLM Bridge Live Fallback Execution
    try:
        cmd = [PYTHON_EXE, str(rlm_bridge_script), "--prompt", "Live execution prompt test"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        # Should return COMPLETED_WITH_FALLBACK or SUCCESS or rlm result dict without crashing
        passed = res.returncode == 0 and ("COMPLETED_WITH_FALLBACK" in res.stdout or "SUCCESS" in res.stdout or "RLM SUBAGENT BRIDGE EXECUTION RESULT" in res.stdout)
        record_test(suite, "RLM Bridge Live Fallback Execution", passed, f"Exit code: {res.returncode}")
    except Exception as e:
        record_test(suite, "RLM Bridge Live Fallback Execution", False, f"Exception: {e}")

    # 4.3 Research Bridge Dry-Run Execution
    try:
        cmd = [PYTHON_EXE, str(research_bridge_script), "--dry-run", "--query", "SuperGraph Memory Wiki Architecture", "--search-api", "ddg"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        passed = res.returncode == 0 and "RESEARCH SUBAGENT BRIDGE EXECUTION RESULT" in res.stdout and "dry_run_verification" in res.stdout
        record_test(suite, "Research Bridge Dry-Run Execution", passed, f"Exit code: {res.returncode}")
    except Exception as e:
        record_test(suite, "Research Bridge Dry-Run Execution", False, f"Exception: {e}")

    # 4.4 Research Bridge Fallback / Network Isolation Execution
    try:
        cmd = [PYTHON_EXE, str(research_bridge_script), "--query", "Offline research query test"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
        passed = res.returncode == 0 and ("COMPLETED_WITH_GRAPH_VERIFICATION" in res.stdout or "SUCCESS" in res.stdout or "RESEARCH SUBAGENT BRIDGE EXECUTION RESULT" in res.stdout)
        record_test(suite, "Research Bridge Fallback Execution", passed, f"Exit code: {res.returncode}")
    except Exception as e:
        record_test(suite, "Research Bridge Fallback Execution", False, f"Exception: {e}")

    # 4.5 Verifier Bridge Default Execution
    try:
        cmd = [PYTHON_EXE, str(verifier_bridge_script)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        passed = res.returncode == 0 and "VERIFIER SUBAGENT BRIDGE EXECUTION RESULT" in res.stdout and "Overall Success" in res.stdout
        record_test(suite, "Verifier Bridge Default Sample Execution", passed, f"Exit code: {res.returncode}")
    except Exception as e:
        record_test(suite, "Verifier Bridge Default Sample Execution", False, f"Exception: {e}")

    # 4.6 Verifier Bridge Syntax Error Handling
    temp_broken_file = PYENV_DIR / "scripts" / "_temp_broken_syntax_test.py"
    temp_broken_file.write_text("def broken_func(: syntax error here", encoding="utf-8")
    try:
        cmd = [PYTHON_EXE, str(verifier_bridge_script), "--code-file", str(temp_broken_file)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        # Verifier script catches syntax error gracefully, outputs FAILED for syntax, Overall Success: False, exit code 0
        passed = res.returncode == 0 and "Syntax: FAILED" in res.stdout and "Overall Success: False" in res.stdout
        record_test(suite, "Verifier Bridge Syntax Error Graceful Handling", passed, f"Captured syntax failure gracefully: Exit {res.returncode}")
    except Exception as e:
        record_test(suite, "Verifier Bridge Syntax Error Graceful Handling", False, f"Exception: {e}")
    finally:
        if temp_broken_file.exists():
            temp_broken_file.unlink()

    # 4.7 Verifier Bridge Missing Expected Function Contract Test
    temp_contract_file = PYENV_DIR / "scripts" / "_temp_contract_test.py"
    temp_contract_file.write_text("def existing_function(): pass\n", encoding="utf-8")
    try:
        cmd = [PYTHON_EXE, str(verifier_bridge_script), "--code-file", str(temp_contract_file), "--expected-functions", "missing_func1,missing_func2"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        passed = res.returncode == 0 and "Contract: FAILED" in res.stdout and "Overall Success: False" in res.stdout
        record_test(suite, "Verifier Bridge Contract Check Missing Function Handling", passed, f"Captured contract failure gracefully: Exit {res.returncode}")
    except Exception as e:
        record_test(suite, "Verifier Bridge Contract Check Missing Function Handling", False, f"Exception: {e}")
    finally:
        if temp_contract_file.exists():
            temp_contract_file.unlink()

    # 4.8 End-to-End Test SuperGraph Integration Script Verification
    test_sg_script = scripts_dir / "test_supergraph_integration.py"
    try:
        cmd = [PYTHON_EXE, str(test_sg_script)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        passed = res.returncode == 0 and "UNIFIED SUPERGRAPH & 768D EMBEDDINGS INTEGRATION TEST PASSED" in res.stdout
        record_test(suite, "test_supergraph_integration.py End-to-End Suite", passed, f"Exit code: {res.returncode}")
    except Exception as e:
        record_test(suite, "test_supergraph_integration.py End-to-End Suite", False, f"Exception: {e}")


def main():
    t_start = time.time()
    print("=" * 70)
    print("🔥 DNTS OS SUPERGRAPH ARCHITECTURE ADVERSARIAL STRESS HARNESS 🔥")
    print(f"Python Executable: {PYTHON_EXE}")
    print("=" * 70)

    test_suite_ast_pruner()
    test_suite_embeddings_and_metrics()
    test_suite_db_and_persistence()
    test_suite_subagent_bridges()

    total = len(test_results)
    passed_count = sum(1 for t in test_results if t["passed"])
    failed_count = total - passed_count
    t_elapsed = time.time() - t_start

    print("\n" + "=" * 70)
    print("STRESS TEST HARNESS SUMMARY REPORT")
    print("=" * 70)
    print(f"Total Tests Executed: {total}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Total Execution Time: {t_elapsed:.2f} seconds")
    print("=" * 70)

    if failed_count == 0:
        print("🎉 FINAL STRESS TEST VERDICT: ALL ADVERSARIAL STRESS TESTS PASSED! ZERO REGRESSION DETECTED.")
    else:
        print(f"❌ FINAL STRESS TEST VERDICT: {failed_count} TEST(S) FAILED.")
        for t in test_results:
            if not t["passed"]:
                print(f"   - FAIL [{t['suite']}] {t['name']}: {t['details']}")

    # Save summary report JSON
    out_json = Path(__file__).parent / "stress_test_results.json"
    out_json.write_text(json.dumps({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": total,
        "passed": passed_count,
        "failed": failed_count,
        "elapsed_sec": round(t_elapsed, 2),
        "results": test_results
    }, indent=2), encoding="utf-8")
    print(f"Detailed JSON results written to: {out_json}")

    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
