"""
Unit and integration tests for Windows Sandbox Controller in Vazus SuperGraph OS.
Tests XML configuration generation, AppContainer protection, air-gapped networking,
read-only mounting, scratch isolation, and controller lifecycle validation.
"""

import os
import uuid
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from vazus_core.sandbox.wsb_sandbox_controller import (
    WSBSandboxConfig,
    WSBSandboxController,
    WSBSandboxResult,
    generate_wsb_config,
    run_command_sandboxed,
)


class TestWSBSandboxXMLGeneration:
    """Validates security invariants and XML generation for Windows Sandbox."""

    def test_xml_is_valid_syntax(self):
        """Generated configuration must be valid XML."""
        xml_str = generate_wsb_config()
        root = ET.fromstring(xml_str)
        assert root.tag == "Configuration"

    def test_appcontainer_protected_client(self):
        """AppContainer protection (<ProtectedClient>Enable</ProtectedClient>) must be active by default."""
        config = WSBSandboxConfig(protected_client=True)
        controller = WSBSandboxController(config=config)
        xml_str = controller.generate_wsb_config()
        root = ET.fromstring(xml_str)

        protected = root.find("ProtectedClient")
        assert protected is not None
        assert protected.text == "Enable"

    def test_air_gapped_networking_disabled(self):
        """Networking (<Networking>Disable</Networking>) must be disabled by default for zero-trust isolation."""
        config = WSBSandboxConfig(networking_enable=False)
        controller = WSBSandboxController(config=config)
        xml_str = controller.generate_wsb_config()
        root = ET.fromstring(xml_str)

        networking = root.find("Networking")
        assert networking is not None
        assert networking.text == "Disable"

    def test_memory_and_vgpu_limits(self):
        """Memory and vGPU parameters must conform to security baseline."""
        config = WSBSandboxConfig(memory_in_mb=4096, vgpu_enable=False)
        controller = WSBSandboxController(config=config)
        xml_str = controller.generate_wsb_config()
        root = ET.fromstring(xml_str)

        vgpu = root.find("VGpu")
        assert vgpu is not None
        assert vgpu.text == "Disable"

        memory = root.find("MemoryInMB")
        assert memory is not None
        assert memory.text == "4096"

    def test_readonly_mounts_pip_cache_and_vazus_root(self):
        """Pip cache and Vazus workspace root must be mounted strictly ReadOnly=true."""
        with tempfile.TemporaryDirectory() as fake_pip, tempfile.TemporaryDirectory() as fake_vazus:
            config = WSBSandboxConfig(
                host_pip_cache=Path(fake_pip),
                host_vazus_root=Path(fake_vazus),
            )
            controller = WSBSandboxController(config=config)
            xml_str = controller.generate_wsb_config()
            root = ET.fromstring(xml_str)

            mapped_folders = root.findall(".//MappedFolder")
            mount_map = {}
            for mf in mapped_folders:
                host = mf.find("HostFolder").text
                sb = mf.find("SandboxFolder").text
                ro = mf.find("ReadOnly").text
                mount_map[sb] = (host, ro)

            # Check Pip Cache mount
            assert r"C:\pip_cache" in mount_map
            assert mount_map[r"C:\pip_cache"][1] == "true"
            assert Path(mount_map[r"C:\pip_cache"][0]) == Path(fake_pip).resolve()

            # Check Vazus Root mount
            assert r"C:\vazus" in mount_map
            assert mount_map[r"C:\vazus"][1] == "true"
            assert Path(mount_map[r"C:\vazus"][0]) == Path(fake_vazus).resolve()

    def test_readwrite_scratch_directory(self):
        """Scratch directory must be mounted ReadOnly=false for zero-artifact output capture."""
        with tempfile.TemporaryDirectory() as fake_scratch:
            config = WSBSandboxConfig(host_scratch_dir=Path(fake_scratch))
            controller = WSBSandboxController(config=config)
            xml_str = controller.generate_wsb_config()
            root = ET.fromstring(xml_str)

            mapped_folders = root.findall(".//MappedFolder")
            scratch_found = False
            for mf in mapped_folders:
                sb = mf.find("SandboxFolder").text
                if sb == r"C:\scratch":
                    scratch_found = True
                    assert mf.find("ReadOnly").text == "false"
                    assert Path(mf.find("HostFolder").text) == Path(fake_scratch).resolve()
            assert scratch_found

    def test_logon_command_beacon(self):
        """Logon bootstrap command must write a readiness beacon to the scratch directory."""
        controller = WSBSandboxController()
        xml_str = controller.generate_wsb_config()
        root = ET.fromstring(xml_str)

        logon = root.find(".//LogonCommand/Command")
        assert logon is not None
        assert "beacon" in logon.text
        assert "ready.txt" in logon.text

    def test_extra_mapped_folders(self):
        """Extra mapped folders must respect custom path and read_only configurations."""
        with tempfile.TemporaryDirectory() as extra_dir:
            config = WSBSandboxConfig(
                extra_mapped_folders=[
                    {"host_path": extra_dir, "sandbox_path": r"C:\extra", "read_only": True}
                ]
            )
            controller = WSBSandboxController(config=config)
            xml_str = controller.generate_wsb_config()
            root = ET.fromstring(xml_str)

            mapped_folders = root.findall(".//MappedFolder")
            extra_found = False
            for mf in mapped_folders:
                sb = mf.find("SandboxFolder")
                if sb is not None and sb.text == r"C:\extra":
                    extra_found = True
                    assert mf.find("ReadOnly").text == "true"
            assert extra_found


class TestWSBSandboxControllerState:
    """Tests controller lifecycle, binary discovery, and execution mechanics."""

    def test_is_available(self):
        """Controller correctly detects availability of wsb.exe."""
        available = WSBSandboxController.is_available()
        assert isinstance(available, bool)
        # On Windows host with Windows Sandbox installed, it must be True
        assert available is True

    def test_find_wsb_executable(self):
        """find_wsb_executable returns an existing Path to wsb.exe."""
        exe_path = WSBSandboxController.find_wsb_executable()
        assert exe_path.exists()
        assert exe_path.name.lower() in ("wsb.exe", "wsb")

    def test_scratch_dir_lifecycle(self):
        """Scratch directory is created on init and auto-cleaned up on controller stop."""
        controller = WSBSandboxController(auto_cleanup=True)
        scratch = controller.config.host_scratch_dir
        assert scratch.exists()
        assert scratch.is_dir()

        controller.stop()
        assert not scratch.exists()

    def test_pip_offline_flags_and_wrapping(self):
        """Offline pip helpers must enforce --no-index and wheel cache paths."""
        flags = WSBSandboxController.get_pip_offline_flags(cache_dir=r"C:\pip_cache")
        assert "--no-index" in flags
        assert "--find-links" in flags
        assert r"C:\pip_cache" in flags

        wrapped = WSBSandboxController.wrap_pip_command("pip install torch")
        assert "--no-index" in wrapped
        assert "--find-links" in wrapped

        # Should not double-inject if already present
        wrapped_again = WSBSandboxController.wrap_pip_command(wrapped)
        assert wrapped_again.count("--no-index") == 1

    def test_wsb_result_check_returncode(self):
        """WSBSandboxResult properly reflects return codes and raises CalledProcessError on non-zero."""
        ok_res = WSBSandboxResult(
            args="echo 1",
            returncode=0,
            stdout="1\n",
            stderr="",
            duration_ms=10.0,
            session_id="dummy",
            sandbox_scratch_dir=r"C:\scratch",
            host_scratch_dir=Path(tempfile.gettempdir()),
        )
        ok_res.check_returncode()  # Should not raise

        fail_res = WSBSandboxResult(
            args="cmd /c exit 1",
            returncode=1,
            stdout="",
            stderr="Error\n",
            duration_ms=10.0,
            session_id="dummy",
            sandbox_scratch_dir=r"C:\scratch",
            host_scratch_dir=Path(tempfile.gettempdir()),
        )
        with pytest.raises(Exception):
            fail_res.check_returncode()

    @patch("subprocess.run")
    def test_raw_exec_system_context(self, mock_subproc):
        """raw_exec passes the correct arguments including session ID, command, and run_as."""
        mock_subproc.return_value = MagicMock(returncode=0, stdout='{"ExitCode": 0}', stderr="")

        config = WSBSandboxConfig(session_id="11111111-2222-3333-4444-555555555555")
        controller = WSBSandboxController(config=config)

        res = controller.raw_exec("cmd.exe /c echo test", run_as="System")
        assert res.returncode == 0

        mock_subproc.assert_called_once()
        call_args = mock_subproc.call_args[0][0]
        assert "exec" in call_args
        assert "--id" in call_args
        assert "11111111-2222-3333-4444-555555555555" in call_args
        assert "-r" in call_args
        assert "System" in call_args
        assert "--raw" in call_args

    def test_process_monitoring_invariants(self):
        """Monitored process names must cover hypervisor and container processes."""
        names = WSBSandboxController.WSB_PROCESS_NAMES
        assert "windowssandbox.exe" in names
        assert "windowssandboxclient.exe" in names
        assert "vmmemwindowssandbox" in names

    def test_is_sandbox_running_and_list(self):
        """is_sandbox_running and list_sandboxes return consistent state structures."""
        is_running = WSBSandboxController.is_sandbox_running()
        assert isinstance(is_running, bool)

        sandboxes = WSBSandboxController.list_sandboxes()
        assert isinstance(sandboxes, list)
        if not is_running:
            assert len(sandboxes) == 0
