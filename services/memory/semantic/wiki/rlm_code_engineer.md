---
id: rlm_code_engineer
title: "RLM Code Engineer Subagent Specification"
date: "2026-09-04"
domain: subagent_rlm
tags:
  - iad
  - zettel
  - subagent
  - rlm_code_engineer
  - code_generation
  - ast_pruner
status: VERIFIED
sources:
  - "subagent_rlm_bridge.py"
  - "vazus_core/rlm/repl_engine.py"
  - "vazus_core/ast_pruner.py"
---

# RLM Code Engineer Subagent Specification

> **Canonical Hub**: [[rlm_code_engineer_Memory_Hub]]  
> **Architecture**: [[SuperGraph_OS_Architecture]]  
> **Status**: `VERIFIED`  

## 📌 Subagent Mission
The `rlm_code_engineer` subagent embodies the MIT Recursive Language Modeling (RLM) paradigm for autonomous code generation, interactive REPL debugging, and Darwinian refactoring.

## Core Mechanisms
- **LocalREPL Sandbox**: Executes Python snippets in an isolated, sandboxed environment with strict path boundaries.
- **AST Pruning**: Leverages `vazus_core/ast_pruner.py` to extract concise symbol headers, achieving 77.57% token reduction.
- **Darwinian Evolution**: Formulates hypotheses, applies parameter mutations, and selects top candidate implementations based on empirical test metrics.

## Linked Memory Nodes
- [[rlm_code_engineer_Memory_Hub]]
- [[RLM_Code_Task_Refactor_AST_pruner]]
- [[verifier_worker]]
- [[open_deep_researcher]]
- [[SuperGraph_OS_Architecture]]
