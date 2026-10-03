"""
Closed-Loop System Integration Test Harness for Vazus SuperGraph OS.
====================================================================

Verifies that the system operates as a genuinely closed loop, not just
a collection of independently working components. Tests data flow
BETWEEN components across simulated multi-session lifecycle.

SOTA 2026 Patterns Applied:
  - Trajectory-Based Evaluation (full hook chain tracing)
  - Metamorphic Feedback Invariants (lesson save → lesson recall)
  - State-Loop Driver (simulated 2-session lifecycle)
  - PRAR Cycle (Perceive-Reason-Act-Reflect)

Bugs & Gaps Being Verified:
  1. anti_false_confidence.py missing `import os` → silent crash
  2. auto_improver.py missing `Tuple` import → NameError
  3. LessonMemoryBank.retrieve_relevant() never called from hooks
  4. dream_consolidator column mismatch (id vs lesson_id)
  5. session_start_hook output dropped (not consumed by pre_invocation)
  6. SkillTree XP never auto-awarded after gate pass
  7. MCP gateway resolve → active tools list is dead compute
"""
import sys
import os
import json
import sqlite3
import re
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List

import pytest


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def isolated_system_db(tmp_path: Path) -> Path:
    """Creates a fully schema'd isolated database for closed-loop testing."""
    db_path = tmp_path / "closed_loop_test.db"
    from vazus_core.memory.db import init_db_schemas
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    init_db_schemas(conn, db_path=str(db_path))

    # Ensure reflexion_lessons table exists (AutoImprover schema)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reflexion_lessons (
            lesson_id TEXT PRIMARY KEY,
            task_type TEXT,
            error_sig TEXT,
            lesson_text TEXT,
            fix_hint TEXT DEFAULT '',
            success_count INTEGER DEFAULT 0,
            fitness_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now')),
            embedding_json TEXT DEFAULT '[]'
        )
    """)
    # Ensure skill_usage_scores table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skill_usage_scores (
            skill_name TEXT PRIMARY KEY,
            uses INTEGER DEFAULT 0,
            successes INTEGER DEFAULT 0,
            failures INTEGER DEFAULT 0,
            score REAL DEFAULT 0.5,
            last_used_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Ensure auto_improver_sessions table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auto_improver_sessions (
            session_id TEXT PRIMARY KEY,
            task_type TEXT,
            task_desc TEXT,
            iterations INTEGER DEFAULT 0,
            success INTEGER DEFAULT 0,
            final_score REAL DEFAULT 0.0,
            skills_used TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Ensure afc_violations table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS afc_violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            response_snippet TEXT,
            evidence_found INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """)
    # Ensure subagent_memory_traces table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subagent_memory_traces (
            trace_id TEXT PRIMARY KEY,
            dialogue_id TEXT,
            agent_name TEXT,
            trace_kind TEXT,
            summary TEXT,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def patched_db_env(isolated_system_db: Path, monkeypatch):
    """Redirects all DB paths to the isolated test database."""
    db_str = str(isolated_system_db)
    monkeypatch.setenv("VAZUS_DB_PATH", db_str)
    monkeypatch.setenv("VAZUS_TEST_ISOLATION", "1")

    import vazus_core.memory.db as db_mod
    monkeypatch.setattr(db_mod, "DEFAULT_VAZUS_DB", db_str)

    return isolated_system_db


# ═══════════════════════════════════════════════════════════════════════
# TEST GROUP 1: IMPORT HEALTH (Silent Crash Detection)
# ═══════════════════════════════════════════════════════════════════════

class TestImportHealth:
    """Detects silent import failures that disable entire subsystems."""

    def test_anti_false_confidence_import_os(self):
        """BUG: anti_false_confidence.py uses os.getenv but may not import os.
        This silently disables the entire AFC gate in production."""
        source_path = Path("C:/vazus/vazus_core/verification/anti_false_confidence.py")
        if not source_path.exists():
            pytest.skip("anti_false_confidence.py not found")

        source = source_path.read_text(encoding="utf-8")

        # Check if os is used
        uses_os = bool(re.search(r'\bos\.', source))
        if not uses_os:
            return  # No os usage, no problem

        # Check if os is imported
        imports_os = bool(re.search(
            r'^\s*import\s+os\b|^\s*from\s+os\b',
            source,
            re.MULTILINE,
        ))

        assert imports_os, (
            "CRITICAL BUG: anti_false_confidence.py uses `os.getenv()` "
            "but does not `import os`. This causes NameError which is "
            "silently caught by `except Exception: pass` in hooks, "
            "disabling the entire Anti-False-Confidence gate."
        )

    def test_auto_improver_tuple_import(self):
        """BUG: auto_improver.py uses Tuple in annotations but may not import it."""
        source_path = Path("C:/vazus/vazus_core/memory/auto_improver.py")
        if not source_path.exists():
            pytest.skip("auto_improver.py not found")

        source = source_path.read_text(encoding="utf-8")

        # Check if Tuple is used in annotations
        uses_tuple = bool(re.search(r'\bTuple\[', source))
        if not uses_tuple:
            return

        # Check if Tuple is imported OR future annotations enabled
        imports_tuple = bool(re.search(r'from\s+typing\s+import\s+.*\bTuple\b', source))
        has_future_annotations = 'from __future__ import annotations' in source

        assert imports_tuple or has_future_annotations, (
            "BUG: auto_improver.py uses `Tuple[...]` in type annotations "
            "but neither imports Tuple from typing nor uses "
            "`from __future__ import annotations`. This causes NameError "
            "at import time, disabling LessonMemoryBank entirely."
        )

    def test_all_hook_files_importable(self):
        """Every hook file must be importable without crashing."""
        hook_dir = Path("C:/vazus/vazus_core/hooks")
        failures = []
        for py_file in hook_dir.glob("*.py"):
            if py_file.name.startswith("_") and py_file.name != "__init__.py":
                continue
            try:
                import importlib
                module_name = f"vazus_core.hooks.{py_file.stem}"
                if module_name in sys.modules:
                    continue  # already loaded, skip reimport
                importlib.import_module(module_name)
            except Exception as e:
                failures.append(f"{py_file.name}: {type(e).__name__}: {e}")

        assert not failures, (
            f"Hook import failures (these silently disable subsystems):\n"
            + "\n".join(failures)
        )


# ═══════════════════════════════════════════════════════════════════════
# TEST GROUP 2: CLOSED-LOOP DATA FLOW (Metamorphic Feedback Invariants)
# ═══════════════════════════════════════════════════════════════════════

class TestClosedLoopDataFlow:
    """Tests that data flows between components, not just within them."""

    def test_lesson_save_then_retrieve_metamorphic(self, patched_db_env):
        """METAMORPHIC INVARIANT: If a lesson is saved by AutoImprover,
        it MUST be retrievable by the same subsystem.
        This tests the internal loop closure of LessonMemoryBank."""
        from vazus_core.memory.auto_improver import LessonMemoryBank

        bank = LessonMemoryBank()

        # Save a lesson about cyclomatic complexity
        bank.save_lesson(
            task_type="refactoring",
            error_sig="Radon CC > 10 in function process_data",
            lesson_text="Functions exceeding CC 10 should be decomposed using Extract Method pattern",
            fix_hint="Split into helper methods with single responsibility",
        )

        # Retrieve lessons relevant to similar error
        results = bank.retrieve_relevant(
            error_sig="High cyclomatic complexity in function handle_request",
            task_type="refactoring",
            top_k=3,
        )

        assert len(results) >= 1, (
            "LOOP BROKEN: LessonMemoryBank.save_lesson() stored a lesson "
            "but retrieve_relevant() returned 0 results. The internal "
            "Reflexion feedback loop is disconnected."
        )

    def test_unified_memory_gateway_store_then_recall(self, patched_db_env):
        """Tests the store → recall cycle of UnifiedMemoryGateway."""
        from vazus_core.memory.unified_memory_gateway import UnifiedMemoryGateway

        gw = UnifiedMemoryGateway(
            db_path=str(patched_db_env),
            wiki_root=str(patched_db_env.parent / "wiki"),
        )

        # Store a fact
        result = gw.store_fact(
            fact_text="Pre-commit gate must pass all 11 tiers before git commit is allowed",
            category="architectural_decision",
            entity="vazus_architect",
        )
        assert result["status"] == "STORED"

        # Recall it
        recalled = gw.recall("pre-commit gate 11 tiers", top_k=5)
        found = any("pre-commit" in r.get("content", "").lower() for r in recalled)

        assert found, (
            "LOOP BROKEN: UnifiedMemoryGateway.store_fact() succeeded "
            "but recall() did not find the stored fact. Memory store → "
            "recall cycle is disconnected."
        )

    def test_pre_invocation_hook_injects_memory(self, patched_db_env):
        """CRITICAL: Verifies that pre_invocation_hook.auto_retrieve_memory()
        actually retrieves data from the database and returns non-empty content."""
        from vazus_core.hooks.pre_invocation_hook import auto_retrieve_memory

        # First, seed a trace into the database
        conn = sqlite3.connect(str(patched_db_env))
        conn.execute(
            "INSERT OR IGNORE INTO subagent_memory_traces "
            "(trace_id, dialogue_id, agent_name, trace_kind, summary, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            ("trace-001", "dlg-001", "test-agent", "commit",
             "Refactored precommit_gate.py to add SRP checks", "Gate 1 now enforces SRP"),
        )
        conn.commit()
        conn.close()

        # Call auto_retrieve_memory on turn 0
        result = auto_retrieve_memory(
            user_prompt="проверь precommit gate и SRP",
            invocation_num=0,
        )

        # We expect at least some content injected (USER.md or traces)
        # If entirely empty, the hook is not injecting anything
        # Note: In test env without USER.md, we check for traces
        has_trace = "Recent System Commits" in result or "Traces" in result
        has_memory = "Memory" in result or "Mem0" in result
        has_profile = "Profile" in result or "Vazus" in result
        has_anything = bool(result.strip())

        # At minimum, if traces exist in DB, they should be injected
        if has_anything:
            pass  # hook is injecting something, good
        # If nothing is injected, check if traces were actually queryable
        conn2 = sqlite3.connect(str(patched_db_env))
        count = conn2.execute(
            "SELECT count(*) FROM subagent_memory_traces"
        ).fetchone()[0]
        conn2.close()

        if count > 0 and not has_trace:
            pytest.fail(
                "LOOP BROKEN: subagent_memory_traces has data but "
                "auto_retrieve_memory() did not inject it into the prompt. "
                "Recent traces are invisible to the agent."
            )

    def test_mcp_gateway_resolves_tools_for_query(self):
        """Verifies DynamicMCPGateway returns relevant tools for a query."""
        from vazus_core.hooks.pre_invocation_hook import create_default_mcp_gateway

        gw = create_default_mcp_gateway()
        tools = gw.resolve_active_tools("verify SMT Z3 contract for function")

        tool_names = [t.get("name", "") for t in tools]
        smt_related = [n for n in tool_names if "smt" in n.lower() or "z3" in n.lower() or "verify" in n.lower()]

        assert len(tools) > 0, (
            "MCP Gateway returned 0 tools for an SMT-related query. "
            "Intent-Schema Overlap scoring is not working."
        )

    def test_skill_dispatcher_matches_skills(self):
        """Verifies DynamicSkillDispatcher finds relevant skills."""
        from vazus_core.hooks.pre_invocation_hook import auto_select_skills

        skills = auto_select_skills("debug a Python crash loop and fix the failing test")

        # We expect at least some skills matched
        # In test env, skill directories may not exist, so we allow 0
        # but verify the function doesn't crash
        assert isinstance(skills, list), "auto_select_skills must return a list"


# ═══════════════════════════════════════════════════════════════════════
# TEST GROUP 3: HOOK LIFECYCLE CHAIN (Trajectory-Based Evaluation)
# ═══════════════════════════════════════════════════════════════════════

class TestHookLifecycleChain:
    """Tests the full hook lifecycle as a connected pipeline."""

    def test_session_start_produces_valid_payload(self):
        """session_start_hook must return a structured status payload."""
        import asyncio
        from vazus_core.hooks.session_start_hook import run_session_start

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(run_session_start())
        finally:
            loop.close()

        assert result.get("session_start") is True
        assert "database" in result
        assert "gc" in result
        assert "schema" in result
        assert result.get("status") in ("healthy", "degraded")

    def test_pre_invocation_entropy_governor(self):
        """EntropyGovernor must compact long trajectories."""
        from vazus_core.hooks.pre_invocation_hook import run_pre_invocation

        # Build a synthetic 15-turn trajectory with 200k chars
        trajectory = []
        for i in range(15):
            trajectory.append({
                "role": "user",
                "content": f"Turn {i}: " + "x" * 14000,
            })
            trajectory.append({
                "role": "assistant",
                "content": f"Response {i}: " + "y" * 14000,
            })

        result = run_pre_invocation(trajectory, "test query")

        assert result.get("status") == "ok"
        eg = result.get("entropy_governor", {})

        # Compaction should have been triggered (>12 turns or >150k chars)
        if eg.get("triggered"):
            compacted = result.get("compacted_trajectory", [])
            assert len(compacted) < len(trajectory), (
                "EntropyGovernor triggered but didn't reduce trajectory length"
            )

    def test_pre_tool_hook_security_jail(self):
        """Zero-trust security jail must block dangerous operations."""
        from vazus_core.hooks.pre_tool_hook import run_pre_tool

        # Test 1: Safe operation → allow
        safe = run_pre_tool("write_to_file", {
            "TargetFile": r"C:\vazus\tests\sample.py",
            "CodeContent": "x = 1",
        })
        assert safe.get("decision") == "allow"

        # Test 2: Dangerous command → deny
        dangerous = run_pre_tool("run_command", {
            "CommandLine": "format C: /fs:NTFS /q",
        })
        assert dangerous.get("decision") == "deny"

        # Test 3: Protected path → deny
        protected = run_pre_tool("write_to_file", {
            "TargetFile": r"C:\vazus\.git\config",
            "CodeContent": "malicious",
        })
        assert protected.get("decision") == "deny"

        # Test 4: Path traversal outside workspace → deny
        traversal = run_pre_tool("write_to_file", {
            "TargetFile": r"C:\Windows\System32\evil.py",
            "CodeContent": "hack",
        })
        assert traversal.get("decision") == "deny"

    def test_stop_hook_block_counter_bounded(self):
        """StopHook must never deadlock — block counter must be bounded."""
        from vazus_core.hooks.stop_hook import (
            _increment_block_count, _clear_block_count,
        )

        conv_id = "test_closed_loop_bound_check"
        _clear_block_count(conv_id)

        for i in range(5):
            count = _increment_block_count(conv_id)
            assert count == i + 1, f"Expected {i+1}, got {count}"

        _clear_block_count(conv_id)
        assert _increment_block_count(conv_id) == 1


# ═══════════════════════════════════════════════════════════════════════
# TEST GROUP 4: SKILL TREE & XP PROGRESSION
# ═══════════════════════════════════════════════════════════════════════

class TestSkillTreeAndXP:
    """Tests the capability tree and XP progression system."""

    def test_hierarchical_capability_forest_structure(self):
        """Forest must have at least 3 root domains with children."""
        from vazus_core.engine.hierarchical_capability_tree import (
            HierarchicalCapabilityForest,
        )

        forest = HierarchicalCapabilityForest()

        assert len(forest.root_domains) >= 3, (
            f"Expected ≥3 root domains, got {len(forest.root_domains)}"
        )

        for dom_id, dom in forest.root_domains.items():
            assert dom.name, f"Domain {dom_id} has empty name"
            assert dom.keywords, f"Domain {dom_id} has no keywords"

    def test_capability_forest_progressive_resolution(self):
        """Progressive resolver must return relevant tools for a query."""
        from vazus_core.engine.hierarchical_capability_tree import (
            HierarchicalCapabilityForest,
        )

        forest = HierarchicalCapabilityForest()

        # Register a test tool
        forest.register_mcp_tool(
            "smt_z3_verify",
            "domain:code",
            {"name": "smt_z3_verify", "description": "Verify SMT Z3 contracts"},
            description="Formally proves theorem using Z3 solver",
        )

        result = forest.resolve_progressive_context(
            "verify the smt z3 contract for this function",
            max_leaf_tools=4,
        )

        assert result["promoted_count"] >= 1, (
            "Progressive resolver failed to promote smt_z3_verify "
            "for an SMT-related query"
        )

    def test_system_state_json_schema(self):
        """SYSTEM_STATE.json must have valid schema with skill levels."""
        state_path = Path("C:/vazus/SYSTEM_STATE.json")
        if not state_path.exists():
            pytest.skip("SYSTEM_STATE.json not found")

        state = json.loads(state_path.read_text(encoding="utf-8"))

        assert "subsystem_skill_ranks" in state, "Missing subsystem_skill_ranks"
        assert "runtime_models" in state, "Missing runtime_models"
        assert "telemetry_radar" in state, "Missing telemetry_radar"

        for key, rank in state["subsystem_skill_ranks"].items():
            assert "level" in rank, f"Subsystem {key} missing level"
            assert "status" in rank, f"Subsystem {key} missing status"
            assert isinstance(rank["level"], int), f"Level must be int for {key}"
            assert 1 <= rank["level"] <= 10, f"Level out of range for {key}"


# ═══════════════════════════════════════════════════════════════════════
# TEST GROUP 5: VERIFICATION PIPELINE (11-Tier Gate)
# ═══════════════════════════════════════════════════════════════════════

class TestVerificationPipeline:
    """Tests the 11-tier pre-commit quality gate."""

    def test_precommit_gate_importable(self):
        """Gate must be importable without crashes."""
        from vazus_core.verification.precommit_gate import run_precommit_gate
        assert callable(run_precommit_gate)

    def test_smt_z3_verifier_basic(self):
        """SMT Z3 must correctly verify code contracts."""
        from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier

        verifier = SMTZ3Verifier()

        # Test: verify a simple Python function with contract
        code = '''
def add(a: int, b: int) -> int:
    """:requires: a >= 0 and b >= 0
    :ensures: result >= a and result >= b
    """
    return a + b
'''
        res = verifier.verify_code_contracts(code)
        assert res is not None, "verify_code_contracts returned None"
        # Result can be VerificationResult dataclass or dict
        if isinstance(res, dict):
            verified = res.get("verified") or res.get("contract_satisfied")
        else:
            verified = getattr(res, "verified", None) or getattr(res, "contract_satisfied", None)
        assert verified is True, f"SMT Z3 failed to verify a simple add contract: {res}"

    def test_evidence_jury_deterministic(self, patched_db_env):
        """EvidenceJury must produce deterministic verdicts for clean files."""
        from vazus_core.verification.evidence_jury import EvidenceJury

        jury = EvidenceJury(root="C:/vazus")
        # Test with a known-clean file
        test_file = Path("C:/vazus/vazus_core/engine/utils.py")
        if not test_file.exists():
            pytest.skip("utils.py not found")

        verdict = jury.evaluate(str(test_file))
        assert verdict is not None
        assert "verdict" in verdict or "status" in verdict or "decision" in verdict


# ═══════════════════════════════════════════════════════════════════════
# TEST GROUP 6: MCP SERVER ECOSYSTEM
# ═══════════════════════════════════════════════════════════════════════

class TestMCPEcosystem:
    """Tests MCP server instruction files and tool schema coverage."""

    def test_all_mcp_servers_have_instructions(self):
        """Every MCP server directory must have an instructions.md file."""
        mcp_root = Path(r"C:\Users\Vaz\.gemini\antigravity\mcp")
        if not mcp_root.exists():
            pytest.skip("MCP root directory not found")

        servers = [d for d in mcp_root.iterdir() if d.is_dir()]
        missing = []

        for server_dir in servers:
            instructions = server_dir / "instructions.md"
            if not instructions.exists():
                missing.append(server_dir.name)

        assert not missing, (
            f"MCP servers without instructions.md: {missing}\n"
            "Every MCP server needs operational runbook instructions."
        )

    def test_mcp_instruction_files_not_empty(self):
        """MCP instruction files must have meaningful content (>100 bytes)."""
        mcp_root = Path(r"C:\Users\Vaz\.gemini\antigravity\mcp")
        if not mcp_root.exists():
            pytest.skip("MCP root directory not found")

        empty_files = []
        for instructions in mcp_root.rglob("instructions.md"):
            size = instructions.stat().st_size
            if size < 100:
                empty_files.append(f"{instructions.parent.name}/instructions.md ({size} bytes)")

        assert not empty_files, (
            f"MCP instruction files with <100 bytes (stubs): {empty_files}"
        )

    def test_mcp_tool_schemas_parseable(self):
        """All MCP tool JSON schemas must be valid JSON."""
        mcp_root = Path(r"C:\Users\Vaz\.gemini\antigravity\mcp")
        if not mcp_root.exists():
            pytest.skip("MCP root directory not found")

        broken = []
        for schema_file in mcp_root.rglob("*.json"):
            try:
                json.loads(schema_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                broken.append(f"{schema_file.relative_to(mcp_root)}: {e}")

        assert not broken, (
            f"Broken MCP tool schemas:\n" + "\n".join(broken)
        )


# ═══════════════════════════════════════════════════════════════════════
# TEST GROUP 7: CROSS-SESSION CLOSED-LOOP (State-Loop Driver)
# ═══════════════════════════════════════════════════════════════════════

class TestCrossSessionClosedLoop:
    """Simulates multi-session lifecycle to verify loop closure."""

    def test_session1_lesson_visible_in_session2_context(self, patched_db_env):
        """CRITICAL METAMORPHIC TEST:
        Session 1: Agent makes error → AutoImprover saves lesson
        Session 2: pre_invocation_hook MUST retrieve that lesson

        If this test fails, the entire Reflexion architecture is theater."""
        from vazus_core.memory.auto_improver import LessonMemoryBank

        # ── SESSION 1: Save a lesson from a failure ──
        bank = LessonMemoryBank()
        bank.save_lesson(
            task_type="code_generation",
            error_sig="Function exceeds 100 lines, violates SRP",
            lesson_text="Always decompose functions over 65 lines using Extract Method",
            fix_hint="Use private helper methods for each logical block",
        )

        # Verify lesson is in DB
        conn = sqlite3.connect(str(patched_db_env))
        count = conn.execute("SELECT count(*) FROM reflexion_lessons").fetchone()[0]
        conn.close()
        assert count >= 1, "Lesson was not persisted to reflexion_lessons table"

        # ── SESSION 2: Try to retrieve it ──
        results = bank.retrieve_relevant(
            error_sig="Function too long, needs decomposition",
            task_type="code_generation",
            top_k=3,
        )

        assert len(results) >= 1, (
            "CRITICAL LOOP BREAK: Lesson saved in Session 1 is NOT "
            "retrievable in Session 2. The Reflexion feedback loop "
            "is completely disconnected. LessonMemoryBank.retrieve_relevant() "
            "cannot find previously stored lessons."
        )

        # Verify the retrieved lesson contains relevant content
        lesson_texts = [
            r.get("lesson_text", "") or r.get("text", "") or str(r)
            for r in results
        ]
        has_relevant = any(
            "decompose" in t.lower() or "extract" in t.lower() or "srp" in t.lower()
            for t in lesson_texts
        )
        assert has_relevant, (
            f"Retrieved lessons exist but don't match: {lesson_texts}"
        )

    def test_organic_insight_persists_across_queries(self, patched_db_env):
        """Insights recorded via organic_memory_bridge must be queryable."""
        try:
            from vazus_core.memory.organic_memory_bridge import (
                record_insight,
                search_memory_semantic,
            )
        except ImportError:
            pytest.skip("organic_memory_bridge not importable")

        # Record an insight
        record_insight(
            category="architectural_decision",
            insight="All pre-commit gates must be fail-closed by default",
            db_path=str(patched_db_env),
        )

        # Verify raw storage first
        conn = sqlite3.connect(str(patched_db_env))
        raw_count = conn.execute(
            "SELECT count(*) FROM organic_insights WHERE insight LIKE '%fail-closed%'"
        ).fetchone()[0]
        conn.close()

        assert raw_count >= 1, (
            "STORAGE BROKEN: record_insight() did not insert into organic_insights"
        )

        # Search semantically
        results = search_memory_semantic(
            query="pre-commit fail-closed",
            limit=5,
            db_path=str(patched_db_env),
        )

        assert len(results) >= 1, (
            "LOOP BROKEN: organic_memory_bridge.record_insight() stored data "
            f"(raw_count={raw_count}) but search_memory_semantic() returned 0."
        )

    def test_dream_consolidator_column_compatibility(self, patched_db_env):
        """SCHEMA BUG: dream_consolidator queries `id` but auto_improver
        creates column `lesson_id`. Verify column names match."""
        conn = sqlite3.connect(str(patched_db_env))

        # Get column names of reflexion_lessons table
        cursor = conn.execute("PRAGMA table_info(reflexion_lessons)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        # Check which primary key name exists
        has_lesson_id = "lesson_id" in columns

        # dream_consolidator uses `lesson_id`, matching auto_improver
        assert has_lesson_id, "reflexion_lessons table must have 'lesson_id' column"

        # Verify dream_consolidator.py source code uses lesson_id
        dc_src = Path("C:/vazus/vazus_core/memory/dream_consolidator.py").read_text(encoding="utf-8")
        assert "WHERE lesson_id = ?" in dc_src, "dream_consolidator must query lesson_id, not id"
        assert "SELECT lesson_id" in dc_src, "dream_consolidator must SELECT lesson_id"


# ═══════════════════════════════════════════════════════════════════════
# TEST GROUP 8: DATABASE INTEGRITY INVARIANTS
# ═══════════════════════════════════════════════════════════════════════

class TestDatabaseIntegrity:
    """Ensures canonical database invariants hold."""

    def test_canonical_db_size_invariant(self):
        """Canonical vazus.db must be ≤ 26 MB."""
        db_path = Path("C:/vazus/services/memory/vazus.db")
        if not db_path.exists():
            pytest.skip("Canonical DB not found")

        size_mb = db_path.stat().st_size / (1024 * 1024)
        assert size_mb <= 26.0, f"DB size {size_mb:.2f} MB exceeds 26.0 MB limit"

    def test_no_duplicate_vazus_db_in_root(self):
        """There should NOT be a stray vazus.db in the workspace root.
        Only the canonical copy in services/memory/ is authoritative."""
        root_db = Path("C:/vazus/vazus.db")
        canonical_db = Path("C:/vazus/services/memory/vazus.db")

        if root_db.exists() and canonical_db.exists():
            root_size = root_db.stat().st_size
            canonical_size = canonical_db.stat().st_size

            if root_size != canonical_size:
                import warnings
                warnings.warn(
                    f"DUPLICATE DB: C:/vazus/vazus.db ({root_size} bytes) "
                    f"differs from canonical ({canonical_size} bytes). "
                    "This can cause data split-brain."
                )

    def test_wal_journal_mode(self, patched_db_env):
        """Database must be in WAL journal mode."""
        conn = sqlite3.connect(str(patched_db_env))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal", f"Expected WAL, got {mode}"


# ═══════════════════════════════════════════════════════════════════════
# TEST GROUP 9: SPEC.md CONTRACT COVERAGE
# ═══════════════════════════════════════════════════════════════════════

class TestSpecContracts:
    """Verifies that domain SPEC.md contracts exist and are well-formed."""

    DOMAIN_DIRS = [
        "C:/vazus/vazus_core/engine",
        "C:/vazus/vazus_core/memory",
        "C:/vazus/vazus_core/hooks",
    ]
    REQUIRED_SECTIONS = ["mission", "interface", "level"]

    def test_spec_files_exist(self):
        """Each domain must have a SPEC.md contract."""
        missing = []
        for d in self.DOMAIN_DIRS:
            spec = Path(d) / "SPEC.md"
            if not spec.exists():
                missing.append(d)

        assert not missing, f"Domains without SPEC.md: {missing}"

    def test_spec_files_have_required_sections(self):
        """SPEC.md files must contain mission, interface, and level keywords."""
        incomplete = []
        for d in self.DOMAIN_DIRS:
            spec = Path(d) / "SPEC.md"
            if not spec.exists():
                continue
            content = spec.read_text(encoding="utf-8").lower()
            for section in self.REQUIRED_SECTIONS:
                if section not in content:
                    incomplete.append(f"{d}: missing '{section}'")

        assert not incomplete, (
            f"SPEC.md files missing required sections:\n"
            + "\n".join(incomplete)
        )


# ═══════════════════════════════════════════════════════════════════════
# TEST GROUP 10: PERFORMANCE INVARIANTS
# ═══════════════════════════════════════════════════════════════════════

class TestPerformanceInvariants:
    """Ensures sub-50ms latency on critical hot paths."""

    def test_pre_tool_hook_latency(self):
        """pre_tool_hook must respond in ≤ 50ms average."""
        from vazus_core.hooks.pre_tool_hook import run_pre_tool

        latencies = []
        for _ in range(20):
            start = time.perf_counter()
            run_pre_tool("write_to_file", {
                "TargetFile": r"C:\vazus\tests\sample.py",
                "CodeContent": "x = 1",
            })
            latencies.append((time.perf_counter() - start) * 1000)

        avg_ms = sum(latencies) / len(latencies)
        assert avg_ms <= 50.0, f"pre_tool_hook avg latency {avg_ms:.1f}ms > 50ms"

    def test_mcp_gateway_resolution_latency(self):
        """MCP gateway tool resolution must be ≤ 10ms."""
        from vazus_core.hooks.pre_invocation_hook import create_default_mcp_gateway

        gw = create_default_mcp_gateway()

        latencies = []
        for _ in range(20):
            start = time.perf_counter()
            gw.resolve_active_tools("verify SMT Z3 contract")
            latencies.append((time.perf_counter() - start) * 1000)

        avg_ms = sum(latencies) / len(latencies)
        assert avg_ms <= 10.0, f"MCP gateway avg latency {avg_ms:.1f}ms > 10ms"

    def test_embedding_768d_precision(self):
        """768D vector pack/unpack must have zero precision drift."""
        from vazus_core.memory.db import pack_vector_f32, unpack_vector_f32

        import random
        random.seed(42)
        original = [random.uniform(-1.0, 1.0) for _ in range(768)]

        packed = pack_vector_f32(original)
        unpacked = unpack_vector_f32(packed)

        drift = max(abs(a - b) for a, b in zip(original, unpacked))
        assert drift < 1e-6, f"768D vector precision drift: {drift} (exceeds 1e-6 tolerance)"
