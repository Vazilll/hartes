# 📊 Vazus SuperGraph OS v4.0 — Empirical Execution Benchmark & Visual Report

**Generated Date**: 2026-07-27 07:40:27 UTC
**Database**: `C:\vazus\vazus.db`
**Benchmark Iterations**: N=10 (Warmup runs=3)

## Executive Summary
This report documents real-world empirical performance metrics measured across production `vazus_core` codebase modules without synthetic mocks or throwaway stubs. All measured results have been verified and persisted into `vazus.db` (`organic_insights` + `kg_nodes` with 768-dim float vector embeddings).

## 📈 Empirical Performance Summary Table
| Module | Original AST Nodes | Pruned AST Nodes | AST Reduction (%) | Baseline Latency | Optimized Latency | Memory Reduction | Visual Progress Bar | Verification Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| `kgb_analytical_extractor.py` | 5,920 | 771 | **86.98%** | 1.074 ms | 1.883 ms | 0.2 KB | `[█████████████████░░░] 87.0%` | 🟢 PASSED (>75%) |
| `ast_pruner.py` | 1,885 | 298 | **84.19%** | 33.880 ms | 24.790 ms | 0.0 KB | `[█████████████████░░░] 84.2%` | 🟢 PASSED (>75%) |
| `embeddings.py` | 2,063 | 370 | **82.06%** | 0.103 ms | 0.113 ms | 0.0 KB | `[████████████████░░░░] 82.1%` | 🟢 PASSED (>75%) |
| `smt_z3_verifier.py` | 4,178 | 492 | **88.22%** | 0.285 ms | 0.296 ms | 0.1 KB | `[██████████████████░░] 88.2%` | 🟢 PASSED (>75%) |
| `supergraph_linker.py` | 3,028 | 657 | **78.30%** | 0.051 ms | 0.049 ms | 0.0 KB | `[████████████████░░░░] 78.3%` | 🟢 PASSED (>75%) |
| `cognitive_tutor_engine.py` | 4,284 | 518 | **87.91%** | 0.989 ms | 1.046 ms | 0.1 KB | `[██████████████████░░] 87.9%` | 🟢 PASSED (>75%) |

## 🔬 Detailed Module Benchmark Breakdown

### 📦 `kgb_analytical_extractor.py`
- **File Path**: `C:\vazus\vazus_core\kgb_analytical_extractor.py`
- **AST Signature Nodes**: 5,920 -> 771 (**86.98% reduction**)
- **Source File Size**: 44,382 bytes -> 5,461 bytes
- **Execution Speed**: Baseline `1.0740 ms` vs Optimized `1.8826 ms` (Speedup ratio: `0.57x`)
- **RAM Allocation**: Peak baseline `20.51 KB` vs Peak optimized `20.33 KB` (Net RAM saved: `0.19 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:kgb_analytical_extractor.py:1785138025986` in `kg_nodes` with 768-dim float vector embedding.

### 📦 `ast_pruner.py`
- **File Path**: `C:\vazus\vazus_core\ast_pruner.py`
- **AST Signature Nodes**: 1,885 -> 298 (**84.19% reduction**)
- **Source File Size**: 13,066 bytes -> 2,560 bytes
- **Execution Speed**: Baseline `33.8796 ms` vs Optimized `24.7898 ms` (Speedup ratio: `1.37x`)
- **RAM Allocation**: Peak baseline `1570.91 KB` vs Peak optimized `1571.76 KB` (Net RAM saved: `0.00 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:ast_pruner.py:1785138026761` in `kg_nodes` with 768-dim float vector embedding.

### 📦 `embeddings.py`
- **File Path**: `C:\vazus\vazus_core\embeddings.py`
- **AST Signature Nodes**: 2,063 -> 370 (**82.06% reduction**)
- **Source File Size**: 11,489 bytes -> 2,587 bytes
- **Execution Speed**: Baseline `0.1029 ms` vs Optimized `0.1131 ms` (Speedup ratio: `0.91x`)
- **RAM Allocation**: Peak baseline `22.28 KB` vs Peak optimized `22.28 KB` (Net RAM saved: `0.00 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:embeddings.py:1785138026886` in `kg_nodes` with 768-dim float vector embedding.

### 📦 `smt_z3_verifier.py`
- **File Path**: `C:\vazus\vazus_core\smt_z3_verifier.py`
- **AST Signature Nodes**: 4,178 -> 492 (**88.22% reduction**)
- **Source File Size**: 28,307 bytes -> 3,856 bytes
- **Execution Speed**: Baseline `0.2850 ms` vs Optimized `0.2957 ms` (Speedup ratio: `0.96x`)
- **RAM Allocation**: Peak baseline `32.86 KB` vs Peak optimized `32.77 KB` (Net RAM saved: `0.09 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:smt_z3_verifier.py:1785138027007` in `kg_nodes` with 768-dim float vector embedding.

### 📦 `supergraph_linker.py`
- **File Path**: `C:\vazus\vazus_core\supergraph_linker.py`
- **AST Signature Nodes**: 3,028 -> 657 (**78.30% reduction**)
- **Source File Size**: 22,401 bytes -> 4,172 bytes
- **Execution Speed**: Baseline `0.0505 ms` vs Optimized `0.0491 ms` (Speedup ratio: `1.03x`)
- **RAM Allocation**: Peak baseline `3.39 KB` vs Peak optimized `3.39 KB` (Net RAM saved: `0.00 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:supergraph_linker.py:1785138027109` in `kg_nodes` with 768-dim float vector embedding.

### 📦 `cognitive_tutor_engine.py`
- **File Path**: `C:\vazus\vazus_core\cognitive_tutor_engine.py`
- **AST Signature Nodes**: 4,284 -> 518 (**87.91% reduction**)
- **Source File Size**: 31,056 bytes -> 4,497 bytes
- **Execution Speed**: Baseline `0.9887 ms` vs Optimized `1.0461 ms` (Speedup ratio: `0.95x`)
- **RAM Allocation**: Peak baseline `28.64 KB` vs Peak optimized `28.53 KB` (Net RAM saved: `0.12 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:cognitive_tutor_engine.py:1785138027241` in `kg_nodes` with 768-dim float vector embedding.
