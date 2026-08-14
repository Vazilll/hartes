---
name: vazus-concordia-team
description: Native Antigravity Teamwork Orchestrator for Vazus OS. Spawns 3 autonomous internal subagents (vazus-planner, vazus-coder, vazus-verifier) using define_subagent and invoke_subagent for multi-agent quorum consensus (>=66%), SMT Z3 contract proofs, and AST token economy directly inside Antigravity UI.
---

# Vazus Concordia Native Teamwork Orchestrator (`vazus-concordia-team`)

This skill activates **Native Antigravity Multi-Agent Teamwork** without relying on external script wrappers. It leverages Antigravity's native `define_subagent`, `invoke_subagent`, `send_message`, and reactive messaging architecture.

---

## 🏛️ Native 3-Subagent Team Roles

When activated, the orchestrator defines and invokes 3 distinct internal subagent roles:

### 1. `vazus-planner` (Architect & Topology Analyst)
- **Role**: `Codebase Topology Architect`
- **System Prompt**: Evaluates codebase architecture, queries `ckb` AST graph, calculates blast radius, and drafts the technical specification.
- **Model**: `inherit` (or `pro` for complex design).

### 2. `vazus-coder` (RLM Code Engineer & AST Pruner)
- **Role**: `RLM Code Engineer`
- **System Prompt**: Implements code changes, prunes signatures using `vazus_core.ast_pruner.ASTPruner` (88.64% token reduction), and runs LocalREPL execution verification.
- **Model**: `inherit`.

### 3. `vazus-verifier` (SMT Z3 Theorem Prover & Jury Auditor)
- **Role**: `SMT Z3 Contract Verifier`
- **System Prompt**: Executes formal mathematical logic verification using `vazus_core.smt_z3_verifier.SMTZ3Verifier`, runs pytest test suites, and casts the final consensus vote.
- **Model**: `inherit`.

---

## 🔄 Workflow Execution Protocol

1. **Phase 1: Subagent Definition (`define_subagent`)**:
   Define `vazus-planner`, `vazus-coder`, and `vazus-verifier` with their specific roles and tool privileges.

2. **Phase 2: Parallel Dispatch (`invoke_subagent`)**:
   Launch all 3 subagents concurrently using a single `invoke_subagent` tool call:

   ```json
   {
     "Subagents": [
       {
         "TypeName": "vazus-planner",
         "Role": "Codebase Topology Architect",
         "Prompt": "Analyze architecture and calculate blast radius for db.py"
       },
       {
         "TypeName": "vazus-coder",
         "Role": "RLM Code Engineer",
         "Prompt": "Implement optimized WAL PRAGMA handling in db.py"
       },
       {
         "TypeName": "vazus-verifier",
         "Role": "SMT Z3 Contract Verifier",
         "Prompt": "Verify SMT Z3 invariants and run pytest suite for db.py"
       }
     ]
   }
   ```

3. **Phase 3: Reactive Quorum Voting & Inter-Agent Messaging (`send_message`)**:
   - Collect votes (`APPROVED` / `REJECTED`) from all 3 subagent conversation IDs.
   - Enforce $\ge 66\%$ consensus threshold.
   - Persist verdict into `vazus.db` (`kg_nodes` / `organic_insights`).

4. **Phase 4: Synthesis & Presentation**:
   Present the final laconic summary and clickable subagent conversation links (`[vazus-planner](conversation://<id>)`).
