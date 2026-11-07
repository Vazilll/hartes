"""
Unit and Integration Test Suite for Milestone 8 (F20, F21) of Vazus SuperGraph OS.

Components Tested:
- F20: Anti-Context-Rot Session Sharder & Entropy Governor (vazus_autonomous_harness.context)
  * Normalized Attention Entropy calculation (H_bar >= 0.78, L > 150k chars, turn lag threshold)
  * Shannon character-level entropy calculation
  * Deterministic EntropyGovernor threshold triggers
  * ObservationMasker (line-based collapsing, turn-based observation masking)
  * StageContextManager (discrete stage isolation, subagent shielding, handoff ledger)
  * SessionSharder (system prompt preservation, recent turn preservation, stale tool masking,
    stale assistant compaction, context compaction metadata)
- F21: Dual NotebookLM Workspaces & 30 TB Drive Vault Sync Bridge (vazus_autonomous_harness.sync)
  * Master 1st Semester Workspace (11f9bc29-99a1-4bab-aac3-cfbee9e4e553, 9 sources)
  * Master 3rd Semester Workspace (99b01f4d-b3b1-44ee-8f54-2ab7a28d617f, 7 sources)
  * Context-based workspace resolution (Math/English -> Sem 1, DC Circuit/Variant 6 -> Sem 3)
  * 30 TB Drive Vault structured bucket mappings with local failover replication
  * Notebook source artifact synchronization
- F21: Automated Google Jules Remediation Payload in Escalation Gate (vazus_autonomous_harness.engine)
  * JulesRemediationPayload schema and builder
  * Automated Jules remediation dispatch payload on 3 consecutive failed cycles
  * Section 5 rendering in executive diagnostic briefing
  * Multi-target persistence of JULES_PAYLOAD_{task_id}.json
  * Staging and dispatch queue handling
"""

import json
from pathlib import Path
import pytest

from vazus_autonomous_harness.context import (
    DEFAULT_BASELINE_CHARS,
    DEFAULT_MAX_BASELINE_CHARS,
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_ENTROPY,
    DEFAULT_MAX_TURNS,
    DEFAULT_UNMASKED_TURN_LAG,
    EntropyGovernor,
    GovernorEvaluation,
    ObservationMasker,
    SessionSharder,
    StageContextManager,
    compute_attention_entropy,
    compute_shannon_entropy,
)
from vazus_autonomous_harness.sync import (
    DEFAULT_CLOUD_VAULT_ROOT,
    DEFAULT_LOCAL_VAULT_ROOT,
    NOTEBOOK_SEM1_ID,
    NOTEBOOK_SEM3_ID,
    SEM1_WORKSPACE,
    SEM3_WORKSPACE,
    VAULT_BUCKET_MAPPINGS,
    CloudBridge,
    DriveVaultSyncMapping,
    NotebookLMSyncBridge,
    NotebookLMWorkspace,
    SyncResult,
)
from vazus_autonomous_harness.engine.anti_thrashing import (
    AntiThrashingCircuitBreaker,
    TaskAttempt,
)
from vazus_autonomous_harness.engine.escalation_gate import (
    EscalationBriefingGenerator,
    JulesRemediationPayload,
    build_jules_remediation_payload,
)


# =====================================================================
# 1. Attention & Shannon Entropy Mathematical Tests
# =====================================================================

def test_compute_attention_entropy_boundary_values():
    """Verifies H_bar behavior at boundary conditions."""
    # Under or equal to baseline (8000)
    assert compute_attention_entropy(0) == 0.0
    assert compute_attention_entropy(4000) == 0.0
    assert compute_attention_entropy(8000) == 0.0

    # Over or equal to max baseline (500000)
    assert compute_attention_entropy(500000) == 1.0
    assert compute_attention_entropy(600000) == 1.0

    # String input support
    assert compute_attention_entropy("A" * 8000) == 0.0
    assert compute_attention_entropy("A" * 500000) == 1.0


def test_compute_attention_entropy_monotonic_growth():
    """Verifies that H_bar monotonically increases with context length."""
    lengths = [10000, 25000, 50000, 100000, 150000, 200000, 350000, 490000]
    entropies = [compute_attention_entropy(l) for l in lengths]

    for i in range(1, len(entropies)):
        assert entropies[i] > entropies[i - 1], f"Failed monotonicity at {lengths[i]}"


def test_compute_attention_entropy_threshold_alignment():
    """Verifies H_bar ~= 0.78 near ~200k characters (~50k tokens)."""
    h_150k = compute_attention_entropy(150000)
    h_200k = compute_attention_entropy(200000)
    h_250k = compute_attention_entropy(250000)

    assert 0.70 < h_150k < 0.73
    assert 0.77 < h_200k < 0.79
    assert h_250k > 0.80


def test_compute_shannon_entropy():
    """Verifies normalized Shannon character entropy calculation."""
    assert compute_shannon_entropy("") == 0.0
    assert compute_shannon_entropy("AAAAAA") == 0.0
    # Diverse text should have substantial entropy
    diverse_text = "The quick brown fox jumps over the lazy dog 1234567890!@#$%^&*()"
    ent = compute_shannon_entropy(diverse_text)
    assert 0.5 < ent <= 1.0


# =====================================================================
# 2. EntropyGovernor Tests
# =====================================================================

def test_entropy_governor_nominal_no_trigger():
    """Verifies that nominal conversation under thresholds does not trigger compaction."""
    governor = EntropyGovernor(max_entropy=0.78, max_chars=150000, max_turns=12)
    eval_res = governor.evaluate("Brief dialogue context", turn_count=5)

    assert isinstance(eval_res, GovernorEvaluation)
    assert eval_res.should_shard is False
    assert len(eval_res.trigger_reasons) == 0
    assert eval_res.attention_entropy == 0.0


def test_entropy_governor_triggers_on_char_budget_exceeded():
    """Verifies governor triggers when L > max_chars."""
    governor = EntropyGovernor(max_chars=150000)
    huge_text = "A" * 160000
    eval_res = governor.evaluate(huge_text, turn_count=3)

    assert eval_res.should_shard is True
    assert any("CHARS_EXCEEDED" in r for r in eval_res.trigger_reasons)


def test_entropy_governor_triggers_on_turns_exceeded():
    """Verifies governor triggers when turn count > 12."""
    governor = EntropyGovernor(max_turns=12)
    eval_res = governor.evaluate("Short content", turn_count=15)

    assert eval_res.should_shard is True
    assert any("TURNS_EXCEEDED" in r for r in eval_res.trigger_reasons)


def test_entropy_governor_triggers_on_entropy_threshold():
    """Verifies governor triggers when H_bar >= 0.78."""
    governor = EntropyGovernor(max_entropy=0.78)
    huge_text = "A" * 210000
    eval_res = governor.evaluate(huge_text, turn_count=5)

    assert eval_res.should_shard is True
    assert any("ENTROPY_EXCEEDED" in r for r in eval_res.trigger_reasons)


# =====================================================================
# 3. ObservationMasker Tests
# =====================================================================

def test_observation_masker_preserves_short_dumps():
    """Outputs with <= 16 lines must remain intact."""
    masker = ObservationMasker(raw_tool_max_lines=16)
    short_text = "\n".join(f"Line {i}" for i in range(12))
    assert masker.collapse_raw_dump(short_text) == short_text


def test_observation_masker_collapses_massive_dumps():
    """Outputs exceeding 16 lines must collapse with head 8 and tail 8."""
    masker = ObservationMasker(raw_tool_max_lines=16)
    lines = [f"Line {i:03d}" for i in range(100)]
    long_text = "\n".join(lines)

    collapsed = masker.collapse_raw_dump(long_text)
    collapsed_lines = collapsed.splitlines()

    assert len(collapsed_lines) == 17  # 8 head + 1 notice + 8 tail
    assert collapsed_lines[0] == "Line 000"
    assert collapsed_lines[7] == "Line 007"
    assert "84 lines omitted" in collapsed_lines[8]
    assert collapsed_lines[-8] == "Line 092"
    assert collapsed_lines[-1] == "Line 099"


def test_observation_masker_turn_stub():
    """Verifies turn observation mask stub format."""
    masker = ObservationMasker()
    stub = masker.mask_turn_observation(turn_index=4)
    assert "[OBSERVATION MASKED: Turn #4 omitted to preserve attention budget. Action succeeded.]" == stub


# =====================================================================
# 4. StageContextManager & Isolation Tests
# =====================================================================

def test_stage_context_manager_isolated_initialization():
    """Verifies that new stage context is pristine with core invariants."""
    mgr = StageContextManager(current_stage="Stage1_DCCircuit")
    summary = "Stage 1 DC Circuit Variant 6 solved: I1=0.25A, I2=-0.12A, power balance verified 0.0% error."
    context = mgr.create_isolated_stage_context(
        stage_name="Stage2_JavaOOP",
        previous_stage_summary=summary,
        system_invariants="Socratic Sovereignty Invariant USER.md#L37 enforced.",
    )

    assert len(context) == 3
    assert context[0]["role"] == "system"
    assert "USER.md#L37" in context[0]["content"]
    assert context[1]["role"] == "user"
    assert "Stage 1 DC Circuit" in context[1]["content"]
    assert "Stage1_DCCircuit -> Stage2_JavaOOP" in context[1]["content"]
    assert context[2]["role"] == "assistant"
    assert "Stage2_JavaOOP" in context[2]["content"]
    assert mgr.current_stage == "Stage2_JavaOOP"


def test_stage_context_manager_subagent_shielding():
    """Verifies raw subagent turns are collapsed into shielded executive message."""
    mgr = StageContextManager()
    raw_subagent_turns = [
        {"role": "user", "content": f"Subagent query {i}"} for i in range(25)
    ]
    task_summary = "AST analysis finished: 0 cyclomatic complexity violations."
    artifacts = ["C:/vazus/hartes/vazus_autonomous_harness/context/session_sharder.py"]

    shielded = mgr.isolate_subagent_dialogue(
        raw_subagent_turns, task_summary, artifact_paths=artifacts
    )

    assert shielded["role"] == "user"
    assert "25 turns executed" in shielded["content"]
    assert "AST analysis finished" in shielded["content"]
    assert artifacts[0] in shielded["content"]
    assert shielded["metadata"]["shielded_turns"] == 25


def test_stage_context_manager_handoff_recording():
    """Verifies recording stage transitions into historical ledger."""
    mgr = StageContextManager(current_stage="stage_a")
    record = mgr.record_stage_handoff(
        from_stage="stage_a",
        to_stage="stage_b",
        summary="Transition complete",
        artifacts=["file1.py"],
    )
    assert record["from_stage"] == "stage_a"
    assert record["to_stage"] == "stage_b"
    assert len(mgr.stage_history) == 1
    assert mgr.current_stage == "stage_b"


# =====================================================================
# 5. SessionSharder Core Dialogue Compaction Tests
# =====================================================================

def test_session_sharder_empty_dialogue():
    """Verifies handling of empty message lists."""
    sharder = SessionSharder()
    compacted, meta = sharder.shard_dialogue([])
    assert compacted == []
    assert meta["sharded"] is False
    assert meta["original_chars"] == 0


def test_session_sharder_preserves_system_prompt_sacrosanct():
    """System prompt must NEVER be modified or masked regardless of length or position."""
    sharder = SessionSharder(unmasked_turn_lag=1, stale_assistant_max_len=100)
    sys_content = "CRITICAL IMMUTABLE SYSTEM PROMPT WITH SOVEREIGNTY INVARIANTS " * 20
    messages = [
        {"role": "system", "content": sys_content},
        {"role": "tool", "content": "Tool output 1"},
        {"role": "assistant", "content": "Assistant answer 1"},
        {"role": "user", "content": "User prompt recent"},
    ]

    compacted, meta = sharder.shard_dialogue(messages)

    assert compacted[0]["role"] == "system"
    assert compacted[0]["content"] == sys_content


def test_session_sharder_preserves_unmasked_recent_window():
    """Messages inside the unmasked_turn_lag window (last 3) must remain verbatim."""
    sharder = SessionSharder(unmasked_turn_lag=3)
    messages = [
        {"role": "tool", "content": "Old tool output to be masked"},
        {"role": "user", "content": "Recent question 1"},
        {"role": "assistant", "content": "Recent answer 2"},
        {"role": "tool", "content": "Recent tool result 3"},
    ]

    compacted, meta = sharder.shard_dialogue(messages)

    # First tool message (index 0, outside last 3) must be masked
    assert "[OBSERVATION MASKED: Turn #1" in compacted[0]["content"]
    # Last 3 messages must remain verbatim
    assert compacted[1]["content"] == "Recent question 1"
    assert compacted[2]["content"] == "Recent answer 2"
    assert compacted[3]["content"] == "Recent tool result 3"


def test_session_sharder_compacts_stale_assistant_messages():
    """Stale assistant responses > 1000 chars must be compacted to head (300) + tail (200)."""
    sharder = SessionSharder(unmasked_turn_lag=2, stale_assistant_max_len=1000)
    stale_head = "HEAD_" + ("H" * 295)
    stale_tail = ("T" * 195) + "_TAIL"
    middle = "M" * 4000
    long_content = f"{stale_head}{middle}{stale_tail}"

    messages = [
        {"role": "user", "content": "Initial query"},
        {"role": "assistant", "content": long_content},
        {"role": "user", "content": "Recent turn 1"},
        {"role": "assistant", "content": "Recent turn 2"},
    ]

    compacted, meta = sharder.shard_dialogue(messages)

    asst_msg = compacted[1]
    assert asst_msg["role"] == "assistant"
    assert "STALE ASSISTANT OUTPUT COMPACTED" in asst_msg["content"]
    assert asst_msg["content"].startswith(stale_head[:300])
    assert asst_msg["content"].endswith(stale_tail[-200:])
    assert meta["compacted_assistant_count"] == 1
    assert meta["chars_saved"] > 3500


def test_session_sharder_full_metadata_contract():
    """Verifies that returned metadata contains all required metrics."""
    sharder = SessionSharder(unmasked_turn_lag=2)
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "tool", "content": "Old tool output"},
        {"role": "assistant", "content": "A" * 2000},
        {"role": "user", "content": "Recent question"},
        {"role": "assistant", "content": "Recent response"},
    ]

    compacted, meta = sharder.shard_dialogue(messages)

    assert meta["sharded"] is True
    assert meta["original_chars"] > meta["compacted_chars"]
    assert meta["chars_saved"] > 0
    assert meta["entropy_after"] <= meta["entropy_before"]
    assert meta["masked_observations_count"] == 1
    assert meta["compacted_assistant_count"] == 1
    assert meta["total_turns"] == 5
    assert meta["unmasked_lag"] == 2


# =====================================================================
# 6. Dual NotebookLM Workspaces & Sync Bridge Tests
# =====================================================================

def test_notebooklm_workspace_authoritative_ids():
    """Verifies Semester 1 and Semester 3 workspace invariants."""
    bridge = NotebookLMSyncBridge()

    sem1 = bridge.get_workspace_for_semester(1)
    assert sem1.workspace_id == "11f9bc29-99a1-4bab-aac3-cfbee9e4e553"
    assert sem1.semester == 1
    assert len(sem1.sources) == 9
    assert "STUDY_GUIDE_MATH_ANALYSIS.md" in sem1.sources
    assert "STUDY_GUIDE_LINEAR_ALGEBRA.md" in sem1.sources
    assert "STUDY_GUIDE_MATH_LOGIC.md" in sem1.sources
    assert "STUDY_GUIDE_ENGLISH_IT.md" in sem1.sources

    sem3 = bridge.get_workspace_for_semester(3)
    assert sem3.workspace_id == "99b01f4d-b3b1-44ee-8f54-2ab7a28d617f"
    assert sem3.semester == 3
    assert len(sem3.sources) == 7
    assert "AI_Lab_01_Var_06.md" in sem3.sources
    assert "Template_Report_GOST.md" in sem3.sources


def test_notebooklm_workspace_resolution_by_context():
    """Verifies dynamic routing between Semester 1 and Semester 3."""
    bridge = NotebookLMSyncBridge()

    # Math analysis / linear algebra context -> Sem 1
    nb1 = bridge.resolve_workspace("Solve linear algebra system with Gauss elimination")
    assert nb1.workspace_id == NOTEBOOK_SEM1_ID

    nb_math = bridge.resolve_workspace("Calculate limit and derivative in calculus")
    assert nb_math.workspace_id == NOTEBOOK_SEM1_ID

    nb_eng = bridge.resolve_workspace("Prepare English vocabulary glossary for IT")
    assert nb_eng.workspace_id == NOTEBOOK_SEM1_ID

    # DC Circuit / TOE / Variant 6 -> Sem 3
    nb3 = bridge.resolve_workspace("Calculate DC Circuit with Kirchhoff laws for Variant 6")
    assert nb3.workspace_id == NOTEBOOK_SEM3_ID

    nb_toe = bridge.resolve_workspace("Check node potential method power balance in TOE")
    assert nb_toe.workspace_id == NOTEBOOK_SEM3_ID


def test_notebooklm_grounded_query_prompt():
    """Verifies formatting of grounded citation prompts."""
    bridge = NotebookLMSyncBridge()
    sem3 = bridge.get_workspace_for_semester(3)
    prompt = bridge.format_grounded_citation_prompt(sem3, "What are resistances for Var 6?")

    assert NOTEBOOK_SEM3_ID in prompt
    assert "AI_Lab_01_Var_06.md" in prompt
    assert "What are resistances for Var 6?" in prompt


# =====================================================================
# 7. 30 TB Drive Vault Sync Mappings Tests
# =====================================================================

def test_drive_vault_bucket_mappings():
    """Verifies that all required 30TB Vault buckets exist in mapping."""
    for expected_key in [
        "checkpoints",
        "sdm_memory",
        "datasets",
        "flywheel_runs",
        "notebooklm_sources",
        "reflexion_wiki",
        "escalations",
        "jules_dispatch",
    ]:
        assert expected_key in VAULT_BUCKET_MAPPINGS


def test_drive_vault_sync_payload_with_local_failover(tmp_path):
    """Verifies payload synchronization and local failover directory creation."""
    local_vault = tmp_path / "local_vault"
    mapping = DriveVaultSyncMapping(cloud_root=tmp_path / "non_existent_drive", local_root=local_vault)

    assert mapping.is_cloud_mounted() is False
    res = mapping.sync_payload(
        bucket_key="checkpoints",
        filename="model_weights_epoch_01.bin",
        content=b"\x00\x01\x02\x03\x04\x05",
        metadata={"epoch": 1, "loss": 0.042},
    )

    assert res.success is True
    assert res.bytes_synced == 6
    assert res.target_path.exists()
    assert (local_vault / "01_model_checkpoints" / "model_weights_epoch_01.bin").exists()
    assert (local_vault / "01_model_checkpoints" / "model_weights_epoch_01.bin.meta.json").exists()


def test_cloud_bridge_sync_notebook_source(tmp_path):
    """Verifies syncing grounding documents into designated NotebookLM sources bucket."""
    bridge = CloudBridge(cloud_vault_root=tmp_path / "cloud_drive", local_vault_root=tmp_path / "local_vault")

    res = bridge.sync_notebook_source(
        semester=3,
        filename="DC_Circuit_Var_6_Reference.md",
        content="# DC Circuit Var 6 Grounding Guide\nR1=64, R2=98, R3=30",
    )

    assert res.success is True
    assert "05_notebooklm_sources" in str(res.target_path)
    assert res.metadata["semester"] == 3
    assert res.metadata["target_workspace"] == NOTEBOOK_SEM3_ID


def test_cloud_bridge_status_telemetry(tmp_path):
    """Verifies comprehensive status report of CloudBridge."""
    bridge = CloudBridge(local_vault_root=tmp_path / "vault")
    status = bridge.get_sync_status()

    assert "cloud_vault_mounted" in status
    assert "notebook_sem1" in status
    assert status["notebook_sem1"]["id"] == NOTEBOOK_SEM1_ID
    assert status["notebook_sem3"]["id"] == NOTEBOOK_SEM3_ID
    assert len(status["buckets"]) >= 6


# =====================================================================
# 8. Automated Google Jules Remediation Payload Tests (EscalationGate)
# =====================================================================

def test_jules_remediation_payload_schema():
    """Verifies JulesRemediationPayload structure and defaults."""
    payload = JulesRemediationPayload(
        task_id="task_fail_01",
        title="Jules Sprint Remediation",
        prompt="Fix invariant violation in Z3 formal proof",
    )

    d = payload.to_dict()
    assert d["task_id"] == "task_fail_01"
    assert d["target"] == "google_jules"
    assert d["url"] == "https://jules.googleapis.com/v1alpha/sessions"
    assert d["prompt"] == "Fix invariant violation in Z3 formal proof"
    assert isinstance(d["timestamp"], float)


def test_build_jules_remediation_payload_from_attempts():
    """Verifies building payload with 3 failed attempts and SMT counterexample."""
    attempts = [
        TaskAttempt("task_jules", 1, 50.0, "h1", "Contract error 1"),
        TaskAttempt("task_jules", 2, 45.0, "h2", "Contract error 2"),
        TaskAttempt("task_jules", 3, 40.0, "h3", "SMT postcondition violation", smt_counterexample={"x": -1}),
    ]

    payload = build_jules_remediation_payload(
        task_id="task_jules",
        reason="3 consecutive failed cycles with non-positive progression.",
        attempts=attempts,
    )

    assert payload.task_id == "task_jules"
    assert "Autonomous Remediation Sprint: task_jules" in payload.title
    assert payload.target == "google_jules"
    assert "AUTONOMOUS REMEDIATION DIRECTIVE" in payload.prompt
    assert "Consecutive Failed Cycles: 3" in payload.prompt
    assert '"x": -1' in payload.prompt
    assert payload.remediation_plan["consecutive_failures"] == 3
    assert payload.remediation_plan["last_score"] == 40.0


def test_escalation_briefing_renders_jules_section_on_three_consecutive_cycles(tmp_path):
    """Verifies that Section 5 for Google Jules is rendered when 3 consecutive cycles trip."""
    generator = EscalationBriefingGenerator(vault_path=tmp_path / "vault", local_path=tmp_path / "local")
    task_id = "jules_trip_task"
    attempts = [
        TaskAttempt(task_id, 1, 55.0, "ha1", "Fail 1"),
        TaskAttempt(task_id, 2, 50.0, "ha2", "Fail 2"),
        TaskAttempt(task_id, 3, 45.0, "ha3", "Fail 3"),
    ]

    briefing = generator.render_briefing(
        task_id=task_id,
        reason="3 consecutive failed cycles with non-positive progression.",
        attempts=attempts,
    )

    assert "## 5. Automated Cloud Remediation Dispatch (Google Jules Tier 1)" in briefing
    assert "https://jules.googleapis.com/v1alpha/sessions" in briefing
    assert "AUTOMATED REMEDIATION PAYLOAD STAGED" in briefing
    assert generator.last_jules_payload is not None
    assert generator.last_jules_payload.task_id == task_id


def test_escalation_briefing_does_not_render_jules_on_single_unrelated_freeze(tmp_path):
    """When task is frozen due to a non-consecutive trip (e.g. single prerequisite missing), Jules is not auto-dispatched."""
    generator = EscalationBriefingGenerator(vault_path=tmp_path / "vault", local_path=tmp_path / "local")
    task_id = "single_cred_task"
    attempts = [
        TaskAttempt(task_id, 1, 0.0, "hc1", missing_prerequisite="GITHUB_TOKEN"),
    ]

    briefing = generator.render_briefing(
        task_id=task_id,
        reason="Immediate halt: missing external prerequisite (GITHUB_TOKEN)",
        attempts=attempts,
    )

    assert "## 5. Automated Cloud Remediation Dispatch" not in briefing
    assert generator.last_jules_payload is None


def test_jules_payload_persisted_to_vault_on_publish(tmp_path):
    """Verifies that JULES_PAYLOAD_{task_id}.json is written to vault upon 3-cycle trip."""
    primary = tmp_path / "primary"
    local = tmp_path / "local"
    generator = EscalationBriefingGenerator(vault_path=primary, local_path=local)
    task_id = "persist_jules_task"
    attempts = [
        TaskAttempt(task_id, 1, 60.0, "h1", "e1"),
        TaskAttempt(task_id, 2, 50.0, "h2", "e2"),
        TaskAttempt(task_id, 3, 40.0, "h3", "e3"),
    ]

    content, written_paths = generator.generate_and_publish(
        task_id=task_id,
        reason="3 consecutive failed cycles with non-positive progression.",
        attempts=attempts,
    )

    expected_jules_file = primary / f"JULES_PAYLOAD_{task_id}.json"
    assert expected_jules_file.exists()
    payload_data = json.loads(expected_jules_file.read_text(encoding="utf-8"))
    assert payload_data["task_id"] == task_id
    assert payload_data["target"] == "google_jules"


def test_jules_dispatch_staging_fallback(tmp_path):
    """Verifies that dispatch_jules_remediation cleanly stages payload when live API key is absent."""
    generator = EscalationBriefingGenerator(local_path=tmp_path / "local_dispatch")
    payload = JulesRemediationPayload(task_id="staged_test", title="Test Staging", prompt="Test Prompt")

    result = generator.dispatch_jules_remediation(payload, api_key="")

    assert result["status"] == "STAGED"
    assert result["dispatched"] is False
    assert result["staged"] is True
    assert Path(result["staged_path"]).exists()
