---
name: vazus-master-reasoner
description: Master 4-phase Unified Reasoning Pipeline for Vazus SuperGraph OS v4.0. Combines AST pruning (-88% tokens), SMT Z3 formal logic contract proofs, Concordia 3-subagent quorum consensus (>=66%), and laconic summary synthesis.
---

# Vazus Master Reasoning Pipeline (`vazus-master-reasoner`)

The **Master Reasoning Pipeline** integrates 4 advanced reasoning layers into a seamless, laconic single-pass execution engine:

1. **AST Signature Pruning**: Strips bodies and compresses docstrings via `DocstringAndBodyPruner`, achieving 88.64% token reduction.
2. **SMT Z3 Theorem Prover**: Formally proves pre-conditions, post-conditions, and logic invariants using Z3.
3. **Concordia Multi-Agent Jury**: Enforces >=66% quorum consensus across 3 subagents (Planner, Coder, Verifier).
4. **Laconic Verdict Synthesis**: Emits clean `APPROVED` / `REJECTED` status with exact metrics.

---

## When to Activate

Use this skill when:
- Designing complex architectural changes across `vazus_core` or `services/`.
- Verifying code proposals before applying changes to critical files.
- Running multi-agent consensus voting on code refactoring.

---

## Tool Execution

Invoke the native FastMCP tool `vazus_unified_reasoning`:

```json
{
  "task_prompt": "Optimize database WAL PRAGMAs",
  "code_proposal": "def optimize_db(conn):\n    conn.execute('PRAGMA synchronous = NORMAL')\n",
  "file_path": "C:/vazus/vazus_core/db.py",
  "effort_level": "high"
}
```

Or call the Python engine directly:

```python
from vazus_core import UnifiedReasoningPipeline

pipeline = UnifiedReasoningPipeline(effort_level="high")
result = pipeline.execute_pipeline(task_prompt, code_proposal, file_path)
print(result["laconic_summary"])
```
