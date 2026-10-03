"""
Root alias forwarding to vazus_core.sandbox.wsb_sandbox_controller.
Preserves backward compatibility with root-level imports.
"""

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
