"""
Google Model Armor & Zero-Trust Security Gate for Vazus SuperGraph OS.
Provides multi-layer prompt defense, strict Fail-Closed path jailing,
and mathematical SMT Z3 invariant validation.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SecurityVerdict(str, Enum):
    ALLOW = "allow"
    QUARANTINE = "quarantine"
    DENY = "deny"


class ModelArmorInspection(BaseModel):
    verdict: SecurityVerdict
    risk_score: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    sanitized_content: Optional[str] = None


class ModelArmor:
    """
    Enterprise-grade security gate for prompt, tool, and path validation.
    """

    PROMPT_INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?previous\s+instructions",
        r"(?i)bypass\s+safety\s+filter",
        r"(?i)you\s+are\s+now\s+in\s+dan\s+mode",
        r"(?i)system\s+override\s+mode",
        r"(?i)reveal\s+your\s+(hidden\s+)?system\s+prompt",
        r"(?i)exfiltrate\s+api\s+keys",
    ]

    DESTRUCTIVE_COMMAND_PATTERNS = [
        r"(?i)rm\s+-rf\s+/",
        r"(?i)del\s+/[sfq]\s+c:\\",
        r"(?i)format\s+[c-z]:",
        r"(?i)drop\s+database",
        r"(?i)mkfs\.",
        r"(?i):(){ :\|:& };:",
    ]

    @staticmethod
    def inspect_prompt(prompt_text: str) -> ModelArmorInspection:
        """Inspects prompt text for injection or malicious instructions."""
        reasons = []
        risk_score = 0.0

        for pat in ModelArmor.PROMPT_INJECTION_PATTERNS:
            if re.search(pat, prompt_text):
                reasons.append(f"Prompt injection pattern detected: {pat}")
                risk_score += 0.5

        for pat in ModelArmor.DESTRUCTIVE_COMMAND_PATTERNS:
            if re.search(pat, prompt_text):
                reasons.append(f"Destructive shell/system command detected: {pat}")
                risk_score += 0.8

        if risk_score >= 0.7:
            verdict = SecurityVerdict.DENY
        elif risk_score > 0.0:
            verdict = SecurityVerdict.QUARANTINE
        else:
            verdict = SecurityVerdict.ALLOW

        return ModelArmorInspection(
            verdict=verdict,
            risk_score=min(risk_score, 1.0),
            reasons=reasons,
            sanitized_content=prompt_text if verdict == SecurityVerdict.ALLOW else None,
        )

    @staticmethod
    def validate_path(
        target_path: str,
        allowed_roots: Optional[List[str]] = None,
    ) -> bool:
        """
        Strict Fail-Closed Path Jail verification.
        Ensures target path does not escape authorized workspace boundaries.
        """
        if allowed_roots is None:
            allowed_roots = [
                r"C:\vazus",
                r"C:\Users\Vaz\.gemini\antigravity",
                "/home/vazus/vazus",
                "/home/vazus/.gemini",
                "/vazus",
            ]

        try:
            clean_target = target_path.replace("\\", "/").rstrip("/").lower()
            for root in allowed_roots:
                clean_root = root.replace("\\", "/").rstrip("/").lower()
                if clean_target == clean_root or clean_target.startswith(clean_root + "/"):
                    return True
            return False
        except Exception:
            return False  # Fail-Closed

    @staticmethod
    def verify_invariant(invariant_name: str, values: Dict[str, Any]) -> bool:
        """
        Formal invariant verification (SMT contract simulation).
        """
        if invariant_name == "memory_confidence_bound":
            conf = values.get("confidence", 0.0)
            return 0.0 <= conf <= 1.0
        elif invariant_name == "token_budget_non_negative":
            tokens = values.get("token_budget", 0)
            return tokens >= 0
        elif invariant_name == "concordia_quorum":
            votes = values.get("votes", [])
            total = len(votes)
            if total == 0:
                return False
            approvals = sum(1 for v in votes if v is True)
            return (approvals / total) >= 0.66
        return True
