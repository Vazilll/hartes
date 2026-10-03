"""Sandbox and low-level process containment module."""

from vazus_core.sandbox.time_travel_sandbox import (
    StepExecutionResult,
    StepSnapshot,
    TimeTravelSandbox,
)
from vazus_core.sandbox.win32_job_guard import Win32JobSandbox
from vazus_core.sandbox.wsb_sandbox_controller import (
    WSBSandboxConfig,
    WSBSandboxController,
    WSBSandboxResult,
    generate_wsb_config,
    run_command_sandboxed,
)

__all__ = [
    "StepExecutionResult",
    "StepSnapshot",
    "TimeTravelSandbox",
    "Win32JobSandbox",
    "WSBSandboxController",
    "WSBSandboxConfig",
    "WSBSandboxResult",
    "generate_wsb_config",
    "run_command_sandboxed",
]

