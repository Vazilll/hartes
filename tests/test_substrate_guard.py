"""
Unit tests for SMT Z3 SubstrateGuard.
"""

from vazus_autonomous_harness.skills.substrate_guard import SubstrateGuard


def test_guard_allows_safe_command():
    guard = SubstrateGuard()
    res = guard.verify("run_command", {"CommandLine": "python -V", "Cwd": "C:/vazus"})
    assert res["decision"] == "allow"
    assert res["latency_ms"] < 2.0  # sub-2ms requirement


def test_guard_vetoes_destructive_command():
    guard = SubstrateGuard()
    res = guard.verify("run_command", {"CommandLine": "format C:", "Cwd": "C:/vazus"})
    assert res["decision"] == "veto"
    assert "destructive" in res["reason"].lower()


def test_guard_path_jail():
    guard = SubstrateGuard()
    # Path outside allowed roots
    res = guard.verify("write_to_file", {"TargetFile": "D:/illegal/path.py"})
    assert res["decision"] == "veto"
    assert "Path Jail" in res["reason"]

    # Safe path
    res_safe = guard.verify("write_to_file", {"TargetFile": "C:/vazus/safe_test.py"})
    assert res_safe["decision"] == "allow"
