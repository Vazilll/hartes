"""
vazus_autonomous_harness.verification.concordia_jury

Concordia Multi-Agent Consensus Jury with MSR Byzantine Anomaly Filtering.
Ensures code and hypothesis decisions require >= 66% consensus across diverse roles,
satisfy AST syntax validity, and filter out hallucinated/byzantine votes.
"""

import ast
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List

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
    Consensus voting engine with Receiver-Side MSR Byzantine filtering.
    Requires >= 66% consensus from quorum (default 3 agents).
    """

    def __init__(self, min_quorum: int = 3, consensus_threshold: float = 0.66):
        self.min_quorum = min_quorum
        self.consensus_threshold = consensus_threshold

    def filter_byzantine_votes(self, votes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Self-Anchored Consensus (SAC) MSR Byzantine Filter.
        Quarantines agents claiming max confidence (>= 0.99) without substantive reasoning (< 15 chars).
        """
        filtered = []
        for vote in votes:
            conf = float(vote.get("confidence", 0.5))
            reason = str(vote.get("reason", "") or "")
            if conf >= 0.99 and len(reason.strip()) < 15:
                logger.warning(f"[Concordia] Byzantine outlier quarantined: {vote.get('agent')} (conf={conf})")
                quarantined_vote = {
                    **vote,
                    "quarantined": True,
                    "approved": False,
                    "verdict": "FAIL",
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
        Evaluates a code proposal against AST syntax and multi-agent vote consensus.
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

        # 3. Filter Byzantine votes
        processed_votes = self.filter_byzantine_votes(votes)
        byzantine_cnt = sum(1 for v in processed_votes if v.get("quarantined", False))

        # 4. Tally active votes
        active_votes = [v for v in processed_votes if not v.get("quarantined", False)]
        total_active = len(active_votes)
        quorum_ok = total_active >= self.min_quorum

        if not quorum_ok:
            rejection_reasons.append(f"Quorum insufficient: {total_active}/{self.min_quorum}")

        pass_votes = sum(
            1 for v in active_votes
            if v.get("approved") is True or str(v.get("verdict", "")).upper() in ("PASS", "APPROVED")
        )
        ratio = pass_votes / max(1, total_active) if total_active > 0 else 0.0

        if ratio < self.consensus_threshold:
            rejection_reasons.append(f"Consensus ratio {ratio:.2f} < required {self.consensus_threshold:.2f}")

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
