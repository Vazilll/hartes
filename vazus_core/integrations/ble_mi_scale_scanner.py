"""
vazus_core.integrations.ble_mi_scale_scanner — Forwarding bridge to services.health_agent.
"""

import sys
from pathlib import Path

_svc_dir = str(Path(__file__).resolve().parents[2] / "services" / "health_agent")
if _svc_dir not in sys.path:
    sys.path.insert(0, _svc_dir)

try:
    from services.health_agent.ble_mi_scale_scanner import *
except ImportError:
    from ble_mi_scale_scanner import *
