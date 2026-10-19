"""
tests.test_subagent_harness_integration — Verification tests for Subagent Framework Hooks,
Harness Execution Policy Injection, and Security API Quota Verification Gates.
"""

import sys
import asyncio
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vazus_core.subagent_framework import (
    SubagentContext,
    SYSTEM_HARNESS_POLICY,
    harness_security_on_start_hook,
    security_api_quota_on_verify_hook,
    DeclarativeSubagentEngine,
    DeclarativeSubagentTemplate,
    subagent_registry
)
from vazus_core.safety_guardrail import (
    verify_no_external_api_quota,
    SMTZ3Verifier,
    SOTA2027JuryEngine
)


class TestSubagentHarnessIntegration(unittest.TestCase):

    def test_harness_security_on_start_hook_injects_policy(self):
        ctx = SubagentContext(
            subagent_name="test_agent",
            task_id="task_1",
            prompt="Analyze AST topology."
        )
        asyncio.run(harness_security_on_start_hook(ctx))
        self.assertIn(SYSTEM_HARNESS_POLICY, ctx.prompt)
        self.assertIn("Analyze AST topology.", ctx.prompt)
        self.assertTrue(any("Injected SYSTEM_HARNESS_POLICY" in log for log in ctx.logs))

    def test_security_api_quota_on_verify_hook_blocks_prohibited_import(self):
        ctx_clean = SubagentContext(
            subagent_name="clean_agent",
            task_id="task_2",
            prompt="Clean code",
            results={"output": "def foo(): pass"}
        )
        self.assertTrue(security_api_quota_on_verify_hook(ctx_clean))

        ctx_dirty = SubagentContext(
            subagent_name="dirty_agent",
            task_id="task_3",
            prompt="Dirty code",
            results={"output": "import google.genai\nclient = google.genai.Client()"}
        )
        self.assertFalse(security_api_quota_on_verify_hook(ctx_dirty))
        self.assertTrue(any("Prohibited direct google.genai import" in log for log in ctx_dirty.logs))

    def test_verify_no_external_api_quota_ast_checker(self):
        clean_code = "def add(a, b):\n    return a + b\n"
        res_clean = verify_no_external_api_quota(clean_code)
        self.assertTrue(res_clean.verified)
        self.assertEqual(res_clean.smt_solver_status, "UNSAT")

        prohibited_code = "from google import genai\nclient = genai.Client()\n"
        res_prohibited = verify_no_external_api_quota(prohibited_code)
        self.assertFalse(res_prohibited.verified)
        self.assertEqual(res_prohibited.smt_solver_status, "SAT")
        self.assertIn("Prohibited direct google.genai import", res_prohibited.error_message)

    def test_verify_no_external_api_quota_rejects_syntax_errors(self):
        malformed_code = "def broken(:\n    return 1\n"
        result = verify_no_external_api_quota(malformed_code)
        self.assertFalse(result.verified)
        self.assertEqual(result.smt_solver_status, "SYNTAX_ERROR")
        self.assertFalse(result.ast_valid)
        self.assertIn("syntax error", result.error_message.lower())

    def test_smt_verifier_rejects_syntax_errors(self):
        result = SMTZ3Verifier().verify_code_contracts("def broken(:\n    return 1\n")
        self.assertFalse(result.verified)
        self.assertEqual(result.smt_solver_status, "SYNTAX_ERROR")
        self.assertFalse(result.contract_satisfied)

    def test_concordia_jury_preflight_security_rejection(self):
        jury = SOTA2027JuryEngine()
        prohibited_code = "import google.genai\nclient = google.genai.Client()\n"
        verdict = jury.evaluate_code_proposal(opt_code=prohibited_code)
        self.assertFalse(verdict.approved)
        self.assertIn("SECURITY_REJECT", verdict.reason)

    def test_declarative_subagent_engine_full_lifecycle(self):
        # Register a mock subagent template
        template = DeclarativeSubagentTemplate(
            name="mock_verifier",
            description="Mock verifier subagent",
            system_prompt="You are a verifier.",
            hermes_protocol=False,
            executor_fn=lambda ctx: {"output": "result = 42"}
        )
        subagent_registry.register(template)

        engine = DeclarativeSubagentEngine()
        ctx = engine.run_subagent_sync(
            subagent_name="mock_verifier",
            prompt="Verify result"
        )
        self.assertTrue(ctx.success)
        self.assertIn(SYSTEM_HARNESS_POLICY, ctx.prompt)
        self.assertEqual(ctx.results.get("output"), "result = 42")


if __name__ == "__main__":
    unittest.main()

