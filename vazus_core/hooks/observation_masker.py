#!/usr/bin/env python3
"""
vazus_core.hooks.observation_masker — Observation Masking and SNR Preserver.
Condenses voluminous command and tool execution outputs to maintain high Signal-to-Noise Ratio
and eliminate context rot across 50+ turn agent sessions.
"""

import re


class ObservationMasker:
    """
    Synthesizes and compacts bulky tool outputs (pytest, terminal logs, compiler dumps)
    into deterministic, high-signal observation summaries.
    """

    @classmethod
    def mask_tool_output(cls, tool_name: str, raw_output: str, max_chars: int = 800) -> str:
        """
        Condenses raw output if it exceeds max_chars, extracting key metrics.
        """
        if not raw_output or len(raw_output) <= max_chars:
            return raw_output

        # Specialized compaction for terminal/test commands
        if tool_name in ("run_command", "bash", "terminal", "exec"):
            # 1. Detect pytest summary
            pytest_match = re.search(r"(=+\s*\d+\s+passed.*in\s+[\d\.]+s.*=+)", raw_output)
            failed_match = re.search(r"(=+\s*\d+\s+failed.*=+)", raw_output)

            if pytest_match and not failed_match:
                return f"[Observation Masked: pytest -> {pytest_match.group(1)} | Exit Code: 0]"

            # 2. Extract error tail if command failed
            lines = [l for l in raw_output.splitlines() if l.strip()]
            if len(lines) > 20:
                header = "\n".join(lines[:4])
                footer = "\n".join(lines[-12:])
                return f"{header}\n\n[... {len(lines) - 16} lines masked to prevent context rot ...]\n\n{footer}"

        return (
            raw_output[:max_chars]
            + f"\n\n[... Truncated {len(raw_output) - max_chars} characters by ObservationMasker ...]"
        )
