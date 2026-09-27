"""
vazus_autonomous_harness.context.session_sharder — Anti-Context-Rot Session Sharder & Entropy Governor.

Implements rigorous session sharding, attention entropy governance, observation masking,
and discrete stage isolation to combat LLM Context Rot, token exhaustion, and tool hallucination.
Adheres strictly to:
- ORIGINAL_REQUEST.md § 2026-09-26T22:47:31Z (R1)
- SCOPE.md § M8 Interface Contracts (F20)
- Explorer Survey R2.3 § 3.4 (Attention Entropy Formula, Stage Sharding, Subagent Shielding)
"""

from __future__ import annotations

import copy
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("vazus.context.session_sharder")

# Core Invariants & Defaults from Survey § 3.4
DEFAULT_MAX_ENTROPY: float = 0.78
DEFAULT_MAX_CHARS: int = 150000
DEFAULT_MAX_TURNS: int = 12
DEFAULT_UNMASKED_TURN_LAG: int = 3
DEFAULT_BASELINE_CHARS: int = 8000
DEFAULT_MAX_BASELINE_CHARS: int = 500000
DEFAULT_STALE_ASSISTANT_MAX_LEN: int = 1000
DEFAULT_RAW_TOOL_MAX_LINES: int = 16


def compute_attention_entropy(
    context_length: Union[int, str],
    baseline_chars: int = DEFAULT_BASELINE_CHARS,
    max_baseline_chars: int = DEFAULT_MAX_BASELINE_CHARS,
) -> float:
    """
    Computes normalized attention entropy H_bar strictly per Explorer Survey § 3.4:
        H_bar = min(1.0, max(0.0, log2(L / L_baseline) / log2(L_max / L_baseline)))

    Args:
        context_length: Character length (int) or text string (str).
        baseline_chars: L_baseline (default 8,000 chars).
        max_baseline_chars: L_max (default 500,000 chars).

    Returns:
        Normalized attention entropy in range [0.0, 1.0].
    """
    length = len(context_length) if isinstance(context_length, str) else int(context_length)
    if length <= 0 or baseline_chars <= 0 or max_baseline_chars <= baseline_chars:
        return 0.0

    if length <= baseline_chars:
        return 0.0
    if length >= max_baseline_chars:
        return 1.0

    denom = math.log2(max_baseline_chars / baseline_chars)
    numer = math.log2(length / baseline_chars)
    val = numer / denom
    return float(min(1.0, max(0.0, val)))


def compute_shannon_entropy(text: str) -> float:
    """
    Computes normalized Shannon character-level entropy:
        H = -sum(p_i * log2(p_i)) / log2(|Sigma|)
    """
    if not text:
        return 0.0
    freqs: Dict[str, int] = {}
    for char in text:
        freqs[char] = freqs.get(char, 0) + 1

    total = len(text)
    num_symbols = len(freqs)
    if num_symbols <= 1:
        return 0.0

    shannon = -sum((count / total) * math.log2(count / total) for count in freqs.values())
    max_possible = math.log2(num_symbols)
    return float(min(1.0, max(0.0, shannon / max_possible)))


@dataclass
class GovernorEvaluation:
    """Diagnostic outcome of an EntropyGovernor evaluation."""
    should_shard: bool
    attention_entropy: float
    shannon_entropy: float
    char_count: int
    turn_count: int
    trigger_reasons: List[str] = field(default_factory=list)


class EntropyGovernor:
    """
    Deterministic Attention Entropy Governor.
    Monitors dialogue context expansion against critical thresholds:
    - Normalized Attention Entropy H_bar >= 0.78
    - Total character budget L > 150,000 (~37.5k tokens)
    - Turn lag / dialogue turns > 12
    """

    def __init__(
        self,
        max_entropy: float = DEFAULT_MAX_ENTROPY,
        max_chars: int = DEFAULT_MAX_CHARS,
        max_turns: int = DEFAULT_MAX_TURNS,
        baseline_chars: int = DEFAULT_BASELINE_CHARS,
        max_baseline_chars: int = DEFAULT_MAX_BASELINE_CHARS,
    ):
        self.max_entropy = float(max_entropy)
        self.max_chars = int(max_chars)
        self.max_turns = int(max_turns)
        self.baseline_chars = int(baseline_chars)
        self.max_baseline_chars = int(max_baseline_chars)

    def evaluate(
        self,
        context: Union[str, int, List[Dict[str, Any]]],
        turn_count: int = 0,
    ) -> GovernorEvaluation:
        """Evaluates whether dialogue compaction / sharding must trigger."""
        if isinstance(context, list):
            # Sum characters from all message contents
            total_chars = sum(len(str(m.get("content", ""))) for m in context)
            full_text = " ".join(str(m.get("content", "")) for m in context if isinstance(m, dict))
            turns = turn_count or len(context)
        elif isinstance(context, str):
            total_chars = len(context)
            full_text = context
            turns = turn_count
        else:
            total_chars = int(context)
            full_text = ""
            turns = turn_count

        att_entropy = compute_attention_entropy(
            total_chars, self.baseline_chars, self.max_baseline_chars
        )
        shannon_ent = compute_shannon_entropy(full_text) if full_text else 0.0

        reasons = []
        if att_entropy >= self.max_entropy:
            reasons.append(f"ENTROPY_EXCEEDED: H_bar={att_entropy:.4f} >= {self.max_entropy:.2f}")
        if total_chars > self.max_chars:
            reasons.append(f"CHARS_EXCEEDED: L={total_chars} > {self.max_chars}")
        if turns > self.max_turns:
            reasons.append(f"TURNS_EXCEEDED: turns={turns} > {self.max_turns}")

        should_shard = len(reasons) > 0
        return GovernorEvaluation(
            should_shard=should_shard,
            attention_entropy=att_entropy,
            shannon_entropy=shannon_ent,
            char_count=total_chars,
            turn_count=turns,
            trigger_reasons=reasons,
        )


class ObservationMasker:
    """
    Dynamically collapses large tool dumps and intermediate observations.
    Strips raw terminal buffers, massive JSON arrays, or stack dumps exceeding 16 lines.
    """

    def __init__(self, raw_tool_max_lines: int = DEFAULT_RAW_TOOL_MAX_LINES):
        self.raw_tool_max_lines = raw_tool_max_lines

    def collapse_raw_dump(self, text: str) -> str:
        """Collapses a single string if it exceeds max allowed lines."""
        if not text:
            return ""
        lines = text.splitlines()
        if len(lines) <= self.raw_tool_max_lines:
            return text

        head_lines = self.raw_tool_max_lines // 2
        tail_lines = self.raw_tool_max_lines - head_lines
        omitted = len(lines) - (head_lines + tail_lines)

        collapsed = (
            lines[:head_lines]
            + [f"... [OBSERVATION COLLAPSED: {omitted} lines omitted to prevent attention dispersion] ..."]
            + lines[-tail_lines:]
        )
        return "\n".join(collapsed)

    def mask_turn_observation(self, turn_index: int, action_status: str = "Action succeeded") -> str:
        """Returns standard compact stub for stale intermediate tool outputs."""
        return f"[OBSERVATION MASKED: Turn #{turn_index} omitted to preserve attention budget. {action_status}.]"


class StageContextManager:
    """
    Enforces discrete stage isolation and short-lived subagent shielding.
    Prevents linear dialogue concatenation across disparate tasks (e.g. DC Circuit -> Java OOP).
    """

    def __init__(self, current_stage: str = "init"):
        self.current_stage = current_stage
        self.stage_history: List[Dict[str, Any]] = []

    def create_isolated_stage_context(
        self,
        stage_name: str,
        previous_stage_summary: Optional[str] = None,
        system_invariants: Optional[str] = None,
        active_adr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Creates a pristine, zero-rot context initialized solely with immutable invariants
        and an executive handoff summary from the preceding stage.
        """
        messages: List[Dict[str, Any]] = []

        # 1. System Prompt with core invariants
        sys_content = system_invariants or (
            "You are Vazus SuperGraph OS Autonomous Agent. "
            "Enforce strict Socratic sovereignty (USER.md#L37), zero stubs, and Z3 formal correctness."
        )
        if active_adr:
            sys_content += f"\n\nActive ADR Context:\n{active_adr}"
        messages.append({"role": "system", "content": sys_content})

        # 2. Handoff summary of prior stage (if any)
        if previous_stage_summary:
            handoff_msg = (
                f"### [STAGE TRANSITION: {self.current_stage} -> {stage_name}]\n"
                f"Prior Stage Executive Summary:\n{previous_stage_summary}\n\n"
                "Note: Prior stage intermediate tokens discarded to prevent context rot. "
                "Begin current stage with clean attention budget."
            )
            messages.append({"role": "user", "content": handoff_msg})
            messages.append({
                "role": "assistant",
                "content": f"Understood. Initialized isolated stage '{stage_name}' with pristine context.",
            })

        self.current_stage = stage_name
        return messages

    def isolate_subagent_dialogue(
        self,
        subagent_turns: List[Dict[str, Any]],
        task_summary: str,
        artifact_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Condenses raw subagent tool calls into a single compact shielded message for the parent.
        Raw subagent turns are excluded from parent context.
        """
        raw_turns_count = len(subagent_turns)
        artifacts_str = "\n".join(f"- {p}" for p in (artifact_paths or [])) if artifact_paths else "None"

        shielded_content = (
            f"### [SUBAGENT WORKFLOW COMPLETE: {raw_turns_count} turns executed]\n"
            f"**Executive Synthesis**:\n{task_summary}\n\n"
            f"**Produced Artifacts**:\n{artifacts_str}\n\n"
            f"(Raw subagent dialogue turns shielded to preserve parent attention budget.)"
        )
        return {
            "role": "user",
            "content": shielded_content,
            "metadata": {
                "shielded_turns": raw_turns_count,
                "artifacts": artifact_paths or [],
            },
        }

    def record_stage_handoff(
        self,
        from_stage: str,
        to_stage: str,
        summary: str,
        artifacts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Records a stage transition in the lifecycle ledger."""
        record = {
            "from_stage": from_stage,
            "to_stage": to_stage,
            "summary": summary,
            "artifacts": artifacts or [],
            "timestamp": math.floor(float(__import__("time").time())),
        }
        self.stage_history.append(record)
        self.current_stage = to_stage
        return record


class SessionSharder:
    """
    Production-grade Session Sharder adhering to SCOPE.md § M8 Interface Contracts.

    Combines:
    - Deterministic Attention Entropy Governance (H_bar >= 0.78, L > 150k chars, turns > 12)
    - Sliding unmasked turn window (last unmasked_turn_lag turns kept verbatim)
    - Intermediate tool observation masking and dump collapsing
    - Stale assistant response summarization
    - Stage isolation context management
    """

    def __init__(
        self,
        max_entropy: float = DEFAULT_MAX_ENTROPY,
        max_chars: int = DEFAULT_MAX_CHARS,
        max_turns: int = DEFAULT_MAX_TURNS,
        unmasked_turn_lag: int = DEFAULT_UNMASKED_TURN_LAG,
        baseline_chars: int = DEFAULT_BASELINE_CHARS,
        max_baseline_chars: int = DEFAULT_MAX_BASELINE_CHARS,
        stale_assistant_max_len: int = DEFAULT_STALE_ASSISTANT_MAX_LEN,
        raw_tool_max_lines: int = DEFAULT_RAW_TOOL_MAX_LINES,
    ):
        self.max_entropy = float(max_entropy)
        self.max_chars = int(max_chars)
        self.max_turns = int(max_turns)
        self.unmasked_turn_lag = int(unmasked_turn_lag)
        self.baseline_chars = int(baseline_chars)
        self.max_baseline_chars = int(max_baseline_chars)
        self.stale_assistant_max_len = int(stale_assistant_max_len)
        self.raw_tool_max_lines = int(raw_tool_max_lines)

        self.governor = EntropyGovernor(
            max_entropy=self.max_entropy,
            max_chars=self.max_chars,
            max_turns=self.max_turns,
            baseline_chars=self.baseline_chars,
            max_baseline_chars=self.max_baseline_chars,
        )
        self.masker = ObservationMasker(raw_tool_max_lines=self.raw_tool_max_lines)
        self.stage_manager = StageContextManager()

    def compute_entropy(self, context_text: Union[str, int]) -> float:
        """Computes normalized attention entropy H_bar for the given context."""
        return compute_attention_entropy(
            context_text, self.baseline_chars, self.max_baseline_chars
        )

    def should_shard(self, context_text: Union[str, int], turn_count: int = 0) -> bool:
        """
        Determines if dialogue context exceeds attention bounds.
        Triggers if H_bar >= max_entropy OR length > max_chars OR turn_count > max_turns.
        """
        eval_res = self.governor.evaluate(context_text, turn_count=turn_count)
        return eval_res.should_shard

    def shard_dialogue(
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Transforms dialogue messages to purge stale observations and compact lengthy outputs.

        Invariants:
        1. System messages are NEVER masked, compacted, or deleted.
        2. The most recent unmasked_turn_lag messages (e.g. last 3 turns) remain verbatim.
        3. Stale tool observations older than unmasked_turn_lag turns are replaced with compact stubs.
        4. Stale assistant messages > 1,000 chars are summarized to head (300) + tail (200).
        5. Raw dumps exceeding raw_tool_max_lines (16 lines) are collapsed.
        """
        if not messages:
            return [], {
                "original_chars": 0,
                "compacted_chars": 0,
                "entropy_before": 0.0,
                "entropy_after": 0.0,
                "sharded": False,
                "masked_observations_count": 0,
                "compacted_assistant_count": 0,
                "collapsed_dumps_count": 0,
            }

        orig_chars = sum(len(str(m.get("content", ""))) for m in messages)
        ent_before = self.compute_entropy(orig_chars)

        total_msgs = len(messages)
        cutoff_index = max(0, total_msgs - self.unmasked_turn_lag)

        compacted: List[Dict[str, Any]] = []
        masked_obs_count = 0
        compacted_asst_count = 0
        collapsed_dumps_count = 0

        for idx, orig_msg in enumerate(messages):
            msg = copy.deepcopy(orig_msg)
            role = str(msg.get("role", "")).lower()
            content = str(msg.get("content", ""))

            # 1. System messages are sacrosanct — never mask or alter
            if role == "system":
                compacted.append(msg)
                continue

            # 2. Recent messages within unmasked_turn_lag window are preserved verbatim
            if idx >= cutoff_index:
                compacted.append(msg)
                continue

            # 3. Stale turn (idx < cutoff_index) — apply compaction rules
            is_tool = role in ("tool", "observation") or "tool_call_id" in msg or "tool_output" in msg
            
            if is_tool:
                # Replace with compact stub
                msg["content"] = self.masker.mask_turn_observation(turn_index=idx + 1)
                masked_obs_count += 1
            elif role == "assistant":
                if len(content) > self.stale_assistant_max_len:
                    head = content[:300]
                    tail = content[-200:]
                    omitted = len(content) - 500
                    msg["content"] = (
                        f"{head}\n\n"
                        f"... [STALE ASSISTANT OUTPUT COMPACTED: {omitted} chars omitted to prevent context rot] ...\n\n"
                        f"{tail}"
                    )
                    compacted_asst_count += 1
                else:
                    # Check for line-based dumps in normal assistant messages
                    collapsed = self.masker.collapse_raw_dump(content)
                    if collapsed != content:
                        msg["content"] = collapsed
                        collapsed_dumps_count += 1
            else:
                # User or other role: collapse extreme command/log dumps
                collapsed = self.masker.collapse_raw_dump(content)
                if collapsed != content:
                    msg["content"] = collapsed
                    collapsed_dumps_count += 1

            compacted.append(msg)

        final_chars = sum(len(str(m.get("content", ""))) for m in compacted)
        ent_after = self.compute_entropy(final_chars)
        was_sharded = (
            masked_obs_count > 0 or compacted_asst_count > 0 or collapsed_dumps_count > 0
        )

        metadata = {
            "original_chars": orig_chars,
            "compacted_chars": final_chars,
            "chars_saved": max(0, orig_chars - final_chars),
            "entropy_before": ent_before,
            "entropy_after": ent_after,
            "entropy_delta": ent_after - ent_before,
            "sharded": was_sharded,
            "total_turns": total_msgs,
            "unmasked_lag": self.unmasked_turn_lag,
            "masked_observations_count": masked_obs_count,
            "compacted_assistant_count": compacted_asst_count,
            "collapsed_dumps_count": collapsed_dumps_count,
        }

        return compacted, metadata
