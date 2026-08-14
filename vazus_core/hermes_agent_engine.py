"""
vazus_core.hermes_agent_engine — Nous Hermes 3 Open-Source Agent Protocol Engine.
Implements Nous Hermes 3 XML tag protocols (<tools>, <tool_call>, <tool_response>, <thinking>, <scratchpad>),
dynamic tool schema generation, high-speed XML parsing, and multi-turn agentic execution loops.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Union

from vazus_core.engine.utils import fast_json_dumps, fast_json_loads
from vazus_core.engine.subagent_framework import SubagentContext

logger = logging.getLogger("HermesAgentEngine")


@dataclass
class HermesToolCall:
    """Represents an extracted Hermes 3 tool call."""
    name: str
    arguments: Dict[str, Any]
    raw_xml: str


@dataclass
class HermesParsedOutput:
    """Parsed output of a Hermes 3 model execution step."""
    thinking: str
    tool_call: Optional[HermesToolCall]
    has_tool_call: bool
    clean_text: str


class HermesToolRegistry:
    """Converts Python functions or tool dicts into Hermes 3 compliant <tools> JSON schemas."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: List[Dict[str, Any]] = []

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable
    ):
        """Registers a Python handler with OpenAI/Hermes compliant JSON schema."""
        self._tools[name] = handler
        self._schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters
            }
        })

    def get_tools_xml(self) -> str:
        """Formats all registered tools into Hermes 3 <tools> XML block."""
        return f"<tools>\n{fast_json_dumps(self._schemas)}\n</tools>"

    def get_handler(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)


class HermesXMLParser:
    """High-speed C/Rust regex parser for Nous Hermes 3 XML tags."""

    TOOL_CALL_REGEX = re.compile(r"<tool_call>\s*({.*?})\s*</tool_call>", re.DOTALL)
    THINKING_REGEX = re.compile(
        r"<(?:thinking|scratchpad|plan|reflection)>(.*?)</(?:thinking|scratchpad|plan|reflection)>",
        re.DOTALL
    )

    @classmethod
    def parse_output(cls, model_output: str) -> HermesParsedOutput:
        """Extracts <thinking> monologue and <tool_call> JSON payload from model output."""
        thinking_matches = cls.THINKING_REGEX.findall(model_output)
        thinking_text = "\n---\n".join(m.strip() for m in thinking_matches) if thinking_matches else ""

        tool_call_match = cls.TOOL_CALL_REGEX.search(model_output)
        tool_call_obj = None

        if tool_call_match:
            raw_xml = tool_call_match.group(0)
            raw_json = tool_call_match.group(1).strip()
            try:
                data = fast_json_loads(raw_json)
                if isinstance(data, dict) and "name" in data:
                    tool_call_obj = HermesToolCall(
                        name=data["name"],
                        arguments=data.get("arguments", {}),
                        raw_xml=raw_xml
                    )
            except Exception as e:
                logger.warning(f"[HermesParser] Failed to parse tool_call JSON: {e}")

        # Strip XML tags to produce clean human-readable narrative text
        clean_text = cls.TOOL_CALL_REGEX.sub("", model_output)
        clean_text = cls.THINKING_REGEX.sub("", clean_text).strip()

        return HermesParsedOutput(
            thinking=thinking_text,
            tool_call=tool_call_obj,
            has_tool_call=tool_call_obj is not None,
            clean_text=clean_text
        )

    @staticmethod
    def format_tool_response(tool_name: str, result: Any) -> str:
        """Formats environment tool output into Hermes 3 <tool_response> XML tag."""
        payload = {
            "name": tool_name,
            "content": result
        }
        return f"<tool_response>\n{fast_json_dumps(payload)}\n</tool_response>"


class HermesAgentEngine:
    """
    Nous Hermes 3 Agent Execution Loop Manager.
    Formats system prompts, manages multi-turn tool calling, and executes tool actions.
    """

    def __init__(self, registry: Optional[HermesToolRegistry] = None):
        self.registry = registry or HermesToolRegistry()
        self.parser = HermesXMLParser()

    def build_system_prompt(self, base_instructions: str) -> str:
        """Builds system prompt with Hermes 3 <tools> XML definitions."""
        tools_xml = self.registry.get_tools_xml()
        return (
            f"{base_instructions}\n\n"
            f"You are a function calling AI agent. You have access to the following tools:\n"
            f"{tools_xml}\n\n"
            f"To call a tool, wrap JSON call inside <tool_call> tags:\n"
            f'<tool_call>\n{{"name": "tool_name", "arguments": {{...}}}}\n</tool_call>\n\n'
            f"Use <scratchpad> or <thinking> tags to plan multi-step execution before calling tools."
        )

    def execute_step(self, ctx: SubagentContext, model_output: str) -> HermesParsedOutput:
        """Processes a single turn of Hermes model output and executes tool calls if present."""
        parsed = self.parser.parse_output(model_output)

        if parsed.thinking:
            ctx.logs.append(f"[Hermes Thinking] {parsed.thinking[:200]}...")

        if parsed.has_tool_call and parsed.tool_call:
            tool_name = parsed.tool_call.name
            args = parsed.tool_call.arguments
            ctx.logs.append(f"[Hermes Tool Call] {tool_name}({args})")

            handler = self.registry.get_handler(tool_name)
            if handler:
                try:
                    tool_result = handler(**args)
                    formatted_resp = self.parser.format_tool_response(tool_name, tool_result)
                    ctx.results[f"tool_response_{tool_name}"] = tool_result
                    ctx.logs.append(f"[Hermes Tool Response] {tool_name} returned success.")
                except Exception as e:
                    err_msg = f"Tool execution error: {e}"
                    ctx.results[f"tool_error_{tool_name}"] = err_msg
                    ctx.logs.append(f"[Hermes Tool Error] {tool_name} failed: {e}")
            else:
                ctx.logs.append(f"[Hermes Tool Error] Handler for '{tool_name}' not registered.")

        return parsed
