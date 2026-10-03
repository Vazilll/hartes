"""Vazus FastMCP Sandbox Control & Autonomous Testbed Server.

Standardized MCP protocol for 100% isolated Windows Sandbox orchestration:
- Zero-Interference GUI Automation: mouse clicks, drags, key typing, hotkeys in guest desktop.
- High-Resolution Screen Capture: Set-of-Mark (SoM) and RapidOCR visual feedback loops.
- In-Guest CLI Execution: Direct PowerShell execution and process lifecycle management.
- Testbed Harness: Automated app deployment, network checks, and AI-in-guest verification.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Literal

from fastmcp import FastMCP

# Ensure vazus package is in path
sys.path.insert(0, r"C:\vazus")
from vazus_core.sandbox.wsb_sandbox_controller import WSBSandboxController as SandboxController

mcp = FastMCP("vazus-sandbox")
_controller = SandboxController()


@mcp.tool()
def sandbox_launch(
    force_restart: bool = False,
    timeout_sec: int = 45
) -> Dict[str, Any]:
    """Launch or attach to an isolated Windows Sandbox instance with active bridge and internet."""
    try:
        success = _controller.launch(force_restart=force_restart, timeout_sec=timeout_sec)
        return {
            "success": success,
            "status": "ready",
            "message": "Windows Sandbox launched and guest agent handshake confirmed.",
            "is_running": _controller.is_running()
        }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "error": str(e)
        }


@mcp.tool()
def sandbox_status() -> Dict[str, Any]:
    """Get current status of Windows Sandbox and guest agent."""
    running = _controller.is_running()
    ready = _controller.ready_file.exists()
    pong = None
    if running and ready:
        try:
            pong = _controller.ping(timeout_sec=2.0)
        except Exception:
            pass
    return {
        "success": True,
        "running": running,
        "ready": ready,
        "responsive": pong is not None and pong.get("success", False),
        "details": pong
    }


@mcp.tool()
def sandbox_capture(mode: str = "som") -> Dict[str, Any]:
    """Capture the Sandbox guest desktop framebuffer with Set-of-Mark & RapidOCR telemetry.
    
    Args:
        mode: 'som' (draw numbered bounding boxes and return element index) or 'raw' (plain screenshot).
    """
    try:
        return _controller.capture_som(mode=mode)
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def sandbox_click_text(
    query: str,
    button: str = "left",
    double: bool = False
) -> Dict[str, Any]:
    """Find a UI element containing the text query via OCR in the guest desktop and click it."""
    try:
        som = _controller.capture_som(mode="som")
        elements = som.get("elements", [])
        matched = [el for el in elements if query.lower() in el["text"].lower()]
        if not matched:
            return {
                "success": False,
                "error": f"No element matching text '{query}' found on guest screen.",
                "available_texts": [el["text"] for el in elements[:15]]
            }
        target = matched[0]
        cx, cy = target["center"]
        click_res = _controller.click(cx, cy, button=button, double=double)
        return {
            "success": True,
            "matched_text": target["text"],
            "element_id": target["id"],
            "coordinates": [cx, cy],
            "click_result": click_res
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def sandbox_action(
    action: Literal["click", "move", "drag", "type", "hotkey", "exec", "launch_app", "capture"],
    x: Optional[int] = None,
    y: Optional[int] = None,
    start_x: Optional[int] = None,
    start_y: Optional[int] = None,
    end_x: Optional[int] = None,
    end_y: Optional[int] = None,
    element_id: Optional[int] = None,
    button: str = "left",
    double: bool = False,
    text: Optional[str] = None,
    press_enter: bool = False,
    keys: Optional[str] = None,
    command: Optional[str] = None,
    path: Optional[str] = None,
    args: str = "",
    timeout: int = 60
) -> Dict[str, Any]:
    """Execute a unified action inside Windows Sandbox with zero host interference.
    
    Actions:
    - 'click': Click at (x, y) or by Set-of-Mark element_id
    - 'move': Move cursor to (x, y)
    - 'drag': Drag from (start_x, start_y) to (end_x, end_y)
    - 'type': Enter text into active window
    - 'hotkey': Press shortcut (e.g. 'win+r', 'ctrl+v', 'alt+f4', 'enter')
    - 'exec': Run PowerShell command in guest and return stdout/stderr
    - 'launch_app': Start executable in guest
    - 'capture': Capture screen with SoM/OCR
    """
    try:
        if action == "click":
            if element_id is not None:
                return _controller.click_element(element_id, button=button, double=double)
            elif x is not None and y is not None:
                return _controller.click(x, y, button=button, double=double)
            else:
                return {"success": False, "error": "Must specify either element_id or (x, y)"}
        
        elif action == "move":
            if x is None or y is None:
                return {"success": False, "error": "Must specify (x, y)"}
            return _controller.move(x, y)
            
        elif action == "drag":
            if any(v is None for v in [start_x, start_y, end_x, end_y]):
                return {"success": False, "error": "Must specify start_x, start_y, end_x, end_y"}
            return _controller.drag(start_x, start_y, end_x, end_y)
            
        elif action == "type":
            if not text:
                return {"success": False, "error": "Must provide text to type"}
            return _controller.type(text, press_enter=press_enter)
            
        elif action == "hotkey":
            if not keys:
                return {"success": False, "error": "Must provide keys (e.g. 'win+r')"}
            return _controller.hotkey(keys)
            
        elif action == "exec":
            if not command:
                return {"success": False, "error": "Must provide PowerShell command to exec"}
            return _controller.exec(command, timeout_sec=timeout)
            
        elif action == "launch_app":
            if not path:
                return {"success": False, "error": "Must provide application path to launch"}
            return _controller.launch_app(path, args=args)
            
        elif action == "capture":
            return _controller.capture_som(mode="som")
            
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def sandbox_terminate() -> Dict[str, Any]:
    """Terminate the active Windows Sandbox instance."""
    terminated = _controller.terminate()
    return {"success": True, "terminated": terminated}


if __name__ == "__main__":
    mcp.run()
