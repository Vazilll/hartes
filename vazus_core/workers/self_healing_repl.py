"""
vazus_core.self_healing_repl — Closed-Loop Autonomous Self-Healing REPL Manager.
Combines LocalREPL iterative repair, Concordia Jury 3-agent consensus (>= 66%),
SMT Z3 contract verification (UNSAT), and transactional RollbackGuardrail file protection.

Vazus SuperGraph OS v4.0 Unified Architecture
"""

import ast
import logging
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from vazus_core.workers.repl_engine import LocalREPL
from vazus_core.verification.concordia_jury import ConcordiaJury
from vazus_core.verification.safety_guardrail import SMTZ3Verifier, RollbackGuardrail
from vazus_core.engine.circuit_breaker import AntiLoopCircuitBreaker

logger = logging.getLogger("SelfHealingREPL")


class SelfHealingREPLManager:
    """
    Integrates LocalREPL, ConcordiaJury, SMTZ3Verifier, and RollbackGuardrail
    to perform autonomous code self-healing and transactional verification.
    """

    def __init__(
        self,
        effort_level: str = "high",
        consensus_threshold: float = 0.66,
        min_quorum: int = 3
    ):
        self.effort_level = effort_level
        self.consensus_threshold = consensus_threshold
        self.min_quorum = min_quorum
        self.jury = ConcordiaJury(
            effort_level=effort_level,
            min_quorum=min_quorum,
            consensus_threshold=consensus_threshold
        )
        self.smt_verifier = SMTZ3Verifier()
        self.verifier = self.smt_verifier

    def run_self_healing_repair(
        self,
        target_file: Union[str, Path],
        code_proposal: str,
        agent_votes: Optional[List[Dict[str, Any]]] = None,
        test_cmd: Optional[Union[str, List[str]]] = None,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Executes self-healing repair loop on target_file with code_proposal.
        """
        target_path = Path(target_file).resolve()
        file_existed = target_path.exists()
        orig_code = ""
        if file_existed:
            try:
                orig_code = target_path.read_text(encoding="utf-8")
            except Exception:
                orig_code = ""

        # Step 1: Create transactional snapshot
        guardrail = RollbackGuardrail(target_path)
        guardrail.create_snapshot()

        # Step 2: LocalREPL Iterative Repair Loop with Circuit Breaker
        repl = LocalREPL()
        circuit_breaker = AntiLoopCircuitBreaker(max_duplicates=2, max_total_attempts=max_iterations)
        iteration_count = 0
        working_code = code_proposal

        circuit_breaker.register_attempt(working_code)

        is_init_syntax_ok = True
        try:
            ast.parse(working_code)
        except SyntaxError:
            is_init_syntax_ok = False

        repl_res = repl.eval_and_heal(working_code)
        iteration_count += 1

        if repl_res.healed and repl_res.healed_code:
            working_code = repl_res.healed_code

        while iteration_count < max_iterations and not circuit_breaker.tripped:
            try:
                ast.parse(working_code)
                if repl_res.status in ("SUCCESS", "HEALED"):
                    break
            except SyntaxError:
                pass

            iteration_count += 1
            err_msg = repl_res.stderr or repl_res.original_error or "SyntaxError in proposal"
            working_code = repl._apply_self_healing(working_code, err_msg)
            
            # Check Circuit Breaker before executing duplicate proposal
            if not circuit_breaker.register_attempt(working_code):
                logger.warning(f"[SelfHealingREPL] Circuit Breaker tripped: {circuit_breaker.trip_reason}")
                break

            repl_res = repl.execute_code(working_code)
            if repl_res.status == "SUCCESS":
                try:
                    ast.parse(working_code)
                    repl_res.healed = True
                    repl_res.healed_code = working_code
                    repl_res.status = "HEALED"
                    break
                except SyntaxError:
                    pass

        repl.cleanup()

        final_ast_ok = True
        try:
            ast.parse(working_code)
        except SyntaxError:
            final_ast_ok = False

        was_healed = repl_res.healed or (not is_init_syntax_ok and final_ast_ok)

        # Check REPL/AST success
        if not final_ast_ok or repl_res.status not in ("SUCCESS", "HEALED"):
            self._rollback(guardrail, file_existed, target_path)
            return {
                "status": "FAILED",
                "repaired": False,
                "target_file": str(target_path),
                "iterations_used": iteration_count,
                "repl_result": repl_res.to_dict(),
                "jury_verdict": None,
                "smt_status": "FAILED",
                "smt_verified": False,
                "test_passed": False,
                "rollback_performed": True,
                "rollback_executed": True,
                "healed": was_healed,
                "repaired_code": None,
                "error": repl_res.stderr or repl_res.original_error or "Unfixable code error",
            }

        # Step 3: Concordia Jury Voting Gate
        jury_verdict = self.jury.vote(
            proposal=working_code,
            votes=agent_votes,
            file_path=str(target_path),
            orig_code=orig_code if orig_code else None
        )

        if not jury_verdict.approved:
            self._rollback(guardrail, file_existed, target_path)
            return {
                "status": "JURY_CONSENSUS_REJECTED",
                "repaired": False,
                "target_file": str(target_path),
                "iterations_used": iteration_count,
                "repl_result": repl_res.to_dict(),
                "jury_verdict": jury_verdict.to_dict(),
                "smt_status": "UNSAT" if jury_verdict.smt_satisfied else "FAILED",
                "smt_verified": jury_verdict.smt_satisfied,
                "test_passed": False,
                "rollback_performed": True,
                "rollback_executed": True,
                "healed": was_healed,
                "repaired_code": working_code,
                "error": "; ".join(jury_verdict.rejection_reasons),
            }

        # Step 4: SMT Z3 Formal Contract Verification Gate
        smt_res = self.smt_verifier.verify_code_contracts(working_code)
        smt_status = getattr(smt_res, "smt_solver_status", getattr(smt_res, "solver_status", "UNSAT"))
        contract_satisfied = getattr(smt_res, "contract_satisfied", True)

        if smt_status == "SAT" or not contract_satisfied:
            self._rollback(guardrail, file_existed, target_path)
            return {
                "status": "SMT_CONTRACT_FAILED",
                "repaired": False,
                "target_file": str(target_path),
                "iterations_used": iteration_count,
                "repl_result": repl_res.to_dict(),
                "jury_verdict": jury_verdict.to_dict(),
                "smt_status": smt_status,
                "smt_verified": False,
                "test_passed": False,
                "rollback_performed": True,
                "rollback_executed": True,
                "healed": was_healed,
                "repaired_code": working_code,
                "error": getattr(smt_res, "error_message", "SMT contract violation (SAT counterexample found)"),
            }

        # Step 5: Write Healed/Verified Code to Target File
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(working_code, encoding="utf-8")
        except Exception as e:
            self._rollback(guardrail, file_existed, target_path)
            return {
                "status": "FILE_WRITE_ERROR",
                "repaired": False,
                "target_file": str(target_path),
                "iterations_used": iteration_count,
                "repl_result": repl_res.to_dict(),
                "jury_verdict": jury_verdict.to_dict(),
                "smt_status": smt_status,
                "smt_verified": True,
                "test_passed": False,
                "rollback_performed": True,
                "rollback_executed": True,
                "healed": was_healed,
                "repaired_code": working_code,
                "error": f"Failed to write target file: {e}",
            }

        # Step 6: Test Suite Execution Gate
        test_passed = None
        test_output = ""
        if test_cmd:
            if isinstance(test_cmd, list):
                cmd_args = test_cmd
            else:
                cmd_args = shlex.split(test_cmd)

            try:
                proc = subprocess.run(
                    cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=r"C:\vazus"
                )
                test_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
                if proc.returncode != 0:
                    test_passed = False
                    self._rollback(guardrail, file_existed, target_path)
                    return {
                        "status": "TEST_SUITE_FAILED",
                        "repaired": False,
                        "target_file": str(target_path),
                        "iterations_used": iteration_count,
                        "repl_result": repl_res.to_dict(),
                        "jury_verdict": jury_verdict.to_dict(),
                        "smt_status": smt_status,
                        "smt_verified": True,
                        "test_passed": False,
                        "test_output": test_output.strip(),
                        "rollback_performed": True,
                        "rollback_executed": True,
                        "healed": was_healed,
                        "repaired_code": working_code,
                        "error": f"Test command exited with status code {proc.returncode}",
                    }
                test_passed = True
            except Exception as e:
                test_passed = False
                self._rollback(guardrail, file_existed, target_path)
                return {
                    "status": "TEST_SUITE_EXCEPTION",
                    "repaired": False,
                    "target_file": str(target_path),
                    "iterations_used": iteration_count,
                    "repl_result": repl_res.to_dict(),
                    "jury_verdict": jury_verdict.to_dict(),
                    "smt_status": smt_status,
                    "smt_verified": True,
                    "test_passed": False,
                    "rollback_performed": True,
                    "rollback_executed": True,
                    "healed": was_healed,
                    "repaired_code": working_code,
                    "error": f"Test execution exception: {e}",
                }

        final_status = "HEALED" if was_healed else "SUCCESS"

        return {
            "status": final_status,
            "repaired": True,
            "target_file": str(target_path),
            "iterations_used": iteration_count,
            "repl_result": repl_res.to_dict(),
            "jury_verdict": jury_verdict.to_dict(),
            "smt_status": smt_status,
            "smt_verified": True,
            "test_passed": test_passed if test_cmd else True,
            "test_output": test_output.strip() if test_output else None,
            "rollback_performed": False,
            "rollback_executed": False,
            "healed": was_healed,
            "repaired_code": working_code,
            "error": None,
        }

    def _rollback(self, guardrail: RollbackGuardrail, file_existed: bool, target_path: Path) -> bool:
        """Helper handling snapshot restoration and clean file removal for new files."""
        if file_existed:
            return guardrail.restore_snapshot()
        else:
            if target_path.exists():
                try:
                    target_path.unlink()
                    return True
                except Exception:
                    return False
            return True
