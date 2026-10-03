"""
vazus_core.integrations.health_telemetry_pipeline — Forwarding bridge to services.health_agent.
"""

import sys
from pathlib import Path

_svc_dir = str(Path(__file__).resolve().parents[2] / "services" / "health_agent")
if _svc_dir not in sys.path:
    sys.path.insert(0, _svc_dir)

try:
    from services.health_agent.health_telemetry_pipeline import *
    from services.health_agent.health_telemetry_pipeline import VazusHealthPipelineManager
except ImportError:
    from health_telemetry_pipeline import *
