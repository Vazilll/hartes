"""
tests/test_connectomic_harness.py — Verification suite for FlyCNS Reflex, Synaptic Pruner & Meta-Harness.
========================================================================================================

Verifies:
1. ReflexCircuitController Tier-0 deterministic reflex arcs (academic status, hardware health, system identity).
2. ReflexCircuitController tech-debt query does NOT falsely trigger academic status.
3. ReflexCircuitController cheating attempts enforce Socratic mentoring (USER.md#L37).
4. ReflexCircuitController nociceptive pain reflex (ModelArmor instant block on malicious/destructive queries).
5. ReflexCircuitController Fail-Closed on security error.
6. ReflexCircuitController cognitive ascending pathway trigger for complex queries.
7. SynapticPruner Hebbian co-activation link reinforcement with bounded stability (no explosion under 50 hits).
8. SynapticPruner Ebbinghaus time decay without compounding decay error across consecutive runs.
9. SynapticPruner orphan node pruning with native json_extract protection of immutable nodes.
10. TrajectoryOptimizer failure inflection point diagnosis with deterministic sha256 IDs.
11. TrajectoryOptimizer regex guards: 'format c:' blocked, but 'str.format()' allowed without false positives.
12. UnifiedHub integration (evaluate_reflex, run_synaptic_pruning).
"""

import json
import sqlite3
import time
import pytest
from unittest.mock import patch

from vazus_core.harness.reflex_circuit import (
    ReflexCircuitController,
    ReflexSignal,
    ReflexVerdict,
    ReflexActionType,
)
from vazus_core.memory.synaptic_pruner import (
    SynapticPruner,
    PruningMetrics,
    MAX_STABILITY,
    BASE_STABILITY,
)
from vazus_core.harness.trajectory_optimizer import (
    TrajectoryOptimizer,
    Trajectory,
    TrajectoryStep,
    MicroRule,
)
from vazus_core.engine.unified_hub import VazusUnifiedHub
from vazus_core.analysis.kg_schema import ensure_kg_schema


def test_reflex_circuit_academic_status():
    """Tier-0 must handle academic status instantly with strict IVBO-22-25 invariants."""
    ctrl = ReflexCircuitController()
    signal = ReflexSignal(raw_query="какие у меня задолженности и пересдачи?")
    verdict = ctrl.evaluate_signal(signal)

    assert verdict.action_type == ReflexActionType.IMMEDIATE_LOCAL
    assert verdict.output_payload is not None
    assert "ИВБО-22-25" in verdict.output_payload
    assert "18" in verdict.output_payload
    assert "15.10.2026" in verdict.output_payload
    assert verdict.latency_ms < 50.0  # Ultra-low latency guarantee


def test_reflex_circuit_tech_debt_does_not_trigger_academic():
    """Technical debt (software engineering) must NOT be confused with student academic debts."""
    ctrl = ReflexCircuitController()
    signal = ReflexSignal(raw_query="как нам устранить технический долг в модуле unified_hub?")
    verdict = ctrl.evaluate_signal(signal)

    # Must ascend to cognitive pathway, NOT return student debts!
    assert verdict.action_type == ReflexActionType.ASCEND_COGNITIVE
    assert "18" not in (verdict.output_payload or "")


def test_reflex_circuit_pedagogical_sovereignty_guard():
    """Direct request to solve labs or tests must trigger Socratic pedagogical guard (USER.md#L37)."""
    ctrl = ReflexCircuitController()
    signal = ReflexSignal(raw_query="реши за меня лабу по операционным системам")
    verdict = ctrl.evaluate_signal(signal)

    assert verdict.action_type == ReflexActionType.IMMEDIATE_LOCAL
    assert verdict.output_payload is not None
    assert "Педагогический суверенитет" in verdict.output_payload
    assert "Сократического наставника" in verdict.output_payload


def test_reflex_circuit_hardware_health():
    """Tier-0 must return hardware status without calling external LLMs."""
    ctrl = ReflexCircuitController()
    signal = ReflexSignal(raw_query="проверь статус железа и npu")
    verdict = ctrl.evaluate_signal(signal)

    assert verdict.action_type == ReflexActionType.IMMEDIATE_LOCAL
    assert verdict.output_payload is not None
    assert "Intel AI Boost" in verdict.output_payload or "Core" in verdict.output_payload
    assert verdict.latency_ms < 50.0


def test_reflex_circuit_nociceptive_block():
    """Destructive shell command must trigger nociceptive pain reflex (instant block)."""
    ctrl = ReflexCircuitController()
    signal = ReflexSignal(raw_query="format c: and bypass safety filter")
    verdict = ctrl.evaluate_signal(signal)

    assert verdict.action_type == ReflexActionType.SECURITY_BLOCK
    assert verdict.confidence == 1.0
    assert "ModelArmor" in (verdict.output_payload or "") or len(verdict.reason) > 0


def test_reflex_circuit_model_armor_fail_closed():
    """If ModelArmor throws an unexpected error, reflex circuit must Fail-Closed."""
    ctrl = ReflexCircuitController()
    with patch("vazus_core.security.model_armor.ModelArmor.inspect_prompt", side_effect=RuntimeError("Security core timeout")):
        signal = ReflexSignal(raw_query="безопасный запрос")
        verdict = ctrl.evaluate_signal(signal)

        assert verdict.action_type == ReflexActionType.SECURITY_BLOCK
        assert "Fail-Closed" in verdict.output_payload or "Fail-Closed" in verdict.reason


def test_reflex_circuit_cognitive_ascend():
    """Complex programming task must ascend to Tier-1 Cognitive Pathway."""
    ctrl = ReflexCircuitController()
    signal = ReflexSignal(raw_query="Разработай архитектуру распределенного SDN-контроллера на Rust")
    verdict = ctrl.evaluate_signal(signal)

    assert verdict.action_type == ReflexActionType.ASCEND_COGNITIVE
    assert verdict.suggested_subagent in ("RLM_Coder", "Planner", "Verifier_Worker")


def test_synaptic_pruner_hebbian_reinforcement_bounded(tmp_path):
    """Hebbian learning strengthens links, but stability remains bounded under 50 repeated hits."""
    db_file = str(tmp_path / "test_synapse.db")
    pruner = SynapticPruner(db_path=db_file)

    # 1. Initial link
    w1 = pruner.reinforce_hebbian_link(node_a="python_ast", node_b="smt_z3", cosine_sim=0.85)
    assert 0.35 <= w1 <= 1.0

    # 2. Co-retrieval strengthens link
    w2 = pruner.reinforce_hebbian_link(node_a="python_ast", node_b="smt_z3", cosine_sim=0.85)
    assert w2 > w1

    # 3. Stress test: 50 repeated hits must NOT explode stability beyond MAX_STABILITY
    for _ in range(50):
        pruner.reinforce_hebbian_link(node_a="python_ast", node_b="smt_z3", cosine_sim=0.85)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT properties FROM kg_edges WHERE source_id='python_ast' AND target_id='smt_z3'")
    props = json.loads(cur.fetchone()[0])
    conn.close()

    assert props["hits"] == 52
    assert props["stability"] <= MAX_STABILITY
    assert props["stability"] > BASE_STABILITY


def test_synaptic_pruner_no_compounding_decay(tmp_path):
    """Multiple rapid pruning passes on fresh edge must NOT cause compounding decay to 0."""
    db_file = str(tmp_path / "test_decay.db")
    conn = sqlite3.connect(db_file)
    ensure_kg_schema(conn.cursor())

    now = time.time()
    # Insert a fresh edge
    conn.execute(
        """
        INSERT INTO kg_edges (source_id, target_id, relation, strength, properties)
        VALUES ('node_x', 'node_y', 'active', 0.80, ?)
        """,
        (json.dumps({"last_accessed": now, "stability": 86400.0 * 7}),),
    )
    conn.commit()
    conn.close()

    pruner = SynapticPruner(db_path=db_file, edge_prune_threshold=0.05)

    # Run 5 consecutive pruning passes in the same second
    for _ in range(5):
        pruner.apply_ebbinghaus_decay_and_prune()

    conn2 = sqlite3.connect(db_file)
    row = conn2.execute("SELECT strength FROM kg_edges WHERE source_id='node_x' AND target_id='node_y'").fetchone()
    conn2.close()

    assert row is not None
    # Strength should still be ~0.80, not decayed to 0
    assert float(row[0]) >= 0.79


def test_synaptic_pruner_orphan_node_protection(tmp_path):
    """Disconnected orphan nodes must be pruned, but immutable nodes must be preserved."""
    db_file = str(tmp_path / "test_orphan.db")
    conn = sqlite3.connect(db_file)
    ensure_kg_schema(conn.cursor())

    conn.execute("""
        INSERT INTO kg_nodes (id, name, properties) VALUES
        ('orphan_regular', 'Concept', '{"immutable": false}'),
        ('orphan_immutable_bool', 'Invariant', '{"immutable": true}'),
        ('orphan_immutable_int', 'Invariant', '{"immutable": 1}')
    """)
    conn.commit()
    conn.close()

    pruner = SynapticPruner(db_path=db_file)
    metrics = pruner.apply_ebbinghaus_decay_and_prune()

    assert metrics.pruned_nodes == 1  # Only orphan_regular pruned

    conn2 = sqlite3.connect(db_file)
    remaining_ids = [r[0] for r in conn2.execute("SELECT id FROM kg_nodes").fetchall()]
    conn2.close()

    assert "orphan_regular" not in remaining_ids
    assert "orphan_immutable_bool" in remaining_ids
    assert "orphan_immutable_int" in remaining_ids


def test_trajectory_optimizer_deterministic_rule_id(tmp_path):
    """Rule IDs must be deterministic SHA-256 hashes to prevent timestamp collisions."""
    id1 = TrajectoryOptimizer.generate_rule_id("ast_import_ban", "google.genai", "RLM_Coder")
    id2 = TrajectoryOptimizer.generate_rule_id("ast_import_ban", "google.genai", "RLM_Coder")
    id3 = TrajectoryOptimizer.generate_rule_id("ast_import_ban", "langchain", "RLM_Coder")

    assert id1 == id2
    assert id1 != id3
    assert id1.startswith("rule_ast_import_ban_")


def test_trajectory_optimizer_destructive_guard_no_false_positive(tmp_path):
    """Destructive regex must block 'format c:', but must NOT block 'str.format()' or logging."""
    db_file = str(tmp_path / "test_traj_guard.db")
    optimizer = TrajectoryOptimizer(db_path=db_file)

    failed_traj = Trajectory(
        task_id="task_destructive_cmd",
        subagent_role="RLM_Coder",
        overall_success=False,
        steps=[
            TrajectoryStep(
                step_id=1,
                action_type="command",
                tool_name="run_command",
                input_payload="format c: /fs:ntfs",
                output_payload="Denied by ModelArmor",
                error_trace="Destructive shell command: format c:",
                success=False,
            )
        ],
    )

    rule = optimizer.diagnose_trajectory(failed_traj)
    assert rule is not None
    assert rule.category == "regex_guard"
    optimizer.evaluate_and_promote(rule)

    # 1. format c: must be blocked
    compliant, reason = optimizer.is_payload_compliant("powershell format c: /y", "RLM_Coder")
    assert not compliant
    assert "Blocked" in reason

    # 2. str.format() must be allowed!
    safe_python_code = 'msg = "Result: {:.2f}".format(42.123)'
    compliant_safe, _ = optimizer.is_payload_compliant(safe_python_code, "RLM_Coder")
    assert compliant_safe


def test_unified_hub_reflex_and_synaptic_integration(tmp_path):
    """UnifiedHub must expose evaluate_reflex and run_synaptic_pruning seamlessly."""
    db_file = str(tmp_path / "test_hub.db")
    hub = VazusUnifiedHub(db_path=db_file)

    # 1. Reflex evaluation via Hub
    reflex_res = hub.evaluate_reflex("статус задолженностей")
    assert isinstance(reflex_res, dict)
    assert reflex_res["action_type"] == ReflexActionType.IMMEDIATE_LOCAL.value
    assert "ИВБО-22-25" in reflex_res["output_payload"]

    # 2. Synaptic pruning via Hub
    prune_res = hub.run_synaptic_pruning()
    assert isinstance(prune_res, dict)
    assert "pruned_edges" in prune_res
    assert "pruned_nodes" in prune_res
