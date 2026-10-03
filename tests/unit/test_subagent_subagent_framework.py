"""
tests/test_subagent_framework.py - Unit tests for vazus_core.subagent_framework module.
"""

import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from vazus_core.subagent_framework import (
    DeclarativeSubagentTemplate,
    DeclarativeSubagentEngine,
    SubagentTemplateRegistry,
    SubagentHookRegistry,
    SubagentContext
)


def test_declarative_subagent_execution_async():
    async def _test():
        registry = SubagentTemplateRegistry()
        hooks = SubagentHookRegistry()
        
        start_called = []
        complete_called = []
        
        hooks.register_on_start(lambda ctx: start_called.append(ctx.subagent_name))
        hooks.register_on_complete(lambda ctx: complete_called.append(ctx.subagent_name))
        
        async def mock_async_executor(ctx: SubagentContext):
            await asyncio.sleep(0.001)
            return {"status": "analyzed", "metrics": [1, 2, 3]}
            
        def mock_verifier(ctx: SubagentContext):
            return ctx.results.get("status") == "analyzed"
            
        template = DeclarativeSubagentTemplate(
            name="test_code_researcher",
            description="Analyzes code structures declaratively",
            system_prompt="You are a code analysis subagent.",
            executor_fn=mock_async_executor,
            verifier_fn=mock_verifier
        )
        registry.register(template)
        
        engine = DeclarativeSubagentEngine(registry=registry, hooks=hooks)
        ctx = await engine.run_subagent(
            subagent_name="test_code_researcher",
            prompt="Analyze AST topology of vazus_core"
        )
        
        assert ctx.success is True
        assert ctx.results["status"] == "analyzed"
        assert ctx.results["metrics"] == [1, 2, 3]
        assert "test_code_researcher" in start_called
        assert "test_code_researcher" in complete_called

    asyncio.run(_test())


def test_declarative_subagent_execution_sync_wrapper():
    registry = SubagentTemplateRegistry()
    hooks = SubagentHookRegistry()
    
    start_called = []
    complete_called = []
    
    hooks.register_on_start(lambda ctx: start_called.append(ctx.subagent_name))
    hooks.register_on_complete(lambda ctx: complete_called.append(ctx.subagent_name))
    
    def mock_executor(ctx: SubagentContext):
        return {"status": "analyzed", "metrics": [1, 2, 3]}
        
    template = DeclarativeSubagentTemplate(
        name="test_code_researcher_sync",
        description="Analyzes code structures synchronously",
        system_prompt="You are a code analysis subagent.",
        executor_fn=mock_executor
    )
    registry.register(template)
    
    engine = DeclarativeSubagentEngine(registry=registry, hooks=hooks)
    ctx = engine.run_subagent_sync(
        subagent_name="test_code_researcher_sync",
        prompt="Analyze AST topology of vazus_core"
    )
    
    assert ctx.success is True
    assert ctx.results["status"] == "analyzed"
    assert ctx.results["metrics"] == [1, 2, 3]
    assert "test_code_researcher_sync" in start_called
    assert "test_code_researcher_sync" in complete_called


def test_unregistered_subagent_handling():
    async def _test():
        engine = DeclarativeSubagentEngine()
        ctx = await engine.run_subagent(
            subagent_name="unknown_agent",
            prompt="Do something"
        )
        assert ctx.success is False
        assert "not registered" in ctx.error

    asyncio.run(_test())

