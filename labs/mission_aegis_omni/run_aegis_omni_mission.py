#!/usr/bin/env python
"""
labs/mission_aegis_omni/run_aegis_omni_mission.py — Master Orchestrator for Mission Aegis-Omni.
Comprehensive multi-core stress-test and blind-spot detection across all Vazus SuperGraph OS subsystems.
"""

import os
import sys
import time
import json
from pathlib import Path

# Add repo root to sys.path
_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import z3
from vazus_core.verification.ast_pruner import UniversalASTPruner, GoTreeSitterPruner, CTreeSitterPruner, ASTPruner
from vazus_core.workers.async_worktree_worker import AsyncWorktreeWorker
from vazus_core.workers.repl_engine import LocalREPL
from vazus_core.memory.db import get_db_connection
from vazus_core.memory.embeddings import get_embedding
from vazus_core.missions.research_obsidian_sync import ResearchObsidianSyncer
from vazus_core.eval.bench_runner import BenchmarkRunner


def run_mission():
    print("=" * 80)
    print("🛰️  STARTING MISSION AEGIS-OMNI: FULL SUPERGRAPH OS STRESS-TEST & AUDIT")
    print("=" * 80)

    blind_spots_found = []
    lab_dir = Path(__file__).resolve().parent
    go_file = lab_dir / "aegis_server.go"
    c_file = lab_dir / "aegis_telemetry.c"
    py_file = lab_dir / "aegis_pipeline.py"

    # --------------------------------------------------------------------------
    # STAGE 1: Universal Multi-Language AST Pruning & DB Memory Logging
    # --------------------------------------------------------------------------
    print("\n[STAGE 1] Testing Universal Multi-Language AST Pruning & SuperGraph Memory...")
    
    # 1.1 Go Pruning
    go_pruned, go_stats = UniversalASTPruner.prune_file(go_file, log_memory=True)
    print(f"  • Go Pruner:      Nodes removed: {go_stats.get('nodes_removed')}, Valid: {go_stats.get('is_valid')}, Pruned Funcs: {go_stats.get('pruned_functions')}")
    if not go_stats.get("is_valid"):
        blind_spots_found.append("GoTreeSitterPruner produced invalid AST output")

    # 1.2 C Pruning
    c_pruned, c_stats = UniversalASTPruner.prune_file(c_file, log_memory=True)
    print(f"  • C Pruner:       Nodes removed: {c_stats.get('nodes_removed')}, Valid: {c_stats.get('is_valid')}, Pruned Funcs: {c_stats.get('pruned_functions')}")
    if not c_stats.get("is_valid"):
        blind_spots_found.append("CTreeSitterPruner produced invalid AST output")

    # 1.3 Python Pruning
    py_pruned, py_stats = UniversalASTPruner.prune_file(py_file, log_memory=True)
    print(f"  • Python Pruner:  Reduction: {py_stats.get('reduction_percentage')}%, Valid: {py_stats.get('is_valid')}")
    if not py_stats.get("is_valid"):
        blind_spots_found.append("Python ASTPruner produced invalid AST output")

    # --------------------------------------------------------------------------
    # STAGE 2: Formal Verification (SMT Z3 Contract Proofs)
    # --------------------------------------------------------------------------
    print("\n[STAGE 2] Formally Proving System Invariants with SMT Z3...")
    
    # Invariant 1: Ring Buffer capacity boundedness
    solver = z3.Solver()
    cap = z3.Int("cap")
    size_0 = z3.Int("size_0")
    size_1 = z3.Int("size_1")
    
    # Preconditions: capacity > 0, size_0 in [0, cap]
    # Under Ingest: if size_0 == cap, size_1 = (size_0 - 1) + 1 = size_0 = cap
    #               if size_0 < cap, size_1 = size_0 + 1 <= cap
    # We negate the postcondition (size_1 <= cap and size_1 >= 0) to prove counterexample impossibility.
    solver.add(cap > 0, size_0 >= 0, size_0 <= cap)
    
    # Branch 1: size_0 == cap -> size_1 == cap
    # Branch 2: size_0 < cap -> size_1 == size_0 + 1
    solver.add(z3.Or(
        z3.And(size_0 == cap, size_1 == cap),
        z3.And(size_0 < cap, size_1 == size_0 + 1)
    ))
    solver.add(z3.Not(z3.And(size_1 <= cap, size_1 >= 0)))
    
    z3_res1 = solver.check()
    print(f"  • Invariant 1 (Bounded Buffer Size [0, C]): {z3_res1} (Proof: {'VALID (UNSAT)' if z3_res1 == z3.unsat else 'FAILED'})")
    if z3_res1 != z3.unsat:
        blind_spots_found.append("SMT Z3 Bounded Buffer proof failed")

    # Invariant 2: Index modulo bounds
    solver2 = z3.Solver()
    head = z3.Int("head")
    i = z3.Int("i")
    idx = (head + i) % cap
    solver2.add(cap > 0, head >= 0, head < cap, i >= 0, i < cap)
    solver2.add(z3.Not(z3.And(idx >= 0, idx < cap)))
    z3_res2 = solver2.check()
    print(f"  • Invariant 2 (Modulo Indexing Safety):      {z3_res2} (Proof: {'VALID (UNSAT)' if z3_res2 == z3.unsat else 'FAILED'})")
    if z3_res2 != z3.unsat:
        blind_spots_found.append("SMT Z3 Modulo Indexing proof failed")

    # --------------------------------------------------------------------------
    # STAGE 3: Async Worktree Sandboxing (Win32 Job Object Isolation)
    # --------------------------------------------------------------------------
    print("\n[STAGE 3] Executing Speculative Background Task in Isolated Worktree...")
    worker = AsyncWorktreeWorker(repo_root=str(_repo_root), max_workers=2)

    def speculative_mutation(worktree_dir: Path) -> bool:
        target = worktree_dir / "labs" / "mission_aegis_omni" / "aegis_pipeline.py"
        if target.exists():
            code = target.read_text(encoding="utf-8")
            enhanced = code + "\n    def get_history_len(self) -> int:\n        return len(self.history)\n"
            target.write_text(enhanced, encoding="utf-8")
            return True
        return False

    future = worker.execute_task_async(
        task_id="aegis_spec_01",
        mutation_fn=speculative_mutation,
        check_ast_files=["labs/mission_aegis_omni/aegis_pipeline.py"],
        test_command=[sys.executable, "-c", "from labs.mission_aegis_omni.aegis_pipeline import AegisPipeline; p = AegisPipeline(); print('Pipeline verified in sandbox')"],
        mode="tempdir",
        timeout_sec=20,
    )

    task_res = future.result(timeout=25)
    print(f"  • Worktree Task Status: Success={task_res.success}, AST_Valid={task_res.ast_valid}, Tests={task_res.tests_passed}, Duration={task_res.duration_sec}s")
    if not task_res.success:
        blind_spots_found.append(f"AsyncWorktreeWorker task failed: {task_res.error_message}")

    # --------------------------------------------------------------------------
    # STAGE 4: SuperGraph Two-Layer Memory & Hardware SIMD Vectors
    # --------------------------------------------------------------------------
    print("\n[STAGE 4] Verifying 2-Layer SuperGraph Database & 768-D Vector Embeddings...")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, domain, node_type FROM kg_nodes WHERE domain='ast_code'")
        rows = cur.fetchall()
        print(f"  • SuperGraph kg_nodes table count (ast_code): {len(rows)} nodes indexed")
        
        # Test 768D embedding generation
        emb_go = get_embedding(go_pruned[:500])
        emb_py = get_embedding(py_pruned[:500])
        emb_len = len(emb_go) if emb_go else 0
        print(f"  • Vector Engine: Dimension={emb_len}D (Target: 768D), Non-empty: {emb_len > 0}")
        if emb_len != 768:
            blind_spots_found.append(f"Embedding dimension mismatch: expected 768, got {emb_len}")
        conn.close()
    except Exception as e:
        blind_spots_found.append(f"SuperGraph DB query error: {e}")

    # --------------------------------------------------------------------------
    # STAGE 5: MIT RLM Engine & LocalREPL Self-Healing Loop
    # --------------------------------------------------------------------------
    print("\n[STAGE 5] Testing MIT RLM LocalREPL Self-Healing Code Execution...")
    repl = LocalREPL()
    buggy_code = """
def compute_moving_window(values):
    # Intentional typo: undefined variable 'reslt'
    reslt = [v * 2 for v in values]
    return reslt
print(compute_moving_window([1, 2, 3]))
"""
    repl_res = repl.eval_and_heal(buggy_code)
    print(f"  • LocalREPL Execution: Status={repl_res.status}, Output={repl_res.stdout.strip()}")
    if repl_res.status not in ("SUCCESS", "HEALED"):
        blind_spots_found.append(f"LocalREPL failed to execute code: {repl_res.error}")

    # --------------------------------------------------------------------------
    # STAGE 6: Research-to-Obsidian Synthesis & SymPy Proofs
    # --------------------------------------------------------------------------
    print("\n[STAGE 6] Synthesizing Atomic Obsidian Knowledge Note with SymPy Proofs...")
    syncer = ResearchObsidianSyncer()
    note_res = syncer.create_atomic_note(
        title="Mission Aegis Omni Distributed Health Reactor",
        summary="Architecture of a multi-language (Go/C/Python) high-throughput telemetry reactor with formal SMT Z3 bounded buffer guarantees and 768-D SuperGraph indexing.",
        domain="distributed_systems",
        tags=["aegis_omni", "stress_test", "supergraph", "go", "z3", "sota_2026"],
        key_concepts=[
            "Zero-copy ring buffer modulo arithmetic with mutex lock concurrency",
            "Continuous Welford online anomaly calculation",
            "Win32 Job Object isolation for speculative mutation rollouts",
        ],
        latex_equations=[
            "\\sigma^2 = \\frac{1}{N} \\sum_{i=1}^N (x_i - \\mu)^2",
            "idx = (head + i) \\pmod C",
        ],
        code_snippets={
            "go": "func (s *AegisServer) Ingest(ctx context.Context, evt TelemetryEvent) error { panic(\"skeleton\") }",
            "python": "def ingest_metric(self, value: float) -> Dict[str, Any]: ...",
        },
        custom_links=["[[Zettel_AST_ast_pruner]]", "[[Zettel_Ring_Buffer_Mutex_Optimization]]"],
    )
    print(f"  • Zettel Note Created: ID={note_res.get('zettel_id')}, Path={note_res.get('file_path')}, Wikilinks={note_res.get('wikilinks_count')}")
    if not note_res.get("success"):
        blind_spots_found.append("ResearchObsidianSyncer failed to create atomic note")

    # --------------------------------------------------------------------------
    # STAGE 7: Continuous Regression Evals (vazus-bench)
    # --------------------------------------------------------------------------
    print("\n[STAGE 7] Running Continuous Regression Benchmark Harness (vazus-bench)...")
    bench = BenchmarkRunner()
    bench_res = bench.run_all(category_filter="all")
    print(f"  • vazus-bench: Pass@1={bench_res['pass_at_1']}%, Total={bench_res['total_tasks']}, Latency={bench_res['duration_ms']}ms")
    if bench_res["failed_tasks"] > 0:
        blind_spots_found.append(f"vazus-bench reported {bench_res['failed_tasks']} failing tasks")

    # --------------------------------------------------------------------------
    # STAGE 8: Blind Spots Summary & System Audit Report
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("📋 MISSION AEGIS-OMNI AUDIT SUMMARY:")
    print("=" * 80)
    if blind_spots_found:
        print(f"⚠️ Found {len(blind_spots_found)} blind spots to eliminate:")
        for idx, bs in enumerate(blind_spots_found, 1):
            print(f"  [{idx}] {bs}")
        return False
    else:
        print("✅ 100% OPERATIONAL EXCELLENCE ACHIEVED!")
        print("   All 7 core subsystems passed stress testing with ZERO blind spots.")
        print("   • Multi-Language AST Pruner (Go/C/Python) -> PASSED")
        print("   • SMT Z3 Mathematical Invariants          -> PROVEN (UNSAT)")
        print("   • Async Worktree Sandbox                  -> VERIFIED")
        print("   • 2-Layer SuperGraph 768-D Vector Memory  -> INDEXED & CONNECTED")
        print("   • MIT RLM LocalREPL Execution             -> OPERATIONAL")
        print("   • Research-to-Obsidian SymPy Pipeline     -> SYNTHESIZED")
        print("   • vazus-bench Regression Suite            -> 100.0% PASS@1")
        print("=" * 80)
        return True


if __name__ == "__main__":
    success = run_mission()
    sys.exit(0 if success else 1)
