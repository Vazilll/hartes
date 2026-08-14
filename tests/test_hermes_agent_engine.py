"""
tests/test_hermes_agent_engine.py — Unit tests for vazus_core.hermes_agent_engine module.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from vazus_core.subagent_framework import SubagentContext
from vazus_core.hermes_agent_engine import (
    HermesToolRegistry,
    HermesXMLParser,
    HermesAgentEngine,
)


def test_hermes_tool_registry():
    registry = HermesToolRegistry()
    registry.register_tool(
        name="calculate_sum",
        description="Calculates sum of two integers",
        parameters={"properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}},
        handler=lambda a, b: a + b
    )

    xml = registry.get_tools_xml()
    assert "<tools>" in xml
    assert "calculate_sum" in xml
    assert registry.get_handler("calculate_sum")(5, 10) == 15


def test_hermes_xml_parser():
    sample_output = """<scratchpad>
Need to calculate sum of 40 and 2.
</scratchpad>
<tool_call>
{"name": "calculate_sum", "arguments": {"a": 40, "b": 2}}
</tool_call>"""

    parsed = HermesXMLParser.parse_output(sample_output)
    assert parsed.has_tool_call is True
    assert parsed.thinking == "Need to calculate sum of 40 and 2."
    assert parsed.tool_call.name == "calculate_sum"
    assert parsed.tool_call.arguments == {"a": 40, "b": 2}


def test_hermes_agent_engine_execution():
    registry = HermesToolRegistry()
    registry.register_tool(
        name="get_system_info",
        description="Returns system status",
        parameters={},
        handler=lambda: {"status": "ONLINE", "version": "4.0"}
    )

    engine = HermesAgentEngine(registry=registry)
    ctx = SubagentContext(
        subagent_name="hermes_test_agent",
        task_id="task_hermes_01",
        prompt="Check system status"
    )

    sample_output = """<thinking>Checking system state...</thinking>
<tool_call>
{"name": "get_system_info", "arguments": {}}
</tool_call>"""

    parsed = engine.execute_step(ctx, sample_output)
    assert parsed.has_tool_call is True
    assert ctx.results.get("tool_response_get_system_info") == {"status": "ONLINE", "version": "4.0"}
