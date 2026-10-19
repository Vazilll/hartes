---
id: Zettel_SuperGraph_Hub
title: "Zettel SuperGraph Knowledge & Vector Index Hub"
date: "2026-09-04"
domain: supergraph_hub
tags:
  - iad
  - zettel
  - supergraph
  - hub
  - vector_space
status: VERIFIED
sources:
  - "vazus_core/engine/supergraph_linker.py"
  - "services/memory/vazus.db"
  - "SuperGraph_OS_Architecture.md"
---

# Zettel SuperGraph Knowledge & Vector Index Hub

> **Architecture**: [[SuperGraph_OS_Architecture]]  
> **Memory Index**: [[Zettel_Karpathy_Memory_Index]]  
> **Evaluation Flywheel**: [[agent_eval_quality_flywheel]]  
> **Status**: `VERIFIED`  

---

## 🌐 Central SuperGraph Hub
This hub anchors all cross-domain semantic associations in Vazus SuperGraph OS. It connects:
- **Code Nodes (`ast:*`)**: Symbols, modules, and callgraphs extracted from source code.
- **Wiki Notes (`wiki:*`)**: Architectural specifications, Zettel notes, and `.canvas` boards.
- **Wiki Sections (`wiki:*#*`)**: Granular markdown sections linked hierarchically via `CONTAINS_SECTION`.

## 4-Component Hybrid Linker
Cross-layer edges (`SUPERGRAPH_LINK`) are calculated via:
$$S(u, v) = 0.45 \cdot S_{\text{cosine}} + 0.25 \cdot S_{\text{fts}} + 0.20 \cdot S_{\text{structural}} + 0.10 \cdot S_{\text{provenance}}$$

Pairs with $S(u, v) \ge 0.15$ are persisted into `kg_edges` with guaranteed referential integrity.

## Key Hub Links
- [[SuperGraph_OS_Architecture]]
- [[Zettel_Karpathy_Memory_Index]]
- [[agent_eval_quality_flywheel]]
- [[ADR_005_CONTINUOUS_AGENT_SELF_IMPROVEMENT_FLYWHEEL]]
- [[Zettel_Continuous_Agent_Self_Improvement_Flywheel]]
- [[open_deep_researcher_Memory_Hub]]
- [[verifier_worker_Memory_Hub]]
- [[rlm_code_engineer_Memory_Hub]]
