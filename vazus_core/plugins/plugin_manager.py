"""
vazus_core.plugins.plugin_manager — Antigravity Plugin & Extension Lifecycle Manager.
Discovers, loads, validates, and dispatches plugin extensions, custom hooks, and MCP servers.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("PluginManager")


@dataclass
class PluginManifest:
    """Represents a loaded plugin metadata and capabilities."""

    name: str
    version: str
    description: str
    author: str
    hooks: Dict[str, str] = field(default_factory=dict)
    mcp_servers: List[str] = field(default_factory=list)
    enabled: bool = True


class PluginManager:
    """
    Manages Antigravity plugins, extensions, and lifecycle hooks.
    """

    DEFAULT_PLUGIN_DIRS = [
        Path(r"C:\vazus\plugins"),
        Path(r"C:\Users\Vaz\.gemini\config\plugins"),
    ]

    def __init__(self, plugin_dirs: Optional[List[Path]] = None):
        self.plugin_dirs = plugin_dirs or self.DEFAULT_PLUGIN_DIRS
        self.plugins: Dict[str, PluginManifest] = {}
        self.hook_registry: Dict[str, List[Callable]] = {
            "pre_tool": [],
            "post_tool": [],
            "on_startup": [],
            "on_error": [],
        }
        self.discover_plugins()

    def discover_plugins(self) -> int:
        """Scans plugin directories and registers valid plugin manifests."""
        count = 0
        for p_dir in self.plugin_dirs:
            if not p_dir.exists():
                continue
            for item in p_dir.iterdir():
                if item.is_dir():
                    manifest_file = item / "plugin.json"
                    if manifest_file.exists():
                        try:
                            data = json.loads(manifest_file.read_text(encoding="utf-8"))
                            manifest = PluginManifest(
                                name=data.get("name", item.name),
                                version=data.get("version", "1.0.0"),
                                description=data.get("description", ""),
                                author=data.get("author", "vazus"),
                                hooks=data.get("hooks", {}),
                                mcp_servers=data.get("mcp_servers", []),
                            )
                            self.plugins[manifest.name] = manifest
                            count += 1
                        except Exception as e:
                            logger.error("Failed to load plugin manifest %s: %s", manifest_file, e)
        return count

    def register_hook_callback(self, event_name: str, callback: Callable) -> None:
        """Registers an in-process hook callback."""
        if event_name not in self.hook_registry:
            self.hook_registry[event_name] = []
        self.hook_registry[event_name].append(callback)

    def dispatch_hook(self, event_name: str, **kwargs) -> List[Any]:
        """Dispatches an event to all registered hook callbacks."""
        results = []
        callbacks = self.hook_registry.get(event_name, [])
        for cb in callbacks:
            try:
                res = cb(**kwargs)
                results.append(res)
            except Exception as e:
                logger.error("Hook %s callback error: %s", event_name, e)
                results.append({"error": str(e)})
        return results


# Global singleton plugin manager
plugin_manager = PluginManager()

__all__ = [
    "PluginManifest",
    "PluginManager",
    "plugin_manager",
]
