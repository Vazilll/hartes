"""
vazus_core.workers.wsb_sandbox_controller
=========================================
Re-export alias forwarding to the canonical sandbox controller:
vazus_core.sandbox.wsb_sandbox_controller.
"""

from vazus_core.sandbox.wsb_sandbox_controller import (
    WSBSandboxConfig,
    WSBSandboxResult,
    WSBSandboxController,
)

# Backward-compatibility aliases
SandboxResult = WSBSandboxResult
WindowsSandboxController = WSBSandboxController

__all__ = [
    "WSBSandboxConfig",
    "WSBSandboxResult",
    "WSBSandboxController",
    "SandboxResult",
    "WindowsSandboxController",
]
