"""
audit_runner.py — Victory Auditor Independent Test Suite Execution Script

Runs the 7 target test commands using C:\\dnts\\pyenv\\.venv\\Scripts\\python.exe
and reports individual exit codes, stdout, stderr, and status.
"""

import sys
import subprocess
from pathlib import Path

PYTHON_EXE = r"C:\dnts\pyenv\.venv\Scripts\python.exe"

TEST_COMMANDS = [
    ("1. RLM Bridge Dry-Run", [PYTHON_EXE, r"C:\dnts\pyenv\scripts\subagent_rlm_bridge.py", "--dry-run"]),
    ("2. Research Bridge Dry-Run", [PYTHON_EXE, r"C:\dnts\pyenv\scripts\subagent_research_bridge.py", "--dry-run"]),
    ("3. Verifier Bridge Pipeline", [PYTHON_EXE, r"C:\dnts\pyenv\scripts\subagent_verifier_bridge.py"]),
    ("4. OpenVINO NPU Verification", [PYTHON_EXE, r"C:\dnts\verify_ov_npu.py"]),
    ("5. System Test Suite (test_dnts_system.py)", [PYTHON_EXE, r"C:\dnts\pyenv\tests\test_dnts_system.py"]),
    ("6. SuperGraph Integration Test", [PYTHON_EXE, r"C:\dnts\pyenv\scripts\test_supergraph_integration.py"]),
    ("7. Token Economy & AST Pruning Test", [PYTHON_EXE, r"C:\dnts\pyenv\scripts\test_token_economy.py"]),
]

def main():
    print("============================================================")
    print("DNTS SUPERGRAPH OS - VICTORY AUDITOR INDEPENDENT TEST SUITE")
    print("============================================================\n")

    results = []

    for label, cmd in TEST_COMMANDS:
        print(f"Executing: {label}")
        print(f"Command: {' '.join(cmd)}")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            status = "PASS" if res.returncode == 0 else "FAIL"
            stdout_str = (res.stdout or "").strip()
            stderr_str = (res.stderr or "").strip()
            print(f"Exit Code: {res.returncode} -> [{status}]")
            print("--- STDOUT ---")
            print(stdout_str)
            if stderr_str:
                print("--- STDERR ---")
                print(stderr_str)
            print("=" * 60 + "\n")
            results.append({
                "label": label,
                "cmd": " ".join(cmd),
                "exit_code": res.returncode,
                "status": status,
                "stdout": stdout_str,
                "stderr": stderr_str,
            })
        except Exception as e:
            print(f"Execution Error: {e}")
            print("=" * 60 + "\n")
            results.append({
                "label": label,
                "cmd": " ".join(cmd),
                "exit_code": -1,
                "status": "ERROR",
                "stdout": "",
                "stderr": str(e),
            })

    print("============================================================")
    print("SUMMARY RESULTS:")
    print("============================================================")
    all_passed = True
    for r in results:
        print(f"  [{r['status']}] Exit {r['exit_code']} - {r['label']}")
        if r["status"] != "PASS":
            all_passed = False

    print("============================================================")
    if all_passed:
        print("OVERALL TEST SUITE VERDICT: ALL 7 TESTS PASSED (EXIT CODE 0)")
    else:
        print("OVERALL TEST SUITE VERDICT: SOME TESTS FAILED")
    print("============================================================")

if __name__ == "__main__":
    main()
