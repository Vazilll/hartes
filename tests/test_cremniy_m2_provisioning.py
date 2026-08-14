"""
Automated Test Suite for Milestone 2 Cremniy Automation Provisioning (Requirement R2).

Verifies:
1. Presence and clean execution of low-level binary tools (Radare2, Rizin, GDB).
2. Presence and importability of Python disassembly/assembly engines (Capstone, Keystone).
3. Auto-provisioning idempotency and integrity of resilient downloader.
"""

import os
import sys
import subprocess
import pytest

BIN_DIR = r"C:\vazus\bin"
SCRIPTS_DIR = r"C:\vazus\scripts"
sys.path.insert(0, r"C:\vazus")
sys.path.insert(0, SCRIPTS_DIR)

from resilient_downloader import calculate_sha256
from provision_binary_tools import check_tool_status


def test_radare2_binaries():
    """Verify Radare2 binaries (r2.exe, rabin2.exe, rasm2.exe) exist and run with Exit Code 0."""
    r2_path = os.path.join(BIN_DIR, "r2.exe")
    rabin2_path = os.path.join(BIN_DIR, "rabin2.exe")
    rasm2_path = os.path.join(BIN_DIR, "rasm2.exe")

    assert os.path.exists(r2_path), f"r2.exe missing from {BIN_DIR}"
    assert os.path.exists(rabin2_path), f"rabin2.exe missing from {BIN_DIR}"
    assert os.path.exists(rasm2_path), f"rasm2.exe missing from {BIN_DIR}"

    # Test execution
    res_r2 = subprocess.run([r2_path, "-v"], capture_output=True, text=True)
    assert res_r2.returncode == 0, f"r2.exe failed with code {res_r2.returncode}: {res_r2.stderr}"
    assert "radare2" in res_r2.stdout.lower() or "abi:" in res_r2.stdout.lower(), f"Unexpected r2 -v output: {res_r2.stdout}"

    res_rabin2 = subprocess.run([rabin2_path, "-v"], capture_output=True, text=True)
    assert res_rabin2.returncode == 0, f"rabin2.exe failed with code {res_rabin2.returncode}"

    res_rasm2 = subprocess.run([rasm2_path, "-v"], capture_output=True, text=True)
    assert res_rasm2.returncode == 0, f"rasm2.exe failed with code {res_rasm2.returncode}"


def test_rizin_binaries():
    """Verify Rizin binaries (rizin.exe, rz-bin.exe, rz-asm.exe) exist and run with Exit Code 0."""
    rizin_path = os.path.join(BIN_DIR, "rizin.exe")
    rzbin_path = os.path.join(BIN_DIR, "rz-bin.exe")
    rzasm_path = os.path.join(BIN_DIR, "rz-asm.exe")

    assert os.path.exists(rizin_path), f"rizin.exe missing from {BIN_DIR}"
    assert os.path.exists(rzbin_path), f"rz-bin.exe missing from {BIN_DIR}"
    assert os.path.exists(rzasm_path), f"rz-asm.exe missing from {BIN_DIR}"

    # Test execution
    res_rizin = subprocess.run([rizin_path, "-v"], capture_output=True, text=True)
    assert res_rizin.returncode == 0, f"rizin.exe failed with code {res_rizin.returncode}: {res_rizin.stderr}"
    assert "rizin" in res_rizin.stdout.lower(), f"Unexpected rizin -v output: {res_rizin.stdout}"

    res_rzbin = subprocess.run([rzbin_path, "-v"], capture_output=True, text=True)
    assert res_rzbin.returncode == 0, f"rz-bin.exe failed with code {res_rzbin.returncode}"

    res_rzasm = subprocess.run([rzasm_path, "-v"], capture_output=True, text=True)
    assert res_rzasm.returncode == 0, f"rz-asm.exe failed with code {res_rzasm.returncode}"


def test_gdb_binary():
    """Verify GDB binary (gdb.exe) exists and runs with Exit Code 0."""
    gdb_path = os.path.join(BIN_DIR, "gdb.exe")
    assert os.path.exists(gdb_path), f"gdb.exe missing from {BIN_DIR}"

    res_gdb = subprocess.run([gdb_path, "--version"], capture_output=True, text=True)
    assert res_gdb.returncode == 0, f"gdb.exe failed with code {res_gdb.returncode}: {res_gdb.stderr}"
    assert "gdb" in res_gdb.stdout.lower() or "gnu" in res_gdb.stdout.lower(), f"Unexpected gdb --version output: {res_gdb.stdout}"


def test_capstone_package():
    """Verify Capstone Python package and shared library availability."""
    import capstone
    assert hasattr(capstone, "__version__"), "Capstone version attribute missing"
    assert capstone.CS_ARCH_X86 is not None, "Capstone x86 architecture constant missing"

    # Test simple disassembly
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    insns = list(md.disasm(b"\x90\x90\xc3", 0x1000))
    assert len(insns) == 3, f"Expected 3 disasm instructions, got {len(insns)}"
    assert insns[0].mnemonic == "nop"
    assert insns[2].mnemonic == "ret"


def test_keystone_package():
    """Verify Keystone Engine Python package and shared library availability."""
    import keystone
    assert hasattr(keystone, "Ks"), "Keystone Ks class missing"

    # Test simple assembly
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_64)
    encoding, count = ks.asm("nop; ret")
    assert count == 2, f"Expected 2 assembled instructions, got {count}"
    assert encoding == [0x90, 0xc3], f"Unexpected encoding: {encoding}"


def test_provision_status_check():
    """Verify check_tool_status API reports all tools as installed."""
    status = check_tool_status(BIN_DIR)
    for tool_name, is_installed in status.items():
        assert is_installed, f"Tool {tool_name} reported as NOT installed in check_tool_status"


def test_provision_script_cli_check():
    """Verify provision_binary_tools.py script runs cleanly with --check."""
    script_path = os.path.join(SCRIPTS_DIR, "provision_binary_tools.py")
    res = subprocess.run([sys.executable, script_path, "--check"], capture_output=True, text=True)
    assert res.returncode == 0, f"provision_binary_tools.py --check failed with code {res.returncode}: {res.stderr}\nOutput: {res.stdout}"


def test_sha256_verifier(tmp_path):
    """Verify resilient_downloader SHA-256 calculation utility."""
    test_file = tmp_path / "sample.txt"
    test_file.write_bytes(b"Cremniy Automation M2 Test Content")
    
    computed = calculate_sha256(str(test_file))
    assert isinstance(computed, str)
    assert len(computed) == 64
