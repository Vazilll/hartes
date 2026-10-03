#!/usr/bin/env python3
"""
Unit tests for Declarative Subagent Framework & Hook Lifecycle in vazus_core.engine.subagent_framework.
Replaces legacy placeholder dummy tests with comprehensive structural and functional assertions.
"""

import pytest
from vazus_core.engine.subagent_framework import (
    SubagentContext,
    SubagentHookRegistry,
    DeclarativeSubagentEngine,
)


def test_subagent_context_initialization():
    """Verify SubagentContext defaults and state mutations."""
    ctx = SubagentContext(
        subagent_name="research_worker",
        task_id="task-001",
        prompt="Analyze codebase AST"
    )
    assert ctx.subagent_name == "research_worker"
    assert ctx.task_id == "task-001"
    assert ctx.prompt == "Analyze codebase AST"
    assert ctx.success is True
    assert ctx.error is None
    assert isinstance(ctx.params, dict)
    assert isinstance(ctx.state, dict)
    assert isinstance(ctx.logs, list)


def test_subagent_hook_registry_lifecycle():
    """Verify registration and execution order of subagent lifecycle hooks."""
    registry = SubagentHookRegistry()
    events = []

    def on_start(ctx):
        events.append(f"start:{ctx.task_id}")

    def on_complete(ctx):
        events.append(f"complete:{ctx.task_id}")

    registry.register_on_start(on_start)
    registry.register_on_complete(on_complete)

    ctx = SubagentContext(subagent_name="tester", task_id="t-100", prompt="test")
    for hook in registry._on_start_hooks:
        hook(ctx)
    for hook in registry._on_complete_hooks:
        hook(ctx)

    assert events == ["start:t-100", "complete:t-100"]


def test_declarative_subagent_engine_creation():
    """Verify DeclarativeSubagentEngine instantiates with clean registries."""
    engine = DeclarativeSubagentEngine()
    assert engine is not None
    assert hasattr(engine, "hooks")
    assert isinstance(engine.hooks, SubagentHookRegistry)
