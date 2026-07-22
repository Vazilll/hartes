"""
Empirical Stress Test Suite for DNTS OS SuperGraph & 768D Embeddings Integration.
Location: C:\\dnts\\.agents\\teamwork_preview_challenger_m3_1\\stress_test_supergraph.py
"""

import os
import sys
import time
import math
import json
import sqlite3
import tempfile
import traceback
from pathlib import Path
from typing import List, Dict, Any

# Add pyenv to sys.path
PYENV_DIR = Path("C:/dnts/pyenv")
if str(PYENV_DIR) not in sys.path:
    sys.path.insert(0, str(PYENV_DIR))

from dnts_core.supergraph_linker import (
    SuperGraphLinker,
    calculate_cosine_similarity,
    calculate_fts_similarity,
    calculate_structural_similarity,
    calculate_provenance_similarity,
)
from dnts_core.embeddings import UnifiedGoogleEmbedder

TEST_RESULTS = []

def record_test(name: str, passed: bool, details: str, severity: str = "INFO"):
    TEST_RESULTS.append({
        "name": name,
        "passed": passed,
        "details": details,
        "severity": severity
    })
    status = "[PASS]" if passed else f"[FAIL - {severity}]"
    print(f"{status}: {name}\n  -> {details}")

print("============================================================")
print("EMPIRICAL STRESS TEST SUITE: SUPERGRAPH LINKER (M3 / R2)")
print("============================================================")

# -------------------------------------------------------------------
# CATEGORY 1: VECTOR DIMENSION EDGE CASES
# -------------------------------------------------------------------
print("\n--- Category 1: Vector Dimension & Cosine Similarity Edge Cases ---")

# 1.1 Vector Dimension Mismatch
v768_a = [0.1] * 768
v768_b = [0.2] * 768
v384 = [0.1] * 384
v_empty = []

sim_mismatch = calculate_cosine_similarity(v768_a, v384)
record_test(
    "1.1 Vector Mismatch (768D vs 384D)",
    sim_mismatch == 0.0,
    f"Returned cosine similarity = {sim_mismatch} (expected 0.0)"
)

sim_empty = calculate_cosine_similarity(v768_a, v_empty)
record_test(
    "1.2 Vector Mismatch (768D vs Empty Vector)",
    sim_empty == 0.0,
    f"Returned cosine similarity = {sim_empty} (expected 0.0)"
)

# 1.3 Zero Vectors
v_zero_a = [0.0] * 768
v_zero_b = [0.0] * 768
sim_zero = calculate_cosine_similarity(v_zero_a, v_zero_b)
record_test(
    "1.3 Zero Vectors (768D zeros vs 768D zeros)",
    sim_zero == 0.0,
    f"Returned cosine similarity = {sim_zero} (expected 0.0 without ZeroDivisionError)"
)

# 1.4 NaN and Infinity values in vectors
v_nan = [0.1] * 767 + [float('nan')]
v_inf = [0.1] * 767 + [float('inf')]

try:
    sim_nan = calculate_cosine_similarity(v768_a, v_nan)
    is_nan = math.isnan(sim_nan)
    record_test(
        "1.4 NaN Vector Handling",
        not is_nan and sim_nan >= 0.0 and sim_nan <= 1.0,
        f"Returned similarity = {sim_nan} (math.isnan={is_nan}). Vulnerability: NaN propagates to similarity score!",
        severity="HIGH" if is_nan else "INFO"
    )
except Exception as e:
    record_test("1.4 NaN Vector Handling", False, f"Unhandled exception: {e}", severity="HIGH")

try:
    sim_inf = calculate_cosine_similarity(v768_a, v_inf)
    is_nan_inf = math.isnan(sim_inf)
    record_test(
        "1.5 Inf Vector Handling",
        not is_nan_inf and sim_inf >= 0.0 and sim_inf <= 1.0,
        f"Returned similarity = {sim_inf} (math.isnan={is_nan_inf}). Vulnerability: Inf propagates to similarity score!",
        severity="HIGH" if is_nan_inf else "INFO"
    )
except Exception as e:
    record_test("1.5 Inf Vector Handling", False, f"Unhandled exception: {e}", severity="HIGH")

# 1.6 Overflow in norm calculation
v_huge = [1e200] * 768
try:
    sim_huge = calculate_cosine_similarity(v_huge, v_huge)
    record_test(
        "1.6 Overflow in Norm Calculation (1e200)",
        sim_huge == 1.0,
        f"Returned similarity = {sim_huge} (expected 1.0)",
        severity="MEDIUM" if sim_huge != 1.0 else "INFO"
    )
except OverflowError as oe:
    record_test("1.6 Overflow in Norm Calculation (1e200)", False, f"OverflowError raised: {oe}", severity="MEDIUM")

# 1.7 Cached embedding with invalid JSON or wrong dimensions in DB
temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
temp_db_path = temp_db_file.name
temp_db_file.close()

try:
    linker = SuperGraphLinker(db_path=temp_db_path)
    bad_node = {
        "id": "corrupt_node_1",
        "name": "Corrupt Node",
        "description": "Node with 384D vector in cache"
    }
    text_content = f"{bad_node['name']} {bad_node['description']} "
    import hashlib
    cache_key = hashlib.sha256(f"{bad_node['id']}:{text_content[:2000]}".encode("utf-8")).hexdigest()
    
    with linker._get_connection() as conn:
        conn.execute("INSERT INTO llm_cache (cache_key, text_content, embedding_json, created_at) VALUES (?, ?, ?, ?)",
                     (cache_key, text_content, json.dumps([0.5]*384), time.time()))
        conn.commit()

    vec_retrieved = linker.get_or_compute_embedding(bad_node)
    record_test(
        "1.7 Corrupted Cache Dimension Fallback (384D in cache for 768D embedder)",
        len(vec_retrieved) == 768,
        f"Retrieved vector length = {len(vec_retrieved)} (successfully ignored 384D cache entry)"
    )
except Exception as e:
    record_test("1.7 Corrupted Cache Dimension Fallback", False, f"Error: {e}", severity="HIGH")

# -------------------------------------------------------------------
# CATEGORY 2: METRIC WEIGHT BOUNDARY CONDITIONS & COMPONENT EDGE CASES
# -------------------------------------------------------------------
print("\n--- Category 2: Metric Weight & Component Score Boundary Conditions ---")

# 2.1 Test None / Missing attributes in nodes
node_none_a = {"id": "n1", "name": None, "description": None, "tags": None, "community": None}
node_none_b = {"id": "n2", "name": None, "description": None, "tags": None, "community": None}

try:
    score_fts_none = calculate_fts_similarity(str(node_none_a.get("name") or ""), str(node_none_b.get("name") or ""))
    score_struct_none = calculate_structural_similarity(node_none_a, node_none_b)
    score_prov_none = calculate_provenance_similarity(node_none_a, node_none_b)
    record_test(
        "2.1 Node Attributes as None / Null",
        True,
        f"Handled cleanly: fts={score_fts_none}, struct={score_struct_none}, prov={score_prov_none}"
    )
except Exception as e:
    record_test("2.1 Node Attributes as None / Null", False, f"Exception with None attrs: {e}", severity="HIGH")

# 2.2 Provenance Similarity Baseline Bias Audit
unrelated_a = {"id": "ast:func_foo", "name": "foo", "source_file": "a.py", "domain": "domain_a"}
unrelated_b = {"id": "wiki:unrelated_note", "name": "bar", "source_file": "b.md", "domain": "domain_b"}
prov_score = calculate_provenance_similarity(unrelated_a, unrelated_b)
record_test(
    "2.2 Provenance Baseline Score Bias",
    prov_score < 0.5,
    f"Unrelated nodes provenance score = {prov_score}. Flaw: Baseline hardcoded to 0.5 (+0.05 bonus to total score for ALL node pairs)",
    severity="MEDIUM"
)

# 2.3 Boundary values: Extreme long text string (100 KB text)
huge_text_a = "func_test_name " * 5000
huge_text_b = "func_test_name " * 5000
t0 = time.time()
fts_huge = calculate_fts_similarity(huge_text_a, huge_text_b)
t_fts = time.time() - t0
record_test(
    "2.3 Large Text Input to FTS Similarity (100KB input)",
    fts_huge == 1.0 and t_fts < 0.5,
    f"FTS score = {fts_huge}, execution time = {t_fts:.4f}s"
)

# 2.4 Hybrid Metric Sum Bounds [0.0, 1.0]
node_full_a = {"id": "a", "name": "test", "description": "test desc", "community": 1, "tags": "test", "_origin": "ast", "source_file": "test.py"}
node_full_b = {"id": "b", "name": "test", "description": "test desc", "community": 1, "tags": "test", "_origin": "ast", "source_file": "test.py"}
metrics_max = linker.compute_hybrid_metric(node_full_a, node_full_b, v768_a, v768_a)

record_test(
    "2.4 Hybrid Score Bounds Check (Max scenario)",
    0.0 <= metrics_max["total_score"] <= 1.0,
    f"Total score = {metrics_max['total_score']} (components: cosine={metrics_max['s_cosine']}, fts={metrics_max['s_fts']}, struct={metrics_max['s_structural']}, prov={metrics_max['s_provenance']})"
)

# -------------------------------------------------------------------
# CATEGORY 3: DATABASE QUERY PERFORMANCE & SCALABILITY
# -------------------------------------------------------------------
print("\n--- Category 3: Database Query Performance & Scalability Benchmark ---")

def benchmark_linker_scaling(num_ast: int, num_wiki: int):
    ast_nodes = []
    for i in range(num_ast):
        ast_nodes.append({
            "id": f"ast:node_{i}",
            "name": f"func_process_{i}",
            "domain": "ast_code",
            "node_type": "Function",
            "description": f"AST node processing function {i} in core engine module.",
            "source_file": f"dnts_core/module_{i % 10}.py",
            "community": i % 5,
            "_origin": "ast",
            "tags": f"ast,code,module_{i % 10}"
        })
    
    wiki_nodes = []
    for j in range(num_wiki):
        wiki_nodes.append({
            "id": f"wiki:note_{j}",
            "name": f"Architecture Note {j}",
            "domain": "memory_wiki",
            "node_type": "WikiNote",
            "description": f"Memory wiki note {j} discussing architectural decisions.",
            "content": f"Architectural guideline {j} for module_{j % 10}.",
            "source_file": f"Note_{j}.md",
            "community": j % 5,
            "_origin": "wiki",
            "tags": f"wiki,memory,note_{j}"
        })
        
    t_start = time.time()
    edges = linker.link_nodes(ast_nodes, wiki_nodes, threshold=0.15)
    t_elapsed = time.time() - t_start
    total_pairs = num_ast * num_wiki
    qps = total_pairs / t_elapsed if t_elapsed > 0 else 0
    return t_elapsed, len(edges), qps

# Optimized scales for subsecond execution
scales = [(10, 5), (50, 10), (100, 20)]
for num_ast, num_wiki in scales:
    t_el, e_count, qps = benchmark_linker_scaling(num_ast, num_wiki)
    record_test(
        f"3. Benchmark Linker Scale ({num_ast} AST x {num_wiki} Wiki = {num_ast*num_wiki} pairs)",
        t_el < 5.0,
        f"Linked {e_count} edges in {t_el:.4f}s ({qps:.1f} pair-evals/sec)"
    )

# Check index presence and usage in SQLite
with linker._get_connection() as conn:
    indices = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    index_names = {r["name"] for r in indices}
    has_nodes_domain = "idx_kg_nodes_domain" in index_names
    has_edges_source = "idx_kg_edges_source" in index_names
    has_edges_target = "idx_kg_edges_target" in index_names

record_test(
    "3.4 SQLite Indices Verification",
    has_nodes_domain and has_edges_source and has_edges_target,
    f"Found indices: {index_names}"
)

# -------------------------------------------------------------------
# CATEGORY 4: SQLITE kg_edges TABLE INSERTION & RESILIENCE
# -------------------------------------------------------------------
print("\n--- Category 4: SQLite kg_edges Table Insertion Handling & Edge Cases ---")

# 4.1 SQL Injection / Special Characters in node IDs and relation
sql_injection_edge = {
    "source_id": "ast:node'; DROP TABLE kg_edges; --",
    "target_id": "wiki:note' OR '1'='1",
    "relation": "SUPERGRAPH' --",
    "strength": 0.85,
    "properties": json.dumps({"test": "quote's test"})
}

try:
    with linker._get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO kg_edges (source_id, target_id, relation, strength, properties)
            VALUES (?, ?, ?, ?, ?)
        """, (sql_injection_edge["source_id"], sql_injection_edge["target_id"], sql_injection_edge["relation"],
              sql_injection_edge["strength"], sql_injection_edge["properties"]))
        conn.commit()

        count = conn.execute("SELECT COUNT(*) as cnt FROM kg_edges WHERE source_id = ?", (sql_injection_edge["source_id"],)).fetchone()["cnt"]
        table_check = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='kg_edges'").fetchone()[0]

    record_test(
        "4.1 SQL Injection Resilience in kg_edges",
        count == 1 and table_check == 1,
        f"SQL Injection string safely escaped. Table exists (check={table_check}), inserted row count={count}"
    )
except Exception as e:
    record_test("4.1 SQL Injection Resilience in kg_edges", False, f"Database error on SQL injection test: {e}", severity="HIGH")

# 4.2 Primary Key Duplicate Constraint Handling
try:
    with linker._get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO kg_edges VALUES (?, ?, ?, ?, ?)",
                     ("src1", "tgt1", "REL1", 0.5, "{}"))
        conn.execute("INSERT OR REPLACE INTO kg_edges VALUES (?, ?, ?, ?, ?)",
                     ("src1", "tgt1", "REL1", 0.95, '{"updated": true}'))
        conn.commit()

        row = conn.execute("SELECT strength, properties FROM kg_edges WHERE source_id='src1' AND target_id='tgt1'").fetchone()
    
    record_test(
        "4.2 Primary Key (source, target, relation) Upsert Handling",
        row["strength"] == 0.95 and "updated" in row["properties"],
        f"Upsert successfully updated strength to {row['strength']} and properties to {row['properties']}"
    )
except Exception as e:
    record_test("4.2 Primary Key Upsert Handling", False, f"Upsert failed: {e}", severity="HIGH")

# 4.3 SQLite Float NaN in Strength column
try:
    with linker._get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO kg_edges VALUES (?, ?, ?, ?, ?)",
                     ("src_nan", "tgt_nan", "REL_NAN", float('nan'), "{}"))
        conn.commit()
        row_nan = conn.execute("SELECT strength FROM kg_edges WHERE source_id='src_nan'").fetchone()
        retrieved_strength = row_nan["strength"]
        is_retrieved_nan = retrieved_strength is None or (isinstance(retrieved_strength, float) and math.isnan(retrieved_strength))
    
    record_test(
        "4.3 SQLite Insertion of NaN Strength Value",
        not is_retrieved_nan,
        f"Retrieved strength for NaN input: {retrieved_strength}. SQLite stores NaN as float NaN without validation!",
        severity="MEDIUM"
    )
except Exception as e:
    record_test("4.3 SQLite Insertion of NaN Strength Value", False, f"Exception: {e}", severity="MEDIUM")

# 4.4 Extremely Long Primary Keys and Properties Payload
long_id = "A" * 5000
long_prop = json.dumps({"payload": "B" * 50000})

try:
    with linker._get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO kg_edges VALUES (?, ?, ?, ?, ?)",
                     (long_id, "tgt_long", "REL_LONG", 0.5, long_prop))
        conn.commit()

        row_long = conn.execute("SELECT LENGTH(source_id) as l_src, LENGTH(properties) as l_prop FROM kg_edges WHERE source_id=?", (long_id,)).fetchone()
    
    record_test(
        "4.4 Extremely Long Primary Keys (5KB ID, 50KB Payload)",
        row_long["l_src"] == 5000 and row_long["l_prop"] >= 50000,
        f"Successfully inserted and retrieved long keys: source_id len={row_long['l_src']}, properties len={row_long['l_prop']}"
    )
except Exception as e:
    record_test("4.4 Extremely Long Primary Keys", False, f"Exception: {e}", severity="HIGH")


# Cleanup temp DB
try:
    os.remove(temp_db_path)
except Exception:
    pass

# -------------------------------------------------------------------
# SUMMARY OF FINDINGS
# -------------------------------------------------------------------
print("\n============================================================")
print("STRESS TEST RESULTS SUMMARY")
print("============================================================")

passed_count = sum(1 for r in TEST_RESULTS if r["passed"])
failed_count = sum(1 for r in TEST_RESULTS if not r["passed"])
high_sev_count = sum(1 for r in TEST_RESULTS if not r["passed"] and r["severity"] == "HIGH")
med_sev_count = sum(1 for r in TEST_RESULTS if not r["passed"] and r["severity"] == "MEDIUM")

print(f"Total Tests Run: {len(TEST_RESULTS)}")
print(f"Passed: {passed_count}")
print(f"Failed: {failed_count} (High Severity: {high_sev_count}, Medium Severity: {med_sev_count})")

if failed_count > 0:
    print("\n--- Failed Stress Tests / Confirmed Bugs ---")
    for r in TEST_RESULTS:
        if not r["passed"]:
            print(f"[FAIL - {r['severity']}] {r['name']}: {r['details']}")

# Write results to json file for reference
results_path = Path("C:/dnts/.agents/teamwork_preview_challenger_m3_1/stress_test_results.json")
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(TEST_RESULTS, f, indent=2)

print(f"\nDetailed JSON report written to: {results_path}")
