"""Dual-jury orchestrator: evidence first, LLM critic only for UNVERIFIED.

Flow (AG2 discussion 15.08):
  Jury-A (EvidenceJury, 0 LLM calls) decides PASS/FAIL by proof.
  * PASS   → approved immediately, zero quota spent.
  * FAIL   → rejected immediately (hard evidence).
  * UNVERIFIED → escalate to Jury-B (critic LLM) when allow_llm=True;
                 otherwise the candidate is NOT approved (rejection safety).

This is the quota-saving replacement for the old "LLM jury on every commit"
pattern: trivial and provable candidates never reach the LLM tier.
"""

from __future__ import annotations

import json
from pathlib import Path

from vazus_core.verification.evidence_jury import EvidenceJury


async def dual_jury_verdict(
    file_path: str | Path,
    code_content: str | None = None,
    allow_llm: bool = True,
    run_tests: bool = True,
    full_suite: bool = False,
    test_timeout: int = 600,
) -> dict:
    result = {"file": str(file_path), "allow_llm": allow_llm}

    a = EvidenceJury().evaluate(
        file_path,
        code_content=code_content,
        run_tests=run_tests,
        full_suite=full_suite,
        test_timeout=test_timeout,
    )
    result["jury_a"] = a
    result["llm_calls"] = a.get("llm_calls", 0)

    if a["verdict"] == "PASS":
        result.update({"jury": "A", "verdict": "PASS", "approved": True, "reason": a.get("reason")})
        return result
    if a["verdict"] == "FAIL":
        result.update({"jury": "A", "verdict": "FAIL", "approved": False, "reason": a.get("reason")})
        return result

    # UNVERIFIED → Jury-B
    if not allow_llm:
        result.update(
            {
                "jury": "A",
                "verdict": "UNVERIFIED",
                "approved": False,
                "reason": "UNVERIFIED and LLM escalation disabled — manual review required (rejection safety)",
            }
        )
        return result

    from vazus_core.verification.critic_jury import evaluate as critic_evaluate

    proposal = code_content if code_content is not None else _read_file(file_path)
    evidence_summary = json.dumps(a, ensure_ascii=False, indent=2, default=str)
    b = await critic_evaluate(str(file_path), proposal, evidence_summary)
    result["jury_b"] = b
    result["llm_calls"] += b.get("llm_calls", 0)
    result.update(
        {
            "jury": "B",
            "verdict": b["verdict"],
            "approved": b.get("approved", False),
            "reason": f"Jury-A UNVERIFIED ({a.get('reason')}); Jury-B verdict {b['verdict']} (fail-closed)",
        }
    )
    return result


def _read_file(file_path) -> str:
    fp = Path(file_path)
    if not fp.is_absolute():
        fp = Path("C:/vazus") / fp
    return fp.read_text(encoding="utf-8", errors="replace")


def run_dual_jury_sync(file_path: str | Path, **kwargs) -> dict:
    from vazus_core.verification.critic_jury import _run_async_safe

    return _run_async_safe(dual_jury_verdict(file_path, **kwargs))
