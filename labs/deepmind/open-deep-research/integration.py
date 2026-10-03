"""
labs.deepmind.open-deep-research.integration
============================================
OpenDeepResearch integration adapter for Vazus SuperGraph OS.
Transfers synthesis reports, market discoveries, and literature insights
directly into SQLite vazus.db (organic_insights & kg_nodes).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("labs.deepmind.open_deep_research.integration")

DEFAULT_DB_PATH = Path(r"C:\vazus\services\memory\vazus.db")


@dataclass
class ResearchReport:
    """Encapsulates a completed deep research analysis."""
    title: str
    summary: str
    tags: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    source: str = "open_deep_research"
    created_at: float = field(default_factory=time.time)


class DeepResearchInsightSink:
    """Sink adapter persisting research outcomes into the persistent memory layer."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def on_research_complete(self, report: ResearchReport) -> Dict[str, Any]:
        """Persists ResearchReport into organic_insights and returns confirmation metadata."""
        insight_text = f"[{report.title}]: {report.summary}"
        if report.findings:
            insight_text += f"\nKey findings: {'; '.join(report.findings[:3])}"

        now_epoch = time.time()

        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO organic_insights (category, insight, timestamp, created_at)
                VALUES (?, ?, ?, datetime('now'))
            """, ("open_deep_research", insight_text, now_epoch))
            inserted_id = cur.lastrowid
            conn.commit()

            logger.info("Persisted research insight #%d: '%s'", inserted_id, report.title)
            return {
                "success": True,
                "insight_id": inserted_id,
                "category": "open_deep_research",
                "title": report.title,
            }
        except Exception as e:
            logger.error("Failed persisting research insight: %s", e)
            return {"success": False, "error": str(e)}
        finally:
            conn.close()
