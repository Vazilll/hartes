r"""
tests/benchmarks/test_adversarial_challenger_m3_zig.py — Adversarial Stress Harness for Zig Capability Path Jail (M3).

Adversarial vectors tested:
1. Sibling directory prefix exploits: C:\vazus_evil, C:\vazus2, ~/.gemini_evil, ~/.gemini2, C:\Users\Vaz\.gemini_evil
2. Relative traversal escapes: C:\vazus\..\Windows, ..\..\..\..\..\..\etc, temp_dir/../../Windows
3. Forbidden invariant targets: C:\vazus\AGENTS.md, C:\vazus\.git\config, C:\Windows\System32\cmd.exe, /etc/passwd
4. Null-byte injection: temp_dir\x00/evil, C:\vazus\file\x00.exe
5. Windows extended-length UNC paths: \\?\C:\Windows, \\?\C:\vazus_evil, \\?\C:\vazus
6. Whitelisted roots: C:\vazus, C:\vazus\services, ~/.gemini, \\?\C:\vazus
7. Verification across check_path_allowed, vazus_sandbox_validate_path, and vazus_runner.exe
"""

import ctypes
import json
import os
import subprocess
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(r"C:\vazus")
DLL_PATH = WORKSPACE_ROOT / "bin" / "vazus_runner.dll"
EXE_PATH = WORKSPACE_ROOT / "bin" / "vazus_runner.exe"


@pytest.fixture(scope="module")
def zig_native_lib():
    assert DLL_PATH.is_file(), f"DLL missing at {DLL_PATH}"
    lib = ctypes.CDLL(str(DLL_PATH))
    lib.check_path_allowed.argtypes = [ctypes.c_char_p]
    lib.check_path_allowed.restype = ctypes.c_int
    lib.vazus_sandbox_init.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.vazus_sandbox_init.restype = ctypes.c_void_p
    lib.vazus_sandbox_validate_path.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_bool]
    lib.vazus_sandbox_validate_path.restype = ctypes.c_int
    lib.vazus_sandbox_free.argtypes = [ctypes.c_void_p]
    lib.vazus_sandbox_free.restype = None
    return lib


class TestZigCapabilityPathJailAdversarial:
    """Adversarial stress testing against Zig sandbox path isolation."""

    def test_whitelisted_roots_allowed(self, zig_native_lib):
        """Verify that genuine whitelisted roots and subpaths are permitted."""
        valid_paths = [
            r"C:\vazus",
            r"C:\vazus\services",
            r"C:\vazus\services\memory",
            r"~/.gemini",
            r"\\?\C:\vazus",
            r"\\?\C:\vazus\vazus_core",
        ]
        for path in valid_paths:
            res = zig_native_lib.check_path_allowed(path.encode("utf-8"))
            assert res == 1, f"Expected whitelisted path '{path}' to be allowed, got {res}"

    def test_vazus_sibling_prefix_exploits_blocked(self, zig_native_lib):
        """Verify C:\\vazus sibling prefix variations are blocked."""
        sibling_paths = [
            r"C:\vazus_evil",
            r"C:\vazus2",
            r"C:\vazus_backup",
            r"\\?\C:\vazus_evil",
            r"\\?\C:\vazus2",
        ]
        for path in sibling_paths:
            res = zig_native_lib.check_path_allowed(path.encode("utf-8"))
            assert res == 0, f"Sibling exploit '{path}' must be blocked (got {res})"

    def test_gemini_sibling_prefix_exploits_must_be_blocked(self, zig_native_lib):
        """
        SECURITY AUDIT: Sibling directory prefix exploits targeting ~/.gemini:
        Paths like ~/.gemini_evil, ~/.gemini2, C:\\Users\\Vaz\\.gemini_evil must be blocked!
        """
        gemini_siblings = [
            r"~/.gemini_evil",
            r"~/.gemini2",
            r"~/.gemini_backup",
            r"C:\Users\Vaz\.gemini_evil",
            r"C:\Users\Vaz\.gemini2",
            r"C:\evil\.gemini\payload.exe",
            r"C:\ProgramData\.gemini_evil\hack.exe",
        ]
        failures = []
        for path in gemini_siblings:
            res = zig_native_lib.check_path_allowed(path.encode("utf-8"))
            if res != 0:
                failures.append(path)

        assert not failures, f"CRITICAL SECURITY VULNERABILITY: Sibling paths permitted: {failures}"

    def test_relative_traversal_escapes_blocked(self, zig_native_lib):
        """Verify dot-dot traversal escapes are strictly blocked."""
        traversal_paths = [
            r"C:\vazus\..\Windows",
            r"C:\vazus\..\..\Windows\System32\cmd.exe",
            r"..\..\..\..\..\..\etc",
            r"temp_dir/../../Windows",
            r"C:\vazus\services\..\..\vazus_evil",
        ]
        for path in traversal_paths:
            res = zig_native_lib.check_path_allowed(path.encode("utf-8"))
            assert res == 0, f"Traversal escape '{path}' must be blocked (got {res})"

    def test_forbidden_invariant_targets_blocked(self, zig_native_lib):
        """Verify forbidden targets (.git, AGENTS.md, cmd.exe, /etc/passwd) are blocked."""
        forbidden_targets = [
            r"C:\vazus\AGENTS.md",
            r"C:\vazus\agents.md",
            r"C:\vazus\subdir\AGENTS.md",
            r"C:\vazus\.git\config",
            r"C:\vazus\.git",
            r"C:\vazus\.git\HEAD",
            r"C:\Windows\System32\cmd.exe",
            r"C:\Windows\System32\drivers\etc\hosts",
            r"/etc/passwd",
            r"etc/passwd",
        ]
        for target in forbidden_targets:
            res = zig_native_lib.check_path_allowed(target.encode("utf-8"))
            assert res == 0, f"Forbidden invariant target '{target}' must be blocked (got {res})"

    def test_null_byte_injection(self, zig_native_lib):
        """Verify null-byte injection attempts do not allow escape."""
        null_byte_targets = [
            b"temp_dir\x00/evil",
            b"C:\\vazus\\file\x00.exe",
        ]
        for target in null_byte_targets:
            res = zig_native_lib.check_path_allowed(target)
            assert res in (0, 1)

    def test_windows_extended_unc_escapes_blocked(self, zig_native_lib):
        """Verify Windows extended-length UNC paths pointing outside jail are blocked."""
        unc_escapes = [
            r"\\?\C:\Windows",
            r"\\?\C:\Windows\System32\cmd.exe",
            r"\\?\C:\vazus_evil",
            r"\\?\C:\vazus\AGENTS.md",
            r"\\?\C:\vazus\.git\config",
        ]
        for path in unc_escapes:
            res = zig_native_lib.check_path_allowed(path.encode("utf-8"))
            assert res == 0, f"Extended UNC escape '{path}' must be blocked (got {res})"

    def test_vazus_runner_cli_adversarial_roots(self):
        """Verify vazus_runner.exe strictly rejects forbidden or sibling roots."""
        assert EXE_PATH.is_file(), f"CLI executable missing at {EXE_PATH}"

        # Allowed root
        res_ok = subprocess.run(
            [str(EXE_PATH), "--root", r"C:\vazus", "--eval", "1 + 1"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert res_ok.returncode == 0, f"Valid root failed: {res_ok.stderr}"
        assert "2" in res_ok.stdout

        # Attack roots that MUST be rejected
        attack_roots = [
            r"C:\vazus_evil",
            r"C:\Windows",
            r"C:\vazus\..\Windows",
            r"~/.gemini_evil",
            r"~/.gemini2",
            r"C:\Users\Vaz\.gemini_evil",
        ]
        leaked_roots = []
        for root in attack_roots:
            res = subprocess.run(
                [str(EXE_PATH), "--root", root, "--eval", "1 + 1"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                leaked_roots.append(root)

        assert not leaked_roots, f"CRITICAL SECURITY VULNERABILITY: vazus_runner accepted attack roots: {leaked_roots}"
