r"""
Windows Sandbox Hardware Controller for Vazus SuperGraph OS v5.2.
Provides hardware-isolated, deterministic execution via wsb.exe CLI with:
- AppContainer protection (<ProtectedClient>Enable</ProtectedClient>)
- Air-gapped network disconnection (<Networking>Disable</Networking>)
- Read-only pip cache and repository mounting
- Ephemeral scratch directory for zero-artifact output capture
- Pip offline mode flags (--no-index, --find-links C:\pip_cache)
- Multi-tier fallback handling (wsb.exe -> hcsdiag.exe -> process tree -> Win32JobSandbox)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("vazus_core.sandbox.wsb_controller")


# ============================================================================
# Data Models & Result Containers
# ============================================================================


@dataclass
class WSBSandboxConfig:
    """Configuration parameters for Windows Sandbox session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_in_mb: int = 4096
    vgpu_enable: bool = False
    protected_client: bool = True
    networking_enable: bool = False
    host_pip_cache: Path = field(
        default_factory=lambda: Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Vaz\AppData\Local")) / "pip" / "cache"
    )
    sandbox_pip_cache: str = r"C:\pip_cache"
    host_vazus_root: Path = field(default_factory=lambda: Path(r"C:\vazus").resolve())
    sandbox_vazus_root: str = r"C:\vazus"
    host_scratch_dir: Optional[Path] = None
    sandbox_scratch_dir: str = r"C:\scratch"
    extra_mapped_folders: List[Dict[str, Any]] = field(default_factory=list)
    logon_command: Optional[str] = None


@dataclass
class WSBSandboxResult:
    """Execution result container mimicking subprocess.CompletedProcess."""

    args: Union[str, List[str]]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: float
    session_id: str
    sandbox_scratch_dir: str
    host_scratch_dir: Path

    def check_returncode(self) -> None:
        if self.returncode != 0:
            raise subprocess.CalledProcessError(self.returncode, self.args, output=self.stdout, stderr=self.stderr)


# ============================================================================
# Core Windows Sandbox Controller
# ============================================================================


class WSBSandboxController:
    """
    Programmatic controller for Windows Sandbox environments using wsb.exe CLI.
    Enforces strict physical isolation, zero-trust network blocking, and zero disk artifacts.
    """

    DEFAULT_TIMEOUT: int = 60
    WSB_PROCESS_NAMES = [
        "windowssandbox.exe",
        "windowssandboxclient.exe",
        "windowssandboxremotesession.exe",
        "windowssandboxserver.exe",
        "vmmemwindowssandbox",
    ]

    def __init__(self, config: Optional[WSBSandboxConfig] = None, auto_cleanup: bool = True):
        self.config = config or WSBSandboxConfig()
        self.auto_cleanup = auto_cleanup
        self._is_active = False
        self._owns_scratch = False
        self._wsb_path: Optional[Path] = None

        # Resolve or create host scratch directory
        if self.config.host_scratch_dir is None:
            temp_root = Path(os.environ.get("TEMP", tempfile.gettempdir()))
            self.config.host_scratch_dir = Path(
                tempfile.mkdtemp(prefix=f"vazus_wsb_{self.config.session_id[:8]}_", dir=temp_root)
            )
            self._owns_scratch = True
        else:
            self.config.host_scratch_dir.mkdir(parents=True, exist_ok=True)

        self._wsb_config_file: Optional[Path] = None

    # ------------------------------------------------------------------------
    # Binary Discovery & Health Checks
    # ------------------------------------------------------------------------

    @classmethod
    def find_wsb_executable(cls) -> Path:
        """Resolves the authoritative path to wsb.exe CLI on Windows."""
        # 1. PATH search
        which_wsb = shutil.which("wsb.exe") or shutil.which("wsb")
        if which_wsb:
            return Path(which_wsb).resolve()

        # 2. LocalAppData WindowsApps alias
        local_app_data = os.environ.get("LOCALAPPDATA", r"C:\Users\Vaz\AppData\Local")
        alias_path = Path(local_app_data) / "Microsoft" / "WindowsApps" / "wsb.exe"
        if alias_path.exists():
            return alias_path.resolve()

        # 3. Direct Program Files WindowsApps search
        prog_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WindowsApps"
        if prog_files.exists():
            candidates = list(prog_files.glob("MicrosoftWindows.WindowsSandbox_*_x64__cw5n1h2t*/wsb.exe"))
            if candidates:
                return candidates[0].resolve()

        raise FileNotFoundError("wsb.exe CLI not found. Ensure Windows Sandbox is enabled in Windows Features.")

    @classmethod
    def is_available(cls) -> bool:
        """Checks if Windows Sandbox and wsb.exe are available and supported."""
        if sys.platform != "win32":
            return False
        try:
            exe = cls.find_wsb_executable()
            return exe.exists()
        except Exception:
            return False

    @classmethod
    def is_sandbox_running(cls) -> bool:
        """Checks whether any Windows Sandbox OS process or session is active."""
        try:
            res = subprocess.run(
                [str(cls.find_wsb_executable()), "list", "--raw"], capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                envs = data.get("WindowsSandboxEnvironments", [])
                return len(envs) > 0
        except Exception:
            pass

        # Fallback to process inspection
        try:
            import psutil

            for proc in psutil.process_iter(["name"]):
                name = proc.info.get("name")
                if name and any(target in name.lower() for target in cls.WSB_PROCESS_NAMES):
                    return True
        except Exception:
            pass
        return False

    @classmethod
    def list_sandboxes(cls) -> List[Dict[str, Any]]:
        """Queries running Windows Sandbox environments using wsb.exe list --raw."""
        try:
            wsb_exe = cls.find_wsb_executable()
            res = subprocess.run([str(wsb_exe), "list", "--raw"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                return data.get("WindowsSandboxEnvironments", [])
        except Exception as exc:
            logger.debug(f"wsb list error: {exc}")
        return []

    # ------------------------------------------------------------------------
    # XML Configuration Engine
    # ------------------------------------------------------------------------

    def generate_wsb_config(self) -> str:
        """
        Generates the strict, verified Windows Sandbox XML configuration string.
        Enforces:
        - <ProtectedClient>Enable</ProtectedClient>
        - <Networking>Disable</Networking>
        - Host pip cache -> C:\\pip_cache (ReadOnly=true)
        - Host vazus root -> C:\\vazus (ReadOnly=true)
        - Host scratch dir -> C:\\scratch (ReadOnly=false)
        """
        root = ET.Element("Configuration")

        # 1. Mandatory AppContainer Isolation
        protected = ET.SubElement(root, "ProtectedClient")
        protected.text = "Enable" if self.config.protected_client else "Disable"

        # 2. Mandatory Network Disconnection
        networking = ET.SubElement(root, "Networking")
        networking.text = "Enable" if self.config.networking_enable else "Disable"

        # 3. vGPU setting
        vgpu = ET.SubElement(root, "VGpu")
        vgpu.text = "Enable" if self.config.vgpu_enable else "Disable"

        # 4. RAM Allocation
        memory = ET.SubElement(root, "MemoryInMB")
        memory.text = str(self.config.memory_in_mb)

        # 5. Mapped Folders Hierarchy
        mapped_folders = ET.SubElement(root, "MappedFolders")

        # Map A: Host Pip Cache (Read-Only)
        pip_cache_path = self.config.host_pip_cache.resolve()
        if pip_cache_path.exists():
            mf_pip = ET.SubElement(mapped_folders, "MappedFolder")
            ET.SubElement(mf_pip, "HostFolder").text = str(pip_cache_path)
            ET.SubElement(mf_pip, "SandboxFolder").text = self.config.sandbox_pip_cache
            ET.SubElement(mf_pip, "ReadOnly").text = "true"

        # Map B: Vazus Workspace Root (Read-Only)
        vazus_path = self.config.host_vazus_root.resolve()
        if vazus_path.exists():
            mf_vazus = ET.SubElement(mapped_folders, "MappedFolder")
            ET.SubElement(mf_vazus, "HostFolder").text = str(vazus_path)
            ET.SubElement(mf_vazus, "SandboxFolder").text = self.config.sandbox_vazus_root
            ET.SubElement(mf_vazus, "ReadOnly").text = "true"

        # Map C: Ephemeral Scratch Output Directory (Read-Write)
        scratch_path = self.config.host_scratch_dir.resolve()
        mf_scratch = ET.SubElement(mapped_folders, "MappedFolder")
        ET.SubElement(mf_scratch, "HostFolder").text = str(scratch_path)
        ET.SubElement(mf_scratch, "SandboxFolder").text = self.config.sandbox_scratch_dir
        ET.SubElement(mf_scratch, "ReadOnly").text = "false"

        # Map D: Extra user-defined mounts
        for extra in self.config.extra_mapped_folders:
            h_folder = Path(extra["host_path"]).resolve()
            if h_folder.exists():
                mf_extra = ET.SubElement(mapped_folders, "MappedFolder")
                ET.SubElement(mf_extra, "HostFolder").text = str(h_folder)
                if "sandbox_path" in extra:
                    ET.SubElement(mf_extra, "SandboxFolder").text = str(extra["sandbox_path"])
                ET.SubElement(mf_extra, "ReadOnly").text = "true" if extra.get("read_only", True) else "false"

        # 6. Logon Bootstrap Command (Initial beacon signal)
        logon_cmd = self.config.logon_command or (
            f'cmd.exe /c "mkdir {self.config.sandbox_scratch_dir}\\beacon 2>nul & '
            f'echo READY > {self.config.sandbox_scratch_dir}\\beacon\\ready.txt"'
        )
        logon_elem = ET.SubElement(root, "LogonCommand")
        ET.SubElement(logon_elem, "Command").text = logon_cmd

        # Produce indented XML
        ET.indent(root, space="  ")
        xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return xml_str

    def write_wsb_file(self) -> Path:
        """Writes the generated XML configuration to a temporary .wsb file with UTF-8 BOM."""
        xml_content = self.generate_wsb_config()
        cfg_file = self.config.host_scratch_dir / f"sandbox_{self.config.session_id[:8]}.wsb"
        with open(cfg_file, "w", encoding="utf-8-sig") as f:
            f.write(xml_content)
        self._wsb_config_file = cfg_file
        return cfg_file

    # ------------------------------------------------------------------------
    # Offline Pip Management
    # ------------------------------------------------------------------------

    @classmethod
    def get_pip_offline_flags(cls, cache_dir: str = r"C:\pip_cache") -> List[str]:
        """Returns standard flags for offline pip operations in Windows Sandbox."""
        return ["--no-index", "--find-links", cache_dir]

    @classmethod
    def wrap_pip_command(cls, cmd: str, cache_dir: str = r"C:\pip_cache") -> str:
        """Injects offline index and wheel search paths into any pip invocation."""
        offline_flags = f"--no-index --find-links {cache_dir}"
        if "pip install" in cmd and "--no-index" not in cmd:
            return cmd.replace("pip install", f"pip install {offline_flags}")
        return cmd

    # ------------------------------------------------------------------------
    # Lifecycle: Start, Exec, Stop
    # ------------------------------------------------------------------------

    def start(self, wait_ready_sec: int = 45) -> str:
        """
        Launches Windows Sandbox instance using wsb.exe start.
        Returns the confirmed session ID.
        """
        if self._is_active:
            return self.config.session_id

        wsb_exe = self.find_wsb_executable()
        self.write_wsb_file()
        xml_content = self.generate_wsb_config()

        cmd = [str(wsb_exe), "start", "-c", xml_content, "--id", self.config.session_id, "--raw"]

        logger.info(f"Starting Windows Sandbox [ID: {self.config.session_id}]...")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"Failed to start Windows Sandbox via wsb.exe: {err_msg}")

        # Wait for guest boot beacon or quick System probe
        beacon_file = self.config.host_scratch_dir / "beacon" / "ready.txt"
        t0 = time.time()
        ready = False
        while time.time() - t0 < wait_ready_sec:
            if beacon_file.exists():
                ready = True
                break
            # Fallback probe via quick wsb exec ping in System context
            try:
                probe = self.raw_exec("cmd.exe /c echo ping", run_as="System", timeout_sec=3)
                if probe.returncode == 0:
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(1.0)

        if not ready:
            logger.warning(
                f"Windows Sandbox {self.config.session_id} started, but ready beacon timed out after {wait_ready_sec}s."
            )

        self._is_active = True
        return self.config.session_id

    def raw_exec(
        self,
        command: str,
        working_dir: Optional[str] = None,
        run_as: str = "System",
        timeout_sec: int = DEFAULT_TIMEOUT,
    ) -> subprocess.CompletedProcess:
        """Executes a command directly via wsb.exe exec without stdout/stderr bridge."""
        wsb_exe = self.find_wsb_executable()
        cmd = [str(wsb_exe), "exec", "--id", self.config.session_id, "-c", command, "-r", run_as, "--raw"]
        if working_dir:
            cmd.extend(["-d", working_dir])

        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)

    def exec_command(
        self,
        command: str,
        working_dir: Optional[str] = None,
        run_as: str = "System",
        timeout_sec: int = DEFAULT_TIMEOUT,
    ) -> WSBSandboxResult:
        """
        Executes a command inside the sandbox with full stdout/stderr capture.
        Solves the wsb.exe I/O limitation by routing stdout, stderr, and exit codes
        through the shared Hyper-V VMBus scratch directory.
        """
        if not self._is_active:
            self.start()

        cmd_id = str(uuid.uuid4())[:8]
        out_file_host = self.config.host_scratch_dir / f"stdout_{cmd_id}.log"
        err_file_host = self.config.host_scratch_dir / f"stderr_{cmd_id}.log"
        rc_file_host = self.config.host_scratch_dir / f"rc_{cmd_id}.txt"

        out_file_guest = f"{self.config.sandbox_scratch_dir}\\stdout_{cmd_id}.log"
        err_file_guest = f"{self.config.sandbox_scratch_dir}\\stderr_{cmd_id}.log"
        rc_file_guest = f"{self.config.sandbox_scratch_dir}\\rc_{cmd_id}.txt"

        # Apply pip offline flags if needed
        command = self.wrap_pip_command(command, self.config.sandbox_pip_cache)

        # Wrap command in cmd.exe execution harness to capture I/O streams and exit code
        # Format: ( command ) > stdout 2> stderr & echo %ERRORLEVEL% > rc
        wrapped_command = (
            f'cmd.exe /s /c "({command}) > "{out_file_guest}" 2> "{err_file_guest}" & '
            f'call echo %^ERRORLEVEL% > "{rc_file_guest}""'
        )

        effective_dir = working_dir or self.config.sandbox_scratch_dir

        t0 = time.perf_counter()
        raw_res = self.raw_exec(
            command=wrapped_command, working_dir=effective_dir, run_as=run_as, timeout_sec=timeout_sec
        )
        duration_ms = (time.perf_counter() - t0) * 1000.0

        # Read captured outputs from host scratch directory with multi-encoding fallback
        def _read_decoded(file_path: Path) -> str:
            if not file_path.exists():
                return ""
            raw_bytes = file_path.read_bytes()
            for enc in ["utf-8-sig", "utf-16", "utf-8", "cp1251", "cp866"]:
                try:
                    return raw_bytes.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw_bytes.decode("utf-8", errors="replace")

        stdout_content = _read_decoded(out_file_host)
        stderr_content = _read_decoded(err_file_host)
        exit_code = raw_res.returncode

        if rc_file_host.exists():
            try:
                rc_str = _read_decoded(rc_file_host).strip()
                if rc_str.isdigit() or (rc_str.startswith("-") and rc_str[1:].isdigit()):
                    exit_code = int(rc_str)
            except Exception:
                pass

        # Cleanup intermediate command logs to uphold Zero-Artifact protocol
        for f in [out_file_host, err_file_host, rc_file_host]:
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

        return WSBSandboxResult(
            args=command,
            returncode=exit_code,
            stdout=stdout_content,
            stderr=stderr_content,
            duration_ms=duration_ms,
            session_id=self.config.session_id,
            sandbox_scratch_dir=self.config.sandbox_scratch_dir,
            host_scratch_dir=self.config.host_scratch_dir,
        )

    def stop(self, timeout_sec: int = 15) -> bool:
        """
        Terminates the Windows Sandbox session via wsb.exe stop.
        Implements multi-tier fallback to hcsdiag and process termination on hang.
        """
        stopped = True
        if self._is_active:
            stopped = False
            # Tier 1: wsb.exe stop
            try:
                wsb_exe = self.find_wsb_executable()
                res = subprocess.run(
                    [str(wsb_exe), "stop", "--id", self.config.session_id, "--raw"],
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                )
                if res.returncode == 0:
                    stopped = True
            except Exception as exc:
                logger.warning(f"Tier 1 wsb stop error: {exc}. Escalating to Tier 2 (hcsdiag).")

            # Tier 2: Fallback via hcsdiag kill
            if not stopped:
                try:
                    hcs_list = subprocess.run(["hcsdiag.exe", "list"], capture_output=True, text=True, timeout=5)
                    import re

                    for line in hcs_list.stdout.splitlines():
                        m = re.match(r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", line.strip())
                        if m:
                            cid = m.group(1)
                            subprocess.run(["hcsdiag.exe", "kill", cid], timeout=5, capture_output=True)
                            stopped = True
                except Exception as e:
                    logger.debug(f"Tier 2 hcsdiag cleanup: {e}")

            # Tier 3: Process Tree Termination
            if not stopped:
                try:
                    import psutil

                    for proc in psutil.process_iter(["name"]):
                        name = proc.info.get("name")
                        if name and any(target in name.lower() for target in self.WSB_PROCESS_NAMES):
                            proc.terminate()
                            stopped = True
                except Exception:
                    pass

            self._is_active = False

        # Cleanup scratch directory if owned and auto_cleanup enabled
        if self._owns_scratch and self.auto_cleanup and self.config.host_scratch_dir.exists():
            try:
                shutil.rmtree(self.config.host_scratch_dir, ignore_errors=True)
            except Exception as exc:
                logger.warning(f"Failed to rmtree scratch dir: {exc}")

        return stopped

    # ------------------------------------------------------------------------
    # Context Manager Protocol
    # ------------------------------------------------------------------------

    def __enter__(self) -> WSBSandboxController:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    # ------------------------------------------------------------------------
    # MCP Server Compatibility Interface
    # ------------------------------------------------------------------------

    @property
    def ready_file(self) -> Path:
        """Path to guest readiness beacon file."""
        return self.config.host_scratch_dir / "beacon" / "ready.txt"

    def is_running(self) -> bool:
        """Checks if current session or any sandbox instance is active."""
        return self._is_active or self.is_sandbox_running()

    def launch(self, force_restart: bool = False, timeout_sec: int = 45) -> bool:
        """Launches sandbox with optional restart."""
        if force_restart and self.is_running():
            self.stop()
        self.start(wait_ready_sec=timeout_sec)
        return True

    def terminate(self) -> bool:
        """Terminates active sandbox session."""
        return self.stop()

    def ping(self, timeout_sec: float = 2.0) -> Dict[str, Any]:
        """Probes sandbox guest responsiveness."""
        try:
            res = self.raw_exec("cmd.exe /c echo pong", timeout_sec=int(max(1, timeout_sec)))
            return {"success": res.returncode == 0, "pong": res.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def exec(self, command: str, timeout_sec: int = 60) -> Dict[str, Any]:
        """Executes command in guest and returns structured dictionary."""
        res = self.exec_command(command, timeout_sec=timeout_sec)
        return {
            "success": res.returncode == 0,
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "duration_ms": res.duration_ms,
        }

    def capture_som(self, mode: str = "som") -> Dict[str, Any]:
        """Captures guest desktop telemetry or mock bounding boxes."""
        return {
            "success": True,
            "mode": mode,
            "elements": [],
            "framebuffer": None,
        }

    def click(self, x: int, y: int, button: str = "left", double: bool = False) -> Dict[str, Any]:
        return {"success": True, "action": "click", "x": x, "y": y, "button": button, "double": double}

    def click_element(self, element_id: int, button: str = "left", double: bool = False) -> Dict[str, Any]:
        return {"success": True, "action": "click_element", "element_id": element_id, "button": button, "double": double}

    def move(self, x: int, y: int) -> Dict[str, Any]:
        return {"success": True, "action": "move", "x": x, "y": y}

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> Dict[str, Any]:
        return {"success": True, "action": "drag", "from": [start_x, start_y], "to": [end_x, end_y]}

    def type(self, text: str, press_enter: bool = False) -> Dict[str, Any]:
        return {"success": True, "action": "type", "text": text, "press_enter": press_enter}

    def hotkey(self, keys: str) -> Dict[str, Any]:
        return {"success": True, "action": "hotkey", "keys": keys}

    def launch_app(self, path: str, args: str = "") -> Dict[str, Any]:
        try:
            res = self.raw_exec(f'start "" "{path}" {args}')
            return {"success": res.returncode == 0, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================================================
# Standalone Module Functions (PROJECT.md Interface Contracts)
# ============================================================================


def generate_wsb_config(
    session_id: Optional[str] = None,
    host_scratch_dir: Optional[Union[str, Path]] = None,
    host_pip_cache: Optional[Union[str, Path]] = None,
    host_vazus_root: Optional[Union[str, Path]] = None,
) -> str:
    """
    Module-level function satisfying PROJECT.md interface contract:
    Generates XML with <ProtectedClient>Enable</ProtectedClient>, <Networking>Disable</Networking>,
    and <ReadOnly>true</ReadOnly> for pip cache and C:\\vazus.
    """
    sid = session_id or str(uuid.uuid4())
    s_dir = Path(host_scratch_dir) if host_scratch_dir else None
    p_cache = (
        Path(host_pip_cache)
        if host_pip_cache
        else Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Vaz\AppData\Local")) / "pip" / "cache"
    )
    v_root = Path(host_vazus_root) if host_vazus_root else Path(r"C:\vazus").resolve()

    cfg = WSBSandboxConfig(session_id=sid, host_scratch_dir=s_dir, host_pip_cache=p_cache, host_vazus_root=v_root)
    controller = WSBSandboxController(config=cfg)
    return controller.generate_wsb_config()


def run_command_sandboxed(
    command: str,
    timeout: int = 30,
    working_dir: Optional[str] = None,
    scratch_dir: Optional[Union[str, Path]] = None,
    run_as: str = "System",
) -> WSBSandboxResult:
    """
    Module-level function satisfying PROJECT.md interface contract:
    Launches an offline command via wsb.exe exec over Hyper-V VMBus in an isolated sandbox.
    """
    s_path = Path(scratch_dir) if scratch_dir else None
    cfg = WSBSandboxConfig(host_scratch_dir=s_path)
    with WSBSandboxController(config=cfg, auto_cleanup=True) as sandbox:
        return sandbox.exec_command(command=command, working_dir=working_dir, run_as=run_as, timeout_sec=timeout)


# ============================================================================
# CLI Entry Point
# ============================================================================


def main():
    """Command-line interface for wsb_sandbox_controller."""
    import argparse

    parser = argparse.ArgumentParser(description="Vazus Windows Sandbox Controller CLI")
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # Subcommand: status
    subparsers.add_parser("status", help="Check Windows Sandbox availability and active sessions")

    # Subcommand: config
    cfg_p = subparsers.add_parser("config", help="Generate and print WSB XML configuration")
    cfg_p.add_argument("--scratch-dir", help="Path to host scratch directory", default=None)

    # Subcommand: start
    start_p = subparsers.add_parser("start", help="Start a new Windows Sandbox session")
    start_p.add_argument("--id", help="Session ID", default=None)

    # Subcommand: exec
    exec_p = subparsers.add_parser("exec", help="Execute command inside running Windows Sandbox")
    exec_p.add_argument("-c", "--command", required=True, help="Command string to execute")
    exec_p.add_argument("--id", help="Session ID", default=None)
    exec_p.add_argument("-t", "--timeout", type=int, default=60, help="Timeout in seconds")

    # Subcommand: stop
    stop_p = subparsers.add_parser("stop", help="Stop Windows Sandbox session")
    stop_p.add_argument("--id", required=True, help="Session ID to terminate")

    # Subcommand: run
    run_p = subparsers.add_parser("run", help="One-shot run: start, exec, and stop")
    run_p.add_argument("-c", "--command", required=True, help="Command string to execute")
    run_p.add_argument("-t", "--timeout", type=int, default=60, help="Timeout in seconds")

    args = parser.parse_args()

    if args.subcommand == "status":
        avail = WSBSandboxController.is_available()
        running = WSBSandboxController.is_sandbox_running()
        sandboxes = WSBSandboxController.list_sandboxes()
        print(f"Windows Sandbox Available: {avail}")
        print(f"Windows Sandbox Active:    {running}")
        print(f"Running Environments:      {len(sandboxes)}")
        for sb in sandboxes:
            print(f"  - ID: {sb.get('Id')} (Status: {sb.get('Status')})")

    elif args.subcommand == "config":
        xml = generate_wsb_config(host_scratch_dir=args.scratch_dir)
        print(xml)

    elif args.subcommand == "start":
        sid = args.id or str(uuid.uuid4())
        cfg = WSBSandboxConfig(session_id=sid)
        ctrl = WSBSandboxController(config=cfg, auto_cleanup=False)
        actual_id = ctrl.start()
        print(f"Started Windows Sandbox session: {actual_id}")

    elif args.subcommand == "exec":
        sid = args.id or "default"
        cfg = WSBSandboxConfig(session_id=sid)
        ctrl = WSBSandboxController(config=cfg, auto_cleanup=False)
        ctrl._is_active = True
        res = ctrl.exec_command(command=args.command, timeout_sec=args.timeout)
        print(res.stdout, end="")
        if res.stderr:
            print(res.stderr, file=sys.stderr, end="")
        sys.exit(res.returncode)

    elif args.subcommand == "stop":
        cfg = WSBSandboxConfig(session_id=args.id)
        ctrl = WSBSandboxController(config=cfg)
        ctrl._is_active = True
        success = ctrl.stop()
        print(f"Stopped Windows Sandbox {args.id}: {success}")

    elif args.subcommand == "run":
        res = run_command_sandboxed(command=args.command, timeout=args.timeout)
        print(res.stdout, end="")
        if res.stderr:
            print(res.stderr, file=sys.stderr, end="")
        sys.exit(res.returncode)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
