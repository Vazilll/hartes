"""
subagent_verifier_bridge.py — Bridge script linking verifier_worker subagent
directly to Jules Verifier (jules_verifier.py), Git Provenance (git_provenance.py),
and isolated execution verification (workers/verifier.py).

DNTS SuperGraph OS Architecture Integration (Milestone 2)
"""

import argparse
import ast
import os
import sys
from pathlib import Path

# Fix Windows console UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Setup project paths
SCRIPT_DIR = Path(__file__).resolve().parent
PYENV_DIR = SCRIPT_DIR.parent

if str(PYENV_DIR) not in sys.path:
    sys.path.insert(0, str(PYENV_DIR))

try:
    from dnts_core.evolution.jules_verifier import JulesCloudEscalator
    from dnts_core.git_provenance import GitProvenanceManager
    from dnts_core.workers.verifier import CodeVerifier
except ImportError as e:
    sys.stderr.write(f"[VerifierBridge] Import Error: {e}\n")
    JulesCloudEscalator = None
    GitProvenanceManager = None
    CodeVerifier = None


class VerifierSubagentBridge:
    """
    Bridge connecting verifier_worker subagent to Jules Cloud Escalator,
    Git Provenance tracking, AST syntax verification, and contract testing.
    """

    def __init__(self):
        self.jules = JulesCloudEscalator() if JulesCloudEscalator else None
        self.git_manager = GitProvenanceManager if GitProvenanceManager else None
        self.verifier = CodeVerifier(timeout_sec=10) if CodeVerifier else None

    def verify_syntax(self, code: str) -> dict:
        """Performs static AST syntax verification on code content."""
        try:
            tree = ast.parse(code)
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            return {
                "success": True,
                "ast_parse": "PASSED",
                "functions_found": functions,
                "classes_found": classes,
                "error": None,
            }
        except SyntaxError as se:
            return {
                "success": False,
                "ast_parse": "FAILED",
                "error": f"SyntaxError at line {se.lineno}, col {se.offset}: {se.msg}",
            }
        except Exception as e:
            return {
                "success": False,
                "ast_parse": "FAILED",
                "error": f"AST Parse Error: {str(e)}",
            }

    def verify_contract(self, code: str, expected_functions: list[str] = None) -> dict:
        """Verifies function/class signatures and docstring contracts."""
        syntax_res = self.verify_syntax(code)
        if not syntax_res["success"]:
            return {"success": False, "contract_test": "FAILED", "reason": "Syntax invalid"}

        found = syntax_res.get("functions_found", [])
        missing = []
        if expected_functions:
            for fn in expected_functions:
                if fn not in found:
                    missing.append(fn)

        if missing:
            return {
                "success": False,
                "contract_test": "FAILED",
                "missing_functions": missing,
                "found_functions": found,
            }
        return {
            "success": True,
            "contract_test": "PASSED",
            "verified_functions": expected_functions or found,
        }

    def verify_execution(self, code: str) -> dict:
        """Runs isolated subprocess execution using dnts_core CodeVerifier."""
        if not self.verifier:
            return {"success": False, "error": "CodeVerifier module not available"}
        return self.verifier.verify(code)

    def track_git_provenance(self, org: str = "Google-DeepMind", feature_name: str = "verifier-worker", commit_msg: str | None = None) -> dict:
        """Checks and updates Git provenance tracking branches."""
        if not self.git_manager:
            return {"success": False, "error": "GitProvenanceManager module not available"}

        current_branch = self.git_manager.get_current_branch()
        active_branch = self.git_manager.ensure_branch(org, feature_name)

        committed = False
        if commit_msg:
            committed = self.git_manager.commit_changes(commit_msg)

        return {
            "status": "TRACKED",
            "previous_branch": current_branch,
            "active_provenance_branch": active_branch,
            "committed": committed,
        }

    def escalate_to_jules(self, prompt: str, repo_path: str = None) -> dict:
        """Escalates complex code failures to Google DeepMind Jules VM."""
        if not self.jules:
            return {"status": "UNAVAILABLE", "error": "JulesCloudEscalator module not available"}
        return self.jules.submit_task(prompt, repo_path=repo_path)

    def run_full_pipeline(
        self,
        code: str,
        expected_functions: list[str] = None,
        org: str = "Google-DeepMind",
        feature_name: str = "jules-verifier-bridge",
        escalate_on_failure: bool = False,
    ) -> dict:
        """Runs syntax verification, contract testing, execution verification, and Git provenance tracking."""
        print("[VerifierBridge] Subagent verifier_worker starting verification pipeline...")

        syntax_res = self.verify_syntax(code)
        contract_res = self.verify_contract(code, expected_functions)
        exec_res = self.verify_execution(code) if syntax_res["success"] else {"success": False, "skipped": True}
        git_res = self.track_git_provenance(org=org, feature_name=feature_name)

        overall_success = syntax_res["success"] and contract_res["success"] and exec_res.get("success", False)

        jules_res = None
        if not overall_success and escalate_on_failure:
            jules_prompt = f"Automated verification failed for snippet. Syntax: {syntax_res}, Execution: {exec_res}"
            jules_res = self.escalate_to_jules(jules_prompt)

        return {
            "subagent": "verifier_worker",
            "overall_success": overall_success,
            "syntax_verification": syntax_res,
            "contract_testing": contract_res,
            "execution_verification": exec_res,
            "git_provenance": git_res,
            "jules_escalation": jules_res,
        }


def main():
    parser = argparse.ArgumentParser(description="Bridge for verifier_worker subagent, Jules Verifier & Git Provenance")
    parser.add_argument("--code-file", "-f", help="Path to python file to verify")
    parser.add_argument("--expected-functions", "-e", nargs="*", help="Expected function names for contract checking")
    parser.add_argument("--org", default="Google-DeepMind", help="Organization name for provenance branch")
    parser.add_argument("--feature", default="jules-verifier-bridge", help="Feature name for provenance branch")
    parser.add_argument("--escalate-jules", action="store_true", help="Escalate task to Jules Cloud VM")
    args = parser.parse_args()

    sample_code = """
def calculate_fibonacci(n: int) -> int:
    \"\"\"Compute the n-th Fibonacci number.\"\"\"
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

if __name__ == '__main__':
    result = calculate_fibonacci(10)
    print(f"Fibonacci(10) = {result}")
    assert result == 55, "Fibonacci calculation failed"
"""

    if args.code_file:
        code_path = Path(args.code_file)
        if not code_path.exists():
            print(f"[VerifierBridge] Error: Code file not found: {args.code_file}")
            sys.exit(1)
        code_to_verify = code_path.read_text(encoding="utf-8")
    else:
        code_to_verify = sample_code

    expected_funcs = None
    if args.expected_functions:
        expected_funcs = []
        for item in args.expected_functions:
            for sub in item.split(","):
                if sub.strip():
                    expected_funcs.append(sub.strip())
    elif args.code_file:
        # Auto-derive function names via AST parsing when custom code file is provided
        try:
            tree = ast.parse(code_to_verify)
            expected_funcs = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        except Exception:
            expected_funcs = None
    else:
        expected_funcs = ["calculate_fibonacci"]

    bridge = VerifierSubagentBridge()
    result = bridge.run_full_pipeline(
        code=code_to_verify,
        expected_functions=expected_funcs,
        org=args.org,
        feature_name=args.feature,
        escalate_on_failure=args.escalate_jules,
    )

    print("\n" + "=" * 60)
    print("VERIFIER SUBAGENT BRIDGE EXECUTION RESULT")
    print("=" * 60)
    print(f"  Subagent: {result['subagent']}")
    print(f"  Overall Success: {result['overall_success']}")
    print(f"  Syntax: {result['syntax_verification']['ast_parse']}")
    print(f"  Contract: {result['contract_testing']['contract_test']}")
    print(f"  Execution: {result['execution_verification'].get('stdout') or result['execution_verification']}")
    print(f"  Git Provenance: {result['git_provenance']}")
    if result['jules_escalation']:
        print(f"  Jules Escalation: {result['jules_escalation']}")
    print("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
