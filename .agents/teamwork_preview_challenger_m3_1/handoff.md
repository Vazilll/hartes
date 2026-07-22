# Empirical Stress-Test Report: Milestone 3 (R2 SuperGraph & 768D Embeddings Integration)

**Target**: DNTS OS SuperGraph Architecture (R2 Integration)  
**Evaluator**: Challenger Agent (`teamwork_preview_challenger_m3_1`)  
**Working Directory**: `C:\vazus\.agents\teamwork_preview_challenger_m3_1`  
**Execution Timestamp**: 2026-07-22T14:23:00Z  

---

## 1. Observation

### Baseline Integration Execution
- **Command**: `C:\vazus\pyenv\.venv\Scripts\python.exe C:\vazus\pyenv\scripts\test_supergraph_integration.py`
- **Output**:
  ```text
  [Embedder] Notice: sentence-transformers not loaded (No module named 'sentence_transformers'). Using deterministic 768 vector.
  ============================================================
  🧪 UNIFIED SUPERGRAPH & 768D EMBEDDINGS INTEGRATION TEST
  ============================================================
  1. Testing Google Gemini 768D Embedder...
     - Generated vector length: 768
     ✅ 768D Vector Dimension Verified.
  2. Testing 4-Component Hybrid Metric Functions...
     - Total Hybrid Score S(u, v): 0.5680
     ✅ 4-Component Hybrid Metric Verified.
  3. Testing SuperGraph Linking & Database Persistence...
     - Loaded AST nodes: 972
     - Loaded Memory Wiki notes: 6
     - Edges created/linked: 4855
  4. Verifying SQLite Database Insertions in vazus.db...
     - Found edge in kg_edges: cleardb -> wiki:AI_Lessons_and_Mistakes (strength: 0.3905)
     - Verified kg_nodes entry: id='cleardb', embedding_dim=768
     - Verified llm_cache entry: key='a9b0dc46e0226970...', embedding_dim=768
  ```

### Codebase Inspection (`C:\vazus\pyenv\dnts_core\supergraph_linker.py`)
- **`calculate_cosine_similarity`** (lines 34-48):
  ```python
  def calculate_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
      if not vec_a or not vec_b or len(vec_a) != len(vec_b):
          return 0.0
      dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
      norm_a = math.sqrt(sum(a * a for a in vec_a))
      norm_b = math.sqrt(sum(b * b for b in vec_b))
      if norm_a == 0.0 or norm_b == 0.0:
          return 0.0
      sim = dot_product / (norm_a * norm_b)
      return max(0.0, min(1.0, float(sim)))
  ```
- **`calculate_provenance_similarity`** (lines 108-110):
  ```python
  def calculate_provenance_similarity(node_a: Dict[str, Any], node_b: Dict[str, Any]) -> float:
      score = 0.5  # Baseline DNTS repository provenance match
  ```
- **`_init_db` Table Schema** (lines 166-174):
  ```sql
  CREATE TABLE IF NOT EXISTS kg_edges (
      source_id TEXT,
      target_id TEXT,
      relation TEXT,
      strength REAL,
      properties TEXT,
      PRIMARY KEY (source_id, target_id, relation)
  )
  ```

### Empirical Stress Harness Results (`stress_test_supergraph.py` & `test_extra_edge_cases.py`)
- **Test 1.4 (NaN Vector Handling)**: Passed vector containing `float('nan')` to `calculate_cosine_similarity`. Returned `1.0` (maximum similarity score).
- **Test 2.2 (Provenance Baseline Bias Audit)**: Evaluated two completely unrelated nodes with distinct file names, tags, and origins. `calculate_provenance_similarity` returned `0.5`.
- **Test 3.1-3.3 (Query & Linking Scalability)**:
  - 10 AST x 5 Wiki (50 pairs): 0.0620s (807 pair-evals/sec)
  - 50 AST x 10 Wiki (500 pairs): 0.2752s (1,816 pair-evals/sec)
  - 100 AST x 20 Wiki (2,000 pairs): 0.8354s (2,393 pair-evals/sec)
- **Test 4.1 (SQL Injection Resilience)**: Node IDs containing `' DROP TABLE kg_edges; --` were safely bound via parameterized query `(?, ?, ?, ?, ?)`. Table remained intact.
- **Test 4.3 & Extra (SQLite Constraint Vulnerability)**:
  - SQLite stored `float('nan')` strength without `CHECK` constraint validation.
  - SQLite accepted multiple rows with `NULL` as `source_id` in `PRIMARY KEY (source_id, target_id, relation)` because columns lacked explicit `NOT NULL` clauses.

---

## 2. Logic Chain

1. **Cosine Similarity NaN Fallacy**:
   - In `calculate_cosine_similarity`, when a vector contains `NaN` values, `dot_product` and `norm_b` evaluate to `float('nan')`.
   - `sim = dot_product / (norm_a * norm_b)` evaluates to `nan`.
   - The clamping code calls `min(1.0, float('nan'))`.
   - In Python, IEEE 754 float comparison `nan < 1.0` returns `False`. The `min(1.0, nan)` function returns the first argument `1.0` when comparison fails.
   - `max(0.0, 1.0)` then evaluates to `1.0`.
   - **Conclusion**: Corrupted, zero-divided, or uninitialized vectors with `NaN` components are falsely evaluated as 100% identical (`1.0` similarity score).

2. **Provenance Baseline Distortion (+0.05 Global Score Inflation)**:
   - In `calculate_provenance_similarity`, `score = 0.5` is initialized unconditionally as a default baseline for all nodes.
   - In `compute_hybrid_metric`, `total_score` applies weight `0.10` to `s_provenance`: `0.10 * 0.5 = 0.05`.
   - **Conclusion**: Every single pairwise comparison in the SuperGraph receives a mandatory `+0.05` score bonus regardless of relationship. Given the default linking threshold `0.15`, any pair needs only `0.10` from the remaining components (cosine, FTS, structural) to form a persisted edge in `kg_edges`.

3. **SQLite Constraints & Primary Key Uniqueness Breach**:
   - SQLite allows `NULL` values in `PRIMARY KEY` columns unless `NOT NULL` is explicitly defined on each column (`source_id TEXT NOT NULL`).
   - Inserting nodes with uninitialized or `None` node IDs creates duplicate rows with `source_id = NULL` in `kg_edges` despite the primary key declaration.
   - Inserting `float('nan')` into `strength REAL` is accepted without database error because there is no `CHECK (strength >= 0.0 AND strength <= 1.0)` column constraint.

4. **Performance & Scalability Dynamics**:
   - `get_or_compute_embedding` instantiates a new database connection (`self._get_connection()`) on every single node lookup.
   - For $N$ AST nodes and $M$ Wiki notes, this opens and closes $2 \times (N + M)$ connections.
   - Pairwise linking complexity is $O(N \times M)$. At 2,000 evaluations (100 AST x 20 Wiki), total execution time is ~0.83s. Extrapolating to 10,000 AST nodes x 100 Wiki notes ($1,000,000$ pairs), execution will take ~400 seconds (~6.6 minutes) sequentially.

---

## 3. Caveats

- **Sentence Transformers Availability**: The tests were executed with the deterministic 768-dim vector fallback (`UnifiedGoogleEmbedder`), as `sentence-transformers` was not installed in the local virtualenv. Real neural models could produce non-deterministic float edge cases.
- **Single-Threaded Execution**: Database concurrency under multi-threaded parallel transactions was not stress-tested, though SQLite WAL mode (`PRAGMA journal_mode=WAL`) was verified in schema setup.

---

## 4. Conclusion

The R2 implementation (`supergraph_linker.py` & `test_supergraph_integration.py`) successfully passes its baseline integration workflow, generates 768D vectors, computes 4-component hybrid scores, and escapes standard SQL injections.

However, empirical stress testing revealed **4 critical/medium findings**:

1. **[HIGH SEVERITY BUG] Cosine Similarity NaN Bug**:
   `calculate_cosine_similarity` returns `1.0` (maximum similarity) when a vector contains `NaN` values due to Python's `min(1.0, float('nan'))` behavior.
   *Fix Recommendation*: Add explicit NaN check:
   ```python
   if any(math.isnan(x) for x in vec_a) or any(math.isnan(x) for x in vec_b):
       return 0.0
   ```
2. **[MEDIUM SEVERITY FLAW] Unconditional Provenance Baseline Score**:
   `calculate_provenance_similarity` defaults to `score = 0.5` for all node pairs, artificially inflating total score by `+0.05` across the entire graph.
   *Fix Recommendation*: Initialize baseline `score = 0.0`, adding score only when origin/commit/file matches exist.
3. **[MEDIUM SEVERITY FLAW] Missing SQLite Schema Constraints**:
   `kg_edges` allows `NULL` values in primary key columns and accepts `NaN` floats in `strength`.
   *Fix Recommendation*: Update schema definition:
   ```sql
   CREATE TABLE IF NOT EXISTS kg_edges (
       source_id TEXT NOT NULL,
       target_id TEXT NOT NULL,
       relation TEXT NOT NULL,
       strength REAL NOT NULL CHECK (strength >= 0.0 AND strength <= 1.0),
       properties TEXT,
       PRIMARY KEY (source_id, target_id, relation)
   );
   ```
4. **[PERFORMANCE OPTIMIZATION] Connection Overhead in Embedding Cache**:
   `get_or_compute_embedding` creates and closes SQLite connections repeatedly during batch processing.
   *Fix Recommendation*: Reuse a single database connection or pass transaction context during batch linking.

---

## 5. Verification Method

To independently verify these empirical findings:

1. **Run the baseline integration test**:
   ```powershell
   C:\vazus\pyenv\.venv\Scripts\python.exe C:\vazus\pyenv\scripts\test_supergraph_integration.py
   ```
2. **Run the empirical stress test suite**:
   ```powershell
   C:\vazus\pyenv\.venv\Scripts\python.exe C:\vazus\.agents\teamwork_preview_challenger_m3_1\stress_test_supergraph.py
   ```
3. **Verify Python `min(1.0, nan)` and SQLite NULL primary key proof**:
   ```powershell
   C:\vazus\pyenv\.venv\Scripts\python.exe C:\vazus\.agents\teamwork_preview_challenger_m3_1\test_extra_edge_cases.py
   ```
4. **Inspect JSON test results**:
   Check `C:\vazus\.agents\teamwork_preview_challenger_m3_1\stress_test_results.json`.
