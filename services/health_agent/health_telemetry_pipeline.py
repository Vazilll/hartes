"""
Vazus Health OS - Unified Telemetry Pipeline Engine
Combines:
  1. Google Fit API (Sessions, Sleep Stages, Workouts, SpO2, Heart Rate, Steps, Calories)
  2. Direct BLE Scanner (Mi Body Composition Scale 2 BIA Bioimpedance)
  3. Async gRPC Health Service (Port 50051)
  4. SQLite SuperGraph Persistence (vazus.db)
"""

import os
import sys
import json
import time
import asyncio
import sqlite3
from datetime import datetime, timedelta

sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")

from google_fit_sync import fetch_and_save_fitness_data, get_google_fit_service
from ble_mi_scale_scanner import calculate_bia_metrics, save_weighin_to_db

DB_PATH = r"C:\vazus\services\memory\vazus.db"

class VazusHealthPipelineManager:
    def __init__(self, db_path=None):
        self.db_path = db_path if db_path is not None else DB_PATH

    def sync_all_google_fit_metrics(self, days_back=4):
        """
        Executes full Google Fit API sync across Sessions, Sleep Stages, Workouts, HR, SpO2
        """
        print(f"[Health Pipeline] Syncing Google Fit telemetry for last {days_back} days...")
        return fetch_and_save_fitness_data()

    async def scan_ble_scale_weighin(self, duration_sec=30):
        """
        Scans BLE radio packets for live Mi Scale 2 weigh-ins
        """
        from ble_mi_scale_scanner import scan_mi_scale
        print(f"[Health Pipeline] Scanning BLE radio for Mi Scale 2 ({duration_sec}s)...")
        await scan_mi_scale(scan_seconds=duration_sec)

    def execute_pipeline(self):
        """
        Executes full health telemetry pipeline returning readiness score, sleep, and BIA metrics
        per PROJECT.md contract line 56.
        """
        sync_result = self.sync_all_google_fit_metrics()
        from langgraph_health_workflow import LangGraphHealthMultiAgentWorkflow
        wf = LangGraphHealthMultiAgentWorkflow()
        wf_output = wf.execute_full_workflow()
        summary = self.get_latest_health_summary()
        
        analysis = wf_output.get('analysis', {})
        return {
            "status": "SUCCESS",
            "readiness_score": analysis.get('readiness_score', 0.0),
            "trimp_load": analysis.get('trimp_load', 0.0),
            "sleep_recovery": analysis.get('sleep_recovery', 0.0),
            "sleep": sync_result.get('sleep_sessions', []) if sync_result else [],
            "sleep_stages": sync_result.get('sleep_stages_by_day', {}) if sync_result else {},
            "bia_metrics": summary.get('latest_scale_weighin'),
            "google_fit_metrics": sync_result,
            "ai_recommendation": wf_output.get('google_ai_recommendation')
        }

    def get_latest_health_summary(self):
        """
        Retrieves the latest unified health summary from vazus.db
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        try:
            node = cur.execute("SELECT id, name, description, properties FROM kg_nodes WHERE domain='health' ORDER BY rowid DESC LIMIT 1").fetchone()
        except sqlite3.OperationalError:
            node = None

        try:
            weighin = cur.execute("SELECT timestamp, weight_kg, bmi, body_fat_pct, muscle_mass_kg, water_pct, visceral_fat, bmr_kcal, source FROM mi_scale_weighins ORDER BY rowid DESC LIMIT 1").fetchone()
        except sqlite3.OperationalError:
            weighin = None
        
        conn.close()
        
        return {
            "latest_google_fit_node": node,
            "latest_scale_weighin": weighin
        }

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    mgr = VazusHealthPipelineManager()
    res = mgr.execute_pipeline()
    print("=== VAZUS HEALTH PIPELINE SUMMARY ===")
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
