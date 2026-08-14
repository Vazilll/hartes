"""
Vazus Health OS - One-Click Health Sync Entry Point
"""

import sys
import os

sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")

from vazus_core.integrations.health_telemetry_pipeline import VazusHealthPipelineManager

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("🚀 Running Vazus Health OS Unified Sync...")
    mgr = VazusHealthPipelineManager()
    metrics = mgr.sync_all_google_fit_metrics(days_back=4)
    summary = mgr.get_latest_health_summary()
    print("✅ Sync completed successfully!")
    print(summary)

if __name__ == "__main__":
    main()
