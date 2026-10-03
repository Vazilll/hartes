import sys
sys.path.insert(0, "C:/vazus")

def test_rlm_web_structure():
    from vazus_core.workers import rlm
    assert hasattr(rlm, "run")
