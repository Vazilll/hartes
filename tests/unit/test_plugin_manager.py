"""
tests/test_plugin_manager.py — Tests for PluginManager and Hook Dispatcher.
"""

from vazus_core.plugins.plugin_manager import PluginManager


def test_plugin_manager_hook_dispatch():
    manager = PluginManager(plugin_dirs=[])

    called = []
    def on_pre_tool(tool_name: str):
        called.append(tool_name)
        return {"decision": "allow"}

    manager.register_hook_callback("pre_tool", on_pre_tool)
    res = manager.dispatch_hook("pre_tool", tool_name="ast_prune")

    assert len(called) == 1
    assert called[0] == "ast_prune"
    assert res[0]["decision"] == "allow"
