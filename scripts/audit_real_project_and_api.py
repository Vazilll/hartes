"""
scripts/audit_real_project_and_api.py — Comprehensive Real-Project & Control Center API Audit.

Tests:
1. Item 1 (SMT Z3 + Concordia Jury) on actual production code in labs/raytsystem.
2. Item 3 (Skill Authoring) on real skill definitions.
3. HTTP Web Control Center endpoints on http://127.0.0.1:8765.
"""

import sys
import json
import urllib.request
from pathlib import Path

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from scripts.unified_supergraph_bridge import UnifiedSuperGraphBridge
from vazus_core.ast_pruner import ASTPruner

BASE_URL = "http://127.0.0.1:8765"


def audit_real_project_code():
    print("=" * 70)
    print("🔬 PART 1: REAL-WORLD PROJECT AUDIT (C:/vazus/labs/raytsystem)")
    print("=" * 70)

    bridge = UnifiedSuperGraphBridge(effort_level="xhigh")

    real_files = [
        ("checkpoint_guard.py", "labs/raytsystem/src/raytsystem/checkpoint_guard.py"),
        ("authority.py", "labs/raytsystem/src/raytsystem/authority.py"),
        ("control.py", "labs/raytsystem/src/raytsystem/control.py"),
    ]

    for name, rel_path in real_files:
        full_path = VAZUS_DIR / rel_path
        if not full_path.exists():
            print(f"   ⚠️ File missing: {rel_path}")
            continue

        code = full_path.read_text(encoding="utf-8")

        # 1. AST Pruning & Syntax Audit
        is_valid_ast = ASTPruner.validate_signatures(code)
        pruned_code = ASTPruner.prune_ast(code)
        raw_size = len(code.encode("utf-8"))
        pruned_size = len(pruned_code.encode("utf-8"))
        reduction = (1 - (pruned_size / raw_size)) * 100

        print(f"\n📁 Module: {name}")
        print(f"   - AST Syntax Valid: {'✅ YES' if is_valid_ast else '❌ NO'}")
        print(f"   - Size: {raw_size}B -> {pruned_size}B (Token Reduction: {reduction:.2f}%)")

        # 2. SMT Z3 & Concordia Jury Audit
        verif_res = bridge.verify_code_with_jury_and_smt(
            file_path=str(full_path),
            code_content=code[:3000],  # Sample first 3000 bytes for contract testing
            smt_depth=10,
        )

        print(f"   - SMT Z3 Solver:   {verif_res['smt_z3_verification'].get('status')}")
        print(f"   - Jury Consensus:  Ratio={verif_res['multi_agent_jury']['consensus_ratio']:.2f} | Verdict={'APPROVED' if verif_res['overall_passed'] else 'REJECTED'}")

    # 3. Real Skill Authoring Audit
    print("\n🛠️ Testing Skill Authoring Engine on Real Skill Specs...")
    real_skill = bridge.validate_and_register_skill(
        skill_id="rayt-checkpoint-guard-skill",
        display_name="Raytsystem Git Checkpoint Guard",
        description="Automated snapshot creation and policy simulation prior to task rollout.",
        instructions="Create git checkpoint, run policy simulator, verify Z3 contracts before commit.",
        trust_class="local_sandbox"
    )
    print(f"   - Real Skill Authoring: Validated={real_skill['success']} | ID={real_skill['skill_id']}")


def audit_control_center_endpoints():
    print("\n" + "=" * 70)
    print("🌐 PART 2: CONTROL CENTER WEB ENDPOINTS AUDIT (http://127.0.0.1:8765)")
    print("=" * 70)

    endpoints = [
        ("/", "HTML Control Center UI"),
        ("/universe", "3D Universe Graph Surface"),
        ("/api/v1/code-graph/status", "Code Graph Engine Status"),
        ("/api/v1/system", "System State & Configuration"),
        ("/api/v1/handbook", "Handbook & Documentation"),
        ("/api/v1/execution/features", "Execution Features List"),
        ("/api/v1/catalog", "Skill & Tool Catalog"),
        ("/api/v1/skills", "Registered Skills List"),
        ("/api/v1/execution/runtime-health", "Runtime Health Metrics"),
    ]

    for path, description in endpoints:
        url = f"{BASE_URL}{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SuperGraph-Auditor/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                status_code = resp.status
                content_type = resp.headers.get("Content-Type", "")
                data = resp.read()
                data_len = len(data)

                # Summary snippet
                summary = ""
                if "application/json" in content_type:
                    try:
                        parsed = json.loads(data.decode("utf-8"))
                        if isinstance(parsed, dict):
                            keys = list(parsed.keys())[:5]
                            summary = f"JSON Keys: {keys}"
                        elif isinstance(parsed, list):
                            summary = f"JSON Array len={len(parsed)}"
                    except Exception:
                        summary = f"JSON {data_len} bytes"
                elif "text/html" in content_type:
                    summary = f"HTML Web Surface ({data_len} bytes)"
                else:
                    summary = f"{data_len} bytes"

                print(f"   - Status {status_code} | {path:35s} | {description:30s} | {summary}")
        except Exception as e:
            print(f"   - ❌ ERROR  | {path:35s} | {description:30s} | {e}")

    print("\n" + "=" * 70)
    print("🎉 COMPREHENSIVE REAL-PROJECT & API AUDIT COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    audit_real_project_code()
    audit_control_center_endpoints()
