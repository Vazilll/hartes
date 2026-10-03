"""
tests/test_dynamic_tool_router.py — Tests for DynamicToolRouter and Payload Projection.
"""

from vazus_core.routing.dynamic_tool_router import DynamicToolRouter


def test_tool_router_find_tools():
    router = DynamicToolRouter()
    # Query intent for mathematical formal proof
    results = router.find_tools("I need to formally prove an invariant with Z3 solver", top_k=2)
    assert len(results) > 0
    top_tool = results[0]
    assert top_tool["name"] == "smt_z3_verify"
    assert "schema" in top_tool


def test_tool_router_find_ast_pruner():
    router = DynamicToolRouter()
    results = router.find_tools("prune go and python ast tree sitter", top_k=1)
    assert len(results) == 1
    assert results[0]["name"] == "ast_prune"


def test_tool_router_payload_projection():
    payload = {
        "status": "success",
        "output_nodes": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        "metadata": {"user": "vaz", "embedding": [0.1] * 768, "debug_log": "ok"},
        "extra_unneeded": "garbage",
    }
    projected = DynamicToolRouter.project_payload(payload, whitelist_keys=["status", "output_nodes", "metadata"], max_array_items=5)
    
    assert "extra_unneeded" not in projected
    assert projected["status"] == "success"
    assert len(projected["output_nodes"]) == 6  # 5 items + 1 truncation message
    assert "embedding" not in projected["metadata"]  # nested embedding filtered out
