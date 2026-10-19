#!/usr/bin/env python3
"""
vazus_core.engine.dialectical_synthesizer — Dialectical Auto-Coding Engine.
==========================================================================

Implements Dialectical Multi-Agent Code Synthesis (Thesis -> Antithesis -> Synthesis):
  - Stage 1 (Thesis / Actor): Generates initial candidate implementation.
  - Stage 2 (Antithesis / Critic & Verifier): Formulates counterarguments, extracts edge cases,
            runs static taint / AST checks, and checks for SMT Z3 contract violations.
  - Stage 3 (Synthesis / Reconciler): Produces a hardened, self-consistent implementation
            resolving all dialectical contradictions.
"""

import logging
import re
from typing import Any, Dict, Optional

from vazus_core.engine.llm_client import async_generate_llm
from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier

logger = logging.getLogger("vazus_core.engine.dialectical")


class DialecticalSynthesizer:
    """
    Orchestrates dialectical 3-stage code synthesis.
    """

    def __init__(self, depth: int = 10):
        self.smt_verifier = SMTZ3Verifier(depth=depth)

    async def _generate_thesis(self, task_description: str, context: Optional[str] = None) -> str:
        """Stage 1: Generate initial candidate implementation (Thesis)."""
        thesis_prompt = f"""
Task: {task_description}
Context: {context or "None"}

Write a clean, idiomatic, high-performance Python implementation for this task.
Include type annotations and docstrings. Return only Python code in ```python ... ```.
"""
        thesis_raw = await async_generate_llm(
            prompt=thesis_prompt,
            system_prompt="You are an expert Principal Engineer (Actor / Thesis). Generate clean, correct code.",
        )
        return self._extract_code(thesis_raw)

    async def _generate_antithesis(self, thesis_code: str, smt_res: Dict[str, Any]) -> str:
        """Stage 2: Formulate counterarguments and critiques (Antithesis)."""
        critic_prompt = f"""
Analyze the candidate Python code below for flaws, edge-case bugs, potential regressions, performance bottlenecks, and security issues.

CANDIDATE CODE:
```python
{thesis_code}
```

SMT CONTRACT STATUS: {smt_res.get("status", "UNVERIFIED")}

Provide a structured list of concrete counterarguments (Antithesis):
1. Edge cases not handled (None, empty, max int, boundary).
2. Algorithmic complexity issues.
3. Potential security or exception handling risks.
"""
        return await async_generate_llm(
            prompt=critic_prompt,
            system_prompt="You are a strict Code Reviewer & Formal Verification Critic (Antithesis). Find all bugs and flaws.",
        )

    async def _generate_synthesis(self, task_description: str, thesis_code: str, antithesis_raw: str) -> str:
        """Stage 3: Synthesize unified hardened implementation."""
        synthesis_prompt = f"""
Task: {task_description}

ORIGINAL PROPOSAL (Thesis):
```python
{thesis_code}
```

CRITIQUE & CONTRADICTIONS (Antithesis):
{antithesis_raw}

Synthesize the final, hardened, production-ready code that incorporates the strengths of the Thesis while resolving every contradiction and edge case raised by the Antithesis.
Return ONLY executable Python code in ```python ... ``` fences.
"""
        synthesis_raw = await async_generate_llm(
            prompt=synthesis_prompt,
            system_prompt="You are a Master Architect (Synthesis). Output the hardened, unified code.",
        )
        return self._extract_code(synthesis_raw)

    async def _apply_cegis_refinement(
        self, task_description: str, final_code: str, final_smt_res: Any
    ) -> tuple[str, Any, bool]:
        """Stage 3b: Closed-Loop SMT Z3 Verification & CEGIS Refinement."""
        if not (
            getattr(final_smt_res, "smt_solver_status", "") == "SAT" and getattr(final_smt_res, "counterexample", None)
        ):
            return final_code, final_smt_res, False

        logger.info("Dialectical Synthesis: SMT SAT violation detected in synthesis. Triggering CEGIS refinement...")
        from vazus_core.verification.smt_z3_verifier import generate_failing_pytest_fixture

        cex = final_smt_res.counterexample
        cex_args = ", ".join(f"{k}={v}" for k, v in cex.items() if not k.startswith("_"))
        fixture_code = generate_failing_pytest_fixture(func_name="synthesized_function", counterexample=cex)

        cegis_prompt = f"""
Task: {task_description}

Your synthesized code failed formal SMT Z3 contract verification.
Counterexample violation: with inputs ({cex_args}), a contract postcondition is violated.

Failing test fixture:
```python
{fixture_code}
```

CURRENT SYNTHESIS:
```python
{final_code}
```

Fix the code so that it strictly satisfies all contract preconditions and postconditions for ALL inputs including the counterexample.
Return ONLY corrected Python code in ```python ... ``` fences.
"""
        refined_raw = await async_generate_llm(
            prompt=cegis_prompt,
            system_prompt="You are a Formal Methods Engineer (CEGIS Refiner). Fix the SMT counterexample violation.",
        )
        refined_code = self._extract_code(refined_raw)
        if refined_code:
            final_code = refined_code
            final_smt_res = self.smt_verifier.verify_code_contracts(final_code)
            return final_code, final_smt_res, True
        return final_code, final_smt_res, False

    async def synthesize(
        self, task_description: str, context: Optional[str] = None, fast_mode: bool = False
    ) -> Dict[str, Any]:
        """Executes Thesis -> Antithesis -> Synthesis cycle, with fast-path TDD support."""
        try:
            logger.info("Dialectical Synthesis: Stage 1 (Thesis)...")
            thesis_code = await self._generate_thesis(task_description, context)

            smt_res = self.smt_verifier.verify_code_contracts(thesis_code)

            if fast_mode and thesis_code:
                # Fast path: Verify AST parse and contract validity
                import ast

                try:
                    ast.parse(thesis_code)
                    initial_status = (
                        smt_res.get("status")
                        if isinstance(smt_res, dict)
                        else getattr(smt_res, "smt_solver_status", getattr(smt_res, "solver_status", "UNVERIFIED"))
                    )
                    if initial_status != "SAT":  # No contract violation found
                        logger.info("Dialectical Synthesis: Fast-mode direct resolution (1 LLM call).")
                        return {
                            "status": "SUCCESS",
                            "task": task_description,
                            "thesis_code": thesis_code,
                            "antithesis_critique": "[Fast-Mode: Direct synthesis without adversarial escalation]",
                            "final_synthesized_code": thesis_code,
                            "smt_initial_status": initial_status,
                            "smt_final_status": initial_status,
                            "smt_final_verified": True,
                            "cegis_refined": False,
                            "mode": "fast",
                        }
                except SyntaxError:
                    pass

            logger.info("Dialectical Synthesis: Stage 2 (Antithesis)...")
            antithesis_raw = await self._generate_antithesis(thesis_code, smt_res)

            logger.info("Dialectical Synthesis: Stage 3 (Synthesis)...")
            final_code = await self._generate_synthesis(task_description, thesis_code, antithesis_raw)

            final_smt_res = self.smt_verifier.verify_code_contracts(final_code)
            final_code, final_smt_res, cegis_refined = await self._apply_cegis_refinement(
                task_description, final_code, final_smt_res
            )

            final_status = getattr(
                final_smt_res, "smt_solver_status", getattr(final_smt_res, "solver_status", "UNVERIFIED")
            )
            final_verified = getattr(final_smt_res, "verified", True)
            initial_status = (
                smt_res.get("status")
                if isinstance(smt_res, dict)
                else getattr(smt_res, "smt_solver_status", getattr(smt_res, "solver_status", "UNVERIFIED"))
            )

            return {
                "status": "SUCCESS",
                "task": task_description,
                "thesis_code": thesis_code,
                "antithesis_critique": antithesis_raw,
                "final_synthesized_code": final_code,
                "smt_initial_status": initial_status,
                "smt_final_status": final_status,
                "smt_final_verified": final_verified,
                "cegis_refined": cegis_refined,
                "mode": "dialectical",
            }
        except Exception as e:
            logger.error("Dialectical synthesis failed for task '%s': %s", task_description, e, exc_info=True)
            return {
                "status": "FAILED",
                "error": str(e),
                "task": task_description,
                "thesis_code": "",
                "antithesis_critique": "",
                "final_synthesized_code": "",
                "smt_initial_status": "FAILED",
                "smt_final_status": "FAILED",
                "smt_final_verified": False,
                "cegis_refined": False,
                "mode": "error",
            }

    def _extract_code(self, text: str) -> str:
        """Extracts python code from markdown code fences."""
        m = re.search(r"```(?:python)?\s*(.*?)\s*```", text, re.DOTALL)
        return m.group(1).strip() if m else text.strip()
