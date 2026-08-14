---
name: vazus-team
description: Instant Native 3-Subagent Concordia Teamwork Orchestrator (vazus-planner, vazus-coder, vazus-verifier). Activated via /vazus-team, vazus-team, or vazus-teamwork for instant multi-agent execution with full MCP tool access.
---

# Vazus Native Teamwork Orchestrator (`/vazus-team`)

This skill provides an ultra-fast, convenient shortcut matching `/teamwork-preview` behavior with full MCP tool privileges.

When activated, the agent **MUST IMMEDIATELY**:

1. **Call `define_subagent`** with `enable_mcp_tools: true` and `enable_write_tools: true` for:
   - `vazus-planner`: Codebase Topology & Blast Radius Architect (has access to `ckb` and `vazus-organic`)
   - `vazus-coder`: RLM Code Engineer & AST Pruner (has access to `vazus-organic` and LocalREPL)
   - `vazus-verifier`: SMT Z3 Contract Verifier & Jury Auditor (has access to `vazus-organic` and Z3)

2. **Call `invoke_subagent`** with a single multi-agent tool call:

```json
{
  "Subagents": [
    {
      "TypeName": "vazus-planner",
      "Role": "Codebase Topology Architect",
      "Prompt": "Analyze codebase topology using ckb AST graph and calculate blast radius for target files."
    },
    {
      "TypeName": "vazus-coder",
      "Role": "RLM Code Engineer",
      "Prompt": "Implement code changes, prune AST signatures using vazus-organic, and verify in LocalREPL."
    },
    {
      "TypeName": "vazus-verifier",
      "Role": "SMT Z3 Contract Verifier",
      "Prompt": "Verify SMT Z3 formal logic contracts using vazus_smt_z3_verify_contract, run pytest suite, and vote PASS/FAIL."
    }
  ]
}
```

3. **Report Results**:
   Present the final laconic summary and clickable subagent conversation links (`[vazus-planner](conversation://<id>)`).
