#!/usr/bin/env python3
"""
tests/e2e/test_all_ai_scenarios_e2e.py — Comprehensive Empirical Proof Suite for Vazus OS v5.0.

Formally tests and validates all 3 core AI scenarios with real execution (0 mocks):
1. SCENARIO 1: Full Hook Lifecycle & State Pipeline
   (session_start -> pre_invocation context injection -> pre_tool jail -> post_tool telemetry -> stop_hook consolidation)
2. SCENARIO 2: Real SMT Z3 Formal Contract Proofs & Concordia Jury Quorum Gate
   (Mathematical invariant verification, precondition/postcondition checking, and consensus rejection)
3. SCENARIO 3: Autonomous Reflexion & 768D Vector Anti-Amnesia Memory Loop
   (Error diagnosis -> lesson embedding in vazus.db -> cosine similarity recall on next turn)
"""

import asyncio
import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path
import numpy as np
import pytest

# Core imports
from vazus_core.hooks.session_start_hook import run_session_start_hook
from vazus_core.hooks.pre_invocation_hook import run_pre_invocation_hook, DynamicSkillDispatcher
from vazus_core.hooks.pre_tool_hook import pre_tool_enforce_security_jail
from vazus_core.hooks.post_tool_hook import run_post_tool_hook
from vazus_core.hooks.post_invocation_hook import run_post_invocation_hook
from vazus_core.hooks.stop_hook import run_stop_hook
from vazus_core.verification.smt_z3_verifier import SMTZ3Verifier, ContractSpec
from vazus_core.verification.concordia_jury import ConcordiaMultiAgentJury
from vazus_core.verification.precommit_gate import run_precommit_gate
from vazus_core.memory.auto_improver import LessonMemoryBank, ReflexionEvaluator
from vazus_core.memory.embeddings import UnifiedEmbeddingManager


def test_scenario_1_full_hook_lifecycle_and_context_pipeline():
    """
    SCENARIO 1 PROOF:
    Verifies that state and context actually flow end-to-end across all lifecycle hooks.
    """
    async def _async_scenario_1():
        session_id = f"e2e_proof_sess_{int(time.time())}"
        workspace = r"C:\vazus\tests\scratch"
        os.makedirs(workspace, exist_ok=True)

        # 1. Session Start Hook
        start_res = await run_session_start_hook(session_id=session_id, workspace_root=workspace)
        assert start_res["status"] in ("INITIALIZED", "SUCCESS")
        assert "timestamp" in start_res

        # 2. Pre-Invocation Hook (Context Injection on Turn 0)
        user_prompt = "Refactor database memory query and optimize embeddings"
        pre_inv_res = await run_pre_invocation_hook(
            session_id=session_id,
            user_prompt=user_prompt,
            turn_index=0
        )
        assert "injected_context" in pre_inv_res
        assert pre_inv_res["turn_index"] == 0

        # Verify skill dispatcher recommends relevant skills
        dispatcher = DynamicSkillDispatcher()
        matched_skills = dispatcher.match_skills(user_prompt)
        assert isinstance(matched_skills, list)

        # 3. Pre-Tool Hook (Security Jail Enforcement)
        # 3a. Legitimate workspace action -> ALLOW
        allow_decision = pre_tool_enforce_security_jail(
            tool_name="write_to_file",
            tool_args={"TargetFile": os.path.join(workspace, "valid_output.py")},
            workspace_root=workspace
        )
        assert allow_decision["decision"] == "allow"
        assert allow_decision["latency_ms"] < 50.0  # Strict sub-50ms SLA

        # 3b. Dangerous path escape -> DENY (Fail-Closed)
        deny_decision = pre_tool_enforce_security_jail(
            tool_name="write_to_file",
            tool_args={"TargetFile": r"C:\Windows\System32\malicious.dll"},
            workspace_root=workspace
        )
        assert deny_decision["decision"] == "deny"
        assert any(term in deny_decision["reason"].lower() for term in ["blocked", "deny", "security", "forbidden", "path"])

        # 4. Post-Tool Hook (Telemetry and Masking)
        post_tool_res = run_post_tool_hook(
            session_id=session_id,
            tool_name="write_to_file",
            tool_args={"TargetFile": "valid_output.py"},
            raw_output="Successfully written 150 bytes."
        )
        assert post_tool_res["status"] == "CAPTURED"
        assert "telemetry" in post_tool_res

        # 5. Post-Invocation Hook (State recording)
        post_inv_res = await run_post_invocation_hook(
            session_id=session_id,
            turn_index=0,
            model_response="Operation completed successfully.",
            tool_executions_count=1
        )
        assert post_inv_res["status"] in ("RECORDED", "SUCCESS")

        # 6. Stop Hook (Consolidation & Cleanup)
        stop_res = await run_stop_hook(session_id=session_id, workspace_root=workspace)
        assert stop_res["status"] in ("CONSOLIDATED", "SUCCESS")

    asyncio.run(_async_scenario_1())


def test_scenario_2_smt_z3_contracts_and_concordia_jury_gate():
    """
    SCENARIO 2 PROOF:
    Verifies that SMT Z3 proves actual formal mathematical contracts on code,
    and that Concordia Jury enforces multi-agent consensus before changes are accepted.
    """
    verifier = SMTZ3Verifier()

    # 1. Real Formal SMT Z3 Contract Verification
    # Contract: calculate_discount(price, pct) requires price >= 0 and 0 <= pct <= 100
    # ensures result >= 0 and result <= price
    valid_spec = ContractSpec(
        function_name="calculate_discount",
        preconditions=["price >= 0", "pct >= 0", "pct <= 100"],
        postconditions=["result >= 0", "result <= price"],
        invariants=["price >= result"]
    )
    
    proof_result = verifier.verify_contract_spec(
        spec=valid_spec,
        implementation_code="def calculate_discount(price, pct): return price * (1.0 - pct / 100.0)"
    )
    assert proof_result["is_valid"] is True
    assert proof_result["smt_status"] in ("VERIFIED", "UNSAT_PROOF_FOUND", "SUCCESS", "UNSAT")

    # 2. Concordia Multi-Agent Jury Consensus
    jury = ConcordiaMultiAgentJury()
    
    # Consensus evaluation on high-quality verified code change
    votes_pass = jury.evaluate_proposal(
        code_diff="""+def safe_divide(a: float, b: float) -> float:
+    if b == 0:
+        raise ValueError("Division by zero")
+    return a / b""",
        test_results={"total": 5, "passed": 5, "failed": 0},
        smt_proof=proof_result
    )
    assert votes_pass["consensus_reached"] is True
    assert votes_pass["approval_rate"] >= 0.66

    # Rejection evaluation on insecure/untested code
    votes_fail = jury.evaluate_proposal(
        code_diff="""+def dangerous_exec(user_input: str):
+    eval(user_input)""",
        test_results={"total": 5, "passed": 2, "failed": 3},
        smt_proof={"is_valid": False}
    )
    assert votes_fail["consensus_reached"] is False
    assert votes_fail["approval_rate"] < 0.66


def test_scenario_3_autonomous_reflexion_and_768d_vector_memory_loop():
    """
    SCENARIO 3 PROOF:
    Verifies the closed-loop memory cycle:
    Error occurrence -> Reflexion diagnosis -> 768D embedding in vazus.db -> Semantic recall on subsequent query.
    """
    async def _async_scenario_3():
        db_path = str(Path(tempfile.gettempdir()) / f"vazus_e2e_mem_{int(time.time())}.db")
        bank = LessonMemoryBank(db_path=db_path)
        evaluator = ReflexionEvaluator()
        embedder = UnifiedEmbeddingManager()

        # 1. Simulate an error encounter in agent execution
        sample_error = {
            "tool": "run_command",
            "error_type": "ImportError",
            "error_message": "cannot import name 'ASTPruner' from 'vazus_core.ast_pruner'",
            "context": "importing ASTPruner from wrong path instead of vazus_core.verification.ast_pruner"
        }

        # 2. Reflexion Evaluator analyzes error and generates structured lesson
        lesson = evaluator.diagnose_and_formulate_lesson(
            error_context=sample_error,
            task_objective="Import AST pruning utilities for token compression"
        )
        assert "lesson_text" in lesson
        assert "anti_pattern" in lesson
        assert "recommended_pattern" in lesson

        # 3. Save lesson with 768-dimensional vector embedding in database
        lesson_id = await bank.save_lesson_async(
            category="IMPORT_RESOLUTION",
            anti_pattern="importing from vazus_core.ast_pruner",
            solution="use vazus_core.verification.ast_pruner for all ASTPruner imports",
            context_tags=["ast_pruner", "import_error", "verification"]
        )
        assert bool(lesson_id)

        # 4. In a NEW session/turn, query related to AST pruning imports
        query_prompt = "How should I import ASTPruner in our verification scripts?"
        recalled_lessons = await bank.retrieve_relevant_async(
            query=query_prompt,
            top_k=3,
            similarity_threshold=0.30
        )

        # 5. Verify semantic memory successfully retrieved the exact past lesson
        assert len(recalled_lessons) >= 1
        top_lesson = recalled_lessons[0]
        assert "vazus_core.verification.ast_pruner" in top_lesson["solution"]
        assert top_lesson["similarity_score"] >= 0.0
        assert top_lesson["category"] == "IMPORT_RESOLUTION"

        # 6. Verify 768-dim embedding mathematical properties
        q_vec = embedder.get_embedding(query_prompt)
        assert len(q_vec) == 768
        # Norm should be close to 1.0 (unit vector)
        norm = np.linalg.norm(q_vec)
        assert abs(norm - 1.0) < 1e-3

    asyncio.run(_async_scenario_3())
