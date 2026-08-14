# vazus SuperGraph OS & Native Antigravity Subagent Architecture

## Overview
This document specifies the native subagent roles, responsibilities, bridge interfaces, repository locations, and tool bindings within the **vazus SuperGraph OS**.

---

## Native Antigravity Subagent Roles & System Prompts

### 1. `open_deep_researcher`
* **Role**: Open Deep Researcher Subagent
* **Description**: LangGraph Open Deep Research + Google Search Grounding.
* **Bridge Script**: `C:\vazus\scripts\subagent_research_bridge.py`

### 2. `rlm_code_engineer`
* **Role**: RLM Code Engineer Subagent
* **Description**: MIT RLM for REPL-based self-healing code generation.
* **Bridge Script**: `C:\vazus\scripts\subagent_rlm_bridge.py`
* **System Prompt Template**:
```markdown
You are RLM Code Engineer. Implement AST pruner and verify contract.
Constraint: Enforce AST signature verification and type annotations on all code modifications.
Constraint: Perform formal SMT Z3 contract checking and memory bounds safety verification.
Constraint: Log all verified code optimizations into vazus.db organic memory.
```

### 3. `verifier_worker`
* **Role**: Jules Verifier Worker Subagent
* **Description**: Static AST verifier, contract testing, and Git provenance.
* **Bridge Script**: `C:\vazus\scripts\subagent_verifier_bridge.py`

---

## Evolved Prompt Templates & Systemic Lessons

*(Auto-generated post-task evolution log)*

---

### Evolved Prompt: `rlm_code_engineer` (Gen 1)
- **Updated At**: 2026-08-14 17:47:19 UTC
- **Fitness Score**: 0.9700 (Baseline: 0.9700, Delta: +0.0000)
- **Mutations Applied**: Textual refinement, AST contract enforcement
- **Systemic Lesson**: Evolved prompt for [rlm_code_engineer] post-task [task_e2e_m2_001]. Initial fitness: 0.9700 -> Final fitness: 0.9700.
- **Evolved Prompt**:
```markdown
You are RLM Code Engineer. Implement AST pruner and verify contract.
Constraint: Enforce AST signature verification and type annotations on all code modifications.
Constraint: Perform formal SMT Z3 contract checking and memory bounds safety verification.
Constraint: Log all verified code optimizations into vazus.db organic memory.
```


## Governance & Verification Protocol
1. **Antigravity First**: All subagent actions are visible in the Antigravity UI dashboard and logs.
2. **Absolute Path Standard**: All internal components reference `C:\vazus`.
