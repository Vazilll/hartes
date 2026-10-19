"""
tests/test_j_space_skill_state.py
==================================
Pytest test suite for:
  - vazus_core.global_j_workspace.GlobalJWorkspace
  - vazus_core.skill_state_runtime.SkillStateRuntime
  - Integration: inject_j_workspace + export_full_state
"""

import json
import pytest
import sys

sys.path.insert(0, "C:/vazus")

from vazus_core.global_j_workspace import GlobalJWorkspace, JSpaceConcept
from vazus_core.skill_state_runtime import SkillStateRuntime


FAKE_LLM_RESPONSE = json.dumps({
    "reasoning": "Transitioning to running phase.",
    "action": "activate",
    "action_args": {"target": "workspace"},
    "state_patch": {"phase": "running", "step": 1},
    "is_terminal": False
})


class TestGlobalJWorkspace:
    def test_initialization(self):
        ws = GlobalJWorkspace(capacity=8)
        assert ws.capacity == 8
        assert len(ws.active_concepts) == 0

    def test_broadcast_single(self):
        ws = GlobalJWorkspace(capacity=4)
        c = ws.broadcast_concept("c1", "SMT_Z3", 0.95, "verifier")
        assert c.concept_id == "c1"
        assert c.activation_strength == 0.95
        assert "c1" in ws.active_concepts

    def test_clamps_activation_bounds(self):
        ws = GlobalJWorkspace(capacity=4)
        c_hi = ws.broadcast_concept("hi", "X", 2.5, "a")
        c_lo = ws.broadcast_concept("lo", "Y", -1.0, "a")
        assert c_hi.activation_strength == 1.0
        assert c_lo.activation_strength == 0.0

    def test_capacity_eviction(self):
        ws = GlobalJWorkspace(capacity=3)
        ws.broadcast_concept("c1", "low",  0.10, "a")
        ws.broadcast_concept("c2", "mid",  0.50, "a")
        ws.broadcast_concept("c3", "high", 0.90, "a")
        ws.broadcast_concept("c4", "new",  0.70, "a")
        assert len(ws.active_concepts) == 3
        assert "c1" not in ws.active_concepts
        assert "c4" in ws.active_concepts

    def test_export_sorted_by_strength(self):
        ws = GlobalJWorkspace()
        ws.broadcast_concept("c1", "Alpha", 0.6, "a")
        ws.broadcast_concept("c2", "Beta",  0.9, "a")
        ws.broadcast_concept("c3", "Gamma", 0.3, "a")
        state = ws.export_workspace_state()
        concepts = state["workspace_concepts"]
        assert concepts[0]["strength"] >= concepts[1]["strength"]
        assert concepts[0]["label"] == "Beta"

    def test_causal_swap(self):
        ws = GlobalJWorkspace()
        ws.broadcast_concept("c1", "Old", 0.5, "p")
        rep = JSpaceConcept("c1_new", "New", 0.99, source_subagent="orch")
        assert ws.swap_concept("c1", rep) is True
        assert "c1" not in ws.active_concepts
        assert "c1_new" in ws.active_concepts

    def test_modulate_zero_removes(self):
        ws = GlobalJWorkspace()
        ws.broadcast_concept("c1", "X", 0.5, "a")
        ws.modulate_concept("c1", 0.0)
        assert "c1" not in ws.active_concepts


class TestSkillStateRuntime:
    def test_process_response_merges_state(self):
        rt = SkillStateRuntime("s", "p", {"phase": "init", "step": 0})
        r = rt.process_llm_response(FAKE_LLM_RESPONSE)
        assert r.new_state["phase"] == "running"
        assert r.step_index == 1
        assert r.is_terminal is False

    def test_null_patch_deletes_key(self):
        rt = SkillStateRuntime("s", "p", {"keep": "yes", "remove": "old"})
        resp = json.dumps({"reasoning": "", "action": "noop", "action_args": {},
                           "state_patch": {"remove": None}, "is_terminal": False})
        r = rt.process_llm_response(resp)
        assert "remove" not in r.new_state
        assert r.new_state["keep"] == "yes"

    def test_ephemeral_cot_not_stored(self):
        rt = SkillStateRuntime("s", "p", {})
        rt.process_llm_response(FAKE_LLM_RESPONSE)
        assert "reasoning" not in rt.state


class TestIntegration:
    def test_inject_j_workspace_embeds(self):
        ws = GlobalJWorkspace(capacity=4)
        ws.broadcast_concept("j1", "SMT_Z3", 0.99, "v")
        ws.broadcast_concept("j2", "Pruner", 0.88, "p")
        rt = SkillStateRuntime("s", "p", {"phase": "init"})
        rt.inject_j_workspace(ws)
        assert "j_workspace" in rt.state
        assert rt.state["j_workspace"]["active_count"] == 2

    def test_inject_none_removes(self):
        ws = GlobalJWorkspace()
        ws.broadcast_concept("j1", "X", 0.9, "a")
        rt = SkillStateRuntime("s", "p", {})
        rt.inject_j_workspace(ws)
        rt.inject_j_workspace(None)
        assert "j_workspace" not in rt.state

    def test_export_full_state(self):
        ws = GlobalJWorkspace()
        ws.broadcast_concept("j1", "Concordia", 0.95, "orch")
        rt = SkillStateRuntime("full", "Coord.", {"step": 0})
        rt.inject_j_workspace(ws)
        full = rt.export_full_state()
        assert full["skill_name"] == "full"
        assert "j_workspace" in full["execution_state"]

    def test_j_workspace_survives_patch(self):
        ws = GlobalJWorkspace()
        ws.broadcast_concept("j1", "SMT", 0.99, "v")
        rt = SkillStateRuntime("s", "p", {"phase": "init"})
        rt.inject_j_workspace(ws)
        resp = json.dumps({"reasoning": "adv", "action": "next",
                           "action_args": {}, "state_patch": {"phase": "step_2"},
                           "is_terminal": False})
        r = rt.process_llm_response(resp)
        assert "j_workspace" in r.new_state
        assert r.new_state["phase"] == "step_2"
