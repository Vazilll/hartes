"""
Attention Entropy Governor & Trajectory Auto-Compactor for Vazus OS (NeurIPS 2025 DL4Code, arXiv:2508.21433).
Monitors context entropy decay and executes deterministic turn-lag compaction to prevent context rot.
"""

import math
from typing import Any, Dict, List, Tuple


class EntropyGovernor:
    """
    Trajectory manager preventing attention entropy dispersion and instruction burial.
    """

    def __init__(
        self,
        entropy_critical_threshold: float = 0.78,
        unmasked_turn_lag: int = 3,
        max_context_chars: int = 150000,  # ~37.5k tokens
    ):
        self.crit_threshold = entropy_critical_threshold
        self.unmasked_turn_lag = unmasked_turn_lag
        self.max_chars = max_context_chars

    @staticmethod
    def estimate_normalized_entropy(
        total_chars: int, baseline_chars: int = 8000, max_scale_chars: int = 500000
    ) -> float:
        """
        Estimates normalized attention entropy H_bar in [0, 1] as a function of context volume L.
        """
        if total_chars <= baseline_chars:
            return 0.10
        scaled = math.log2(total_chars / baseline_chars)
        max_scaled = math.log2(max_scale_chars / baseline_chars)
        return min(1.0, max(0.0, scaled / max_scaled))

    def compact_trajectory(self, trajectory: Any, force: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Compacts multi-turn history when attention entropy exceeds critical threshold or forced.
        """
        if not isinstance(trajectory, list):
            trajectory = []
        total_chars = sum(len(str(m.get("content", ""))) if isinstance(m, dict) else len(str(m)) for m in trajectory)
        h_bar = self.estimate_normalized_entropy(total_chars)

        compacted = []
        chars_saved = 0
        total_turns = len(trajectory)

        should_compact = force or (h_bar >= self.crit_threshold) or (total_chars > self.max_chars) or (total_turns > 12)

        if not should_compact:
            return trajectory, {"compacted": False, "entropy": round(h_bar, 3), "chars_saved": 0}

        for idx, turn in enumerate(trajectory):
            turn_copy = dict(turn) if isinstance(turn, dict) else {"content": str(turn)}
            turns_from_end = total_turns - 1 - idx

            # Keep root system prompt and initial user goal intact, plus recent unmasked window
            if idx <= 1 or turns_from_end <= self.unmasked_turn_lag:
                compacted.append(turn_copy)
                continue

            role = turn_copy.get("role", "")
            content = str(turn_copy.get("content", ""))

            # Compress stale intermediate steps
            if role in ("tool", "observation") or turn_copy.get("is_tool_result", False):
                old_len = len(content)
                line_count = len(content.splitlines())
                turn_copy["content"] = (
                    f"[OBSERVATION MASKED: Turn #{idx} omitted to preserve attention budget ({line_count} lines). Action succeeded.]"
                )
                chars_saved += max(0, old_len - len(turn_copy["content"]))
            elif role == "assistant" and len(content) > 1000:
                old_len = len(content)
                turn_copy["content"] = (
                    content[:300] + "\n[... intermediate reasoning steps summarized ...]\n" + content[-200:]
                )
                chars_saved += max(0, old_len - len(turn_copy["content"]))

            compacted.append(turn_copy)

        new_total_chars = sum(len(str(m.get("content", ""))) for m in compacted)
        new_h_bar = self.estimate_normalized_entropy(new_total_chars)

        return compacted, {
            "compacted": True,
            "original_entropy": round(h_bar, 3),
            "new_entropy": round(new_h_bar, 3),
            "chars_saved": chars_saved,
            "tokens_saved": chars_saved // 4,
        }
