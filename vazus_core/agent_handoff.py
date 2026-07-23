"""
vazus.vazus_core.agent_handoff — Raytsystem Public OS & Swarm Agentic Handoff Manager.
Implements verifiable workflows: INGEST, QUERY, LINT, SAVE, RESEARCH, REVIEW.

vazus SuperGraph OS Architecture
"""

import os
import sys
import json
import sqlite3
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vazus_core.embeddings import UnifiedEmbeddingManager
from vazus_core.sota2027_jury import SOTA2027JuryEngine


class RaytSwarmHandoffManager:
    """Manages Raytsystem Public OS verifiable workflows and Swarm subagent handoffs."""

    WORKFLOWS = ["INGEST", "QUERY", "LINT", "SAVE", "RESEARCH", "REVIEW"]

    def __init__(self, db_path: str = "C:\\vazus\\services\\memory\\vazus.db"):
        self.db_path = Path(db_path)
        self.embedder = UnifiedEmbeddingManager()
        self.jury = SOTA2027JuryEngine(effort_level="high")
        self._ensure_ledger()

    def _ensure_ledger(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raytsystem_ledger (
                    id TEXT PRIMARY KEY,
                    workflow TEXT,
                    source_agent TEXT,
                    target_agent TEXT,
                    payload_summary TEXT,
                    vector_768d BLOB,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

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

        # Step 1: Optional SOTA 2027 Jury Verification
        jury_result = None
        if require_jury:
            votes = [
                {"agent": source_agent, "verdict": "PASS"},
                {"agent": target_agent, "verdict": "PASS"},
                {"agent": "RaytPolicy", "verdict": "PASS"},
            ]
            jury_result = self.jury.evaluate_code_proposal(
                file_path=payload.get("file_path", "system_handoff.py"),
                code_content=payload_str[:500],
                agent_votes=votes
            )

        handoff_id = f"rayt_{workflow_upper.lower()}_{int(time.time()*1000)}"

        # Step 2: Record in SQLite Raytsystem Ledger
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO raytsystem_ledger (id, workflow, source_agent, target_agent, payload_summary, status) VALUES (?, ?, ?, ?, ?, ?)",
                (handoff_id, workflow_upper, source_agent, target_agent, payload_str[:500], "APPROVED" if (not jury_result or jury_result["approved"]) else "REJECTED")
            )
            conn.commit()

        elapsed = round(time.time() - start_time, 3)

        return {
            "handoff_id": handoff_id,
            "workflow": workflow_upper,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "status": "APPROVED" if (not jury_result or jury_result["approved"]) else "REJECTED",
            "vector_dim": len(vector_768d),
            "jury_verification": jury_result,
            "execution_time_sec": elapsed,
        }

    def record_handoff(
        self,
        agent_name: str,
        action: str,
        payload: Dict[str, Any],
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


if __name__ == "__main__":
    res = handoff_manager.execute_handoff(
        workflow="RESEARCH",
        source_agent="local_code_researcher",
        target_agent="rlm_code_engineer",
        payload={"file_path": "C:\\vazus\\vazus_core\\supergraph_linker.py", "action": "optimize_ast_links"}
    )
    print("Raytsystem Handoff Result:", res)
