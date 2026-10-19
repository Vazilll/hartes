"""
vazus.vazus_core.agent_handoff — Raytsystem Public OS & Swarm Agentic Handoff Manager.
Implements verifiable workflows: INGEST, QUERY, LINT, SAVE, RESEARCH, REVIEW.

vazus SuperGraph OS Architecture
"""

import json
import logging
import os
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.memory.embeddings import UnifiedEmbeddingManager
from vazus_core.verification.sota2027_jury import SOTA2027JuryEngine


class RaytSwarmHandoffManager:
    """Manages Raytsystem Public OS verifiable workflows and Swarm subagent handoffs."""

    WORKFLOWS = ["INGEST", "QUERY", "LINT", "SAVE", "RESEARCH", "REVIEW"]

    def __init__(self, db_path: Optional[str | Path] = None):
        target = db_path if db_path is not None else os.getenv("VAZUS_DB_PATH", "/home/tarhes/Проекты/vazus/services/memory/vazus.db")
        self.db_path = Path(target)
        self.embedder = UnifiedEmbeddingManager()
        self.jury = SOTA2027JuryEngine(effort_level="high")
        self._ensure_tables()

    @contextmanager
    def _connection(self, db_file: Optional[Path] = None):
        target_path = Path(db_file) if db_file else self.db_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception as exc:
            logger.debug("PRAGMA setup note for %s: %s", target_path, exc)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _ensure_tables(self):
        """Auto-creates raytsystem_ledger table in target DB location."""
        ddl = """
        CREATE TABLE IF NOT EXISTS raytsystem_ledger (
            handoff_id TEXT PRIMARY KEY,
            from_agent TEXT,
            to_agent TEXT,
            task_name TEXT,
            status TEXT,
            payload TEXT,
            timestamp TEXT,
            id TEXT,
            workflow TEXT,
            source_agent TEXT,
            target_agent TEXT,
            payload_summary TEXT,
            vector_768d BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection(self.db_path) as conn:
                conn.execute(ddl)
                existing_cols = {col[1] for col in conn.execute("PRAGMA table_info(raytsystem_ledger)").fetchall()}
                column_defs = {
                    "handoff_id": "TEXT",
                    "from_agent": "TEXT",
                    "to_agent": "TEXT",
                    "task_name": "TEXT",
                    "status": "TEXT",
                    "payload": "TEXT",
                    "timestamp": "TEXT",
                    "id": "TEXT",
                    "workflow": "TEXT",
                    "source_agent": "TEXT",
                    "target_agent": "TEXT",
                    "payload_summary": "TEXT",
                    "vector_768d": "BLOB",
                    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                }
                for col_name, col_type in column_defs.items():
                    if col_name not in existing_cols:
                        conn.execute(f"ALTER TABLE raytsystem_ledger ADD COLUMN {col_name} {col_type};")

                conn.execute("CREATE INDEX IF NOT EXISTS idx_raytsystem_ledger_from_to ON raytsystem_ledger(from_agent, to_agent);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_raytsystem_ledger_status ON raytsystem_ledger(status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_raytsystem_ledger_workflow ON raytsystem_ledger(workflow);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_raytsystem_ledger_created ON raytsystem_ledger(created_at);")
                conn.commit()
        except Exception as e:
            logger.warning("DB table init error for %s: %s", self.db_path, e)

    def _ensure_ledger(self):
        """Alias for _ensure_tables for backward compatibility."""
        self._ensure_tables()

    def _run_jury_verification(self, payload: Dict[str, Any], payload_str: str) -> Optional[Dict[str, Any]]:
        target_file = payload.get("target_file", "handoff_payload.py")
        code_content = payload.get("code_proposal", payload.get("code", payload_str))
        jury_verdict = self.jury.evaluate_code_proposal(
            file_path=target_file,
            code_content=code_content,
            agent_votes=payload.get("agent_votes")
        )
        return {
            "approved": jury_verdict.get("approved", False),
            "consensus_ratio": jury_verdict.get("consensus_ratio", 0.0),
            "rejection_reasons": jury_verdict.get("rejection_reasons", []),
            "votes": jury_verdict.get("votes", []),
        }

    def _persist_ledger_entry(
        self,
        handoff_id: str,
        source_agent: str,
        target_agent: str,
        workflow_upper: str,
        *,
        status_val: str,
        payload_str: str
    ) -> None:
        try:
            with self._connection(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO raytsystem_ledger 
                    (handoff_id, id, from_agent, source_agent, to_agent, target_agent, task_name, workflow, status, payload, payload_summary, timestamp) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        handoff_id, handoff_id,
                        source_agent, source_agent,
                        target_agent, target_agent,
                        workflow_upper, workflow_upper,
                        status_val,
                        payload_str, payload_str[:500]
                    )
                )
        except Exception as e:
            logger.warning("Ledger record error for %s: %s", self.db_path, e)

    def execute_handoff(
        self,
        workflow: str,
        source_agent: str,
        target_agent: str,
        payload: Dict[str, Any],
        require_jury: bool = True
    ) -> Dict[str, Any]:
        """Executes verifiable workflow handoff between subagents with Raytsystem ledger logging."""
        workflow_upper = workflow.upper()
        if workflow_upper not in self.WORKFLOWS:
            raise ValueError(f"Invalid workflow '{workflow}'. Supported: {self.WORKFLOWS}")

        start_time = time.time()
        payload_str = json.dumps(payload, ensure_ascii=False)
        vector_768d = self.embedder.get_embedding(payload_str[:2000])

        jury_result = self._run_jury_verification(payload, payload_str) if require_jury else None
        handoff_id = f"rayt_{workflow_upper.lower()}_{int(time.time()*1000)}"
        status_val = "APPROVED" if (not jury_result or jury_result["approved"]) else "REJECTED"

        self._persist_ledger_entry(
            handoff_id, source_agent, target_agent, workflow_upper,
            status_val=status_val, payload_str=payload_str
        )

        return {
            "handoff_id": handoff_id,
            "workflow": workflow_upper,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "status": status_val,
            "vector_dim": len(vector_768d),
            "jury_verification": jury_result,
            "execution_time_sec": round(time.time() - start_time, 3),
        }

    def record_handoff(
        self,
        agent_name: str,
        action: str,
        payload: Dict[str, Any],
        *,
        status: str = "APPROVED",
        target_agent: str = "system",
        workflow: str = "RESEARCH"
    ) -> Dict[str, Any]:
        """Convenience method to record subagent handoff events into Raytsystem ledger."""
        wf = workflow.upper()
        if wf not in self.WORKFLOWS:
            wf = "RESEARCH"
        full_payload = {"action": action, **payload}
        res = self.execute_handoff(
            workflow=wf,
            source_agent=agent_name,
            target_agent=target_agent,
            payload=full_payload,
            require_jury=False
        )
        if status != "APPROVED":
            res["status"] = status
        return res


# Global singleton instance
handoff_manager = RaytSwarmHandoffManager()
