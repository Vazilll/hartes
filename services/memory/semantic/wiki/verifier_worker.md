---
id: verifier_worker
title: "Verifier Worker Subagent Specification"
date: "2026-09-04"
domain: subagent_verification
tags:
  - iad
  - zettel
  - subagent
  - verifier_worker
  - verification
  - smt_z3
status: VERIFIED
sources:
  - "subagent_verifier_bridge.py"
  - "vazus_core/verification/smt_z3_verifier.py"
---

# Verifier Worker Subagent Specification

> **Canonical Hub**: [[verifier_worker_Memory_Hub]]  
> **Architecture**: [[SuperGraph_OS_Architecture]]  
> **Status**: `VERIFIED`  

## 📌 Subagent Mission
The `verifier_worker` is responsible for rigorous, mathematical verification of all code mutations, AST invariants, and runtime behavior before commit.

## 5-Tier Quality Gate
1. **Tier 1 (AST Syntax & Linting)**: Validates AST compilation, style conventions, and import trees.
2. **Tier 2 (Pytest Unit & E2E)**: Executes regression suites across `tests/`.
3. **Tier 3 (SMT Z3 Contract Proofs)**: Formally verifies state invariants and absence of dead-ends.
4. **Tier 4 (Concordia Multi-Agent Jury)**: Requires $\ge 66\%$ consensus quorum among Planner, Coder, and Verifier.
5. **Tier 5 (Vulture Clean Audit)**: Guarantees zero dead-code or orphaned temporary scripts.

## Linked Memory Nodes
- [[verifier_worker_Memory_Hub]]
- [[open_deep_researcher]]
- [[rlm_code_engineer]]
- [[SuperGraph_OS_Architecture]]
- [[agent_eval_quality_flywheel]]
