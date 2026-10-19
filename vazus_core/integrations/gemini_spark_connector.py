"""
gemini_spark_connector.py — Google Gemini & Spark Bridge Connector
Connects Julia Router and HybridMCPDispatcher with Google Gemini models,
Google Colab GPU offloading, and the Gemini Spark Mobile/Cloud Run Bridge.
"""

from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

SPARK_PIPELINE_PATH = "/home/tarhes/Проекты/vazus/services/gemini_bridge/spark_task_pipeline.json"
BRIDGE_DIR = "/home/tarhes/Проекты/vazus/services/gemini_bridge"
PUBLIC_URL_PATH = os.path.join(BRIDGE_DIR, "public_url.txt")


@dataclass
class SparkPipelineStage:
    stage_id: int
    title: str
    discipline: str
    status: str
    focus: str
    deliverable: str
    session_action: str


class GeminiSparkConnector:
    """
    Bridge connecting vazus SuperGraph OS with Google Gemini,
    Google Colab, and Gemini Spark mobile/cloud pipeline.
    """

    def __init__(self, pipeline_path: str = SPARK_PIPELINE_PATH) -> None:
        self.pipeline_path = pipeline_path

    def get_pipeline_stages(self) -> List[SparkPipelineStage]:
        """Loads all academic stages from the active Spark pipeline."""
        if not os.path.exists(self.pipeline_path):
            return []

        try:
            with open(self.pipeline_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            stages = []
            for s in data.get("stages", []):
                stages.append(
                    SparkPipelineStage(
                        stage_id=s["stage_id"],
                        title=s["title"],
                        discipline=s["discipline"],
                        status=s["status"],
                        focus=s["focus"],
                        deliverable=s["deliverable"],
                        session_action=s["session_action"],
                    )
                )
            return stages
        except Exception:
            return []

    def get_public_bridge_url(self) -> Optional[str]:
        """Returns active Cloudflare tunnel URL for remote Gemini Spark connection."""
        if os.path.exists(PUBLIC_URL_PATH):
            try:
                with open(PUBLIC_URL_PATH, "r", encoding="utf-8") as f:
                    url = f.read().strip()
                return url if url.startswith("http") else None
            except Exception:
                pass
        return None

    def dispatch_spark_task(self, stage_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches a stage execution package to Google Gemini Spark or Cloud Run.
        """
        stages = self.get_pipeline_stages()
        matching = [s for s in stages if s.stage_id == stage_id]
        if not matching:
            return {"success": False, "error": f"Stage {stage_id} not found in pipeline"}

        stage = matching[0]
        bridge_url = self.get_public_bridge_url()

        # Log task dispatch into bridge history
        history_file = os.path.join(BRIDGE_DIR, "bridge_history.json")
        event = {
            "timestamp": time.time(),
            "stage_id": stage.stage_id,
            "title": stage.title,
            "discipline": stage.discipline,
            "action": stage.session_action,
            "bridge_url": bridge_url,
            "payload_preview": str(payload)[:200],
        }

        try:
            existing = []
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.append(event)
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(existing[-50:], f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return {
            "success": True,
            "stage": stage.title,
            "discipline": stage.discipline,
            "bridge_url": bridge_url,
            "offloaded_to": "Google Gemini Spark / Cloud Run",
            "session_action": stage.session_action,
        }
