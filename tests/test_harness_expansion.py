import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import labs.harness_expansion as he


def test_master_registry_list_and_health_checks():
    bps = he.list_blueprints()
    assert len(bps) == 7
    
    health = he.execute_all_blueprint_health_checks()
    assert health["total_blueprints"] == 7
    for harness_id, status_dict in health["health_checks"].items():
        assert status_dict["status"] == "OPERATIONAL"


def test_nous_hermes_blueprint():
    bp = he.get_blueprint("nous_hermes")
    meta = bp.get_metadata()
    assert meta["harness_id"] == "nous_hermes"

    # Test format tool calls
    xml_str = bp.format_tool_calls([{"name": "read_file", "arguments": {"path": "main.py"}}])
    assert "<tool_call>" in xml_str
    assert "<name>read_file</name>" in xml_str

    # Test parse xml response
    parsed = bp.parse_xml_response(xml_str)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "read_file"
    assert parsed[0]["arguments"]["path"] == "main.py"

    # Test skill sync
    skills = bp.sync_skills()
    assert skills["status"] == "SUCCESS"

    # Test execute agent step
    step = bp.execute_agent_step("Run tool test", context="test")
    assert step["status"] == "SUCCESS"


def test_deepmind_odr_blueprint():
    bp = he.get_blueprint("deepmind_odr")
    meta = bp.get_metadata()
    assert meta["harness_id"] == "deepmind_odr"

    res = bp.run_research("Quantum Computing Overview", dry_run=True)
    assert res["status"] == "SUCCESS"

    pruned = bp.prune_research_context("def calculate():\n    pass")
    assert "original_length" in pruned


def test_anthropic_thinking_blueprint():
    bp = he.get_blueprint("anthropic_thinking")
    meta = bp.get_metadata()
    assert meta["harness_id"] == "anthropic_thinking"

    budget = bp.compute_thinking_budget("high")
    assert budget["thinking_budget"] > 0

    model_res = bp.select_model("code reasoning", effort_level="high")
    assert "selected_model" in model_res

    step = bp.execute_reasoning_step("Analyze data structure", effort="medium")
    assert step["status"] == "SUCCESS"


def test_mit_rlm_blueprint():
    bp = he.get_blueprint("mit_rlm")
    meta = bp.get_metadata()
    assert meta["harness_id"] == "mit_rlm"

    hw = bp.profile_hardware_execution()
    assert hw["status"] == "OPERATIONAL"

    exec_res = bp.execute_code_in_repl("a = 10\nb = 20\nprint(a + b)")
    assert "30" in exec_res["stdout"]


def test_openai_swarm_jury_blueprint():
    bp = he.get_blueprint("openai_swarm_jury")
    meta = bp.get_metadata()
    assert meta["harness_id"] == "openai_swarm_jury"

    vote_res = bp.convene_jury_vote(
        proposal_id="prop_test_001",
        file_path="src/module.py",
        code_content="def hello(): return 'world'",
        agent_votes=[{"agent": "planner", "verdict": "PASS"}],
    )
    assert vote_res["proposal_id"] == "prop_test_001"
    assert "approved" in vote_res

    routed = bp.route_subagent_task("code", {"task": "refactor"})
    assert "status" in routed


def test_graphify_ast_blueprint():
    bp = he.get_blueprint("graphify_ast")
    meta = bp.get_metadata()
    assert meta["harness_id"] == "graphify_ast"

    code_sample = "class Processor:\n    def process(self):\n        return True\n"
    topo = bp.analyze_code_topology(code_sample, filename="processor.py")
    assert topo["classes_count"] == 1

    pruned = bp.prune_signatures(code_sample)
    assert "token_reduction_pct" in pruned

    idx = bp.index_ast_nodes("processor.py", topo)
    assert idx["status"] == "INDEXED"
    assert idx["vector_dim"] == 768


def test_concordia_jury_blueprint():
    bp = he.get_blueprint("concordia_jury")
    meta = bp.get_metadata()
    assert meta["harness_id"] == "concordia_jury"

    code_sample = "def multiply(x, y):\n    \"\"\":requires: x > 0\n    :ensures: result > 0\"\"\"\n    return x * y\n"
    smt_res = bp.verify_smt_contracts(code_sample)
    assert "contract_satisfied" in smt_res or "status" in smt_res

    code_func = "def f(x):\n    return x + 1\n"
    equiv_res = bp.verify_functional_equivalence(code_func, code_func, "f")
    assert equiv_res["verified"] is True
