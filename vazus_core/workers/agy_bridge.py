"""
vazus_core/workers/agy_bridge.py — Antigravity (AGY) CLI Headless Subagent Bridge.

Leverages the local `agy.exe` runtime to execute external tasks, code generation,
and deep reasoning using Google Antigravity quotas (Gemini 3.1 Pro, Flash, Claude Sonnet).
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("vazus.agy_bridge")

DEFAULT_AGY_PATH = Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Vaz\AppData\Local")) / "agy" / "bin" / "agy.exe"


@dataclass
class AgyExecutionResult:
    success: bool
    output_text: str
    parsed_json: Optional[Dict[str, Any]] = None
    exit_code: int = 0
    latency_ms: float = 0.0
    model: str = "gemini-3.1-pro-high"
    error: Optional[str] = None


class AgyBridge:
    """
    Subagent bridge to the local Antigravity (AGY) CLI.
    Runs headless prompts with automatic tool approval and quota consumption.
    """

    def __init__(self, agy_path: Optional[Path] = None):
        self.agy_path = agy_path or DEFAULT_AGY_PATH
        if not self.agy_path.exists():
            # Check PATH
            cmd = subprocess.run(["where", "agy"], capture_output=True, text=True)
            if cmd.returncode == 0:
                self.agy_path = Path(cmd.stdout.strip().splitlines()[0])

    def is_available(self) -> bool:
        return self.agy_path.exists()

    async def execute_task_async(
        self,
        prompt: str,
        model: str = "gemini-3.1-pro-high",
        effort: str = "high",
        timeout: float = 120.0,
        cwd: Optional[Path] = None,
        dangerously_skip_permissions: bool = True,
    ) -> AgyExecutionResult:
        """
        Executes a prompt non-interactively via `agy.exe -p` and captures output.
        """
        if not self.is_available():
            return AgyExecutionResult(
                success=False,
                output_text="",
                error=f"agy.exe not found at {self.agy_path}",
                exit_code=-1,
                model=model,
            )

        cmd = [
            str(self.agy_path),
            "--print",
            prompt,
            "--model",
            model,
            "--effort",
            effort,
            "--output-format",
            "json",
        ]
        if dangerously_skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        t0 = asyncio.get_event_loop().time()
        work_dir = str(cwd) if cwd else r"C:\vazus"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            elapsed_ms = (asyncio.get_event_loop().time() - t0) * 1000

            out_text = stdout.decode("utf-8", errors="replace").strip()
            err_text = stderr.decode("utf-8", errors="replace").strip()

            parsed = None
            if out_text.startswith("{") or out_text.startswith("["):
                try:
                    parsed = json.loads(out_text)
                except Exception:
                    pass

            return AgyExecutionResult(
                success=(proc.returncode == 0),
                output_text=out_text,
                parsed_json=parsed,
                exit_code=proc.returncode or 0,
                latency_ms=elapsed_ms,
                model=model,
                error=err_text if proc.returncode != 0 else None,
            )
        except asyncio.TimeoutError:
            return AgyExecutionResult(
                success=False,
                output_text="",
                error=f"Timeout after {timeout}s",
                exit_code=-2,
                model=model,
            )
        except Exception as e:
            return AgyExecutionResult(
                success=False,
                output_text="",
                error=str(e),
                exit_code=-3,
                model=model,
            )


def main():
    bridge = AgyBridge()
    print(f"[AgyBridge] Available: {bridge.is_available()} at {bridge.agy_path}")


if __name__ == "__main__":
    main()
