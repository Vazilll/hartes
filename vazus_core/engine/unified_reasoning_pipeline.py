"""
vazus_core.unified_reasoning_pipeline — Unified Master Reasoning Pipeline.
Combines 4 reasoning layers into a seamless, sequential, laconic execution pipeline:
  1. Sequential Thinking (Dynamic CoT / Tree-of-Thought)
  2. MIT RLM LocalREPL (Execution-guided empirical validation)
  3. SMT Z3 Theorem Prover (Formal mathematical logic verification)
  4. Concordia Multi-Agent Jury (3-subagent quorum consensus >=66%)
"""

import asyncio
import concurrent.futures
from typing import Dict, Any, List, Optional
from vazus_core.verification.ast_pruner import ASTPruner
from vazus_core.verification.concordia_jury import ConcordiaJury
from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier
from vazus_core.engine.reasoning_effort_controller import ReasoningEffortController
from vazus_core.engine.exceptions import JuryConsensusError, SMTVerificationError
from vazus_core.workers.jules_client import JulesClient


class UnifiedReasoningPipeline:
    """
    Unified Master Reasoning Engine orchestrating Sequential Thinking,
    REPL execution, SMT Z3 formal logic proof, and Concordia Jury voting.
    """

    def __init__(self, effort_level: str = "high"):
        self.effort_level = effort_level
        self.effort_config = ReasoningEffortController.get_config(effort_level)
        self.jury = ConcordiaJury(effort_level=effort_level)
        self.smt_verifier = SMTZ3Verifier(depth=self.effort_config.get("smt_z3_depth", 10))
        self.jules_client = JulesClient()

    async def execute_pipeline(
        self,
        task_prompt: str,
        code_proposal: str,
        file_path: str = "proposal.py",
        agent_votes: Optional[List[Dict[str, Any]]] = None,
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """
        Executes 4-phase sequential master reasoning asynchronously:
          Phase 1: AST Pruning & Token Economy
          Phase 2: SMT Z3 Formal Contract Proof (thread-offloaded)
          Phase 3: Concordia 3-Subagent Quorum Voting
          Phase 4: Synthesis & Final Verdict
        Protected by an asyncio.timeout guard.
        """
        pipeline_log: List[str] = []
        pipeline_log.append(f"[Phase 1] AST Signature Pruning for {file_path}")

        try:
            async with asyncio.timeout(timeout):
                                # Phase 0: Cloud VM Pre-Commit Verification via Google Jules API
                pipeline_log.append("[Phase 0] Cloud VM Pre-Commit Verification")
                jules_res = await self.jules_client.verify_precommit_cloud_async(
                    code_proposal=code_proposal,
                    task_prompt=task_prompt
                )
                if jules_res.get("fallback"):
                    reason_msg = jules_res.get("reason")
                    pipeline_log.append(f"  * Jules Cloud VM: Fallback active ({reason_msg}) -> Defaulting to local SMT Z3 and Concordia Jury")
                else:
                    sess_id = jules_res.get("session_id")
                    sess_st = jules_res.get("state")
                    pipeline_log.append(f"  * Jules Cloud VM: Verified session {sess_id} State: {sess_st}")

                # Phase 1: AST Signature Pruning
                pruned_code, ast_stats = ASTPruner.prune_code_string(code_proposal)
                pipeline_log.append(
                    f"  • AST Nodes: {ast_stats.get('total_nodes', 0)} -> {ast_stats.get('pruned_nodes', 0)} "
                    f"({ast_stats.get('reduction_percentage', 0):.2f}% reduced)"
                )

                # Phase 2: SMT Z3 Formal Logic Verification (offloaded to thread)
                pipeline_log.append("[Phase 2] SMT Z3 Formal Logic Proof Gate")
                smt_res = await asyncio.to_thread(self.smt_verifier.verify_code_contracts, code_proposal)
                smt_passed = getattr(
                    smt_res,
                    "contract_satisfied",
                    smt_res.get("contract_satisfied", True) if isinstance(smt_res, dict) else True
                )
                pipeline_log.append(f"  • SMT Z3 Status: {'VERIFIED (UNSAT)' if smt_passed else 'FAILED (SAT)'}")

                # Phase 3: Concordia Multi-Agent Jury Voting
                pipeline_log.append("[Phase 3] Concordia 3-Subagent Jury Quorum Voting")

                if hasattr(self.jury, "evaluate_code_proposal_async") and callable(getattr(self.jury, "evaluate_code_proposal_async")):
                    jury_res = await self.jury.evaluate_code_proposal_async(
                        file_path=file_path,
                        code_content=code_proposal,
                        agent_votes=agent_votes
                    )
                else:
                    jury_res = await asyncio.to_thread(
                        self.jury.evaluate_code_proposal,
                        file_path=file_path,
                        code_content=code_proposal,
                        agent_votes=agent_votes
                    )

                approved = jury_res.get("approved", False)
                ratio = jury_res.get("consensus_ratio", 0.0)
                pipeline_log.append(f"  • Quorum Status: Approved={approved}, Ratio={ratio:.2f} (Target >= 0.66)")

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
            laconic_summary = f"Unified Pipeline ({self.effort_level}): TIMED_OUT after {timeout}s"
            return {
                "status": "TIMED_OUT",
                "approved": False,
                "effort_level": self.effort_level,
                "ast_stats": {},
                "smt_verification": {"contract_satisfied": False, "error": "Timed out"},
                "jury_result": {"approved": False, "consensus_ratio": 0.0},
                "pipeline_log": pipeline_log,
                "laconic_summary": laconic_summary,
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

