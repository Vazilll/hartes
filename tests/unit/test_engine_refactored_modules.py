"""
Unit tests for Worker M1A refactored engine modules:
1. dialectical_synthesizer.py
2. dynamic_skill_dispatcher.py
3. graphify_engine.py
4. reasoning_effort_controller.py
5. rlm_driver.py
6. self_healing_compiler.py
7. supergraph_bridge.py
8. supergraph_linker.py
9. supergraph_master_orchestrator.py
10. system_discovery_engine.py
11. unified_reasoning_pipeline.py
"""

import pytest
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, patch

from vazus_core.engine.dialectical_synthesizer import DialecticalSynthesizer
from vazus_core.engine.dynamic_skill_dispatcher import (
    DynamicSkillDispatcher,
    SkillIntentParser,
    TranscriptLoopGuardrails,
    SkillMetadata,
)
from vazus_core.engine.graphify_engine import GraphifyEngine, GraphifyASTVisitor
from vazus_core.engine.reasoning_effort_controller import ReasoningEffortController, ExecutionPolicyController
from vazus_core.engine.rlm_driver import RLMDriver
from vazus_core.engine.self_healing_compiler import SelfHealingCompiler
from vazus_core.engine.supergraph_bridge import SuperGraphBridge, UnifiedSuperGraphBridge
from vazus_core.engine.supergraph_linker import (
    SuperGraphLinker,
    calculate_cosine_similarity,
    calculate_fts_similarity,
    calculate_structural_similarity,
    calculate_provenance_similarity,
)
from vazus_core.engine.supergraph_master_orchestrator import SuperGraphMasterOrchestrator
from vazus_core.engine.system_discovery_engine import SystemDiscoveryEngine
from vazus_core.engine.unified_reasoning_pipeline import UnifiedReasoningPipeline


import asyncio

def test_dialectical_synthesizer_flow():
    async def _test():
        synth = DialecticalSynthesizer(depth=5)
        with patch.object(synth, "_generate_thesis", new_callable=AsyncMock) as mock_thesis, \
             patch.object(synth, "_generate_antithesis", new_callable=AsyncMock) as mock_anti, \
             patch.object(synth, "_generate_synthesis", new_callable=AsyncMock) as mock_syn:
            mock_thesis.return_value = "def add(a: int, b: int) -> int:\n    return a + b\n"
            mock_anti.return_value = "Critique: Looks good, test edge cases."
            mock_syn.return_value = "def add(a: int, b: int) -> int:\n    return a + b\n"

            res = await synth.synthesize("Implement add function")
            assert res["status"] == "SUCCESS"
            assert "def add" in res["final_synthesized_code"]

    asyncio.run(_test())


def test_dynamic_skill_dispatcher_guardrails():
    ok, msg = TranscriptLoopGuardrails.validate_view_file_path("screenshot.png")
    assert not ok
    assert "GUARDRAIL BLOCKED" in msg

    ok_txt, _ = TranscriptLoopGuardrails.validate_view_file_path("code.py")
    assert ok_txt


def test_dynamic_skill_dispatcher_init_and_intent():
    dispatcher = DynamicSkillDispatcher(
        prompt="analyze bigquery sql data",
        max_skills=2,
        effort="medium",
        prune_mode="summary",
        auto_index=False
    )
    assert dispatcher.max_skills == 2
    assert dispatcher.effort == "medium"


def test_graphify_engine_memory_mode(tmp_path):
    db_file = str(tmp_path / "graph.db")
    engine = GraphifyEngine(db_path=db_file, workspace_root=str(tmp_path), shm_bus_name=None)
    
    sample_code = """
def calculate_metrics(x: int) -> int:
    return x * 2

class MetricProcessor:
    def process(self):
        return calculate_metrics(10)
"""
    py_file = tmp_path / "sample.py"
    py_file.write_text(sample_code, encoding="utf-8")
    
    res = engine.index_file_ast("sample.py", source_code=sample_code)
    assert res["nodes"] >= 3
    assert res["edges"] >= 2
    
    ctx = engine.get_compact_subgraph_context("calculate_metrics")
    assert "GRAPHIFY TOPOLOGY" in ctx


def test_reasoning_effort_controller():
    cfg_low = ReasoningEffortController.get_config("low")
    assert cfg_low["level"] == "low"
    assert cfg_low["smt_z3_depth"] == 5

    cfg_ultra = ExecutionPolicyController.get_config("ultra")
    assert cfg_ultra["level"] == "ultra"
    assert cfg_ultra["smt_z3_depth"] == 30


def test_rlm_driver_execution():
    driver = RLMDriver(
        llm_engine_call=lambda msgs: "```repl\nanswer['content'] = 'Found ' + str(len(context))\nanswer['ready'] = True\n```",
        max_iterations=3
    )
    res = driver.run("Count items", long_context="hello world test")
    assert res["status"] == "SUCCESS"
    assert res["final_answer"] == "Found 16"


def test_self_healing_compiler_extract():
    compiler = SelfHealingCompiler()
    raw = "Here is the fix:\n```python\ndef test():\n    return 42\n```\nDone."
    code = compiler._extract_code(raw)
    assert code == "def test():\n    return 42"


def test_supergraph_bridge_sync(tmp_path):
    db_file = str(tmp_path / "bridge.db")
    bridge = SuperGraphBridge(db_path=db_file, workspace_root=str(tmp_path))
    
    ok_node = bridge.sync_ast_node(
        node_id="ast:test_func",
        name="test_func",
        node_type="Function",
        file_path="test.py",
        description="A test function",
        embedding_768d=[0.1] * 768
    )
    assert ok_node is True

    ok_edge = bridge.sync_call_edge("ast:caller", "ast:test_func", relation="CALLS")
    assert ok_edge is True

    lineage = bridge.query_symbol_lineage("ast:test_func")
    assert lineage["in_degree"] == 1


def test_supergraph_linker_metrics():
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [1.0, 0.0, 0.0]
    cos_sim = calculate_cosine_similarity(vec_a, vec_b)
    assert abs(cos_sim - 1.0) < 1e-4

    fts_sim = calculate_fts_similarity("hello world search", "search world token")
    assert fts_sim > 0.0


def test_system_discovery_engine(tmp_path):
    py_file = tmp_path / "mod_a.py"
    py_file.write_text("def my_func():\n    '''Performs data calculation.'''\n    return 123\n", encoding="utf-8")
    
    engine = SystemDiscoveryEngine(workspace_root=tmp_path)
    scan_res = engine.scan_codebase()
    assert scan_res["total_files"] == 1
    assert scan_res["total_defined_symbols"] >= 1

    caps = engine.search_capabilities("data calculation")
    assert len(caps) >= 1
    assert caps[0]["name"] == "my_func"


def test_unified_reasoning_pipeline_init():
    pipeline = UnifiedReasoningPipeline(effort_level="low")
    assert pipeline.effort_level == "low"
    assert pipeline.smt_verifier.depth == 5
