#!/usr/bin/env python3
"""
vazus_core.hooks.hud_writer — Lightweight HUD log writer.

Called by ALL hooks to append a timestamped entry to a JSON-Lines
session log at C:\\vazus\\data\\logs\\hud_session.jsonl
This log is consumed and displayed by the Vazus HUD monitor.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

HUD_LOG = Path(r"C:\vazus\data\logs\hud_session.jsonl")


def write_hud_event(event_type: str, payload: dict) -> None:
    """Appends one line to the HUD session log (JSON-Lines format)."""
    HUD_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **payload,
    }
    with open(HUD_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
