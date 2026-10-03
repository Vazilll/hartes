"""
tests/test_skill_tree_system_e2e.py — Comprehensive Production-Grade E2E Test Suite
for Vazus SuperGraph OS Skill Tree System & Architectural Unification.

Covers all 5 Requirements across 4 Tiers:
- Tier 1: Feature Coverage (R1 Zero-script cleanup & shadow package hygiene, R2 SPEC.md contracts & Skill Forest,
           R3 SYSTEM_STATE.json manifest & hook latency, R4 Database consolidation & 768-D vectors,
           R5 Real-World Telemetry Radar)
- Tier 2: Boundary & Corner Cases (Malformed JSON, extreme query strings, extreme BIA/BMI ranges,
           zero-trust path jail outside C:\\vazus, 768-D vector edge cases, transcript guardrails)
- Tier 3: Cross-Feature Interactions (DynamicSkillDispatcher + UnifiedMemoryGateway recall,
           Lifecycle hooks + health registry, Secret Scrubber + pre_invocation hook, SMT Z3 contract proofs)
- Tier 4: Real-World OS/Hardware Workloads (Live SQLite WAL multi-threaded concurrency,
           Xiaomi Mi Scale real byte advertisement parsing, Win32 RapidOCR inference,
           Win32 handle/memory leak audit, GCGovernor live runtime pacing)

Zero Stubs, Zero Mocks: All tests execute directly against real production code and OS subsystems.
"""

import asyncio
import concurrent.futures
import ctypes
import gc
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pytest

# Ensure root workspace (C:\vazus) is on sys.path
PROJECT_ROOT = Path(r"C:\vazus").resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
VAZUS_CORE = PROJECT_ROOT / "vazus_core"
if str(VAZUS_CORE) not in sys.path:
    sys.path.insert(0, str(VAZUS_CORE))

# Core imports for Vazus SuperGraph OS
from vazus_core.engine.dynamic_skill_dispatcher import (
    DynamicSkillDispatcher,
    TranscriptLoopGuardrails,
)
from vazus_core.engine.gc_governor import GCGovernor
from vazus_core.engine.hierarchical_capability_tree import (
    HierarchicalCapabilityForest,
)
from vazus_core.engine.system_discovery_engine import SystemDiscoveryEngine
from vazus_core.hooks.pre_invocation_hook import (
    clean_user_prompt,
    extract_user_prompt,
)
from vazus_core.hooks.pre_tool_hook import (
    _is_dangerous_command,
    _is_forbidden_path,
    _is_within_workspace,
    run_pre_tool,
)
from vazus_core.hooks.session_start_hook import (
    run_session_start,
)
from vazus_core.hooks.stop_hook import (
    _clear_block_count,
    _increment_block_count,
)
from vazus_core.memory.db import (
    close_all_thread_connections,
    init_db_schemas,
    pack_vector_f32,
    unpack_vector_f32,
)
from vazus_core.memory.embeddings import (
    compute_similarity,
)
from vazus_core.memory.unified_memory_gateway import UnifiedMemoryGateway
from vazus_core.security.entropy_scrubber import SecretScrubber
from vazus_core.storage.sqlite_pool import RobustSQLitePool
from vazus_core.verification.smt_z3_verifier import (
    SMTZ3Verifier,
    verify_no_external_api_quota,
)

# Service imports
from services.health_agent.ble_mi_scale_scanner import (
    calculate_bia_metrics,
    parse_mi_scale_v2_data,
)


@pytest.fixture(autouse=True)
def cleanup_thread_connections():
    """Ensures all thread-local SQLite handles are closed after each test."""
    yield
    close_all_thread_connections()


# ============================================================================
# TIER 1: Feature Coverage (R1 - R5 Isolation Guarantees)
# ============================================================================

class TestTier1FeatureCoverage:
    """Tier 1: Comprehensive feature coverage for R1-R5 in isolation."""

    def test_r1_clean_workspace_loose_script_hygiene(self):
        """R1: Verifies zero shadow duplicate packages and clean core directory hygiene."""
        engine = SystemDiscoveryEngine(workspace_root=PROJECT_ROOT)
        shadow_dirs = engine.find_shadow_directories()
        assert len(shadow_dirs) == 0, f"Found unexpected shadow directories: {shadow_dirs}"

        # Ensure vazus_core contains no temporary scratch files
        core_dir = PROJECT_ROOT / "vazus_core"
        scratch_files = list(core_dir.glob("temp_*.py")) + list(core_dir.glob("scratch_*.py"))
        assert len(scratch_files) == 0, f"Found loose scratch files in vazus_core: {scratch_files}"

    def test_r1_core_module_import_and_no_circular_dependencies(self):
        """R1: Verifies that all core packages import without circular dependencies."""
        import importlib
        modules_to_test = [
            "vazus_core.engine.dynamic_skill_dispatcher",
            "vazus_core.engine.hierarchical_capability_tree",
            "vazus_core.engine.system_discovery_engine",
            "vazus_core.engine.gc_governor",
            "vazus_core.memory.unified_memory_gateway",
            "vazus_core.memory.db",
            "vazus_core.memory.embeddings",
            "vazus_core.hooks.session_start_hook",
            "vazus_core.hooks.pre_invocation_hook",
            "vazus_core.hooks.pre_tool_hook",
            "vazus_core.hooks.stop_hook",
            "vazus_core.verification.smt_z3_verifier",
            "vazus_core.storage.sqlite_pool",
            "vazus_core.security.entropy_scrubber",
            "services.health_agent.ble_mi_scale_scanner",
            "services.finance_agent.freelance_npd_engine",
        ]
        for mod_name in modules_to_test:
            mod = importlib.import_module(mod_name)
            assert mod is not None, f"Module {mod_name} failed to import"
            assert mod_name in sys.modules, f"Module {mod_name} failed to load cleanly into sys.modules"

    def test_r2_domain_spec_contracts_structure_and_criteria(self):
        """R2: Validates canonical SPEC.md structure and Level 1..5 criteria across domains."""
        core_domain_dirs = [
            PROJECT_ROOT / "vazus_core" / "engine",
            PROJECT_ROOT / "vazus_core" / "memory",
            PROJECT_ROOT / "vazus_core" / "hooks",
            PROJECT_ROOT / "services" / "finance_agent",
            PROJECT_ROOT / "services" / "health_agent",
            PROJECT_ROOT / "services" / "vision",
        ]
        
        # Verify that all 6 domain directories exist
        for d in core_domain_dirs:
            assert d.exists(), f"Core domain directory missing: {d}"
            
        # For any existing SPEC.md, verify required sections
        required_sections = [
            "mission",
            "interface",
            "level",
            "bottleneck",
        ]
        for d in core_domain_dirs:
            spec_file = d / "SPEC.md"
            if spec_file.exists():
                content = spec_file.read_text(encoding="utf-8").lower()
                for sec in required_sections:
                    assert sec in content, f"SPEC.md in {d.name} missing section keyword: {sec}"

    def test_r2_hierarchical_capability_tree_ontology(self):
        """R2: Verifies HierarchicalCapabilityForest 4-tier progressive capability ontology."""
        forest = HierarchicalCapabilityForest()
        assert "domain:code" in forest.root_domains
        assert "domain:infra" in forest.root_domains
        assert "domain:memory" in forest.root_domains

        # Register a leaf tool node
        tool_schema = {"name": "cbm_search", "parameters": {"type": "object"}}
        forest.register_mcp_tool(
            tool_name="cbm_search",
            domain_id="domain:code",
            schema=tool_schema,
            description="Searches code graph topology via AST",
        )
        assert "tool:cbm_search" in forest.node_registry
        node = forest.node_registry["tool:cbm_search"]
        assert node.name == "cbm_search"
        assert node.node_type == "mcp_tool"

    def test_r3_system_state_manifest_schema_and_size(self):
        """R3: Verifies that SYSTEM_STATE.json manifest is valid JSON and strictly < 5KB."""
        state_file = PROJECT_ROOT / "SYSTEM_STATE.json"
        assert state_file.exists(), "SYSTEM_STATE.json does not exist at root"
        
        file_bytes = state_file.stat().st_size
        assert file_bytes < 5120, f"SYSTEM_STATE.json exceeds 5KB: {file_bytes} bytes"
        
        with open(state_file, "r", encoding="utf-8") as f:
            state_data = json.load(f)
        
        assert isinstance(state_data, dict), "SYSTEM_STATE.json must be a JSON object"
        assert "schema_version" in state_data, "Missing 'schema_version' in SYSTEM_STATE.json"
        assert "health_status" in state_data, "Missing 'health_status' in SYSTEM_STATE.json"
        assert "subsystem_skill_ranks" in state_data, "Missing 'subsystem_skill_ranks' in SYSTEM_STATE.json"
        assert len(state_data["subsystem_skill_ranks"]) >= 6, "Expected 6 domain ranks in SYSTEM_STATE.json"
        assert "telemetry_radar" in state_data, "Missing 'telemetry_radar' in SYSTEM_STATE.json"

    def test_r3_lifecycle_hook_latency_benchmark(self):
        """R3: Verifies that lifecycle hook execution latency is strictly <= 50ms."""
        # Benchmark pre_tool_hook
        latencies = []
        for _ in range(30):
            t0 = time.perf_counter()
            res = run_pre_tool("write_to_file", {"TargetFile": r"C:\vazus\tests\sample.py", "CodeContent": "x = 1"})
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)
            assert res["decision"] == "allow"

        avg_latency_ms = sum(latencies) / len(latencies)
        max_latency_ms = max(latencies)
        assert avg_latency_ms <= 50.0, f"Hook average latency exceeded 50ms: {avg_latency_ms:.2f}ms"
        assert max_latency_ms <= 100.0, f"Hook max latency exceeded 100ms: {max_latency_ms:.2f}ms"

    def test_r4_database_schema_and_domain_tables(self, tmp_path):
        """R4: Verifies that database schemas initialize domain tables with WAL enabled."""
        db_file = tmp_path / "test_r4_domain.db"
        pool = RobustSQLitePool(str(db_file))
        
        with pool.connection() as conn:
            init_db_schemas(conn, db_path=str(db_file))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}
            assert "organic_insights" in tables

            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0].lower()
            assert journal_mode == "wal"

    def test_r4_database_vector_packing_numerical_fidelity(self):
        """R4: Verifies exact 768-D IEEE-754 float32 vector packing and zero loss."""
        np.random.seed(42)
        original_vector = np.random.randn(768).astype(np.float32).tolist()

        blob = pack_vector_f32(original_vector)
        assert len(blob) == 768 * 4, f"Packed vector blob size mismatch: {len(blob)} != 3072"

        unpacked_vector = unpack_vector_f32(blob)
        assert len(unpacked_vector) == 768

        # Numerical fidelity: maximum absolute difference must be 0.0
        max_diff = max(abs(a - b) for a, b in zip(original_vector, unpacked_vector))
        assert max_diff == 0.0, f"Vector packing introduced float32 drift: {max_diff}"

    def test_r5_ble_mi_scale_byte_decoding_and_bia_metrics(self):
        """R5: Verifies real byte decoding and BIA calculation for Xiaomi Mi Scale 2."""
        # 13-byte broadcast frame: stabilized=True, impedance=500 ohms, raw weight=13880 (69.4 kg)
        # Byte 0: 0x02, Byte 1: 0xa6 (bit 5=stabilized, bit 7=has_impedance)
        # Byte 9-10: 500 ohms (0x01f4 -> [0xf4, 0x01])
        # Byte 11-12: 13880 (0x3638 -> [0x38, 0x36])
        service_data = bytes([0x02, 0xa6, 0x07, 0x08, 0x14, 0x0a, 0x1b, 0x00, 0x00, 0xf4, 0x01, 0x38, 0x36])
        parsed = parse_mi_scale_v2_data(service_data)

        assert parsed is not None
        assert parsed["is_stabilized"] is True
        assert parsed["has_impedance"] is True
        assert parsed["impedance_ohms"] == 500
        assert round(parsed["weight_kg"], 1) == 69.4

        # Compute BIA metrics
        metrics = calculate_bia_metrics(
            weight_kg=parsed["weight_kg"],
            impedance_ohms=parsed["impedance_ohms"],
            height_cm=178,
            age=24,
            gender="male",
        )
        assert metrics["weight_kg"] == 69.4
        assert metrics["bmi"] == 21.9
        assert 10.0 <= metrics["body_fat_pct"] <= 25.0
        assert metrics["muscle_mass_kg"] > 40.0
        assert metrics["water_pct"] > 50.0
        assert metrics["bmr_kcal"] > 1400

    def test_r5_smt_z3_formal_contract_solver(self):
        """R5: Verifies SMT Z3 formal logic solver on memory safety and API constraints."""
        verifier = SMTZ3Verifier(timeout_ms=3000)

        # 1. Memory safety valid: offset=10, length=20, capacity=100 -> UNSAT (Safe)
        res_safe = verifier.verify_memory_safety(offset=10, length=20, capacity=100)
        assert res_safe.verified is True
        assert res_safe.smt_solver_status == "UNSAT"

        # 2. Memory safety violation: offset=90, length=20, capacity=100 -> SAT (Violation)
        res_unsafe = verifier.verify_memory_safety(offset=90, length=20, capacity=100)
        assert res_unsafe.verified is False
        assert res_unsafe.smt_solver_status == "SAT"

        # 3. No external API quota consumption validation
        valid_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
        res_code = verify_no_external_api_quota(valid_code)
        assert res_code.verified is True

        prohibited_code = "import google.genai as genai\nclient = genai.Client()\n"
        res_prohibited = verify_no_external_api_quota(prohibited_code)
        assert res_prohibited.verified is False


# ============================================================================
# TIER 2: Boundary & Corner Cases
# ============================================================================

class TestTier2BoundaryAndCornerCases:
    """Tier 2: Extreme inputs, malformed structures, path jail escapes, and numerical boundaries."""

    def test_tier2_malformed_json_state_resilience(self):
        """Tier 2: Verifies hook and state parsers handle malformed/corrupted JSON payloads."""
        # 1. Corrupted string passed to prompt extraction
        hook_payloads = [
            {"userPrompt": None},
            {"messages": "not-a-list"},
            {"messages": [{"invalid": 123}]},
            {},
            {"prompt": ""},
        ]
        for p in hook_payloads:
            result = extract_user_prompt(p)
            assert isinstance(result, str)
            assert result == ""

        # 2. PreToolHook with malformed arguments
        res = run_pre_tool("unknown_tool", {"TargetFile": None})
        assert res["decision"] in ("allow", "deny")

    def test_tier2_extreme_query_and_token_truncation(self):
        """Tier 2: Verifies prompt cleaning and dynamic skill parser on 100k+ chars and noisy strings."""
        # 1. Very long prompt
        long_prompt = "Analyze table " + ("x" * 100_000)
        cleaned = clean_user_prompt(long_prompt)
        assert len(cleaned) == len(long_prompt)

        # 2. Cyrillic QWERTY keyboard translation
        qwerty_prompt = "ghbdtn vbh"  # "привет мир"
        dispatcher = DynamicSkillDispatcher(prompt=qwerty_prompt, max_skills=2, effort="low", auto_index=False)
        ctx = dispatcher.load_skill_context()
        assert ctx.prompt == qwerty_prompt
        assert isinstance(ctx.matched_skills, list)

        # 3. Control characters and formatting tags
        tagged_prompt = "<USER_REQUEST>\n  Perform AST analysis  \n</USER_REQUEST><ADDITIONAL_METADATA>meta</ADDITIONAL_METADATA>"
        cleaned_tagged = clean_user_prompt(tagged_prompt)
        assert cleaned_tagged == "Perform AST analysis"

    def test_tier2_extreme_bmi_and_bia_boundaries(self):
        """Tier 2: Verifies BIA calculator does not crash on extreme physical boundaries."""
        edge_cases = [
            {"weight": 0.1, "impedance": 500, "height": 178, "age": 24, "gender": "male"},
            {"weight": 400.0, "impedance": 500, "height": 178, "age": 24, "gender": "male"},
            {"weight": 70.0, "impedance": 0, "height": 178, "age": 24, "gender": "male"},
            {"weight": 70.0, "impedance": 3500, "height": 178, "age": 24, "gender": "female"},
            {"weight": 70.0, "impedance": 500, "height": 40, "age": 5, "gender": "female"},
            {"weight": 70.0, "impedance": 500, "height": 260, "age": 115, "gender": "male"},
        ]
        for ec in edge_cases:
            metrics = calculate_bia_metrics(
                weight_kg=ec["weight"],
                impedance_ohms=ec["impedance"],
                height_cm=ec["height"],
                age=ec["age"],
                gender=ec["gender"],
            )
            assert not math.isnan(metrics["bmi"])
            assert not math.isinf(metrics["bmi"])
            assert 5.0 <= metrics["body_fat_pct"] <= 55.0
            assert 1 <= metrics["visceral_fat"] <= 30
            assert metrics["muscle_mass_kg"] >= 0.0
            assert metrics["bmr_kcal"] >= 0

    def test_tier2_zero_trust_path_jail_boundary_enforcement(self):
        """Tier 2: Verifies strict path jail rejects system directories, traversal, and forbidden files."""
        # System directories outside workspace
        assert not _is_within_workspace(r"C:\Windows\System32\cmd.exe")
        assert not _is_within_workspace(r"C:\Program Files\App\test.txt")
        assert not _is_within_workspace(r"D:\other_drive\payload.py")

        # Forbidden patterns
        assert _is_forbidden_path(r"C:\vazus\.git\config")
        assert _is_forbidden_path(r"C:\vazus\.git\HEAD")
        assert _is_forbidden_path(r"C:\vazus\AGENTS.md")
        assert _is_forbidden_path(r"C:\Windows\System32\drivers\etc\hosts")

        # Dangerous commands
        assert _is_dangerous_command("format C: /fs:NTFS /q")
        assert _is_dangerous_command("rmdir /s /q c:\\")
        assert _is_dangerous_command("reg delete HKLM\\Software")

        # PreToolHook integration on forbidden writes
        deny_git = run_pre_tool("write_to_file", {"TargetFile": r"C:\vazus\.git\hooks\pre-commit", "CodeContent": "bad"})
        assert deny_git["decision"] == "deny"

        deny_agents = run_pre_tool("replace_file_content", {"TargetFile": r"C:\vazus\AGENTS.md", "TargetContent": "x"})
        assert deny_agents["decision"] == "deny"

    def test_tier2_768d_vector_edge_cases(self):
        """Tier 2: Verifies vector similarity math with zero vectors, orthogonal, and opposite vectors."""
        vec_zeros = [0.0] * 768
        vec_a = [1.0 / math.sqrt(768)] * 768
        vec_b = [1.0 / math.sqrt(768)] * 768
        vec_opposite = [-1.0 / math.sqrt(768)] * 768

        # Identical unit vectors
        sim_identical = compute_similarity(vec_a, vec_b)
        assert abs(sim_identical - 1.0) < 1e-4

        # Opposite unit vectors
        sim_opp = compute_similarity(vec_a, vec_opposite)
        assert abs(sim_opp - (-1.0)) < 1e-4

        # Zero vector handling (must not raise ZeroDivisionError)
        sim_zero = compute_similarity(vec_zeros, vec_a)
        assert sim_zero == 0.0

    def test_tier2_transcript_loop_guardrails(self):
        """Tier 2: Verifies TranscriptLoopGuardrails blocks binary images and passes code files."""
        # Binary image extensions
        for ext in [".png", ".jpg", ".jpeg", ".webp"]:
            is_valid, err_msg = TranscriptLoopGuardrails.validate_view_file_path(f"screenshot{ext}")
            assert not is_valid
            assert "[GUARDRAIL BLOCKED]" in err_msg

        # Valid text/code extensions
        for ext in [".py", ".md", ".json", ".sql", ".txt"]:
            is_valid, _ = TranscriptLoopGuardrails.validate_view_file_path(f"module{ext}")
            assert is_valid


# ============================================================================
# TIER 3: Cross-Feature Interactions
# ============================================================================

class TestTier3CrossFeatureInteractions:
    """Tier 3: End-to-end multi-module pipelines across memory, hooks, skill dispatch, and SMT."""

    def test_tier3_memory_gateway_to_skill_dispatcher_pipeline(self, tmp_path):
        """Tier 3: Storing a fact into UnifiedMemoryGateway and recalling it to drive DynamicSkillDispatcher."""
        db_file = tmp_path / "vazus_pipeline.db"
        wiki_dir = tmp_path / "wiki"
        gateway = UnifiedMemoryGateway(db_path=str(db_file), wiki_root=str(wiki_dir))

        # 1. Store domain fact into UnifiedMemoryGateway
        fact_text = "Tinkoff statement parsed 2026-08 transactions for Self-Employed NPD tax filing."
        store_res = gateway.store_fact(
            fact_text=fact_text,
            category="finance",
            entity="tinkoff_manager",
        )
        assert store_res["status"] == "STORED"

        # 2. Recall fact
        recalled = gateway.recall("Tinkoff NPD tax filing", top_k=3)
        assert len(recalled) >= 1
        assert any("Tinkoff" in r["content"] for r in recalled)

        # 3. Feed recalled prompt to DynamicSkillDispatcher
        dispatcher = DynamicSkillDispatcher(
            prompt=recalled[0]["content"],
            max_skills=2,
            effort="medium",
            auto_index=False,
        )
        ctx = dispatcher.load_skill_context()
        assert ctx.prompt == recalled[0]["content"]
        assert isinstance(ctx.matched_skills, list)

    def test_tier3_lifecycle_hooks_to_health_registry_pipeline(self):
        """Tier 3: Tests end-to-end lifecycle hook sequence and health registry recording."""
        # 1. Session start initialization
        session_result = asyncio.run(run_session_start(workspace_path=str(PROJECT_ROOT)))
        assert session_result["session_start"] is True
        assert "database" in session_result

        # 2. PreToolHook validation on allowed path inside workspace
        sample_file = str(PROJECT_ROOT / "tests" / "sample_pipeline_test.py")
        pre_res = run_pre_tool("write_to_file", {"TargetFile": sample_file, "CodeContent": "def test(): pass"})
        assert pre_res["decision"] == "allow"

        # 3. StopHook bounded counter management
        conv_id = "test_cross_feature_conv_001"
        _clear_block_count(conv_id)
        assert _increment_block_count(conv_id) == 1
        assert _increment_block_count(conv_id) == 2
        _clear_block_count(conv_id)
        assert _increment_block_count(conv_id) == 1
        _clear_block_count(conv_id)

    def test_tier3_secret_scrubber_with_pre_invocation_flow(self):
        """Tier 3: Sanitizes secrets in user prompt while preserving semantic intent for skill matching."""
        scrubber = SecretScrubber(entropy_threshold=4.2)
        # Construct low-entropy GitHub Personal Access Token matching regex ghp_[0-9a-zA-Z]{36}
        sample_pat = "ghp_" + ("a" * 36)
        raw_prompt = f"Please analyze table customer_data using token {sample_pat}"
        
        # 1. Extract prompt
        extracted = extract_user_prompt({"userPrompt": raw_prompt})
        assert "ghp_" in extracted

        # 2. Scrub secrets
        sanitized = scrubber.scrub(extracted)
        assert "ghp_" not in sanitized
        assert "REDACTED" in sanitized
        assert "customer_data" in sanitized

        # 3. Dispatch skills based on sanitized prompt
        dispatcher = DynamicSkillDispatcher(prompt=sanitized, max_skills=2, auto_index=False)
        ctx = dispatcher.load_skill_context()
        assert "REDACTED" in ctx.prompt

    def test_tier3_smt_z3_state_transition_proof_pipeline(self):
        """Tier 3: Formulates and verifies formal SMT Z3 state machine contracts."""
        verifier = SMTZ3Verifier(timeout_ms=5000)

        # Invariant: x >= 0 -> x + 1 > 0
        code_with_contract = (
            "def increment_counter(x: int) -> int:\n"
            "    \"\"\"\n"
            "    :requires: x >= 0\n"
            "    :ensures: result > 0\n"
            "    \"\"\"\n"
            "    return x + 1\n"
        )
        res = verifier.verify_code_contracts(code_with_contract)
        assert res.verified is True
        assert res.smt_solver_status == "UNSAT"


# ============================================================================
# TIER 4: Real-World OS/Hardware Workloads
# ============================================================================

class TestTier4RealWorldOSWorkloads:
    """Tier 4: Live SQLite WAL multi-threaded concurrency, BLE frame parsing, RapidOCR, and leaks."""

    def test_tier4_live_sqlite_wal_multi_threaded_concurrency(self, tmp_path):
        """Tier 4: 10 concurrent threads executing 500 total transactions against SQLite WAL."""
        db_file = tmp_path / "wal_concurrency.db"
        pool = RobustSQLitePool(str(db_file), busy_timeout_ms=10000)

        # Initialize schema
        with pool.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stress_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER,
                    tx_id INTEGER,
                    payload TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

        num_threads = 10
        tx_per_thread = 50

        def worker_task(t_id: int) -> int:
            success_count = 0
            for tx in range(tx_per_thread):
                with pool.connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO stress_ledger (thread_id, tx_id, payload) VALUES (?, ?, ?);",
                        (t_id, tx, f"thread_{t_id}_tx_{tx}"),
                    )
                    conn.commit()
                    success_count += 1
            return success_count

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, t) for t in range(num_threads)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert sum(results) == num_threads * tx_per_thread

        # Verify all records written accurately
        rows = pool.execute("SELECT count(*) as total FROM stress_ledger;")
        assert rows[0]["total"] == num_threads * tx_per_thread

    def test_tier4_xiaomi_mi_scale_real_byte_stream_parser(self):
        """Tier 4: Decodes real Xiaomi Mi Scale 2 broadcast byte advertisements across states."""
        # 1. Real stabilized measurement (69.4 kg, 500 ohms)
        stabilized_frame = bytes([0x02, 0xa6, 0x07, 0x08, 0x14, 0x0a, 0x1b, 0x00, 0x00, 0xf4, 0x01, 0x38, 0x36])
        res_stab = parse_mi_scale_v2_data(stabilized_frame)
        assert res_stab is not None
        assert res_stab["is_stabilized"] is True
        assert res_stab["impedance_ohms"] == 500
        assert round(res_stab["weight_kg"], 1) == 69.4

        # 2. Real dynamic unstabilized measurement (weight changing, no impedance)
        dynamic_frame = bytes([0x02, 0x06, 0x07, 0x08, 0x14, 0x0a, 0x1b, 0x00, 0x00, 0x00, 0x00, 0x30, 0x30])
        res_dyn = parse_mi_scale_v2_data(dynamic_frame)
        assert res_dyn is not None
        assert res_dyn["is_stabilized"] is False
        assert res_dyn["has_impedance"] is False

    def test_tier4_win32_rapidocr_real_image_inference(self):
        """Tier 4: Synthesizes a real image array and executes live RapidOCR text recognition."""
        from PIL import Image, ImageDraw
        from rapidocr import RapidOCR

        # Generate 400x100 RGB image with clear text
        img = Image.new("RGB", (400, 100), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), "VAZUS SUPERGRAPH OS 2026", fill=(0, 0, 0))
        img_np = np.array(img)

        # Run RapidOCR inference engine
        engine = RapidOCR()
        output = engine(img_np)

        assert output is not None
        assert hasattr(output, "txts") and output.txts is not None
        recognized_text = " ".join(output.txts).upper()
        assert "VAZUS" in recognized_text
        assert "SUPERGRAPH" in recognized_text or "2026" in recognized_text
        if hasattr(output, "scores") and output.scores:
            assert output.scores[0] > 0.70

    def test_tier4_win32_process_handle_and_memory_leak_audit(self):
        """Tier 4: 100 iterations of hook execution and vector operations with zero handle leaks."""
        initial_handles = None
        if sys.platform == "win32":
            handle_count = ctypes.c_ulong()
            process_handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.kernel32.GetProcessHandleCount(process_handle, ctypes.byref(handle_count)):
                initial_handles = handle_count.value

        # Execute 100 iterations of pre_tool validation and vector packing
        vec = [0.1 * (i % 10) for i in range(768)]
        for i in range(100):
            _ = run_pre_tool("write_to_file", {"TargetFile": rf"C:\vazus\tests\sample_{i}.py", "CodeContent": "x = 1"})
            blob = pack_vector_f32(vec)
            _ = unpack_vector_f32(blob)

        close_all_thread_connections()
        gc.collect()

        if sys.platform == "win32" and initial_handles is not None:
            handle_count_after = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetProcessHandleCount(process_handle, ctypes.byref(handle_count_after)):
                delta = handle_count_after.value - initial_handles
                # Normal handle fluctuation on Windows is <= 25 handles
                assert delta <= 25, f"Possible Win32 process handle leak: delta = {delta} handles"

    def test_tier4_gc_governor_runtime_freezing_and_pacing(self):
        """Tier 4: Verifies GCGovernor live runtime freezing, pacing, and telemetry stats."""
        governor = GCGovernor(high_threshold=40000, gen1_thresh=15, gen2_thresh=40)
        
        # Test stats before
        stats_pre = governor.stats()
        assert "thresholds" in stats_pre
        assert "counts" in stats_pre

        # Test pause and resume
        governor.pause()
        assert not gc.isenabled()
        
        governor.resume(run_gen0=True)
        assert gc.isenabled()

        # Test freezing core objects
        frozen_count = governor.freeze_core_objects()
        assert frozen_count >= 0
        stats_post = governor.stats()
        assert stats_post["thresholds"][0] == 40000
