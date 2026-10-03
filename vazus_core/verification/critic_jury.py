"""Jury-B: LLM Critic escalation — used ONLY for UNVERIFIED candidates.

CriticGPT-style design (AG2 discussion 15.08): the critic looks for CONCRETE
errors in the proposal and in the evidence, it does not "vote like/dislike".

Fail-closed contract:
  * LLM call failure, mock/quota fallback, or unparsable output → ABSTAIN.
  * Any CONTRADICT → REJECT (the critic found a real problem).
  * Only unanimous CONFIRM (all critics confirm, zero contradictions) → CONFIRM.

Zero-quota mode: when LLM is unavailable the whole jury returns ABSTAIN and
callers must treat ABSTAIN as "not approved" (rejection safety).

Env:
  VAZUS_JURY_CRITIC_MODELS — comma-separated model keys (default gemini-3.6-flash x2)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time

logger = logging.getLogger("vazus_core.verification.critic_jury")

DEFAULT_JURY_TIMEOUT_SECONDS = 120.0


def _jury_timeout_seconds(value: float | None = None) -> float:
    """Return a bounded total timeout for a critic-jury round.

    The old implementation had no deadline around the two serial LLM calls;
    each call could spend its timeout in the adapter, again in agy, and again
    in the broken SDK fallback. A single deadline is the safety boundary.
    """
    if value is None:
        raw = os.getenv("VAZUS_JURY_TIMEOUT", str(DEFAULT_JURY_TIMEOUT_SECONDS))
    else:
        raw = value
    try:
        return max(0.1, float(raw))
    except (TypeError, ValueError):
        return DEFAULT_JURY_TIMEOUT_SECONDS


def _timeout_verdicts(paths: list[str], issue: str) -> dict[str, dict[str, object]]:
    return {p: {"verdict": "ABSTAIN", "approved": False, "issue": issue} for p in paths}


logger = logging.getLogger("CriticJury")

CRITIC_A_SYSTEM = (
    "You are a skeptical senior engineer performing final review. Your only job is to "
    "find CONCRETE errors: bugs, broken contracts, import mistakes, security holes, "
    "inconsistencies between the proposal and its evidence summary. If you find none, "
    "say so. You are NOT asked whether you like the code.\n"
    'Respond strictly in JSON: {"verdict": "CONFIRM" | "CONTRADICT" | "ABSTAIN", '
    '"issue": "one-line concrete problem or empty string"}.'
)

CRITIC_B_SYSTEM = (
    "You are a security-focused code verifier. Review the proposal against its evidence: "
    "look for unsafe patterns (shell=True, os.system, eval/exec, hardcoded secrets), "
    "unhandled exceptions in new paths, and anything the evidence checks may have missed. "
    "Be concrete: name the exact line/fragment. No praise, no style opinions.\n"
    'Respond strictly in JSON: {"verdict": "CONFIRM" | "CONTRADICT" | "ABSTAIN", '
    '"issue": "one-line concrete problem or empty string"}.'
)

CRITIC_BATCH_SYSTEM = (
    "You are a skeptical senior code verifier reviewing a BATCH of files. For EACH file "
    "find CONCRETE errors: bugs, broken contracts, import mistakes, security holes, "
    "inconsistencies between the code and its evidence summary. Note: a file marked "
    "TRUNCATED is cut for length — judge only the visible part. No praise, no style "
    "opinions. If a file looks fine, CONFIRM it.\n"
    'Respond strictly in JSON: {"files": {"<path>": {"verdict": "CONFIRM" | '
    '"CONTRADICT" | "ABSTAIN", "issue": "one-line concrete problem or empty string"}}} '
    "covering every listed file."
)

_VERDICT_RE = re.compile(r'"(?:verdict)"\s*:\s*"(CONFIRM|CONTRADICT|ABSTAIN)"', re.I)


def _parse_critic_verdict(raw: str) -> str:
    m = _VERDICT_RE.search(raw)
    if m:
        return m.group(1).upper()
    up = (raw or "").upper()
    if "CONTRADICT" in up:
        return "CONTRADICT"
    if "CONFIRM" in up:
        return "CONFIRM"
    return "ABSTAIN"


def _extract_issue(raw: str) -> str:
    """Pulls the 'issue' field even when the model wraps the JSON in fences."""
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return str(json.loads(text).get("issue", ""))
    except Exception:
        return ""


def _default_models() -> list[str]:
    raw = os.getenv("VAZUS_JURY_CRITIC_MODELS", "gemini-3.7-flash,gemini-3.7-flash")
    return [m.strip() for m in raw.split(",") if m.strip()]


BATCH_CODE_CAP = 4000
BATCH_EVIDENCE_CAP = 1200
BATCH_TOTAL_BUDGET = 18000  # per-batch prompt budget (agy adds ~10K system ctx on top)


def pack_batches(items: list[dict], budget: int = BATCH_TOTAL_BUDGET) -> list[list[dict]]:
    """Greedily packs files into batches that fit the prompt budget so files
    travel WHOLE (truncation causes critic false positives)."""
    batches: list[list[dict]] = []
    cur: list[dict] = []
    cur_len = 0
    for it in items:
        size = len(it["proposal"] or "") + len(_compact_evidence(it.get("evidence", ""))) + 200
        if cur and cur_len + size > budget:
            batches.append(cur)
            cur, cur_len = [], 0
        cur.append(it)
        cur_len += size
    if cur:
        batches.append(cur)
    return batches


def _compact_evidence(evidence_summary: str) -> str:
    return (evidence_summary or "")[:BATCH_EVIDENCE_CAP]


def _truncate_lines(code: str, cap: int) -> tuple[str, bool]:
    """Truncates on a LINE boundary so the critic never sees a mid-statement cut."""
    if len(code) <= cap:
        return code, False
    cut = code.rfind("\n", 0, cap)
    if cut <= 0:
        cut = cap
    return code[:cut] + "\n# ... TRUNCATED (see git diff for the rest)\n", True


def _build_batch_prompt(items: list[dict], code_cap: int | None = None) -> str:
    # Per-file code slice cap: each file's CODE block is bounded by
    # BATCH_CODE_CAP (the total batch budget is handled by pack_batches).
    cap = code_cap or BATCH_CODE_CAP
    sections = []
    for it in items:
        code = it["proposal"] or ""
        code, truncated = _truncate_lines(code, cap)
        if truncated:
            pass  # marker already appended
        sections.append(
            f"### FILE: {it['path']}\n"
            f"EVIDENCE: {_compact_evidence(it.get('evidence', ''))}\n"
            f"CODE:\n```python\n{code}\n```"
        )
    return (
        "Review EVERY file below. Find CONCRETE errors per file: bugs, broken "
        "contracts, import mistakes, security holes, inconsistencies between "
        "code and evidence.\n"
        'Respond strictly in JSON: {"files": {"<path>": {"verdict": "CONFIRM" | '
        '"CONTRADICT" | "ABSTAIN", "issue": "one-line concrete problem or empty '
        'string"}}} for every listed file.\n\n' + "\n\n".join(sections)
    )


def _parse_batch_verdicts(raw: str, paths: list[str]) -> dict:
    """Parses the critic batch reply. Missing/garbage entries → ABSTAIN."""
    out = {p: {"verdict": "ABSTAIN", "issue": "no verdict (fail-closed)"} for p in paths}
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end <= start:
            return out
        data = json.loads(raw[start : end + 1])
        files = data.get("files", {}) if isinstance(data, dict) else {}
        for p in paths:
            entry = files.get(p)
            if not isinstance(entry, dict):
                continue
            verdict = str(entry.get("verdict", "ABSTAIN")).upper()
            if verdict not in ("CONFIRM", "CONTRADICT", "ABSTAIN"):
                verdict = "ABSTAIN"
            out[p] = {"verdict": verdict, "issue": str(entry.get("issue", ""))}
    except Exception as e:
        logger.debug("parse_critic_response JSON decode non-fatal: %s", e)
    return out


async def evaluate_batch(
    items: list[dict],
    models: list[str] | None = None,
    timeout_seconds: float | None = None,
) -> dict:
    """One critic round for MANY files in a single prompt (2 LLM calls total).

    items: [{"path": str, "proposal": str, "evidence": str}]
    Fail-closed per file: mock/error/unparsable → ABSTAIN (not approved).
    ``timeout_seconds`` is a TOTAL deadline for the whole batch, not a per-tier
    timeout. This prevents adapter → agy → SDK fallback multiplication.
    """
    from vazus_core.engine.llm_client import async_generate_llm
    from vazus_core.verification.concordia_jury import is_mock_response

    models = models or _default_models()
    personas = [CRITIC_BATCH_SYSTEM, CRITIC_BATCH_SYSTEM]
    paths = [it["path"] for it in items]
    prompt = _build_batch_prompt(items)
    per_critic: list[dict] = []
    llm_calls = 0
    deadline = time.monotonic() + _jury_timeout_seconds(timeout_seconds)

    for i, model in enumerate(models):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            per_critic.append(_timeout_verdicts(paths, "critic jury total timeout (fail-closed)"))
            continue
        system = personas[i % len(personas)]
        try:
            raw = await asyncio.wait_for(
                async_generate_llm(
                    prompt=prompt,
                    system_prompt=system,
                    model=model,
                    temperature=0.0,
                    timeout_seconds=remaining,
                ),
                timeout=remaining,
            )
            llm_calls += 1
            if is_mock_response(raw):
                per_critic.append(
                    {p: {"verdict": "ABSTAIN", "issue": "mock/quota fallback (fail-closed)"} for p in paths}
                )
                continue
            per_critic.append(_parse_batch_verdicts(raw, paths))
        except asyncio.TimeoutError:
            logger.warning("[CriticJury] batch LLM call timed out for '%s' (fail-closed)", model)
            per_critic.append(_timeout_verdicts(paths, "critic jury timeout (fail-closed)"))
        except Exception as e:
            logger.warning(f"[CriticJury] batch LLM call failed for '{model}': {e}")
            per_critic.append({p: {"verdict": "ABSTAIN", "issue": f"LLM error (fail-closed): {e}"} for p in paths})

    verdicts: dict = {}
    for p in paths:
        votes = [c[p] for c in per_critic]
        if any(v["verdict"] == "CONTRADICT" for v in votes):
            final, approved = "REJECT", False
        elif votes and all(v["verdict"] == "CONFIRM" for v in votes):
            final, approved = "CONFIRM", True
        else:
            final, approved = "ABSTAIN", False
        issues = "; ".join(v["issue"] for v in votes if v.get("issue")) or "fail-closed abstention"
        verdicts[p] = {"verdict": final, "approved": approved, "issue": issues}

    return {"jury": "B", "verdicts": verdicts, "llm_calls": llm_calls, "fail_closed": True}


def _run_async_safe(coro):
    """asyncio.run() that also works when called from inside a running loop
    (e.g. MCP tool invoked from an async context) — no RuntimeError."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


async def evaluate_batches(
    items: list[dict],
    models: list[str] | None = None,
    timeout_seconds: float | None = None,
) -> dict:
    """Packs files into size-bounded batches and runs one critic round per
    batch under a single total deadline. Timeout is an abstention, never an
    approval and never an unbounded wait."""
    verdicts: dict = {}
    llm_calls = 0
    deadline = time.monotonic() + _jury_timeout_seconds(timeout_seconds)
    for batch in pack_batches(items):
        paths = [it["path"] for it in batch]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            verdicts.update(_timeout_verdicts(paths, "critic jury total timeout (fail-closed)"))
            continue
        try:
            res = await asyncio.wait_for(
                evaluate_batch(batch, models=models, timeout_seconds=remaining),
                timeout=remaining,
            )
        except asyncio.TimeoutError:
            verdicts.update(_timeout_verdicts(paths, "critic jury total timeout (fail-closed)"))
            continue
        verdicts.update(res["verdicts"])
        llm_calls += res.get("llm_calls", 0)
    return {"jury": "B", "verdicts": verdicts, "llm_calls": llm_calls, "fail_closed": True}


def run_critic_jury_batches_sync(
    items: list[dict],
    models: list[str] | None = None,
    timeout_seconds: float | None = None,
) -> dict:
    """Synchronous entry point with a bounded total jury deadline."""
    return _run_async_safe(evaluate_batches(items, models, timeout_seconds))


async def evaluate(
    file_path: str,
    proposal: str,
    evidence_summary: str,
    models: list[str] | None = None,
) -> dict:
    """Runs the critic jury. Never raises — returns a structured result."""
    from vazus_core.engine.llm_client import async_generate_llm
    from vazus_core.verification.concordia_jury import is_mock_response

    models = models or _default_models()
    personas = [CRITIC_A_SYSTEM, CRITIC_B_SYSTEM]
    votes: list[dict] = []
    llm_calls = 0

    for i, model in enumerate(models):
        system = personas[i % len(personas)]
        user_prompt = (
            f"File: {file_path}\n\nEVIDENCE SUMMARY:\n{evidence_summary}\n\n"
            f"PROPOSAL CODE:\n```python\n{proposal}\n```\n"
            "Find concrete errors. Respond in JSON only."
        )
        try:
            raw = await async_generate_llm(prompt=user_prompt, system_prompt=system, model=model, temperature=0.0)
            llm_calls += 1
            if is_mock_response(raw):
                votes.append({"model": model, "verdict": "ABSTAIN", "issue": "mock/quota fallback (fail-closed)"})
                continue
            verdict = _parse_critic_verdict(raw)
            votes.append({"model": model, "verdict": verdict, "issue": _extract_issue(raw)})
        except Exception as e:
            logger.warning(f"[CriticJury] LLM call failed for '{model}': {e}")
            votes.append({"model": model, "verdict": "ABSTAIN", "issue": f"LLM error (fail-closed): {e}"})

    if any(v["verdict"] == "CONTRADICT" for v in votes):
        final = "REJECT"
    elif votes and all(v["verdict"] == "CONFIRM" for v in votes):
        final = "CONFIRM"
    else:
        final = "ABSTAIN"

    return {
        "jury": "B",
        "verdict": final,
        "approved": final == "CONFIRM",
        "votes": votes,
        "llm_calls": llm_calls,
        "fail_closed": True,
    }


def run_critic_jury_sync(file_path: str, proposal: str, evidence_summary: str, models: list[str] | None = None) -> dict:
    return _run_async_safe(evaluate(file_path, proposal, evidence_summary, models))
