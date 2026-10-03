"""
vazus_core.verification.anti_false_confidence
Anti-False-Confidence Gate (AFC Gate).

Addresses Coverage Theater / Hallucination of Completeness:
agent claims done/ready/all-layers-work via pattern-match,
not via empirical execution.

Entry point: afc_check_response() called from post_invocation_hook.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("vazus.anti_false_confidence")

AFC_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"все\s+\d+\s+слоёв?\s+(зелёные|работают|активны|подключены)",
        r"все\s+(слои|системы)\s+(работают|green|active)",
        r"замкнутый\s+контур\s+(готов|работает)",
        r"система\s+работает\s+как\s+единое\s+целое",
        r"(всё|все)\s+(готово|работает|подключено)\b",
        r"\ball\s+layers\s+(?:are\s+)?(?:green|working|verified)\b",
        r"\bsystem\s+is\s+(?:ready|done|complete)\b",
        r"\bclosed[\s-]loop\s+(?:is\s+)?(?:ready|working)\b",
        r"\ball\s+\d+\s+layers?\s+pass\b",
    ]
]

EVIDENCE_ANCHORS = [
    "exit code 0",
    " passed",
    "evolution_completed",
    "all_layers_passed",
    "fitness: 1.0",
    "ast_valid = true",
    "pytest",
    "decision: allow",
]

DB_PATH = Path(os.getenv("VAZUS_DB_PATH", r"C:\vazus\services\memory\vazus.db"))
TABLE = "afc_violations"


def _get_db_path() -> Path:
    return Path(os.getenv("VAZUS_DB_PATH", str(DB_PATH)))


def _ensure_table():
    try:
        dbp = _get_db_path()
        if not dbp.parent.exists():
            dbp.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(dbp), timeout=3)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS afc_violations "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, "
            "conversation_id TEXT, claim_excerpt TEXT, "
            "evidence_verdict TEXT, resolved INTEGER DEFAULT 0)"
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("AFC DB init: %s", e)


def record_afc_violation(conv_id: str, excerpt: str, verdict: str):
    _ensure_table()
    try:
        conn = sqlite3.connect(str(_get_db_path()), timeout=3)
        conn.execute(
            "INSERT INTO afc_violations (ts,conversation_id,claim_excerpt,evidence_verdict) VALUES (?,?,?,?)",
            (time.time(), conv_id, excerpt[:400], verdict),
        )
        conn.commit()
        conn.close()
        logger.warning("AFC VIOLATION | conv=%s | verdict=%s", conv_id[:8], verdict)
    except Exception as e:
        logger.error("AFC record failed: %s", e)


def resolve_afc_violation(conv_id: str):
    try:
        conn = sqlite3.connect(str(_get_db_path()), timeout=3)
        conn.execute("UPDATE afc_violations SET resolved=1 WHERE conversation_id=? AND resolved=0", (conv_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("resolve_afc_violations non-fatal: %s", e)


def has_open_violation(conv_id: str) -> bool:
    _ensure_table()
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=3)
        cur = conn.execute("SELECT COUNT(*) FROM afc_violations WHERE conversation_id=? AND resolved=0", (conv_id,))
        n = cur.fetchone()[0]
        conn.close()
        return n > 0
    except Exception as e:
        logger.debug("has_open_violation non-fatal: %s", e)
        return False


def detect_premature_claim(text: str) -> Optional[str]:
    """
    Returns the matched claim excerpt if a premature-success statement is found
    WITHOUT any empirical evidence anchors. Returns None if the claim is grounded.
    """
    if not text or len(text) < 20:
        return None
    tl = text.lower()
    if any(a.lower() in tl for a in EVIDENCE_ANCHORS):
        return None  # claim is accompanied by real output
    for p in AFC_PATTERNS:
        m = p.search(text)
        if m:
            s = max(0, m.start() - 40)
            e = min(len(text), m.end() + 80)
            return text[s:e].strip()
    return None


def require_evidence_before_claim(
    target_file: Optional[str],
    conv_id: str,
    excerpt: str,
) -> dict:
    """Run EvidenceJury on target_file (or most-recently-modified .py)."""
    result = {"passed": False, "verdict": "UNVERIFIED", "reason": "not run", "target": target_file}

    if not target_file or not Path(target_file).is_file():
        try:
            py_files = sorted(Path(r"C:\vazus\vazus_core").rglob("*.py"), key=lambda f: f.stat().st_mtime, reverse=True)
            target_file = str(py_files[0]) if py_files else None
        except Exception as e:
            logger.debug("Finding recent py file non-fatal: %s", e)

    if not target_file:
        result["reason"] = "No target file found"
        record_afc_violation(conv_id, excerpt, "NO_TARGET")
        return result

    try:
        from vazus_core.verification.evidence_jury import EvidenceJury

        jr = EvidenceJury().evaluate(target_file, run_tests=False)
        verdict = jr.get("verdict", "UNVERIFIED")
        result.update({"verdict": verdict, "reason": jr.get("reason", ""), "target": target_file})
        if verdict == "VERIFIED":
            result["passed"] = True
            resolve_afc_violation(conv_id)
        else:
            record_afc_violation(conv_id, excerpt, verdict)
    except Exception as e:
        result["reason"] = str(e)
        record_afc_violation(conv_id, excerpt, f"JURY_ERROR:{e}")

    return result


def afc_check_response(
    response_text: str,
    conversation_id: str,
    last_modified_file: Optional[str] = None,
) -> dict:
    """
    Main entry. Called from post_invocation_hook after every agent response.
    Returns: {"afc_triggered": bool, "action": "ok"|"require_verification", ...}
    """
    excerpt = detect_premature_claim(response_text)
    if not excerpt:
        return {"afc_triggered": False, "action": "ok"}

    logger.warning("AFC triggered: %r", excerpt[:80])
    evidence = require_evidence_before_claim(last_modified_file, conversation_id, excerpt)
    action = "ok" if evidence["passed"] else "require_verification"
    return {
        "afc_triggered": True,
        "claim_excerpt": excerpt,
        "evidence": evidence,
        "action": action,
        "message": (
            f"[AFC Gate] Claim: {excerpt[:60]!r} | "
            f"EvidenceJury: {evidence['verdict']} | "
            + ("VALIDATED" if evidence["passed"] else f"BLOCKED — {evidence.get('reason', '?')}")
        ),
    }
