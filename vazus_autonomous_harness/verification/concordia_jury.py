"""
vazus_autonomous_harness.verification.concordia_jury

Concordia Multi-Agent Consensus Jury with MSR Byzantine Anomaly Filtering.
Ensures code and hypothesis decisions require >= 66% consensus across diverse roles,
satisfy AST syntax validity, and filter out hallucinated/byzantine votes.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger("vazus.harness.verification.concordia")


@dataclass
class JuryVerdict:
    approved: bool
    consensus_ratio: float
    quorum_satisfied: bool
    ast_valid: bool
    votes: List[Dict[str, Any]] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    byzantine_count: int = 0


class ConcordiaJuryCore:
    """
    Consensus voting engine with Receiver-Side MSR Byzantine filtering and CP-WBFT.
    Requires >= 2/3 consensus from quorum (min_quorum >= 3 agents).
    """

    def __init__(self, min_quorum: int = 3, consensus_threshold: float = 2.0 / 3.0):
        # Enforce strict >= 2/3 quorum and minimum 3 agents
        self.min_quorum = max(3, int(min_quorum))
        self.consensus_threshold = float(consensus_threshold)

    def compute_cp_wbft_weight(
        self,
        confidence: float,
        reason: str,
        base_weight: Optional[float] = None,
        lambda_penalty: float = 0.5,
        tau_baseline: float = 0.70,
        ref_length: float = 25.0,
    ) -> tuple[float, float]:
        """
        Computes CP-WBFT dynamic overconfidence penalty and effective weight (arXiv:2605.09076).
        Penalty_overconf = max(0, conf - tau_baseline) * (1.0 / max(1.0, len(reason) / ref_length))
        W_i = w_i * max(0, 1 - lambda * Penalty_overconf)
        """
        conf = float(confidence)
        w_i = float(base_weight if base_weight is not None else conf)
        reason_len = float(len(str(reason or "").strip()))

        overconf_penalty = max(0.0, conf - tau_baseline) * (1.0 / max(1.0, reason_len / ref_length))
        penalty_factor = max(0.0, 1.0 - lambda_penalty * overconf_penalty)
        effective_weight = w_i * penalty_factor
        return effective_weight, overconf_penalty

    def filter_byzantine_votes(self, votes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Self-Anchored Consensus (SAC) MSR Byzantine Filter.
        Quarantines agents claiming max confidence (>= 0.99) without substantive reasoning (< 15 chars),
        anomalous confidence ranges outside [0.0, 1.0], or explicit outlier flags.
        """
        filtered = []
        for vote in votes:
            conf = float(vote.get("confidence", 0.5))
            reason = str(vote.get("reason", "") or "")
            reason_clean = reason.strip()
            reason_len = len(reason_clean)
            is_explicit_outlier = bool(vote.get("quarantined", False) or vote.get("byzantine", False) or vote.get("outlier", False))
            is_conf_anomaly = conf < 0.0 or conf > 1.0
            is_terse_high_conf = (
                (conf >= 0.99 and reason_len < 25)
                or (conf >= 0.95 and reason_len < 20)
                or (conf >= 0.90 and reason_len < 10)
            )

            if is_explicit_outlier or is_conf_anomaly or is_terse_high_conf:
                agent_name = vote.get("agent", "UnknownAgent")
                logger.warning(
                    f"[Concordia] Byzantine outlier quarantined: {agent_name} "
                    f"(conf={conf}, reason_len={len(reason.strip())})"
                )
                quarantined_vote = {
                    **vote,
                    "quarantined": True,
                    "approved": False,
                    "verdict": "FAIL",
                    "effective_weight": 0.0,
                }
                filtered.append(quarantined_vote)
            else:
                filtered.append(vote)
        return filtered

    def evaluate_proposal(
        self,
        code_str: str,
        votes: List[Dict[str, Any]],
    ) -> JuryVerdict:
        """
        Evaluates a code proposal against AST syntax and multi-agent vote consensus
        under CP-WBFT dynamic weighting and strict >= 2/3 Byzantine quorum.
        """
        rejection_reasons = []

        # 1. AST Syntax Gate
        ast_valid = True
        if code_str and code_str.strip():
            try:
                ast.parse(code_str)
            except SyntaxError as se:
                ast_valid = False
                rejection_reasons.append(f"AST SyntaxError line {se.lineno}: {se.msg}")

        # 2. Forbidden dangerous patterns
        for bad in ["eval(", "exec(", "os.system(", "shutil.rmtree("]:
            if bad in code_str:
                rejection_reasons.append(f"Dangerous pattern detected: {bad}")
                ast_valid = False

        # 3. Filter Byzantine votes and quarantine outliers
        processed_votes = self.filter_byzantine_votes(votes)
        byzantine_cnt = sum(1 for v in processed_votes if v.get("quarantined", False))

        # 4. Tally active votes using CP-WBFT (Confidence-Penalized Weighted BFT, arXiv:2605.09076)
        active_votes = [v for v in processed_votes if not v.get("quarantined", False)]
        total_active = len(active_votes)
        quorum_ok = total_active >= self.min_quorum

        if not quorum_ok:
            rejection_reasons.append(f"Quorum insufficient: {total_active}/{self.min_quorum}")

        # CP-WBFT Dynamic Weighting: W_i = w_i * max(0, 1 - lambda * Penalty_overconfidence)
        weighted_pass = 0.0
        total_weight = 0.0

        for v in active_votes:
            conf = float(v.get("confidence", 0.8))
            w_i = float(v.get("weight", conf))
            reason = str(v.get("reason", "") or "")

            eff_weight, overconf_penalty = self.compute_cp_wbft_weight(
                confidence=conf,
                reason=reason,
                base_weight=w_i,
                lambda_penalty=0.5,
            )
            v["effective_weight"] = eff_weight
            v["overconfidence_penalty"] = overconf_penalty

            is_pass = v.get("approved") is True or str(v.get("verdict", "")).upper() in ("PASS", "APPROVED")
            if is_pass:
                weighted_pass += eff_weight
            total_weight += eff_weight

        # Weighted ratio per CP-WBFT
        ratio = (weighted_pass / total_weight) if total_weight > 0 else 0.0

        if ratio < self.consensus_threshold:
            rejection_reasons.append(
                f"Consensus ratio {ratio:.4f} < required {self.consensus_threshold:.4f}"
            )

        approved = ast_valid and quorum_ok and (ratio >= self.consensus_threshold)

        return JuryVerdict(
            approved=approved,
            consensus_ratio=ratio,
            quorum_satisfied=quorum_ok,
            ast_valid=ast_valid,
            votes=processed_votes,
            rejection_reasons=rejection_reasons,
            byzantine_count=byzantine_cnt,
        )
