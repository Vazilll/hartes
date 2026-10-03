# 📊 Vazus SuperGraph OS v4.0 — Empirical Execution Benchmark & Visual Report

**Generated Date**: 2026-08-18 18:52:05 UTC
**Database**: `C:\vazus\services\memory\vazus.db`
**Benchmark Iterations**: N=10 (Warmup runs=3)

## Executive Summary
This report documents real-world empirical performance metrics measured across production `vazus_core` codebase modules without synthetic mocks or throwaway stubs. All measured results have been verified and persisted into `vazus.db` (`organic_insights` + `kg_nodes` with 768-dim float vector embeddings).

## 📈 Empirical Performance Summary Table
| Module | Original AST Nodes | Pruned AST Nodes | AST Reduction (%) | Baseline Latency | Optimized Latency | Memory Reduction | Visual Progress Bar | Verification Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| `kgb_analytical_extractor.py` | 7,478 | 1,729 | **76.88%** | 3.013 ms | 2.456 ms | 0.2 KB | `[███████████████░░░░░] 76.9%` | 🟢 PASSED (>75%) |
| `ast_pruner.py` | 4,677 | 1,020 | **78.19%** | 67.216 ms | 46.004 ms | 1209.5 KB | `[████████████████░░░░] 78.2%` | 🟢 PASSED (>75%) |
| `embeddings.py` | 4,594 | 917 | **80.04%** | 7.290 ms | 7.534 ms | 0.8 KB | `[████████████████░░░░] 80.0%` | 🟢 PASSED (>75%) |
| `smt_z3_verifier.py` | 6,752 | 1,561 | **76.88%** | 5.002 ms | 4.006 ms | 0.0 KB | `[███████████████░░░░░] 76.9%` | 🟢 PASSED (>75%) |
| `supergraph_linker.py` | 3,215 | 685 | **78.69%** | 0.137 ms | 0.271 ms | 0.0 KB | `[████████████████░░░░] 78.7%` | 🟢 PASSED (>75%) |
| `cognitive_tutor_engine.py` | 4,542 | 550 | **87.89%** | 6.982 ms | 9.882 ms | 0.7 KB | `[██████████████████░░] 87.9%` | 🟢 PASSED (>75%) |

## 🔬 Detailed Module Benchmark Breakdown

### 📦 `kgb_analytical_extractor.py`
- **File Path**: `C:\vazus\vazus_core\integrations\kgb_analytical_extractor.py`
- **AST Signature Nodes**: 7,478 -> 1,729 (**76.88% reduction**)
- **Source File Size**: 46,051 bytes -> 9,779 bytes
- **Execution Speed**: Baseline `3.0133 ms` vs Optimized `2.4560 ms` (Speedup ratio: `1.23x`)
- **RAM Allocation**: Peak baseline `19.93 KB` vs Peak optimized `19.71 KB` (Net RAM saved: `0.21 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:kgb_analytical_extractor.py:1787079122242` in `kg_nodes` with 768-dim float vector embedding.

### 📦 `ast_pruner.py`
- **File Path**: `C:\vazus\vazus_core\verification\ast_pruner.py`
- **AST Signature Nodes**: 4,677 -> 1,020 (**78.19% reduction**)
- **Source File Size**: 32,347 bytes -> 6,759 bytes
- **Execution Speed**: Baseline `67.2158 ms` vs Optimized `46.0038 ms` (Speedup ratio: `1.46x`)
- **RAM Allocation**: Peak baseline `4100.77 KB` vs Peak optimized `2891.22 KB` (Net RAM saved: `1209.55 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:ast_pruner.py:1787079123800` in `kg_nodes` with 768-dim float vector embedding.

### 📦 `embeddings.py`
- **File Path**: `C:\vazus\vazus_core\memory\embeddings.py`
- **AST Signature Nodes**: 4,594 -> 917 (**80.04% reduction**)
- **Source File Size**: 25,111 bytes -> 6,741 bytes
- **Execution Speed**: Baseline `7.2905 ms` vs Optimized `7.5344 ms` (Speedup ratio: `0.97x`)
- **RAM Allocation**: Peak baseline `30.44 KB` vs Peak optimized `29.69 KB` (Net RAM saved: `0.75 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:embeddings.py:1787079124176` in `kg_nodes` with 768-dim float vector embedding.

### 📦 `smt_z3_verifier.py`
- **File Path**: `C:\vazus\vazus_core\verification\smt_z3_verifier.py`
- **AST Signature Nodes**: 6,752 -> 1,561 (**76.88% reduction**)
- **Source File Size**: 41,642 bytes -> 10,794 bytes
- **Execution Speed**: Baseline `5.0021 ms` vs Optimized `4.0061 ms` (Speedup ratio: `1.25x`)
- **RAM Allocation**: Peak baseline `44.83 KB` vs Peak optimized `45.59 KB` (Net RAM saved: `0.00 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:smt_z3_verifier.py:1787079124459` in `kg_nodes` with 768-dim float vector embedding.

### 📦 `supergraph_linker.py`
- **File Path**: `C:\vazus\vazus_core\engine\supergraph_linker.py`
- **AST Signature Nodes**: 3,215 -> 685 (**78.69% reduction**)
- **Source File Size**: 22,509 bytes -> 4,236 bytes
- **Execution Speed**: Baseline `0.1374 ms` vs Optimized `0.2712 ms` (Speedup ratio: `0.51x`)
- **RAM Allocation**: Peak baseline `3.39 KB` vs Peak optimized `3.39 KB` (Net RAM saved: `0.00 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:supergraph_linker.py:1787079124653` in `kg_nodes` with 768-dim float vector embedding.

### 📦 `cognitive_tutor_engine.py`
- **File Path**: `C:\vazus\vazus_core\integrations\cognitive_tutor_engine.py`
- **AST Signature Nodes**: 4,542 -> 550 (**87.89% reduction**)
- **Source File Size**: 31,038 bytes -> 4,084 bytes
- **Execution Speed**: Baseline `6.9816 ms` vs Optimized `9.8822 ms` (Speedup ratio: `0.71x`)
- **RAM Allocation**: Peak baseline `36.81 KB` vs Peak optimized `36.09 KB` (Net RAM saved: `0.72 KB`)
- **AST Syntax Compliance**: `ast.parse()` valid (`True`)
- **Closed-Loop DB Persistence**: Node ID `opt:cognitive_tutor_engine.py:1787079125059` in `kg_nodes` with 768-dim float vector embedding.
