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

    def _build_failure_result(
        self,
        status: str,
        target_path: Path,
        *,
        iterations: int = 0,
        repl_res: Any = None,
        jury_verdict: Any = None,
        smt_status: str = "FAILED",
        smt_verified: bool = False,
        was_healed: bool = False,
        repaired_code: Optional[str] = None,
        error: str = "",
        test_output: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Constructs standardized failure payload for self-healing repair stages."""
        j_dict = None
        if jury_verdict is not None:
            if hasattr(jury_verdict, "to_dict"):
                j_dict = jury_verdict.to_dict()
            elif isinstance(jury_verdict, dict):
                j_dict = jury_verdict
            else:
                j_dict = {"approved": getattr(jury_verdict, "approved", False)}

        return {
            "status": status,
            "repaired": False,
            "target_file": str(target_path),
            "iterations_used": iterations,
            "repl_result": repl_res.to_dict() if repl_res else None,
            "jury_verdict": j_dict,
            "smt_status": smt_status,
            "smt_verified": smt_verified,
            "test_passed": False,
            "test_output": test_output.strip() if test_output else None,
            "rollback_performed": True,
            "rollback_executed": True,
            "healed": was_healed,
            "repaired_code": repaired_code,
            "error": error,
        }

    def _execute_repl_repair_loop(
        self, working_code: str, max_iterations: int
    ) -> tuple[str, Any, int, bool]:
        """Executes LocalREPL evaluation, iterative healing, and AntiLoop circuit breaker."""
        repl = LocalREPL()
        circuit_breaker = AntiLoopCircuitBreaker(max_duplicates=2, max_total_attempts=max_iterations)
        iteration_count = 0
        circuit_breaker.register_attempt(working_code)

        try:
            ast.parse(working_code)
        except SyntaxError as syn_err:
            logger.debug("Initial proposal syntax check note: %s", syn_err)

        repl_res = repl.eval_and_heal(working_code)
        iteration_count += 1
        if repl_res.healed and repl_res.healed_code:
            working_code = repl_res.healed_code

        while iteration_count < max_iterations and not circuit_breaker.tripped:
            try:
                ast.parse(working_code)
                if repl_res.status in ("SUCCESS", "HEALED"):
                    break
            except SyntaxError as syn_err:
                logger.debug("Syntax loop parse note: %s", syn_err)

            iteration_count += 1
            err_msg = repl_res.stderr or repl_res.original_error or "SyntaxError in proposal"
            working_code = repl._apply_self_healing(working_code, err_msg)
            if not circuit_breaker.register_attempt(working_code):
                logger.warning("[SelfHealingREPL] Circuit Breaker tripped: %s", circuit_breaker.trip_reason)
                break

            repl_res = repl.execute_code(working_code)
            if repl_res.status == "SUCCESS":
                try:
                    ast.parse(working_code)
                    repl_res.healed = True
                    repl_res.healed_code = working_code
                    repl_res.status = "HEALED"
                    break
                except SyntaxError as syn_err:
                    logger.debug("Repaired code syntax check note: %s", syn_err)

        repl.cleanup()
        final_ast_ok = True
        try:
            ast.parse(working_code)
        except SyntaxError as syn_err:
            logger.debug("Final AST parse note: %s", syn_err)
            final_ast_ok = False

        repl_ok = final_ast_ok and repl_res.status in ("SUCCESS", "HEALED")
        return working_code, repl_res, iteration_count, repl_ok

    def _execute_test_verification(
        self, test_cmd: Union[str, List[str]]
    ) -> tuple[bool, str, Optional[str]]:
        """Runs external pytest or regression command within sandbox."""
        cmd_args = test_cmd if isinstance(test_cmd, list) else shlex.split(test_cmd)
        try:
            proc = subprocess.run(cmd_args, capture_output=True, text=True, timeout=30, cwd=r"C:\vazus")
            output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            if proc.returncode != 0:
                return False, output, f"Test command exited with status code {proc.returncode}"
            return True, output, None
        except Exception as e:
            logger.debug("Test verification error: %s", e)
            return False, "", f"Test execution exception: {e}"

    def _verify_jury_and_smt(
        self,
        guardrail: RollbackGuardrail,
        target_path: Path,
        orig_code: str,
        working_code: str,
        agent_votes: Optional[List[Dict[str, Any]]],
        *,
        iters: int,
        repl_res: Any,
        repl_ok: bool,
        file_existed: bool
    ) -> tuple[bool, Optional[Dict[str, Any]], Any, str]:
        jury_verdict = self.jury.vote(proposal=working_code, votes=agent_votes, file_path=str(target_path), orig_code=orig_code or None)
        if not jury_verdict.approved:
            self._rollback(guardrail, file_existed, target_path)
            res = self._build_failure_result(
                "JURY_CONSENSUS_REJECTED", target_path, iterations=iters, repl_res=repl_res, jury_verdict=jury_verdict,
                smt_status="UNSAT" if jury_verdict.smt_satisfied else "FAILED", smt_verified=jury_verdict.smt_satisfied,
                was_healed=repl_ok and repl_res.healed, repaired_code=working_code, error="; ".join(jury_verdict.rejection_reasons)
            )
            return False, res, jury_verdict, "FAILED"

        smt_res = self.smt_verifier.verify_code_contracts(working_code)
        smt_status = getattr(smt_res, "smt_solver_status", getattr(smt_res, "solver_status", "UNSAT"))
        if smt_status == "SAT" or not getattr(smt_res, "contract_satisfied", True):
            self._rollback(guardrail, file_existed, target_path)
            err = getattr(smt_res, "error_message", "SMT contract violation (SAT counterexample found)")
            res = self._build_failure_result(
                "SMT_CONTRACT_FAILED", target_path, iterations=iters, repl_res=repl_res, jury_verdict=jury_verdict,
                smt_status=smt_status, smt_verified=False, was_healed=repl_ok and repl_res.healed, repaired_code=working_code, error=err
            )
            return False, res, jury_verdict, smt_status

        return True, None, jury_verdict, smt_status

    def _write_and_verify_tests(
        self,
        guardrail: RollbackGuardrail,
        target_path: Path,
        working_code: str,
        test_cmd: Optional[Union[str, List[str]]],
        *,
        iters: int,
        repl_res: Any,
        jury_verdict: Any,
        smt_status: str,
        repl_ok: bool,
        file_existed: bool
    ) -> Dict[str, Any]:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(working_code, encoding="utf-8")
        except Exception as e:
            logger.warning("Target file write error: %s", e)
            self._rollback(guardrail, file_existed, target_path)
            return self._build_failure_result(
                "FILE_WRITE_ERROR", target_path, iterations=iters, repl_res=repl_res, jury_verdict=jury_verdict,
                smt_status=smt_status, smt_verified=True, was_healed=repl_ok and repl_res.healed, repaired_code=working_code,
                error=f"Failed to write target file: {e}"
            )

        test_passed, test_out, test_err = True, None, None
        if test_cmd:
            test_passed, test_out, test_err = self._execute_test_verification(test_cmd)
            if not test_passed:
                self._rollback(guardrail, file_existed, target_path)
                status = "TEST_SUITE_EXCEPTION" if "exception" in (test_err or "").lower() else "TEST_SUITE_FAILED"
                return self._build_failure_result(
                    status, target_path, iterations=iters, repl_res=repl_res, jury_verdict=jury_verdict,
                    smt_status=smt_status, smt_verified=True, was_healed=repl_ok and repl_res.healed, repaired_code=working_code,
                    error=test_err or "Test failed", test_output=test_out
                )

        return {
            "status": "HEALED" if repl_ok and repl_res.healed else "SUCCESS",
            "repaired": True,
            "target_file": str(target_path),
            "iterations_used": iters,
            "repl_result": repl_res.to_dict(),
            "jury_verdict": jury_verdict.to_dict() if hasattr(jury_verdict, "to_dict") else jury_verdict,
            "smt_status": smt_status,
            "smt_verified": True,
            "test_passed": test_passed,
            "test_output": test_out,
            "rollback_performed": False,
            "rollback_executed": False,
            "healed": repl_ok and repl_res.healed,
            "repaired_code": working_code,
            "error": None,
        }

    def run_self_healing_repair(
        self,
        target_file: Union[str, Path],
        code_proposal: str,
        agent_votes: Optional[List[Dict[str, Any]]] = None,
        test_cmd: Optional[Union[str, List[str]]] = None,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """Executes self-healing repair loop on target_file with code_proposal."""
        target_path = Path(target_file).resolve()
        file_existed = target_path.exists()
        orig_code = target_path.read_text(encoding="utf-8") if file_existed else ""

        guardrail = RollbackGuardrail(target_path)
        guardrail.create_snapshot()

        working_code, repl_res, iters, repl_ok = self._execute_repl_repair_loop(code_proposal, max_iterations)
        if not repl_ok or repl_res.status not in ("SUCCESS", "HEALED"):
            self._rollback(guardrail, file_existed, target_path)
            err = repl_res.stderr or repl_res.original_error or "Unfixable code error"
            return self._build_failure_result("FAILED", target_path, iterations=iters, repl_res=repl_res, was_healed=repl_ok and repl_res.healed, error=err)

        ok_v, fail_res, jury_verdict, smt_status = self._verify_jury_and_smt(
            guardrail, target_path, orig_code, working_code, agent_votes,
            iters=iters, repl_res=repl_res, repl_ok=repl_ok, file_existed=file_existed
        )
        if not ok_v and fail_res is not None:
            return fail_res

        return self._write_and_verify_tests(
            guardrail, target_path, working_code, test_cmd,
            iters=iters, repl_res=repl_res, jury_verdict=jury_verdict,
            smt_status=smt_status, repl_ok=repl_ok, file_existed=file_existed
        )

    def _rollback(self, guardrail: RollbackGuardrail, file_existed: bool, target_path: Path) -> bool:
        """Helper handling snapshot restoration and clean file removal for new files."""
        if file_existed:
            return guardrail.restore_snapshot()
        if target_path.exists():
            try:
                target_path.unlink()
                return True
            except Exception as exc:
                logger.debug("Target path cleanup note: %s", exc)
                return False
        return True
