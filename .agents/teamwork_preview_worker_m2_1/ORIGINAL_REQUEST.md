## 2026-07-22T16:26:08+03:00
You are Worker 1 for Milestone 2 (R1: Native Subagents & GitHub Wrappers Bridge) of DNTS OS SuperGraph Architecture Integration.
Working directory: C:\dnts\.agents\teamwork_preview_worker_m2_1
Project root: C:\dnts

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Task:
Implement the Python bridge scripts in C:\dnts\pyenv\scripts linking native subagents directly to the downloaded GitHub repositories:
1. Create C:\dnts\pyenv\scripts\subagent_rlm_bridge.py:
   - Links rlm_code_engineer subagent directly to C:\dnts\pyenv\rlm-mit.
   - Imports RLM engine (from rlm import RLM or rlm.core.rlm import RLM) and dnts_core.workers.rlm.
   - Accepts prompt / task input via CLI arguments or python function call.
   - Runs MIT RLM engine loop with LocalREPL environment.
   - Supports main block execution (`if __name__ == '__main__': ...`) that tests functionality and exits with code 0 when run directly.

2. Create C:\dnts\pyenv\scripts\subagent_research_bridge.py:
   - Links open_deep_researcher subagent directly to C:\dnts\pyenv\open-deep-research.
   - Imports open_deep_research.deep_researcher (deep_researcher_builder).
   - Accepts research query / topic via CLI arguments or python function call.
   - Builds/compiles the LangGraph StateGraph research workflow.
   - Supports main block execution (`if __name__ == '__main__': ...`) that tests building/invoking research graph (or mock dry-run) and exits with code 0.

3. Create C:\dnts\pyenv\scripts\subagent_verifier_bridge.py:
   - Links verifier_worker subagent directly to C:\dnts\pyenv\dnts_core\evolution\jules_verifier.py and git_provenance.py.
   - Performs syntax verification, contract testing, and Git provenance tracking.
   - Exits with code 0 when executed.

Verification requirement:
Run all three bridge scripts using C:\dnts\pyenv\.venv\Scripts\python.exe and verify that each executes with Exit Code 0. Document commands and outputs in your report.

Write your detailed handoff report to C:\dnts\.agents\teamwork_preview_worker_m2_1\handoff.md and notify parent via send_message when finished.
