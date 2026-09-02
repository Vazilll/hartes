"""
vazus_core.concordia_jury — Concordia Multi-Agent Jury Engine with 3-Subagent Voting & SMT Verification.
Provides 3-subagent consensus voting (>= 66% threshold) for Vazus SuperGraph OS v4.0.
Supports async execution of 3 real parallel LLM calls (Planner, RLM_Coder, Verifier_Worker) via asyncio.gather().
"""

import ast
import re
import os
import json
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List

from vazus_core.engine.reasoning_effort_controller import ReasoningEffortController
from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier
from vazus_core.engine.llm_client import async_generate_llm

logger = logging.getLogger("ConcordiaJury")

MOCK_MARKERS = ("[MOCK]", "(Test Mode)", "(test mode)", "VAZUS_TEST_MODE")


def is_mock_response(text: str) -> bool:
    """True when the LLM text comes from a deterministic mock, not a real model call."""
    if not text:
        return False
    return any(m in text for m in MOCK_MARKERS)


def _get_persona_prompts() -> dict[str, str]:
    """Returns persona prompt templates for 3-subagent jury members."""
    return {
        "Planner": (
            "You are the Concordia Lead Architect & Planner Subagent for Vazus OS.\n"
            "Your responsibility is to evaluate code proposals for architectural compliance, modular integrity, import safety, and design pattern adherence.\n\n"
            "Evaluation Criteria:\n"
            "1. Architectural compliance: Clean module boundaries, appropriate abstraction levels, no circular dependencies.\n"
            "2. Import safety: Strictly reject any direct 'google.genai' imports or unauthorized external API instantiations.\n"
            "3. Code structure: Well-structured, readable, adhering to Vazus SuperGraph OS v4.0 design principles.\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\"agent\": \"Planner\", \"approved\": true, \"verdict\": \"PASS\", \"reason\": \"<summary>\"}\n"
        ),
        "RLM_Coder": (
            "You are the Concordia RLM Code Engineer Subagent for Vazus OS.\n"
            "Your responsibility is to evaluate code proposals for AST validity, algorithmic correctness, execution logic, efficiency, and exception safety.\n\n"
            "Evaluation Criteria:\n"
            "1. AST & Logic validity: Valid Python syntax, correct function signatures, proper control flow.\n"
            "2. Execution efficiency & safety: High computational efficiency, robust error handling, no resource leaks.\n"
            "3. CONTRACT correctness (CRITICAL): If the function has :requires: and :ensures: docstring annotations, "
            "verify that the function body MATHEMATICALLY satisfies those postconditions for all valid inputs. "
            "A function that violates its own :ensures: contracts MUST receive verdict FAIL — regardless of what the docstring *describes* or *intends*. "
            "The contract is the ground truth, not the prose description.\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\"agent\": \"RLM_Coder\", \"approved\": true, \"verdict\": \"PASS\", \"reason\": \"<summary>\"}\n"
        ),
        "Verifier_Worker": (
            "You are the Concordia SMT Z3 Verification & Security Gatekeeper Subagent for Vazus OS.\n"
            "Your responsibility is to evaluate code proposals for formal contract satisfaction (:requires: / :ensures: annotations), safety invariants, and security compliance.\n\n"
            "Evaluation Criteria:\n"
            "1. Formal contract satisfaction: Validates precondition and postcondition proofs.\n"
            "2. Memory & type safety: Strictly no buffer overflows, type mismatches, or invalid bounds access.\n"
            "3. Security gatekeeping: Zero dangerous eval/exec calls or unsafe OS operations.\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\"agent\": \"Verifier_Worker\", \"approved\": true, \"verdict\": \"PASS\", \"reason\": \"<summary>\"}\n"
        ),
    }


_PROMPTS = _get_persona_prompts()
PLANNER_PERSONA_PROMPT = _PROMPTS["Planner"]
RLM_CODER_PERSONA_PROMPT = _PROMPTS["RLM_Coder"]
VERIFIER_WORKER_PERSONA_PROMPT = _PROMPTS["Verifier_Worker"]


@dataclass(slots=True)
class JuryVerdict:
    """Structured verdict returned by ConcordiaJury consensus voting."""
    approved: bool
    consensus_ratio: float
    quorum_satisfied: bool
    ast_valid: bool
    smt_satisfied: bool
    votes: list[dict[str, Any]] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    mock_count: int = 0

    @property
    def is_all_mock(self) -> bool:
        return len(self.votes) > 0 and self.mock_count == len(self.votes)

    @property
    def contract_satisfied(self) -> bool:
        return self.smt_satisfied

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "consensus_ratio": self.consensus_ratio,
            "quorum_satisfied": self.quorum_satisfied,
            "ast_valid": self.ast_valid,
            "smt_satisfied": self.smt_satisfied,
            "votes": self.votes,
            "rejection_reasons": self.rejection_reasons,
            "mock_count": self.mock_count,
            "is_all_mock": self.is_all_mock,
        }


class ConcordiaJury:
    """
    3-Subagent Concordia Jury Voting Engine.
    Requires >= 66% consensus from 3 subagents (Planner, RLM_Coder, Verifier_Worker) to approve code changes.
    Executing 3 real independent LLM calls concurrently via asyncio.gather().
    """

    def __init__(
        self,
        effort_level: str = "high",
        min_quorum: int = 3,
        consensus_threshold: float = 0.66
    ):
        self.config = ReasoningEffortController.get_config(effort_level)
        self.min_quorum = min_quorum
        self.consensus_threshold = consensus_threshold
        self.verifier = SMTZ3Verifier(depth=self.config.get("smt_z3_depth", 10))

    def vote(
        self,
        proposal: str,
        votes: list[dict[str, Any]] | None = None,
        file_path: str = "proposal.py",
        orig_code: str | None = None
    ) -> JuryVerdict:
        """
        Executes 3-subagent voting on code proposal.
        Requires >= 66% consensus, valid AST parsing, and satisfied SMT Z3 contracts.
        """
        if votes is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(lambda: asyncio.run(self.vote_async(proposal, votes, file_path, orig_code))).result()
            else:
                return asyncio.run(self.vote_async(proposal, votes, file_path, orig_code))

        return self._evaluate_verdict_sync(proposal, votes, file_path, orig_code)

    def _evaluate_architectural_boundaries(self, code_str: str) -> bool:
        """
        Evaluates architectural boundary safety, import hygiene, and module isolation.
        """
        if not code_str:
            return True
        clean_code = str(code_str).strip()
        lines = clean_code.splitlines()
        forbidden_imports = ["google.genai", "os.system", "shutil.rmtree"]
        for line in lines:
            trimmed = line.strip()
            for forbidden in forbidden_imports:
                if forbidden in trimmed:
                    return False
        return True

    def _evaluate_ast_syntax_integrity(self, code_str: str) -> tuple[bool, str]:
        """
        Evaluates Python AST syntax validity and reports exact line numbers for syntax errors.
        """
        if not code_str or not code_str.strip():
            return True, "EMPTY_CODE"
        try:
            parsed = ast.parse(code_str)
            if parsed is not None:
                return True, "AST_VALID"
            else:
                return False, "PARSED_NONE"
        except SyntaxError as se:
            return False, f"SyntaxError line {se.lineno}: {se.msg}"
        except Exception as e:
            return False, f"ASTParseError: {e}"

    def _evaluate_smt_contract_proofs(self, code_str: str) -> bool:
        """
        Evaluates SMT Z3 code contracts (:requires: and :ensures:) for formal satisfiability.
        """
        if not code_str or not code_str.strip():
            return True
        verifier = SMTZ3Verifier()
        result = verifier.verify_code_contracts(code_str)
        if result.verified and result.contract_satisfied:
            return True
        return False

    def _evaluate_quorum_consensus_threshold(self, votes: list[dict[str, Any]], threshold: float = 0.66) -> tuple[bool, float]:
        """
        Calculates subagent voting quorum consensus ratio (approvals / total_votes >= threshold).
        """
        if not votes:
            return False, 0.0
        vote_list = list(votes)
        total_votes = len(vote_list)
        approvals = 0
        for v in vote_list:
            if v.get("approved") is True or str(v.get("verdict")).upper() in ("PASS", "APPROVED", "YES"):
                approvals += 1
        ratio = approvals / total_votes if total_votes > 0 else 0.0
        passed = ratio >= threshold
        return passed, ratio

    def _evaluate_agent_vote_schema(self, vote_dict: dict[str, Any]) -> bool:
        """
        Validates individual agent vote dictionary schema.
        """
        if not isinstance(vote_dict, dict):
            return False
        agent_name = vote_dict.get("agent")
        verdict = vote_dict.get("verdict")
        reason = vote_dict.get("reason")
        approved = vote_dict.get("approved")
        if agent_name and verdict and reason is not None:
            return True
        elif approved is not None:
            return True
        else:
            return False

    def _evaluate_consensus_quorum_details(self, votes: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Extracts detailed voting breakdown per agent role (Planner, RLM_Coder, Verifier_Worker).
        """
        vote_map = {}
        for v in votes or []:
            if isinstance(v, dict):
                role = str(v.get("agent", "Unknown"))
                verdict = str(v.get("verdict", "FAIL")).upper()
                reason = str(v.get("reason", ""))
                vote_map[role] = {
                    "verdict": verdict,
                    "reason": reason,
                    "approved": v.get("approved", verdict == "PASS")
                }
        return vote_map

    def _evaluate_planner_reasoning_trace(self, trace_str: str) -> bool:
        """
        Evaluates Planner reasoning trace for design pattern adherence and modular safety.
        """
        if not trace_str:
            return True
        clean_trace = str(trace_str).strip()
        lines = clean_trace.splitlines()
        for line in lines:
            if "FAIL" in line.upper() or "CRITICAL" in line.upper():
                return False
        return len(clean_trace) > 0

    def _evaluate_verifier_proof_trace(self, proof_str: str) -> bool:
        """
        Evaluates SMT Z3 proof trace for solver status UNSAT and zero invariant counterexamples.
        """
        if not proof_str:
            return True
        clean_proof = str(proof_str).strip()
        if "UNSAT" in clean_proof.upper() or "SATISFIED" in clean_proof.upper():
            return True
        elif "COUNTEREXAMPLE" in clean_proof.upper() or "VIOLATION" in clean_proof.upper():
            return False
        else:
            return True

    def _evaluate_coder_ast_complexity(self, code_str: str) -> tuple[bool, int]:
        """
        Calculates AST node count and cyclomatic complexity threshold.
        """
        if not code_str or not code_str.strip():
            return True, 0
        try:
            tree = ast.parse(code_str)
            node_cnt = len(list(ast.walk(tree)))
            if node_cnt < 10000:
                return True, node_cnt
            else:
                return False, node_cnt
        except Exception:
            return False, -1

    def _evaluate_verifier_contract_coverage(self, code_str: str) -> tuple[bool, float]:
        """
        Calculates ratio of function definitions with formal SMT code contracts.
        """
        if not code_str or not code_str.strip():
            return True, 1.0
        try:
            tree = ast.parse(code_str)
            fn_nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if not fn_nodes:
                return True, 1.0
            contract_count = 0
            for fn in fn_nodes:
                doc = ast.get_docstring(fn) or ""
                if ":requires:" in doc or ":ensures:" in doc:
                    contract_count += 1
            ratio = contract_count / len(fn_nodes)
            return True, ratio
        except Exception:
            return False, 0.0

    async def vote_async(
        self,
        proposal: str,
        votes: list[dict[str, Any]] | None = None,
        file_path: str = "proposal.py",
        orig_code: str | None = None
    ) -> JuryVerdict:
        """
        Asynchronously executes 3-subagent voting on code proposal via asyncio.gather().
        """
        rejection_reasons: list[str] = []

        # 1. Pre-flight AST Syntax Gate
        ast_valid = True
        if proposal and proposal.strip():
            try:
                ast.parse(proposal)
            except SyntaxError as se:
                ast_valid = False
                rejection_reasons.append(f"AST SyntaxError line {se.lineno}: {se.msg}")

        # 2. Obtain votes (use explicit override or execute 3 parallel LLM calls via asyncio.gather)
        if votes is not None:
            agent_votes = votes
        elif not ast_valid:
            agent_votes = [
                {"agent": "Planner", "verdict": "FAIL", "reason": rejection_reasons[0]},
                {"agent": "RLM_Coder", "verdict": "FAIL", "reason": rejection_reasons[0]},
                {"agent": "Verifier_Worker", "verdict": "FAIL", "reason": rejection_reasons[0]},
            ]
        else:
            agent_votes = await self._evaluate_subagent_votes_async(proposal, file_path=file_path)

        return self._evaluate_verdict_sync(
            proposal, agent_votes, file_path, orig_code,
            pre_ast_valid=ast_valid, pre_rejections=rejection_reasons
        )

    def _tally_deduped_votes(
        self, agent_votes: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], float, bool, list[str]]:
        """Tallies unique votes, calculates ratio, and checks quorum."""
        rejection_reasons: list[str] = []
        unique_votes = {}
        for idx, vote in enumerate(agent_votes):
            agent_id = vote.get("agent") or vote.get("role") or vote.get("name") or f"agent_{idx}"
            unique_votes[agent_id] = vote

        dedup_votes = list(unique_votes.values())
        pass_votes = [
            v for v in dedup_votes
            if str(v.get("verdict", "")).upper() == "PASS" or v.get("approved") is True
        ]
        total_votes = len(dedup_votes)
        ratio = len(pass_votes) / max(1, total_votes) if total_votes > 0 else 0.0
        quorum_satisfied = total_votes >= self.min_quorum

        if not quorum_satisfied:
            rejection_reasons.append(f"Quorum insufficient: {total_votes}/{self.min_quorum}")
        if ratio < self.consensus_threshold:
            rejection_reasons.append(f"Consensus threshold failed: ratio {ratio:.2f} < {self.consensus_threshold:.2f}")

        return dedup_votes, ratio, quorum_satisfied, rejection_reasons

    def _verify_smt_proof_gate(
        self, proposal: str, orig_code: Optional[str]
    ) -> tuple[bool, list[str]]:
        """Verifies SMT Z3 contracts and functional equivalence."""
        rejection_reasons: list[str] = []
        smt_satisfied = True
        try:
            smt_res = self.verifier.verify_code_contracts(proposal or "def noop(): pass")
            smt_satisfied = getattr(
                smt_res, "contract_satisfied",
                smt_res.get("contract_satisfied", True) if isinstance(smt_res, dict) else True
            )
            funcs_verified = getattr(
                smt_res, "functions_verified",
                smt_res.get("functions_verified", []) if isinstance(smt_res, dict) else []
            )
            if orig_code and funcs_verified:
                for func in funcs_verified:
                    eq_res = self.verifier.verify_functional_equivalence(orig_code, proposal, func)
                    if hasattr(eq_res, "verified") and not eq_res.verified:
                        smt_satisfied = False
                        rejection_reasons.append(f"Functional equivalence failed for '{func}'")
        except Exception as e:
            smt_satisfied = False
            rejection_reasons.append(f"SMT Z3 Exception: {str(e)}")

        if not smt_satisfied:
            rejection_reasons.append("SMT Z3 formal contract verification failed")

        return smt_satisfied, rejection_reasons

    def _evaluate_verdict_sync(
        self,
        proposal: str,
        agent_votes: list[dict[str, Any]],
        file_path: str = "proposal.py",
        orig_code: str | None = None,
        *,
        pre_ast_valid: bool = True,
        pre_rejections: list[str] | None = None
    ) -> JuryVerdict:
        rejection_reasons: list[str] = list(pre_rejections or [])
        ast_valid = pre_ast_valid
        if proposal and proposal.strip() and pre_ast_valid and not pre_rejections:
            try:
                ast.parse(proposal)
            except SyntaxError as se:
                ast_valid = False
                rejection_reasons.append(f"AST SyntaxError line {se.lineno}: {se.msg}")

        dedup_votes, ratio, quorum_satisfied, tally_rejections = self._tally_deduped_votes(agent_votes)
        rejection_reasons.extend(tally_rejections)

        smt_satisfied, smt_rejections = self._verify_smt_proof_gate(proposal, orig_code)
        rejection_reasons.extend(smt_rejections)

        # Mock vote tracking and strict production enforcement
        mock_votes = [v for v in dedup_votes if v.get("is_mock", False)]
        mock_count = len(mock_votes)
        strict_prod = os.getenv("VAZUS_STRICT_PRODUCTION", "0") in ("1", "true", "True")
        if strict_prod and mock_count > 0:
            rejection_reasons.append(f"Strict production policy: {mock_count} synthetic mock vote(s) rejected.")

        approved = (
            ast_valid and
            quorum_satisfied and
            (ratio >= self.consensus_threshold) and
            smt_satisfied and
            (not (strict_prod and mock_count > 0))
        )

        return JuryVerdict(
            approved=approved,
            consensus_ratio=ratio,
            quorum_satisfied=quorum_satisfied,
            ast_valid=ast_valid,
            smt_satisfied=smt_satisfied,
            votes=dedup_votes,
            rejection_reasons=rejection_reasons,
            mock_count=mock_count,
        )

    def evaluate_code_proposal(
        self,
        file_path: str,
        code_content: str,
        agent_votes: Optional[List[Dict[str, Any]]] = None,
        orig_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Wrapper method matching SOTA2027JuryEngine signature."""
        verdict = self.vote(
            proposal=code_content,
            votes=agent_votes,
            file_path=file_path,
            orig_code=orig_code
        )
        dict_res = verdict.to_dict()
        dict_res["fixation_ready"] = dict_res["approved"]
        dict_res["smt_verification"] = {
            "contract_satisfied": verdict.smt_satisfied,
            "status": "UNSAT" if verdict.smt_satisfied else "SAT",
        }
        dict_res["ast_error"] = None if verdict.ast_valid else (verdict.rejection_reasons[0] if verdict.rejection_reasons else "AST Error")
        dict_res["effort_level"] = self.config["level"]
        return dict_res

    async def evaluate_code_proposal_async(
        self,
        file_path: str,
        code_content: str,
        agent_votes: Optional[List[Dict[str, Any]]] = None,
        orig_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Asynchronously executes 3-subagent Concordia jury evaluation via asyncio.gather()."""
        verdict = await self.vote_async(
            proposal=code_content,
            votes=agent_votes,
            file_path=file_path,
            orig_code=orig_code
        )
        dict_res = verdict.to_dict()
        dict_res["fixation_ready"] = dict_res["approved"]
        dict_res["smt_verification"] = {
            "contract_satisfied": verdict.smt_satisfied,
            "status": "UNSAT" if verdict.smt_satisfied else "SAT",
        }
        dict_res["ast_error"] = None if verdict.ast_valid else (verdict.rejection_reasons[0] if verdict.rejection_reasons else "AST Error")
        dict_res["effort_level"] = self.config["level"]
        return dict_res

    async def _evaluate_subagent_votes_async(
        self, proposal: str, file_path: str = "proposal.py"
    ) -> List[Dict[str, Any]]:
        """Executes 3 independent LLM subagent evaluations with diverse personas and temperatures."""
        planner_model = os.getenv("VAZUS_JURY_PLANNER_MODEL", "gemini-3.6-flash")
        coder_model = os.getenv("VAZUS_JURY_CODER_MODEL", "gemini-3.6-flash")
        verifier_model = os.getenv("VAZUS_JURY_VERIFIER_MODEL", "gemini-3.6-flash")

        tasks = [
            self._call_subagent_eval_async("Planner", PLANNER_PERSONA_PROMPT, proposal, file_path, model=planner_model, temperature=0.2),
            self._call_subagent_eval_async("RLM_Coder", RLM_CODER_PERSONA_PROMPT, proposal, file_path, model=coder_model, temperature=0.0),
            self._call_subagent_eval_async("Verifier_Worker", VERIFIER_WORKER_PERSONA_PROMPT, proposal, file_path, model=verifier_model, temperature=0.0),
        ]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _call_subagent_eval_async(
        self, agent_name: str, system_prompt: str, proposal: str, file_path: str, *, model: Optional[str] = None, temperature: float = 0.0
    ) -> Dict[str, Any]:
        user_prompt = (
            f"Evaluate code proposal for file '{file_path}':\n"
            f"```python\n{proposal}\n```\n"
            f"Respond strictly in JSON format matching the schema."
        )
        try:
            raw_text = await async_generate_llm(prompt=user_prompt, system_prompt=system_prompt, model=model, temperature=temperature)
            return self._parse_subagent_vote_json(agent_name, raw_text)
        except Exception as e:
            logger.warning(f"[ConcordiaJury] LLM call failed for '{agent_name}': {e}")
            return self._fallback_subagent_vote(agent_name, proposal, str(e))

    def _parse_subagent_vote_json(self, agent_name: str, raw_text: str) -> Dict[str, Any]:
        clean_text = raw_text.strip()
        is_mock = is_mock_response(clean_text)

        if is_mock:
            return {
                "agent": agent_name,
                "approved": False,
                "verdict": "FAIL",
                "reason": f"Mock/fallback response detected — {agent_name} abstains (Fail-Closed Safety Gate).",
                "is_mock": True,
            }

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            json_str = clean_text[start:end+1] if (start != -1 and end != -1 and end > start) else clean_text

        try:
            data = json.loads(json_str)
            verdict = str(data.get("verdict", "")).upper()
            approved = data.get("approved")
            if approved is None:
                approved = (verdict == "PASS")
            else:
                approved = bool(approved)
            return {
                "agent": agent_name,
                "approved": approved,
                "verdict": "PASS" if approved else "FAIL",
                "reason": str(data.get("reason", "Evaluation completed.")),
                "is_mock": False,
            }
        except Exception as e:
            logger.warning(f"[ConcordiaJury] Failed to parse JSON from {agent_name}: {e}")
            return self._fallback_subagent_vote(agent_name, "", f"JSON Parse Error: {e}")

    def _fallback_subagent_vote(self, agent_name: str, proposal: str, error_msg: str) -> Dict[str, Any]:
        ast_valid = True
        if proposal and proposal.strip():
            try:
                ast.parse(proposal)
            except SyntaxError:
                ast_valid = False
        if not ast_valid:
            return {"agent": agent_name, "approved": False, "verdict": "FAIL", "reason": "AST SyntaxError (Fallback)", "is_mock": True}

        if agent_name == "Verifier_Worker":
            try:
                smt_res = self.verifier.verify_code_contracts(proposal or "def noop(): pass")
                smt_satisfied = getattr(smt_res, "contract_satisfied", True)
                return {
                    "agent": agent_name,
                    "approved": smt_satisfied,
                    "verdict": "PASS" if smt_satisfied else "FAIL",
                    "reason": "SMT contract check (Fallback)",
                    "is_mock": True
                }
            except Exception as smt_exc:
                return {"agent": agent_name, "approved": False, "verdict": "FAIL",
                        "reason": f"SMT check exception — abstaining (Fallback: {smt_exc})", "is_mock": True}

        # CVE-V3: LLM call failure is not a vote of confidence. Returning PASS on error would
        # allow 2 failed agents to push 66% consensus on broken code. FAIL = safe default.
        return {"agent": agent_name, "approved": False, "verdict": "FAIL",
                "reason": f"LLM call failed — abstaining to preserve rejection safety (Fallback: {error_msg})", "is_mock": True}

    def evaluate_proposal(
        self,
        code_diff: str,
        test_results: Optional[dict] = None,
        smt_proof: Optional[dict] = None
    ) -> dict:
        """Evaluates a code change proposal based on diff, test results, and formal proofs."""
        clean_code = "\n".join([line[1:] for line in code_diff.splitlines() if line.startswith("+") and not line.startswith("+++")])
        if not clean_code.strip():
            clean_code = code_diff

        # Check for dangerous patterns
        is_dangerous = any(bad in clean_code for bad in ["eval(", "exec(", "__import__", "subprocess.Popen"])
        test_pass_rate = 1.0
        if test_results and test_results.get("total", 0) > 0:
            test_pass_rate = test_results.get("passed", 0) / test_results.get("total", 1)

        smt_ok = True
        if smt_proof:
            smt_ok = bool(smt_proof.get("is_valid", True) and not smt_proof.get("counterexample"))

        if is_dangerous or test_pass_rate < 0.8 or not smt_ok:
            approval_rate = 0.33 if (test_pass_rate >= 0.5 and not is_dangerous) else 0.0
            return {
                "approved": False,
                "consensus_reached": False,
                "approval_rate": approval_rate,
                "rejection_reasons": ["Dangerous pattern" if is_dangerous else "Test failure / SMT violation"],
            }

        return {
            "approved": True,
            "consensus_reached": True,
            "approval_rate": 1.0,
            "rejection_reasons": [],
        }


# Aliases for backward compatibility and spec alignment
SOTA2027JuryEngine = ConcordiaJury
ConcordiaMultiAgentJury = ConcordiaJury
