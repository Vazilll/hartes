"""
tests/test_architectural_enhancements.py
=========================================
Comprehensive Test Suite for the 6 SOTA 2026 Architectural Enhancements:
1. Dynamic Hypergraph with Hebbian Reinforcement & Ebbinghaus Decay (Two-Tier Consolidation).
2. Deterministic Time-Travel Sandbox with CoW Snapshots & Rollback.
3. Neurosymbolic SMT-Guided Generation & Database State Invariants (Z3).
4. Actor-Model Multi-Agent Message Bus & Dynamic DAG Pipeline (Map-Reduce).
5. Split-Brain Speculative Execution Engine on NPU.
6. Causal Graph Tracing & Merkle-Chained Decision Provenance.
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
import pytest

from vazus_core.memory.dynamic_hypergraph import CognitiveDynamicHypergraph
from vazus_core.sandbox.time_travel_sandbox import TimeTravelSandbox
from vazus_core.verification.smt_guided_synthesizer import SMTGuidedSynthesizer
from vazus_core.ipc.actor_bus import ActorBus, BaseActor, ActorMessage, DynamicDAGPipeline
from vazus_core.engine.speculative_npu_engine import SpeculativeNPUEngine
from vazus_core.telemetry.causal_tracer import CausalGraphTracer, CausalNode


# ==============================================================================
# 1. Cognitive Memory: Dynamic Hypergraph & Two-Tier Decay Consolidation
# ==============================================================================

def test_dynamic_hypergraph_reinforcement_and_decay(tmp_path):
    db_file = tmp_path / "test_vazus.db"
    graph = CognitiveDynamicHypergraph(db_path=db_file)

    # 1. Add active facts
    n1 = graph.add_node("fact_1", "Z3 formal contracts guarantee soundness", category="formal_spec", salience=0.8)
    n2 = graph.add_node("fact_2", "Concordia Jury requires 66% consensus", category="jury_rule", salience=0.8)
    edge = graph.add_hyper_edge(sources=["fact_1"], targets=["fact_2"], relation="verifies_with", weight=0.5)

    assert n1.node_id in graph.nodes
    assert edge.weight == 0.5

    # 2. Hebbian reinforcement
    graph.reinforce(node_ids=["fact_1", "fact_2"], success_confidence=1.0)
    assert graph.nodes["fact_1"].salience > 0.8
    assert graph.nodes["fact_1"].access_count == 2
    assert graph.edges[edge.edge_id].hits == 2
    assert graph.edges[edge.edge_id].weight > 0.5

    # 3. Episodic buffering & consolidation
    graph.record_episodic_event("repl_failure", "IndexError: list index out of range", "Array indexing task")
    graph.record_episodic_event("repl_failure", "IndexError: pop from empty list", "Stack operation task")

    # Force artificial staleness on an unreinforced node to test decay into cold storage
    stale_node = graph.add_node("stale_hypo", "Tentative unverified hypothesis", salience=0.1)
    stale_node.last_accessed = time.time() - (86400.0 * 30)  # 30 days ago

    report = graph.consolidate_memory(decay_threshold=0.15)
    assert report.episodes_processed == 2
    assert report.abstractions_formed >= 1
    assert report.nodes_archived >= 1
    assert "stale_hypo" not in graph.nodes  # Archived to cold storage

    # 4. Search active context
    results = graph.search_active_context("Z3 consensus", top_k=3)
    assert len(results) >= 1
    assert any("Z3" in r.content for r in results)


# ==============================================================================
# 2. Execution Environment: Time-Travel Sandbox & CoW Rollback
# ==============================================================================

def test_time_travel_sandbox_execution_and_rollback(tmp_path):
    sandbox = TimeTravelSandbox(base_dir=tmp_path / "sandbox", timeout_seconds=10.0)
    target_file = tmp_path / "sandbox" / "target.py"

    # Step 1: Initial state
    target_file.write_text("X = 10\n", encoding="utf-8")
    sandbox.track_file(target_file)
    cp1 = sandbox.create_checkpoint("initial_clean_state")

    # Step 2: Mutate code (Step 2 introduces bad state)
    target_file.write_text("X = 'corrupted_state'\n", encoding="utf-8")
    cp2 = sandbox.create_checkpoint("corrupted_mutation")
    assert "corrupted_state" in target_file.read_text(encoding="utf-8")

    # Step 3: Run execution that fails invariant
    res = sandbox.execute_code(
        code_str="import sys; sys.exit(1)",
        step_name="failing_contract_check",
    )
    assert res.success is False

    # Step 4: Time-Travel Rollback to clean state
    rollback_ok = sandbox.rollback(cp1.step_id)
    assert rollback_ok is True
    # Target file must be back to initial state
    assert target_file.read_text(encoding="utf-8") == "X = 10\n"

    # Step 5: Counterexample prompt augmentation
    augmented_prompt = sandbox.inject_counterexample(
        prompt="Fix the function to handle division",
        counterexample={"x": 5, "y": 0},
        failing_step_id=res.step_id,
    )
    assert "TIME-TRAVEL ROLLBACK ALERT" in augmented_prompt
    assert "y = 0" in augmented_prompt
    sandbox.cleanup()


# ==============================================================================
# 3. Formal Verification: Neurosymbolic SMT Synthesis & DB Invariants
# ==============================================================================

def test_smt_guided_synthesizer():
    synthesizer = SMTGuidedSynthesizer()

    # 1. Test counterexample and boundary test generation
    res = synthesizer.extract_counterexample_and_test(
        func_name="compute_ratio",
        code_str="def compute_ratio(x, y):\n    return x / y\n",
        postconditions=["y != 0"],
    )
    assert res.is_valid is False
    assert res.status == "SAT"
    assert res.counterexample is not None
    assert res.counterexample.get("y") == 0
    assert "def test_smt_counterexample_compute_ratio():" in res.generated_test_code

    # 2. Academic schedule invariant verification
    # Valid liquidation
    v_acad_ok = synthesizer.verify_academic_state_transition(
        current_debt_count=5,
        days_until_deadline=10,
        proposed_action="LIQUIDATE_DEBT",
        target_debt_delta=2,
    )
    assert v_acad_ok.approved is True
    assert v_acad_ok.status == "UNSAT"

    # Invalid transition (liquidating more debts than exist: delta 10 > debt 5)
    v_acad_bad = synthesizer.verify_academic_state_transition(
        current_debt_count=5,
        days_until_deadline=10,
        proposed_action="LIQUIDATE_DEBT",
        target_debt_delta=10,
    )
    assert v_acad_bad.approved is False
    assert v_acad_bad.status == "SAT"

    # 3. Financial solvency invariant verification
    # Balance 100, min_reserve 20, debit 50 -> post balance 50 >= 20 -> Approved
    v_fin_ok = synthesizer.verify_financial_state_transition(
        current_balance=100.0,
        min_reserve=20.0,
        transaction_amount=50.0,
        is_debit=True,
    )
    assert v_fin_ok.approved is True

    # Balance 100, min_reserve 20, debit 90 -> post balance 10 < 20 -> Rejected (insolvency)
    v_fin_bad = synthesizer.verify_financial_state_transition(
        current_balance=100.0,
        min_reserve=20.0,
        transaction_amount=90.0,
        is_debit=True,
    )
    assert v_fin_bad.approved is False
    assert v_fin_bad.status == "SAT"


# ==============================================================================
# 4. Multi-Agent Bus: Actor Model & Dynamic DAG Map-Reduce
# ==============================================================================

class MockWorkerActor(BaseActor):
    async def receive(self, message: ActorMessage):
        self._private_state["last_received"] = message.payload
        return None


def test_actor_bus_and_dynamic_dag():
    async def _test():
        bus = ActorBus()
        actor_a = MockWorkerActor("actor_a")
        actor_b = MockWorkerActor("actor_b")

        bus.register_actor(actor_a)
        bus.register_actor(actor_b)

        # 1. Message delivery
        msg = ActorMessage.create(
            sender="actor_a",
            recipient="actor_b",
            msg_type="TASK",
            payload={"task": "SMT verification", "effort": "high"},
        )
        delivered = await bus.send(msg)
        assert delivered is True
        assert actor_b.mailbox.qsize() == 1

        # Process message
        msg_in_box = await actor_b.mailbox.get()
        assert msg_in_box.payload["task"] == "SMT verification"

        # 2. Dynamic DAG Pipeline with Map-Reduce
        pipeline = DynamicDAGPipeline(bus)

        # Stage 1: Map across 3 hypotheses
        pipeline.add_stage(
            stage_id="hypotheses_generation",
            dependencies=[],
            worker_actors=["hypo_1", "hypo_2", "hypo_3"],
            map_task_fn=lambda inp, w: {"agent": w, "proposed_fix": f"patch_by_{w}", "score": 85},
            reduce_fn=lambda results: {"best_fix": sorted(results, key=lambda x: x["score"], reverse=True)[0]},
        )

        # Stage 2: SMT verification of selected fix
        pipeline.add_stage(
            stage_id="smt_verification",
            dependencies=["hypotheses_generation"],
            worker_actors=["z3_prover"],
            map_task_fn=lambda inp, w: {
                "verdict": "UNSAT_PROVEN",
                "verified_patch": inp["dep_hypotheses_generation"]["best_fix"]["proposed_fix"],
            },
            reduce_fn=lambda results: {"all_verified": all(r["verdict"] == "UNSAT_PROVEN" for r in results)},
        )

        dag_output = await pipeline.execute(initial_payload={"context": "Fix division error"})
        assert "hypotheses_generation" in dag_output
        assert "smt_verification" in dag_output
        assert dag_output["smt_verification"]["all_verified"] is True

    asyncio.run(_test())


# ==============================================================================
# 5. Hybrid Inference: Speculative NPU Split-Brain Engine
# ==============================================================================

def test_speculative_npu_engine():
    engine = SpeculativeNPUEngine(npu_device="NPU_Intel_Meteor_Lake")

    # 1. Fast draft generation
    draft = engine.generate_speculative_draft("Create API route service for students")
    assert draft.device == "NPU_Intel_Meteor_Lake"
    assert "GeneratedService" in draft.draft_code or "handle_request" in draft.draft_code
    assert draft.draft_tokens > 0

    # 2. Validator accepts valid AST draft
    res_accepted = engine.execute_speculative_pipeline(
        task_prompt="Build data model class",
        architectural_validator_fn=lambda code, prompt: (True, "Valid architecture", None),
    )
    assert res_accepted.accepted is True
    assert res_accepted.tokens_saved > 0
    assert res_accepted.speedup_multiplier > 1.0

    # 3. Validator rejects and provides targeted patch
    res_rejected = engine.execute_speculative_pipeline(
        task_prompt="Complex cryptographic routine",
        architectural_validator_fn=lambda code, prompt: (False, "Requires SHA3-512 instead", "def secure_sha3(): pass"),
    )
    assert res_rejected.accepted is False
    assert res_rejected.tokens_saved == 0
    assert "secure_sha3" in res_rejected.final_code


# ==============================================================================
# 6. Observability: Causal Graph Tracing & Merkle Decision Provenance
# ==============================================================================

def test_causal_graph_tracer(tmp_path):
    db_file = tmp_path / "causal_test.db"
    tracer = CausalGraphTracer(db_path=db_file)

    # 1. Record parent decision
    node_parent = tracer.record_decision(
        artifact_type="ARCH_DECISION",
        content="Enforce fail-closed SMT precommit gate",
        memory_facts=["GATE_DESIGN_SPEC_L4"],
        test_verifier_output="PASSED_AST_VALIDATION",
        jury_approval_verdict="CONCORDIA_APPROVED_100",
        agent_id="system_architect",
    )
    assert node_parent.merkle_signature is not None

    # 2. Record child code patch chained to parent
    node_child = tracer.record_decision(
        artifact_type="CODE_PATCH",
        content="def verify(): return True",
        memory_facts=["GATE_DESIGN_SPEC_L4", "HOARE_LOGIC_INV"],
        test_verifier_output="PASSED_PYTEST_EXITCODE_0",
        jury_approval_verdict="CONCORDIA_APPROVED_85",
        parent_node_ids=[node_parent.node_id],
        agent_id="coding_worker",
    )

    # 3. Verify provenance & Merkle integrity
    is_valid, msg = tracer.verify_provenance(node_child.node_id)
    assert is_valid is True
    assert "verified cryptographically" in msg

    # 4. Generate narrative
    narrative = tracer.get_provenance_narrative(node_child.node_id)
    assert "CODE_PATCH" in narrative
    assert "Verified by Test Suite" in narrative
    assert "Approved by Concordia Jury" in narrative


# ==============================================================================
# 7. Deep Edge Cases & Robustness Verification
# ==============================================================================

def test_dynamic_hypergraph_persistence_edge_pruning_and_extreme_decay(tmp_path):
    db_file = tmp_path / "deep_hypergraph.db"
    g1 = CognitiveDynamicHypergraph(db_path=db_file)
    n1 = g1.add_node("persisted_node_1", "Invariant A", salience=0.9)
    n2 = g1.add_node("persisted_node_2", "Invariant B", salience=0.08)  # Will decay
    e1 = g1.add_hyper_edge(sources=["persisted_node_1"], targets=["persisted_node_2"], relation="implies")

    # Verify second instance loads from SQLite
    g2 = CognitiveDynamicHypergraph(db_path=db_file)
    assert "persisted_node_1" in g2.nodes
    assert e1.edge_id in g2.edges

    # Test negative confidence penalty
    sal_before = g2.nodes["persisted_node_1"].salience
    g2.reinforce(["persisted_node_1"], success_confidence=0.0)
    assert g2.nodes["persisted_node_1"].salience < sal_before

    # Test extreme decay jump (> 1000 days)
    sal_extreme = g2.nodes["persisted_node_1"].compute_current_salience(time.time() + 86400.0 * 1000)
    assert 0.0 <= sal_extreme <= 1.0

    # Consolidation must archive decayed node and prune dangling edge
    rep = g2.consolidate_memory(decay_threshold=0.15)
    assert rep.nodes_archived >= 1
    assert rep.edges_pruned >= 1
    assert e1.edge_id not in g2.edges


def test_time_travel_sandbox_untracked_files_cleanup_and_wasm(tmp_path):
    sandbox = TimeTravelSandbox(base_dir=tmp_path / "sandbox_untracked", timeout_seconds=10.0)
    cp = sandbox.create_checkpoint("clean_state")

    # Step creates untracked file and fails with auto rollback
    junk_file = tmp_path / "sandbox_untracked" / "junk.txt"
    code = f"open(r'{junk_file}', 'w').write('bad_data'); import sys; sys.exit(1)"

    res = sandbox.execute_code(
        code_str=code,
        step_name="failing_with_untracked",
        rollback_on_failure=True,
        counterexample={"witness": "untracked_fail"},
    )
    assert res.success is False
    assert res.rolled_back is True
    assert res.injected_counterexample == {"witness": "untracked_fail"}
    # Untracked junk file must be cleaned up
    assert not junk_file.exists()

    # WASM execution: valid header
    wasm_bytes = b"\x00asm\x01\x00\x00\x00"
    wasm_res = sandbox.execute_wasm(wasm_bytes, step_name="test_wasm")
    assert wasm_res.success is True
    assert wasm_res.exit_code == 0

    # WASM execution: invalid header
    bad_wasm = b"not_a_wasm_binary"
    bad_res = sandbox.execute_wasm(bad_wasm, step_name="test_bad_wasm", rollback_on_failure=True)
    assert bad_res.success is False
    assert "Invalid WASM" in bad_res.stderr

    sandbox.cleanup()


def test_smt_guided_synthesizer_symbolic_vars_and_edge_cases():
    synth = SMTGuidedSynthesizer()

    # Variable-to-variable symbolic comparison
    res = synth.extract_counterexample_and_test(
        func_name="check_order",
        code_str="def check_order(x, y):\n    return x < y\n",
        postconditions=["x < y"],
    )
    assert res.status in ("SAT", "UNSAT")
    assert res.counterexample is not None

    # Floating point NaN/Inf rejection in financial state
    v_nan = synth.verify_financial_state_transition(
        current_balance=float("nan"),
        min_reserve=10.0,
        transaction_amount=5.0,
    )
    assert v_nan.approved is False
    assert "Non-finite" in str(v_nan.violation_witness)

    # Negative liquidation delta rejection in academic state
    v_acad_neg = synth.verify_academic_state_transition(
        current_debt_count=5,
        days_until_deadline=10,
        proposed_action="LIQUIDATE_DEBT",
        target_debt_delta=-2,
    )
    assert v_acad_neg.approved is False
    assert v_acad_neg.status == "SAT"


def test_actor_bus_serialization_and_async_dag():
    async def _test():
        # Serialization round-trip
        msg = ActorMessage.create(
            sender="actor_1",
            recipient="actor_2",
            msg_type="TASK",
            payload={"action": "reconcile", "amount": 100},
        )
        data_bytes = msg.to_bytes()
        restored = ActorMessage.from_bytes(data_bytes)
        assert restored.message_id == msg.message_id
        assert restored.payload == msg.payload

        # Async DAG pipeline
        bus = ActorBus()
        pipeline = DynamicDAGPipeline(bus)

        async def async_map_fn(inp, worker):
            await asyncio.sleep(0.01)
            return {"worker": worker, "value": 42}

        async def async_reduce_fn(results):
            await asyncio.sleep(0.01)
            return {"sum": sum(r["value"] for r in results)}

        pipeline.add_stage(
            stage_id="stage_async",
            dependencies=[],
            worker_actors=["w1", "w2"],
            map_task_fn=async_map_fn,
            reduce_fn=async_reduce_fn,
        )

        res = await pipeline.execute(initial_payload={})
        assert res["stage_async"]["sum"] == 84

        # Test missing dependency detection
        pipeline.add_stage("invalid_dep_stage", dependencies=["non_existent_predecessor"])
        with pytest.raises(ValueError, match="depends on non-existent stage"):
            await pipeline.execute(initial_payload={})

    asyncio.run(_test())


def test_speculative_npu_refined_preservation_and_custom_generator():
    engine = SpeculativeNPUEngine(
        npu_device="NPU_Intel_AI_Boost",
        draft_generator_fn=lambda prompt: "def custom_npu_generated(): pass",
    )

    draft = engine.generate_speculative_draft("Generate crypto routine")
    assert "custom_npu_generated" in draft.draft_code

    # Validator accepts with minor refinement -> refinement must be preserved!
    res = engine.validate_and_refine(
        draft=draft,
        task_prompt="Generate crypto routine",
        architectural_validator_fn=lambda code, prompt: (True, "Accepted with type annotations", "def custom_npu_generated() -> None: pass"),
    )
    assert res.accepted is True
    assert res.final_code == "def custom_npu_generated() -> None: pass"


def test_causal_graph_tracer_tamper_and_cycles(tmp_path):
    db_file = tmp_path / "causal_deep.db"
    tracer = CausalGraphTracer(db_path=db_file)

    n1 = tracer.record_decision(
        artifact_type="DECISION_1",
        content="Action 1",
        metadata={"sec_level": "high"},
    )
    assert tracer.verify_provenance(n1.node_id)[0] is True

    # Tampering with metadata invalidates signature
    tampered_node = tracer._nodes[n1.node_id]
    object.__setattr__(tampered_node, "metadata", {"sec_level": "hacked"})
    is_valid, msg = tracer.verify_provenance(n1.node_id)
    assert is_valid is False
    assert "Tamper detected" in msg

    # Cycle detection in parent ancestry
    cA = tracer.record_decision(artifact_type="CYCLIC_A", content="A")
    cB = tracer.record_decision(artifact_type="CYCLIC_B", content="B", parent_node_ids=[cA.node_id])
    # Introduce cycle B -> A -> B with matching signatures
    import hashlib
    meta_hash_A = hashlib.sha256(json.dumps(cA.metadata or {}, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    sig_A = CausalNode.compute_signature(
        content_hash=cA.content_hash,
        memory_fact_hashes=cA.memory_fact_hashes,
        test_verifier_hash=cA.test_verifier_hash,
        jury_approval_hash=cA.jury_approval_hash,
        parent_node_ids=(cB.node_id,),
        agent_id=cA.agent_id,
        timestamp=cA.timestamp,
        metadata_hash=meta_hash_A,
    )
    object.__setattr__(tracer._nodes[cA.node_id], "parent_node_ids", (cB.node_id,))
    object.__setattr__(tracer._nodes[cA.node_id], "merkle_signature", sig_A)
    is_cycle_valid, cycle_msg = tracer.verify_provenance(cB.node_id)
    assert is_cycle_valid is False
    assert "Cycle detected" in cycle_msg

