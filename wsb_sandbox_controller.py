"""Backward compatibility forwarder for wsb_sandbox_controller."""
from vazus_core.sandbox.wsb_sandbox_controller import (
    WSBSandboxController,
    WSBSandboxConfig,
    WSBSandboxResult,
    generate_wsb_config,
    run_command_sandboxed,
)

__all__ = [
    "WSBSandboxController",
    "WSBSandboxConfig",
    "WSBSandboxResult",
    "generate_wsb_config",
    "run_command_sandboxed",
]
