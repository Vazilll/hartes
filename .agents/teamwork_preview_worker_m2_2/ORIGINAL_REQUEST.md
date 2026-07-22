## 2026-07-22T14:05:38Z
You are Worker 2 for Milestone 2 of DNTS OS SuperGraph Architecture Integration.
Working directory: C:\vazus\.agents\teamwork_preview_worker_m2_2
Project root: C:\vazus

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Task:
Fix 2 minor CLI issues in C:\vazus\pyenv\scripts\subagent_verifier_bridge.py identified by the Challenger:
1. In argument handling / main(): If `--code-file` is specified by the user but `Path(args.code_file).exists()` is False, print an error message `[VerifierBridge] Error: Code file not found: <path>` and exit with status 1 (sys.exit(1)) instead of silently falling back to sample code.
2. In argument handling / main(): Add an optional `--expected-functions` argument (or auto-derive function names via AST parsing if `--code-file` is passed) so that contract checking doesn't hardcode `expected_functions=["calculate_fibonacci"]` when verifying custom code files.

Verification:
- Run `C:\vazus\pyenv\.venv\Scripts\python.exe C:\vazus\pyenv\scripts\subagent_verifier_bridge.py` (verify sample code still passes).
- Run `C:\vazus\pyenv\.venv\Scripts\python.exe C:\vazus\pyenv\scripts\subagent_verifier_bridge.py --code-file non_existent_file.py` (verify it prints error and exits with code 1).

Write your handoff report to C:\vazus\.agents\teamwork_preview_worker_m2_2\handoff.md and notify parent via send_message when finished.
