#!/usr/bin/env python3
"""
vazus_core.workers.context_watchdog — Autonomous Context Health & Session Monitor.
===================================================================================

Monitors conversation transcripts in ~/.gemini/antigravity/brain/<id> to prevent
context degradation, token exhaustion, and catastrophic forgetting.

Thresholds:
  - WARN: >= 15 user turns or >= 70,000 characters
  - CRITICAL_COMPRESS: >= 25 user turns or >= 120,000 characters

Usage:
  from vazus_core.workers.context_watchdog import ContextWatchdog
  watchdog = ContextWatchdog()
  report = watchdog.inspect_active_session()
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

logger = logging.getLogger("vazus_core.workers.context_watchdog")

DEFAULT_BRAIN_DIR = Path(os.path.expanduser(r"~\.gemini\antigravity\brain"))


class ContextWatchdog:
    """Monitors active conversation transcripts and flags context bloat."""

    WARN_TURNS: int = 15
    COMPRESS_TURNS: int = 25
    WARN_CHARS: int = 70_000
    COMPRESS_CHARS: int = 120_000

    def __init__(
        self,
        brain_dir: Optional[Union[str, Path]] = None,
        warn_turns: int = WARN_TURNS,
        compress_turns: int = COMPRESS_TURNS,
        warn_chars: int = WARN_CHARS,
        compress_chars: int = COMPRESS_CHARS,
    ) -> None:
        self.brain_dir = Path(brain_dir) if brain_dir else DEFAULT_BRAIN_DIR
        self.warn_turns = warn_turns
        self.compress_turns = compress_turns
        self.warn_chars = warn_chars
        self.compress_chars = compress_chars

    def find_latest_session_id(self) -> Optional[str]:
        """Finds the most recently modified conversation session ID."""
        if not self.brain_dir.exists():
            return None
        dirs = [d for d in self.brain_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if not dirs:
            return None
        dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        return dirs[0].name

    def inspect_session(self, session_id: str) -> Dict[str, Any]:
        """
        Inspects the transcript for the specified session_id.
        Returns message count, char count, estimated tokens, and health state.
        """
        transcript_file = (
            self.brain_dir / session_id / ".system_generated" / "logs" / "transcript.jsonl"
        )
        if not transcript_file.exists():
            return {
                "session_id": session_id,
                "status": "NOT_FOUND",
                "exists": False,
                "total_steps": 0,
                "user_turns": 0,
                "total_chars": 0,
                "estimated_tokens": 0,
                "level": "HEALTHY",
                "needs_compression": False,
            }

        total_steps = 0
        user_turns = 0
        total_chars = 0

        try:
            with open(transcript_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    total_steps += 1
                    total_chars += len(line)
                    try:
                        record = json.loads(line)
                        if record.get("type") == "USER_INPUT":
                            user_turns += 1
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("Failed reading transcript %s: %s", transcript_file, exc)

        estimated_tokens = total_chars // 4

        # Evaluate level
        if user_turns >= self.compress_turns or total_chars >= self.compress_chars:
            level = "CRITICAL_COMPRESS"
            needs_compression = True
        elif user_turns >= self.warn_turns or total_chars >= self.warn_chars:
            level = "WARN"
            needs_compression = False
        else:
            level = "HEALTHY"
            needs_compression = False

        report = {
            "session_id": session_id,
            "status": "OK",
            "exists": True,
            "total_steps": total_steps,
            "user_turns": user_turns,
            "total_chars": total_chars,
            "estimated_tokens": estimated_tokens,
            "level": level,
            "needs_compression": needs_compression,
            "thresholds": {
                "warn_turns": self.warn_turns,
                "compress_turns": self.compress_turns,
                "warn_chars": self.warn_chars,
                "compress_chars": self.compress_chars,
            },
        }

        # Telemetry
        if level in ("WARN", "CRITICAL_COMPRESS"):
            try:
                from vazus_core.hooks.hud_writer import write_hud_event
                write_hud_event("ContextWatchdog", {
                    "session_id": session_id,
                    "level": level,
                    "user_turns": user_turns,
                    "estimated_tokens": estimated_tokens,
                })
            except Exception:
                pass

        return report

    def inspect_active_session(self, explicit_session_id: Optional[str] = None) -> Dict[str, Any]:
        """Inspects active session (or most recent)."""
        sid = explicit_session_id or self.find_latest_session_id()
        if not sid:
            return {
                "session_id": None,
                "status": "NO_SESSIONS",
                "exists": False,
                "level": "HEALTHY",
                "needs_compression": False,
            }
        return self.inspect_session(sid)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    watchdog = ContextWatchdog()
    sid = sys.argv[1] if len(sys.argv) > 1 else None
    rep = watchdog.inspect_active_session(sid)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
