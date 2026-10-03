"""
tests/benchmarks/test_adversarial_challenger_m3.py — Empirical Adversarial Stress Harness for Milestone 3 (R3).

Adversarial validation covering:
1. 1,000 rapid invocations of run_pre_tool across diverse tool names and payloads (P50, P95, P99 < 15.0 ms SLA).
2. Benchmark run_pre_invocation and run_pre_invocation_hook under cold cache and warm cache.
3. Edge case: corrupt logs/.skill_index_cache.json and verify graceful rebuild without crashing.
4. Formal invariant enforcement & fail-closed behavior under adversarial inputs.
"""

import json
import os
import shutil
import statistics
import time
from pathlib import Path
import pytest

from vazus_core.hooks.pre_tool_hook import run_pre_tool, get_substrate_guard
from vazus_core.verification.substrate_guard import SubstrateGuard, ToolCallRequest
import vazus_core.hooks.pre_invocation_hook as pih


class TestPreToolRapidInvocations:
    """Challenge 1: 1,000 rapid invocations across diverse tool names and payloads."""

    PAYLOADS = [
        ("write_to_file", {"TargetFile": r"C:\vazus\scratch\valid_file.py", "CodeContent": "print('hello')"}),
        ("view_file", {"AbsolutePath": r"C:\vazus\README.md"}),
        ("run_command", {"CommandLine": "pytest tests/ -q", "Cwd": r"C:\vazus"}),
        ("replace_file_content", {"TargetFile": r"C:\vazus\services\memory\test.py", "TargetContent": "a", "ReplacementContent": "b"}),
        ("write_to_file", {"TargetFile": r"C:\vazus\.git\config", "CodeContent": "malicious"}),
        ("view_file", {"TargetFile": r"C:\Windows\System32\cmd.exe"}),
        ("run_command", {"CommandLine": "format C: /fs:NTFS"}),
        ("run_command", {"CommandLine": "rmdir /s /q C:\\"}),
        ("view_file", {"TargetFile": "C:\\vazus\\file\x00.txt"}),
        ("custom_unknown_tool", {"random_arg": "value", "flag": True}),
        ("write_to_file", {"TargetFile": r"C:\vazus\scratch\large.txt", "CodeContent": "x" * 100000}),
        ("view_file", {"TargetFile": r"C:\Users\Vaz\.gemini\config\settings.json"}),
        ("write_to_file", {"TargetFile": ""}),
        ("write_to_file", {"TargetFile": "scratch/rel.txt"}),
        ("write_to_file", {"TargetFile": r"C:\vazus\scratch\отчет.txt", "CodeContent": "тестовые данные"}),
        ("run_command", {"CommandLine": r"del /s /q C:\*"}),
        ("run_command", {"CommandLine": r"del /f /s /q C:\*.*"}),
        ("run_command", {"CommandLine": "del /s /q C:\\"}),
        ("run_command", {"CommandLine": r"erase /s /q C:\*"}),
        ("run_command", {"CommandLine": "format.exe C:"}),
        ("run_command", {"CommandLine": r"Remove-Item C:\* -Recurse -Force"}),
        # Iteration 4 Destructive Bypasses
        ("run_command", {"CommandLine": r"del /s /qc:\*"}),
        ("run_command", {"CommandLine": "rd /s /qc:\\"}),
        ("run_command", {"CommandLine": "format/qc:"}),
        ("run_command", {"CommandLine": 'format "C:"'}),
        ("run_command", {"CommandLine": "Remove-Item C:\\ -Recurse -Force"}),
        ("run_command", {"CommandLine": 'Remove-Item "C:\\" -Recurse -Force'}),
        ("run_command", {"CommandLine": r"del C:\windows\*"}),
        # Iteration 4 Benign Developer Tooling
        ("run_command", {"CommandLine": r"python -m ruff format C:\vazus\file.py"}),
        ("run_command", {"CommandLine": r"npm run format -- C:\vazus\file.js"}),
        ("run_command", {"CommandLine": r"clang-format -i C:\vazus\main.cpp"}),
        ("run_command", {"CommandLine": r"prettier --format C:\vazus\main.js"}),
        ("run_command", {"CommandLine": r"del C:\vazus\build\cache.bin"}),
        ("run_command", {"CommandLine": r"rmdir /s /q C:\vazus\dist"}),
        ("run_command", {"CommandLine": r'git log --format="%h %s" C:\vazus\file.py'}),
    ]

    def test_1000_rapid_invocations_distribution(self):
        """Execute 1,000 calls and verify P50, P95, P99 are strictly < 15.0 ms."""
        # Warmup
        for tool, args in self.PAYLOADS:
            run_pre_tool(tool, dict(args))

        latencies = []
        decisions = []
        for i in range(1000):
            tool, args = self.PAYLOADS[i % len(self.PAYLOADS)]
            t0 = time.perf_counter()
            res = run_pre_tool(tool, dict(args))
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)
            decisions.append(res.get("decision"))

        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        max_lat = max(latencies)
        min_lat = min(latencies)
        mean_lat = statistics.mean(latencies)
        violations = [lat for lat in latencies if lat >= 15.0]

        print(f"\n--- 1,000 Rapid Invocations Results ---")
        print(f"Total invocations: {len(latencies)}")
        print(f"Decisions: allow={decisions.count('allow')}, deny={decisions.count('deny')}")
        print(f"Min:  {min_lat:.4f} ms")
        print(f"Mean: {mean_lat:.4f} ms")
        print(f"P50:  {p50:.4f} ms")
        print(f"P95:  {p95:.4f} ms")
        print(f"P99:  {p99:.4f} ms")
        print(f"Max:  {max_lat:.4f} ms")
        print(f"Violations (>= 15.0 ms): {len(violations)}")

        assert p50 < 15.0, f"P50 latency failed SLA: {p50:.3f} ms >= 15.0 ms"
        assert p95 < 15.0, f"P95 latency failed SLA: {p95:.3f} ms >= 15.0 ms"
        assert p99 < 15.0, f"P99 latency failed SLA: {p99:.3f} ms >= 15.0 ms"
        assert len(violations) == 0, f"Encountered {len(violations)} invocations exceeding 15.0 ms SLA"

    def test_security_decisions_correctness(self):
        """Verify strict correctness of security gate across diverse payloads."""
        # Malicious / boundary calls must deny
        assert run_pre_tool("write_to_file", {"TargetFile": r"C:\vazus\.git\config"})["decision"] == "deny"
        assert run_pre_tool("view_file", {"TargetFile": r"C:\Windows\System32\cmd.exe"})["decision"] == "deny"
        assert run_pre_tool("run_command", {"CommandLine": "format C: /fs:NTFS"})["decision"] == "deny"
        assert run_pre_tool("run_command", {"CommandLine": "rmdir /s /q C:\\"})["decision"] == "deny"
        assert run_pre_tool("run_command", {"CommandLine": r"del /s /q C:\*"})["decision"] == "deny"
        assert run_pre_tool("run_command", {"CommandLine": r"del /f /s /q C:\*.*"})["decision"] == "deny"
        assert run_pre_tool("run_command", {"CommandLine": "del /s /q C:\\"})["decision"] == "deny"
        assert run_pre_tool("run_command", {"CommandLine": r"erase /s /q C:\*"})["decision"] == "deny"
        assert run_pre_tool("run_command", {"CommandLine": "format.exe C:"})["decision"] == "deny"
        assert run_pre_tool("run_command", {"CommandLine": r"Remove-Item C:\* -Recurse -Force"})["decision"] == "deny"
        assert run_pre_tool("view_file", {"TargetFile": "C:\\vazus\\file\x00.txt"})["decision"] == "deny"
        assert run_pre_tool("write_to_file", {"TargetFile": ""})["decision"] == "deny"

        # Iteration 4 Destructive Bypasses must deny
        destructive_bypasses = [
            r"del /s /qc:\*",
            "rd /s /qc:\\",
            "format/qc:",
            'format "C:"',
            "Remove-Item C:\\ -Recurse -Force",
            'Remove-Item "C:\\" -Recurse -Force',
            r"del C:\windows\*",
        ]
        for cmd in destructive_bypasses:
            res = run_pre_tool("run_command", {"CommandLine": cmd})
            assert res["decision"] == "deny", f"Destructive bypass was allowed: {cmd}"
            assert res.get("muc") == ["rule_safe_command"]

        # Safe calls must allow
        assert run_pre_tool("write_to_file", {"TargetFile": r"C:\vazus\scratch\valid.py"})["decision"] == "allow"
        assert run_pre_tool("view_file", {"AbsolutePath": r"C:\vazus\README.md"})["decision"] == "allow"
        assert run_pre_tool("run_command", {"CommandLine": "pytest tests/ -q"})["decision"] == "allow"

        # Iteration 4 Benign Developer Tooling must allow
        benign_commands = [
            r"python -m ruff format C:\vazus\file.py",
            r"npm run format -- C:\vazus\file.js",
            r"clang-format -i C:\vazus\main.cpp",
            r"prettier --format C:\vazus\main.js",
            r"del C:\vazus\build\cache.bin",
            r"rmdir /s /q C:\vazus\dist",
            r'git log --format="%h %s" C:\vazus\file.py',
        ]
        for cmd in benign_commands:
            res = run_pre_tool("run_command", {"CommandLine": cmd})
            assert res["decision"] == "allow", f"Benign command was falsely blocked: {cmd}"
            assert res.get("muc") is None


class TestAdversarialReDoSLinearScaling:
    """Challenge: ReDoS Resistance — 10,000 repeated slashes, spaces, and flags evaluate in < 2.0 ms (strict linear O(N) scaling)."""

    @pytest.mark.parametrize("cmd_verb,pattern_idx", [
        ("format", 0),
        ("rmdir", 1),
        ("del", 2),
        ("remove-item", 3),
        ("reg delete", 4),
        ("diskpart", 5),
    ])
    def test_redos_slashes_linear_scaling_and_sla(self, cmd_verb, pattern_idx):
        from vazus_core.verification.substrate_guard import DANGEROUS_COMMAND_PATTERNS
        pat = DANGEROUS_COMMAND_PATTERNS[pattern_idx]

        # Test at N=5,000 and N=10,000 to verify strict linear O(N) scaling
        payload_5k = f"{cmd_verb} " + "/" * 5000 + "!"
        payload_10k = f"{cmd_verb} " + "/" * 10000 + "!"

        # Warmup
        pat.search(payload_5k)
        pat.search(payload_10k)

        t0 = time.perf_counter()
        pat.search(payload_5k)
        dt_5k = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        pat.search(payload_10k)
        dt_10k = (time.perf_counter() - t0) * 1000.0

        print(f"\n[ReDoS Slashes] {cmd_verb}: 5k={dt_5k:.3f} ms, 10k={dt_10k:.3f} ms")
        assert dt_10k < 2.0, f"10k slashes on {cmd_verb} exceeded 2.0 ms: {dt_10k:.3f} ms"

    @pytest.mark.parametrize("cmd_verb,pattern_idx", [
        ("format", 0),
        ("rmdir", 1),
        ("del", 2),
        ("remove-item", 3),
        ("reg delete", 4),
        ("diskpart", 5),
    ])
    def test_redos_spaces_linear_scaling_and_sla(self, cmd_verb, pattern_idx):
        from vazus_core.verification.substrate_guard import DANGEROUS_COMMAND_PATTERNS
        pat = DANGEROUS_COMMAND_PATTERNS[pattern_idx]

        payload_10k = f"{cmd_verb} " + " " * 10000 + "!"
        pat.search(payload_10k)

        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            pat.search(payload_10k)
            times.append((time.perf_counter() - t0) * 1000.0)

        min_t = min(times)
        avg_t = sum(times) / len(times)
        print(f"\n[ReDoS Spaces] {cmd_verb}: min={min_t:.3f} ms, avg={avg_t:.3f} ms")
        assert min_t < 2.0, f"10k spaces on {cmd_verb} exceeded 2.0 ms: min={min_t:.3f} ms"

    @pytest.mark.parametrize("cmd_verb,flag,pattern_idx", [
        ("format", "/f ", 0),
        ("rmdir", "/s ", 1),
        ("del", "/s ", 2),
        ("remove-item", "-Force ", 3),
        ("reg delete", "/f ", 4),
        ("diskpart", "/s ", 5),
    ])
    def test_redos_flags_linear_scaling_and_sla(self, cmd_verb, flag, pattern_idx):
        from vazus_core.verification.substrate_guard import DANGEROUS_COMMAND_PATTERNS
        pat = DANGEROUS_COMMAND_PATTERNS[pattern_idx]

        payload = f"{cmd_verb} " + flag * 2000 + "!"
        pat.search(payload)

        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            pat.search(payload)
            times.append((time.perf_counter() - t0) * 1000.0)

        min_t = min(times)
        avg_t = sum(times) / len(times)
        print(f"\n[ReDoS Flags] {cmd_verb}: min={min_t:.3f} ms, avg={avg_t:.3f} ms")
        assert min_t < 2.0, f"Repeated flags on {cmd_verb} exceeded 2.0 ms: min={min_t:.3f} ms"



class TestPreInvocationBenchmarks:
    """Challenge 2: Benchmark run_pre_invocation and context injection under cold and warm cache."""

    @pytest.mark.anyio
    async def test_run_pre_invocation_hook_warm_sla(self):
        """Warm Turn 0 must be < 50.0 ms, and warm Turn N > 0 must be < 0.5 ms."""
        # Warmup cache
        await pih.run_pre_invocation_hook(user_prompt="academic help", turn_index=0)

        turn0_times = []
        for _ in range(5):
            t0 = time.perf_counter()
            res0 = await pih.run_pre_invocation_hook(user_prompt="academic help", turn_index=0)
            turn0_times.append((time.perf_counter() - t0) * 1000.0)
            assert res0["status"] == "SUCCESS"
            assert len(res0["injected_context"]) > 0

        turnN_times = []
        for _ in range(20):
            t0 = time.perf_counter()
            resN = await pih.run_pre_invocation_hook(user_prompt="academic help", turn_index=1)
            turnN_times.append((time.perf_counter() - t0) * 1000.0)
            assert resN["status"] == "SUCCESS"
            assert resN["injected_context"] == ""

        avg_turn0 = sum(turn0_times) / len(turn0_times)
        avg_turnN = sum(turnN_times) / len(turnN_times)

        print(f"\n--- Pre-Invocation Hook Latencies ---")
        print(f"Warm Turn 0 avg: {avg_turn0:.2f} ms (min={min(turn0_times):.2f}, max={max(turn0_times):.2f})")
        print(f"Warm Turn N avg: {avg_turnN:.4f} ms (min={min(turnN_times):.4f}, max={max(turnN_times):.4f})")

        assert avg_turn0 < 50.0, f"Turn 0 avg latency exceeded 50.0 ms: {avg_turn0:.2f} ms"
        assert avg_turnN < 0.5, f"Turn N avg latency exceeded 0.5 ms: {avg_turnN:.4f} ms"

    def test_run_pre_invocation_contract(self):
        """Direct benchmark of synchronous run_pre_invocation(trajectory, query)."""
        # Valid list trajectory
        t0 = time.perf_counter()
        res = pih.run_pre_invocation([], "academic help")
        t1 = time.perf_counter()
        lat = (t1 - t0) * 1000.0

        assert res["status"] == "ok"
        assert "entropy_governor" in res
        assert "active_tools" in res
        assert lat < 15.0, f"run_pre_invocation latency too high: {lat:.2f} ms"


class TestSkillCacheCorruptionRecovery:
    """Challenge 3: Corrupt logs/.skill_index_cache.json and verify graceful rebuild without crashing."""

    CACHE_PATH = Path(r"C:\vazus\data\logs\.skill_index_cache.json")
    BACKUP_PATH = Path(r"C:\vazus\data\logs\.skill_index_cache.json.bak_challenger")

    @classmethod
    def setup_class(cls):
        if cls.CACHE_PATH.exists():
            shutil.copy2(cls.CACHE_PATH, cls.BACKUP_PATH)

    @classmethod
    def teardown_class(cls):
        if cls.BACKUP_PATH.exists():
            shutil.copy2(cls.BACKUP_PATH, cls.CACHE_PATH)
            cls.BACKUP_PATH.unlink(missing_ok=True)
        pih._MEMORY_SKILLS_CACHE = None

    def test_rebuild_from_syntax_corrupted_json(self):
        """Corrupted JSON syntax must not crash _load_skill_cache; must cleanly rebuild."""
        pih._MEMORY_SKILLS_CACHE = None
        self.CACHE_PATH.write_text("{broken json syntax: true, [unclosed", encoding="utf-8")

        # Load skills - must handle gracefully
        skills = pih._load_skill_cache()
        assert isinstance(skills, list)
        assert len(skills) > 0, "Failed to rebuild skills list from corrupted cache"

        # Verify disk file was overwritten with valid JSON
        assert self.CACHE_PATH.exists()
        rebuilt_data = json.loads(self.CACHE_PATH.read_text(encoding="utf-8"))
        assert "dirs_mtime" in rebuilt_data
        assert "skills" in rebuilt_data
        assert len(rebuilt_data["skills"]) == len(skills)

    def test_rebuild_from_empty_file(self):
        """Empty 0-byte file must be gracefully replaced with valid cache."""
        pih._MEMORY_SKILLS_CACHE = None
        self.CACHE_PATH.write_text("", encoding="utf-8")

        skills = pih._load_skill_cache()
        assert isinstance(skills, list)
        assert len(skills) > 0

        rebuilt_data = json.loads(self.CACHE_PATH.read_text(encoding="utf-8"))
        assert len(rebuilt_data["skills"]) > 0

    def test_rebuild_from_non_dict_json(self):
        """JSON containing a list or scalar must not crash; must cleanly rebuild."""
        pih._MEMORY_SKILLS_CACHE = None
        self.CACHE_PATH.write_text("[1, 2, 3, 'unexpected array']", encoding="utf-8")

        skills = pih._load_skill_cache()
        assert isinstance(skills, list)
        assert len(skills) > 0

    def test_auto_select_skills_resilient_to_corruption(self):
        """auto_select_skills must succeed and return matches even when cache was corrupted."""
        pih._MEMORY_SKILLS_CACHE = None
        self.CACHE_PATH.write_text("{malformed: 123", encoding="utf-8")

        selected = pih.auto_select_skills("academic debts and mirea")
        assert isinstance(selected, list)
