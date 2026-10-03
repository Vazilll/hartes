import pytest
from vazus_core.engine.unified_hub import VazusUnifiedHub

def test_unified_hub_initialization():
    hub = VazusUnifiedHub()
    status = hub.get_system_status()
    assert isinstance(status, dict)
    assert "jules" in status
    assert "cloud_run" in status
    assert "notebooklm" in status
    assert "local_npu" in status
    assert "mcp_servers" in status
    assert "dream_consolidation" in status

def test_unified_hub_academic_summary():
    hub = VazusUnifiedHub()
    summary = hub.get_academic_summary()
    assert "15.10.2026" in summary
    assert "18" in summary
