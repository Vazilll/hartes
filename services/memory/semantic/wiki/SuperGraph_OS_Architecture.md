---
id: SuperGraph_OS_Architecture
title: "SuperGraph OS Architecture Specification & Canonical Guide"
date: "2026-09-04"
domain: architecture
tags:
  - iad
  - zettel
  - supergraph
  - architecture
  - canonical
status: VERIFIED
sources:
  - "Research_SuperGraph_OS_Architecture.md"
  - "PROJECT.md"
  - "vazus_core/engine/supergraph_linker.py"
---

# SuperGraph OS Architecture Specification & Canonical Guide

> **Canonical Research Document**: [[Research_SuperGraph_OS_Architecture]]  
> **Knowledge Hub**: [[Zettel_SuperGraph_Hub]]  
> **Memory Index**: [[Zettel_Karpathy_Memory_Index]]  
> **Quality Flywheel**: [[agent_eval_quality_flywheel]]  
> **Status**: `VERIFIED`  

---

## 🏗️ Unified SuperGraph Architecture Overview
Vazus SuperGraph OS unifies codebase topology, persistent episodic memory, and operational knowledge into a single two-layer graph aligned via 768-dimensional vector embeddings:

1. **Layer A (AST Code Topology & SCIP Indexing)**:
   - Generated via `@tastehub/ckb` and `scip-python-plus` into `C:\vazus\index.scip`.
   - Captures classes, functions, calls, and inheritance hierarchies.
2. **Layer B (Karpathy Semantic Memory Wiki & Obsidian Graph)**:
   - Markdown Zettelkasten notes and interactive `.canvas` boards in `C:\vazus\services\memory\semantic\wiki\`.
   - Formalizes architectural decisions (ADRs), user preferences, and continuous improvement flywheels.
3. **Unified Alignment Vector Layer (768-D)**:
   - Synchronized by `vazus_core/embeddings.py` and `vazus_core/engine/supergraph_linker.py` using Google Gemini Embedding 2 / OpenVINO NPU embedders.
   - Enforces zero dangling references across code and knowledge domains.

## 🤖 Core Subagents Matrix
- [[open_deep_researcher]] & [[open_deep_researcher_Memory_Hub]]: Autonomous deep web research.
- [[verifier_worker]] & [[verifier_worker_Memory_Hub]]: SMT Z3 formal verification and quality gating.
- [[rlm_code_engineer]] & [[rlm_code_engineer_Memory_Hub]]: MIT RLM interactive code generation.

## Canonical Reference
For raw research dry-run traces and node configurations, refer to [[Research_SuperGraph_OS_Architecture]].
