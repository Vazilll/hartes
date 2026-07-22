#!/usr/bin/env python3
"""
context_compaction.py — Context Window Auto-Compaction.

When accumulated conversation/trace history exceeds a threshold (by character count),
this module calls a lightweight LLM to summarize the history into key milestones,
dramatically reducing token usage while preserving critical state.

Based on LDR research finding (ldr_98e3db02):
  "Context compaction: at 85% context limit, lightweight LLM summarizes history
   to milestones while preserving REPL variable state."

Usage:
    from context_compaction import maybe_compact, compact_history

    # Automatically compact if over threshold
    compacted = maybe_compact(full_history_text, threshold_chars=60000)
"""

import json
import urllib.request
from pathlib import Path

WORKSPACE = Path("C:/vazus/pyenv")

# ── Thresholds ────────────────────────────────────────────────────────────────
DEFAULT_THRESHOLD_CHARS = 60_000     # ~85% of ~72k char context window
DEFAULT_TARGET_CHARS    = 8_000      # target compacted size

# ── LLM config ───────────────────────────────────────────────────────────────
ADAPTER_URL = "http://127.0.0.1:5001/v1/chat/completions"
COMPACTION_MODEL = "openai:gemini-3.5-flash"


def _load_adapter_key() -> str:
    key_file = WORKSPACE / ".adapter_key"
    return key_file.read_text().strip() if key_file.exists() else "any_key_for_adapter"


def compact_history(
    history_text: str,
    task_context: str = "",
    target_chars: int = DEFAULT_TARGET_CHARS,
) -> str:
    """
    Compress a long conversation/execution history to essential milestones.

    Args:
        history_text: The full accumulated context/history string.
        task_context: Short description of the current task (helps LLM focus).
        target_chars: Target output length in characters.

    Returns:
        Compacted summary string. Falls back to truncation on LLM failure.
    """
    api_key = _load_adapter_key()
    system_prompt = (
        f"You are compacting an agent's execution history to save context space. "
        f"Compress the following history into AT MOST {target_chars} characters. "
        f"Keep: final answers, key variables/state, critical errors, completed subtasks, "
        f"and decision rationale. Discard: verbose reasoning steps, raw code outputs, "
        f"redundant observations. Output ONLY the compact milestone summary."
    )
    user_content = (
        f"Current task: {task_context}\n\n---HISTORY TO COMPACT---\n{history_text}"
        if task_context else history_text
    )

    payload = {
        "model": COMPACTION_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content[:80_000]},  # hard cap to avoid API error
        ],
        "temperature": 0.05,
        "max_tokens": 1024,
    }

    req = urllib.request.Request(
        ADAPTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            compacted = data["choices"][0]["message"]["content"].strip()
            print(
                f"[ContextCompaction] Compressed {len(history_text):,} → "
                f"{len(compacted):,} chars ({100*len(compacted)/max(len(history_text),1):.0f}%)"
            )
            return compacted
    except Exception as e:
        print(f"[ContextCompaction] LLM failed ({e}), falling back to truncation")
        # Tail truncation: keep the most recent content (most relevant)
        return history_text[-target_chars:]


def maybe_compact(
    history_text: str,
    threshold_chars: int = DEFAULT_THRESHOLD_CHARS,
    target_chars: int = DEFAULT_TARGET_CHARS,
    task_context: str = "",
) -> str:
    """
    Compact history only if it exceeds the threshold.

    Args:
        history_text: Full history string.
        threshold_chars: If len(history_text) > this, compact.
        target_chars: Target compacted size.
        task_context: Optional task description for better compaction.

    Returns:
        Original text if under threshold, else compacted summary.
    """
    if len(history_text) <= threshold_chars:
        return history_text

    ratio = len(history_text) / threshold_chars
    print(
        f"[ContextCompaction] History {len(history_text):,} chars "
        f"({ratio:.1f}x threshold) — compacting..."
    )
    return compact_history(history_text, task_context=task_context, target_chars=target_chars)


def estimate_token_pressure(text: str, chars_per_token: float = 3.5) -> dict:
    """
    Estimate token usage and pressure level.

    Returns:
        dict with 'estimated_tokens', 'pressure' ('low'|'medium'|'high'|'critical'),
        and 'should_compact' bool.
    """
    tokens = int(len(text) / chars_per_token)
    # Gemini Flash: 1M token limit; conservative threshold for agent use = 64k tokens
    context_limit = 64_000
    ratio = tokens / context_limit

    if ratio < 0.5:
        pressure = "low"
    elif ratio < 0.75:
        pressure = "medium"
    elif ratio < 0.90:
        pressure = "high"
    else:
        pressure = "critical"

    return {
        "estimated_tokens": tokens,
        "context_limit": context_limit,
        "ratio": round(ratio, 3),
        "pressure": pressure,
        "should_compact": ratio >= 0.80,
    }


if __name__ == "__main__":
    # Quick self-test
    test_text = "Step 1: Loaded data. " * 3000
    stats = estimate_token_pressure(test_text)
    print(f"Token pressure: {stats}")

    if stats["should_compact"]:
        result = maybe_compact(test_text, task_context="data loading pipeline")
        print(f"Compacted to {len(result)} chars")
    else:
        print("No compaction needed")
