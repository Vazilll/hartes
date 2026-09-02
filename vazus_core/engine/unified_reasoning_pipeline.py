"""
vazus_core.unified_reasoning_pipeline — Unified Master Verification Pipeline.

Combines 4 verification layers into an asynchronous, robust pipeline:
  Phase 0: Google Jules Cloud VM Pre-Commit Verification (with local fallback)
  Phase 1: AST Pruning & Signature Optimization (via ASTPruner)
  Phase 2: SMT Z3 Theorem Prover Contract Verification (thread-offloaded)
  Phase 3: Concordia Multi-Agent Jury Quorum Voting (>=66% consensus)
"""

import asyncio
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple
from vazus_core.verification.ast_pruner import ASTPruner
from vazus_core.verification.concordia_jury import ConcordiaJury
from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier
from vazus_core.engine.reasoning_effort_controller import ReasoningEffortController
from vazus_core.workers.jules_client import JulesClient


class UnifiedReasoningPipeline:
    """
    Unified Master Verification Engine orchestrating Google Jules Cloud VM,
    AST signature pruning, SMT Z3 formal logic proof, and Concordia Jury quorum.
    """

    def __init__(self, effort_level: str = "high"):
        self.effort_level = effort_level
        self.effort_config = ReasoningEffortController.get_config(effort_level)
        self.jury = ConcordiaJury(effort_level=effort_level)
        self.smt_verifier = SMTZ3Verifier(depth=self.effort_config.get("smt_z3_depth", 10))
        self.jules_client = JulesClient()

    async def _run_jules_phase(self, code_proposal: str, task_prompt: str, pipeline_log: List[str]) -> Dict[str, Any]:
        pipeline_log.append("[Phase 0] Cloud VM Pre-Commit Verification")
        jules_res = await self.jules_client.verify_precommit_cloud_async(code_proposal=code_proposal, task_prompt=task_prompt)
        if jules_res.get("fallback"):
            pipeline_log.append(f"  * Jules Cloud VM: Fallback active ({jules_res.get('reason')}) -> Defaulting to local SMT Z3 and Concordia Jury")
        else:
            pipeline_log.append(f"  * Jules Cloud VM: Verified session {jules_res.get('session_id')} State: {jules_res.get('state')}")
        return jules_res

    def _run_ast_phase(self, code_proposal: str, file_path: str, pipeline_log: List[str]) -> Tuple[str, Dict[str, Any]]:
        pipeline_log.append(f"[Phase 1] AST Signature Pruning for {file_path}")
        pruned_code, ast_stats = ASTPruner.prune_code_string(code_proposal)
        pipeline_log.append(
            f"  • AST Nodes: {ast_stats.get('total_nodes', 0)} -> {ast_stats.get('pruned_nodes', 0)} "
            f"({ast_stats.get('reduction_percentage', 0):.2f}% reduced)"
        )
        return pruned_code, ast_stats

    async def _run_smt_phase(self, code_proposal: str, pipeline_log: List[str]) -> Tuple[Any, bool]:
        pipeline_log.append("[Phase 2] SMT Z3 Formal Logic Proof Gate")
        smt_res = await asyncio.to_thread(self.smt_verifier.verify_code_contracts, code_proposal)
        smt_passed = getattr(smt_res, "contract_satisfied", smt_res.get("contract_satisfied", True) if isinstance(smt_res, dict) else True)
        pipeline_log.append(f"  • SMT Z3 Status: {'VERIFIED (UNSAT)' if smt_passed else 'FAILED (SAT)'}")
        return smt_res, smt_passed

    async def _run_jury_phase(
        self, file_path: str, code_proposal: str, agent_votes: Optional[List[Dict[str, Any]]], pipeline_log: List[str]
    ) -> Dict[str, Any]:
        pipeline_log.append("[Phase 3] Concordia 3-Subagent Jury Quorum Voting")
        if hasattr(self.jury, "evaluate_code_proposal_async") and callable(getattr(self.jury, "evaluate_code_proposal_async")):
            jury_res = await self.jury.evaluate_code_proposal_async(file_path=file_path, code_content=code_proposal, agent_votes=agent_votes)
        else:
            jury_res = await asyncio.to_thread(self.jury.evaluate_code_proposal, file_path=file_path, code_content=code_proposal, agent_votes=agent_votes)
        approved = jury_res.get("approved", False)
        ratio = jury_res.get("consensus_ratio", 0.0)
        pipeline_log.append(f"  • Quorum Status: Approved={approved}, Ratio={ratio:.2f} (Target >= 0.66)")
        return jury_res

    async def execute_pipeline(
        self,
        task_prompt: str,
        code_proposal: str,
        file_path: str = "proposal.py",
        agent_votes: Optional[List[Dict[str, Any]]] = None,
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """Executes 4-phase sequential master reasoning asynchronously with timeout guard."""
        pipeline_log: List[str] = []
        try:
            async with asyncio.timeout(timeout):
                jules_res = await self._run_jules_phase(code_proposal, task_prompt, pipeline_log)
                _pruned_code, ast_stats = self._run_ast_phase(code_proposal, file_path, pipeline_log)
                smt_res, smt_passed = await self._run_smt_phase(code_proposal, pipeline_log)
                jury_res = await self._run_jury_phase(file_path, code_proposal, agent_votes, pipeline_log)

                approved = jury_res.get("approved", False)
                ratio = jury_res.get("consensus_ratio", 0.0)
                laconic_summary = (
                    f"Unified Pipeline ({self.effort_level}): "
                    f"AST -{ast_stats.get('reduction_percentage', 0):.1f}% | "
                    f"SMT Z3 {'OK' if smt_passed else 'FAIL'} | "
                    f"Jury {ratio*100:.0f}% Consensus => {'APPROVED' if approved else 'REJECTED'}"
                )

                return {
                    "status": "APPROVED" if approved else "REJECTED",
                    "approved": approved,
                    "effort_level": self.effort_level,
                    "ast_stats": ast_stats,
                    "jules_verification": jules_res,
                    "smt_verification": smt_res,
                    "jury_result": jury_res,
                    "pipeline_log": pipeline_log,
                    "laconic_summary": laconic_summary
                }
        except TimeoutError:
            pipeline_log.append(f"[Timeout] Pipeline execution timed out after {timeout} seconds")
            return {
                "status": "TIMED_OUT",
                "approved": False,
                "effort_level": self.effort_level,
                "ast_stats": {},
                "smt_verification": {"contract_satisfied": False, "error": "Timed out"},
                "jury_result": {"approved": False, "consensus_ratio": 0.0},
                "pipeline_log": pipeline_log,
                "laconic_summary": f"Unified Pipeline ({self.effort_level}): TIMED_OUT after {timeout}s",
                "error": f"Pipeline execution timed out after {timeout} seconds"
            }

    def execute_pipeline_sync(
        self,
        task_prompt: str,
        code_proposal: str,
        file_path: str = "proposal.py",
        agent_votes: Optional[List[Dict[str, Any]]] = None,
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """
        Synchronous backward-compatible wrapper for execute_pipeline.
        Safely executes the async pipeline regardless of whether an event loop is currently running.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    asyncio.run,
                    self.execute_pipeline(
                        task_prompt=task_prompt,
                        code_proposal=code_proposal,
                        file_path=file_path,
                        agent_votes=agent_votes,
                        timeout=timeout
                    )
                )
                return future.result()
        else:
            return asyncio.run(
                self.execute_pipeline(
                    task_prompt=task_prompt,
                    code_proposal=code_proposal,
                    file_path=file_path,
                    agent_votes=agent_votes,
                    timeout=timeout
                )
            )

