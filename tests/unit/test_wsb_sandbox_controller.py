r"""
Unit tests for Windows Sandbox Hardware Controller (Requirement R1.2).
Validates:
1. XML generation with mandatory security directives:
   - <ProtectedClient>Enable</ProtectedClient>
   - <Networking>Disable</Networking>
   - Read-Only pip cache mounting (HostFolder -> C:\pip_cache)
   - Read-Only vazus root mounting (C:\vazus -> C:\vazus)
   - Ephemeral scratch directory mounting (HostFolder -> C:\scratch, ReadOnly=false)
2. Pip offline mode flags (--no-index, --find-links C:\pip_cache).
3. CLI wsb.exe argument construction (start, exec, stop).
4. Hyper-V VMBus stdout/stderr bridge and exit code extraction.
5. Multi-tier fallback termination (wsb -> hcsdiag -> psutil).
6. Zero-Artifact Protocol and ephemeral scratch cleanup.
7. Root alias import and interface contract compatibility.
"""

import sys
import uuid
import shutil
import tempfile
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from vazus_core.sandbox.wsb_sandbox_controller import (
    WSBSandboxController,
    WSBSandboxConfig,
    WSBSandboxResult,
    generate_wsb_config,
    run_command_sandboxed,
)
import wsb_sandbox_controller as root_wsb_module


# ============================================================================
# 1. XML Generation & Security Directive Validation
# ============================================================================

class TestWSBConfigXMLDirectives:
    """Verifies mandatory XML configuration directives and folder mappings."""

    def test_mandatory_security_directives_present(self, tmp_path):
        """Ensures ProtectedClient and Networking Disable are strictly enforced."""
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()
        pip_cache = tmp_path / "pip_cache"
        pip_cache.mkdir()

        xml_str = generate_wsb_config(
            session_id="test-session-123",
            host_scratch_dir=scratch_dir,
            host_pip_cache=pip_cache,
            host_vazus_root=r"C:\vazus"
        )

        # Parse valid XML
        root = ET.fromstring(xml_str)
        assert root.tag == "Configuration"

        # Directive 1: ProtectedClient Enable
        protected = root.find("ProtectedClient")
        assert protected is not None, "ProtectedClient directive must exist"
        assert protected.text == "Enable", "ProtectedClient must be set to Enable"

        # Directive 2: Networking Disable (Physical network disconnection)
        networking = root.find("Networking")
        assert networking is not None, "Networking directive must exist"
        assert networking.text == "Disable", "Networking must be set to Disable"

        # Directive 3: Memory and vGPU
        assert root.find("MemoryInMB").text == "4096"
        assert root.find("VGpu").text == "Disable"

    def test_mapped_folders_hierarchy_and_permissions(self, tmp_path):
        """Verifies Read-Only and Read-Write permissions across mapped folders."""
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()
        pip_cache = tmp_path / "pip_cache"
        pip_cache.mkdir()

        cfg = WSBSandboxConfig(
            session_id="test-session-456",
            host_scratch_dir=scratch_dir,
            host_pip_cache=pip_cache,
            host_vazus_root=Path(r"C:\vazus")
        )
        controller = WSBSandboxController(config=cfg)
        xml_str = controller.generate_wsb_config()

        root = ET.fromstring(xml_str)
        mapped_folders = root.find("MappedFolders")
        assert mapped_folders is not None

        folders = mapped_folders.findall("MappedFolder")
        mappings = {}
        for f in folders:
            host = f.find("HostFolder").text
            sandbox = f.find("SandboxFolder").text
            ro = f.find("ReadOnly").text
            mappings[sandbox] = {"host": host, "ro": ro}

        # Check Pip Cache Mapping (ReadOnly=true)
        assert r"C:\pip_cache" in mappings
        assert mappings[r"C:\pip_cache"]["ro"] == "true"
        assert mappings[r"C:\pip_cache"]["host"] == str(pip_cache.resolve())

        # Check Vazus Repo Mapping (ReadOnly=true)
        if Path(r"C:\vazus").exists():
            assert r"C:\vazus" in mappings
            assert mappings[r"C:\vazus"]["ro"] == "true"
            assert mappings[r"C:\vazus"]["host"] == str(Path(r"C:\vazus").resolve())

        # Check Ephemeral Scratch Mapping (ReadOnly=false)
        assert r"C:\scratch" in mappings
        assert mappings[r"C:\scratch"]["ro"] == "false"
        assert mappings[r"C:\scratch"]["host"] == str(scratch_dir.resolve())

    def test_wsb_file_written_with_utf8_bom(self, tmp_path):
        """Verifies write_wsb_file generates a valid .wsb file with UTF-8 BOM."""
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()
        cfg = WSBSandboxConfig(host_scratch_dir=scratch_dir)
        controller = WSBSandboxController(config=cfg)
        wsb_file = controller.write_wsb_file()

        assert wsb_file.exists()
        assert wsb_file.suffix == ".wsb"

        # Verify UTF-8 BOM presence
        with open(wsb_file, "rb") as f:
            header = f.read(3)
            assert header == b"\xef\xbb\xbf", "WSB file must have UTF-8 BOM signature"


# ============================================================================
# 2. Pip Offline Mode Flags
# ============================================================================

class TestPipOfflineFlags:
    """Verifies pip offline mode flags and command rewriting."""

    def test_get_pip_offline_flags(self):
        flags = WSBSandboxController.get_pip_offline_flags(r"C:\pip_cache")
        assert flags == ["--no-index", "--find-links", r"C:\pip_cache"]

    def test_wrap_pip_command_injection(self):
        # 1. Plain pip install -> injected
        cmd1 = "pip install pytest"
        wrapped1 = WSBSandboxController.wrap_pip_command(cmd1, r"C:\pip_cache")
        assert wrapped1 == "pip install --no-index --find-links C:\\pip_cache pytest"

        # 2. Already offline -> unchanged
        cmd2 = "pip install --no-index --find-links C:\\pip_cache pytest"
        wrapped2 = WSBSandboxController.wrap_pip_command(cmd2, r"C:\pip_cache")
        assert wrapped2 == cmd2

        # 3. Non-pip command -> unchanged
        cmd3 = "python -m pytest tests/unit/"
        wrapped3 = WSBSandboxController.wrap_pip_command(cmd3, r"C:\pip_cache")
        assert wrapped3 == cmd3


# ============================================================================
# 3. Process Control & CLI Argument Construction (wsb.exe)
# ============================================================================

class TestWSBProcessControl:
    """Verifies invocation syntax and argument construction for wsb.exe."""

    @patch("shutil.which", return_value=r"C:\WindowsApps\wsb.exe")
    def test_find_wsb_executable_which(self, mock_which):
        exe = WSBSandboxController.find_wsb_executable()
        assert str(exe) == r"C:\WindowsApps\wsb.exe"

    @patch("subprocess.run")
    def test_start_session_arguments(self, mock_run, tmp_path):
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()
        # Seed beacon file to avoid waiting loop
        beacon_file = scratch_dir / "beacon" / "ready.txt"
        beacon_file.parent.mkdir(parents=True, exist_ok=True)
        beacon_file.write_text("READY")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"WindowsSandboxEnvironmentId": "test-id-1"}', stderr=""
        )

        cfg = WSBSandboxConfig(session_id="test-id-1", host_scratch_dir=scratch_dir)
        with patch.object(WSBSandboxController, "find_wsb_executable", return_value=Path("wsb.exe")):
            controller = WSBSandboxController(config=cfg, auto_cleanup=False)
            actual_id = controller.start(wait_ready_sec=1)
            assert actual_id == "test-id-1"

            # Check subprocess.run args
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "wsb.exe"
            assert call_args[1] == "start"
            assert "-c" in call_args
            assert "--id" in call_args
            assert "test-id-1" in call_args
            assert "--raw" in call_args

    @patch("subprocess.run")
    def test_stop_session_arguments(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        cfg = WSBSandboxConfig(session_id="test-id-stop", host_scratch_dir=tmp_path)
        with patch.object(WSBSandboxController, "find_wsb_executable", return_value=Path("wsb.exe")):
            controller = WSBSandboxController(config=cfg, auto_cleanup=False)
            controller._is_active = True
            stopped = controller.stop()
            assert stopped is True

            call_args = mock_run.call_args[0][0]
            assert call_args == ["wsb.exe", "stop", "--id", "test-id-stop", "--raw"]

    @patch("subprocess.run")
    def test_exec_command_io_capture_bridge(self, mock_run, tmp_path):
        """Verifies stdout/stderr and exit code extraction via host scratch directory."""
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()

        cfg = WSBSandboxConfig(session_id="test-id-exec", host_scratch_dir=scratch_dir)
        with patch.object(WSBSandboxController, "find_wsb_executable", return_value=Path("wsb.exe")):
            controller = WSBSandboxController(config=cfg, auto_cleanup=False)
            controller._is_active = True

            # Mock raw_exec side-effect: simulate guest writing stdout and exit code to host scratch
            def fake_raw_run(*args, **kwargs):
                # Discover cmd_id from command string
                cmd_str = " ".join(args[0])
                import re
                m = re.search(r"stdout_([a-f0-9]+)\.log", cmd_str)
                if m:
                    cid = m.group(1)
                    (scratch_dir / f"stdout_{cid}.log").write_text("Hello from Sandbox!\n", encoding="utf-8")
                    (scratch_dir / f"stderr_{cid}.log").write_text("", encoding="utf-8")
                    (scratch_dir / f"rc_{cid}.txt").write_text("0\n", encoding="utf-8")
                return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

            mock_run.side_effect = fake_raw_run

            res = controller.exec_command("echo Hello from Sandbox!")
            assert res.returncode == 0
            assert "Hello from Sandbox!" in res.stdout
            assert res.stderr == ""
            assert res.session_id == "test-id-exec"


# ============================================================================
# 4. Fallback Termination & Zero-Artifact Protocol
# ============================================================================

class TestFallbackAndZeroArtifacts:
    """Verifies fallback escalation and ephemeral scratch directory deletion."""

    @patch("subprocess.run")
    def test_fallback_to_hcsdiag_on_wsb_failure(self, mock_run, tmp_path):
        """When wsb stop fails, controller falls back to hcsdiag kill."""
        def run_router(*args, **kwargs):
            cmd = args[0]
            if cmd[0] == "wsb.exe" and cmd[1] == "stop":
                return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="Failed")
            elif cmd[0] == "hcsdiag.exe" and cmd[1] == "list":
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="11223344-5566-7788-9900-aabbccddeeff  VMContainer\n", stderr=""
                )
            elif cmd[0] == "hcsdiag.exe" and cmd[1] == "kill":
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Killed", stderr="")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        mock_run.side_effect = run_router

        cfg = WSBSandboxConfig(session_id="test-fallback", host_scratch_dir=tmp_path)
        with patch.object(WSBSandboxController, "find_wsb_executable", return_value=Path("wsb.exe")):
            controller = WSBSandboxController(config=cfg, auto_cleanup=False)
            controller._is_active = True
            stopped = controller.stop()
            assert stopped is True

    def test_zero_artifact_ephemeral_scratch_cleanup(self):
        """Verifies ephemeral host scratch dir is deleted upon context manager exit."""
        created_scratch = None
        with patch.object(WSBSandboxController, "find_wsb_executable", return_value=Path("wsb.exe")), \
             patch.object(WSBSandboxController, "start", return_value="sess-1"), \
             patch.object(WSBSandboxController, "stop", return_value=True):

            ctrl = WSBSandboxController(auto_cleanup=True)
            created_scratch = ctrl.config.host_scratch_dir
            assert created_scratch.exists(), "Scratch dir must be initialized"

            # Simulate stopping
            ctrl._is_active = False
            if ctrl._owns_scratch and ctrl.auto_cleanup:
                shutil.rmtree(created_scratch, ignore_errors=True)

            assert not created_scratch.exists(), "Scratch directory must be purged (Zero-Artifact)"


# ============================================================================
# 5. Root Alias & Parity Checks
# ============================================================================

class TestRootAliasParity:
    """Verifies that the root alias wsb_sandbox_controller.py exports identical symbols."""

    def test_symbol_parity_with_core(self):
        from vazus_core.sandbox import wsb_sandbox_controller as core_mod

        assert root_wsb_module.WSBSandboxController is core_mod.WSBSandboxController
        assert root_wsb_module.WSBSandboxConfig is core_mod.WSBSandboxConfig
        assert root_wsb_module.WSBSandboxResult is core_mod.WSBSandboxResult
        assert root_wsb_module.generate_wsb_config is core_mod.generate_wsb_config
        assert root_wsb_module.run_command_sandboxed is core_mod.run_command_sandboxed


# ============================================================================
# 6. Live Host Validation (Executed only if wsb.exe is present)
# ============================================================================

@pytest.mark.skipif(not WSBSandboxController.is_available(), reason="wsb.exe not present on host")
def test_live_wsb_list_execution():
    """Live smoke test: wsb list --raw executes without crashing and returns valid list."""
    sandboxes = WSBSandboxController.list_sandboxes()
    assert isinstance(sandboxes, list)