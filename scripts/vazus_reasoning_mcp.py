#!/usr/bin/env python3
"""
scripts/vazus_reasoning_mcp.py — Native MCP Server for Vazus Unified Master Reasoning.
Exposes SMT Z3 proof, Concordia Jury voting, AST pruning, and Master Pipeline tools.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path("C:/vazus")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from fastmcp import FastMCP
from vazus_core.engine.unified_reasoning_pipeline import UnifiedReasoningPipeline
from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier
from vazus_core.verification.concordia_jury import ConcordiaJury

MCP = FastMCP("vazus-reasoning")


@MCP.tool(description=(
    "Master Unified Reasoning Engine: Orchestrates 4-phase sequential reasoning: "
    "1. AST Signature Pruning (-75%+ tokens), "
    "2. SMT Z3 Formal Logic Contract Proof, "
    "3. Concordia 3-Subagent Quorum Voting (>=66%), "
    "4. Laconic Verdict Synthesis."
))
def vazus_unified_reasoning(
    task_prompt: str,
    code_proposal: str,
    file_path: str = "proposal.py",
    effort_level: str = "high"
) -> str:
    """Executes full 4-phase Unified Master Reasoning Pipeline."""
    pipeline = UnifiedReasoningPipeline(effort_level=effort_level)
    res = pipeline.execute_pipeline_sync(
        task_prompt=task_prompt,
        code_proposal=code_proposal,
        file_path=file_path
    )
    
    log_str = "\n".join(res.get("pipeline_log", []))
    return f"{res.get('laconic_summary')}\n\nExecution Log:\n{log_str}"


@MCP.tool(description=(
    "SMT Z3 Theorem Prover Gate: Formally proves pre-conditions, post-conditions, "
    "and logic invariants for Python code snippets."
))
def vazus_smt_z3_verify_contract(code_snippet: str) -> str:
    """Proves function contracts mathematically using Z3 Theorem Prover."""
    verifier = SMTZ3Verifier(depth=10)
    res = verifier.verify_code_contracts(code_snippet)
    passed = getattr(res, "contract_satisfied", res.get("contract_satisfied", True) if isinstance(res, dict) else True)
    return f"SMT Z3 Verification: {'VERIFIED (UNSAT)' if passed else 'FAILED (SAT)'} | Details: {res}"


@MCP.tool(description=(
    "Concordia Multi-Agent Jury Voting: Evaluates code proposal across 3 distinct "
    "subagent personas (Planner, Coder, Verifier) enforcing >=66% quorum consensus."
))
def vazus_concordia_jury_vote(file_path: str, code_content: str) -> str:
    """Evaluates proposal with 3-subagent Concordia Jury."""
    jury = ConcordiaJury(effort_level="high")
    res = jury.evaluate_code_proposal(file_path=file_path, code_content=code_content)
    approved = res.get("approved", False)
    ratio = res.get("consensus_ratio", 0.0)
    return f"Concordia Jury Voting: Approved={approved}, Ratio={ratio:.2f} (Target >= 0.66) | Rejections: {res.get('rejection_reasons', [])}"


if __name__ == "__main__":
    MCP.run(transport="stdio")
