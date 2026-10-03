"""
vazus_core.integrations.freelance_npd_engine — Forwarding bridge to services.finance_agent.
"""

import sys
from pathlib import Path

_svc_dir = str(Path(__file__).resolve().parents[2] / "services" / "finance_agent")
if _svc_dir not in sys.path:
    sys.path.insert(0, _svc_dir)

try:
    from services.finance_agent.freelance_npd_engine import *
except ImportError:
    from freelance_npd_engine import *
