"""
audit_runner.py — Extension Victory Auditor Independent Verification Script
"""

import sys
import os
import re
import glob
import sqlite3
import subprocess
from pathlib import Path

PYTHON_EXE = r"C:\vazus\.venv\Scripts\python.exe"
PROJECT_ROOT = r"C:\vazus"

ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

TEST_COMMANDS = [
    ("1. Core & Script Python Syntax Check", [PYTHON_EXE, "-m", "py_compile", 
        r"C:\vazus\vazus_core\multimodal_knowledge.py",
        r"C:\vazus\vazus_core\kgb_analytical_extractor.py",
        r"C:\vazus\vazus_core\zettelkasten_exporter.py",
        r"C:\vazus\vazus_core\cognitive_tutor_engine.py",
        r"C:\vazus\scripts\personal_tutor.py",
        r"C:\vazus\scripts\dashboard.py"
    ]),
    ("2. Unit Test: Multimodal Knowledge", [PYTHON_EXE, "-m", "unittest", r"C:\vazus\tests\test_multimodal_knowledge.py"]),
    ("3. Unit Test: KGB Analytical Extractor", [PYTHON_EXE, "-m", "unittest", r"C:\vazus\tests\test_kgb_analytical_extractor.py"]),
    ("4. Unit Test: Zettelkasten Exporter", [PYTHON_EXE, "-m", "unittest", r"C:\vazus\tests\test_zettelkasten_exporter.py"]),
    ("5. Unit Test: Cognitive Tutor Engine", [PYTHON_EXE, "-m", "unittest", r"C:\vazus\tests\test_cognitive_tutor_engine.py"]),
    ("6. Active Recall CLI Self-Test", [PYTHON_EXE, r"C:\vazus\scripts\personal_tutor.py", "--test"]),
    ("7. Milestone 4 Verification Suite", [PYTHON_EXE, r"C:\vazus\scripts\verify_m4_requirements.py"]),
    ("8. Milestone 5 E2E Integration Suite", [PYTHON_EXE, r"C:\vazus\scripts\verify_m5_e2e_integration.py"]),
]


def verify_database_and_notes():
    print("\n" + "=" * 60, flush=True)
    print("9. Database Graph Topology & Zettelkasten Verification", flush=True)
    print("=" * 60, flush=True)
    db_paths = [r"C:\vazus\vazus.db", r"C:\vazus\memory\dnts.db", r"C:\vazus\services\memory\vazus.db"]
    
    total_theses = 0
    total_protocols = 0
    total_causes = 0
    total_contradicts = 0
    total_requires = 0

    for dbp in db_paths:
        if os.path.exists(dbp):
            try:
                conn = sqlite3.connect(dbp)
                c = conn.cursor()
                t_cnt = c.execute("SELECT count(*) FROM kg_nodes WHERE node_type='ThesisNode'").fetchone()[0]
                p_cnt = c.execute("SELECT count(*) FROM kg_nodes WHERE node_type='ProtocolNode'").fetchone()[0]
                c_cnt = c.execute("SELECT count(*) FROM kg_edges WHERE relation='CAUSES'").fetchone()[0]
                ct_cnt = c.execute("SELECT count(*) FROM kg_edges WHERE relation='CONTRADICTS'").fetchone()[0]
                r_cnt = c.execute("SELECT count(*) FROM kg_edges WHERE relation='REQUIRES'").fetchone()[0]
                print(f"  DB [{dbp}]: ThesisNodes={t_cnt}, ProtocolNodes={p_cnt}, CAUSES={c_cnt}, CONTRADICTS={ct_cnt}, REQUIRES={r_cnt}", flush=True)
                total_theses += t_cnt
                total_protocols += p_cnt
                total_causes += c_cnt
                total_contradicts += ct_cnt
                total_requires += r_cnt
                conn.close()
            except Exception as e:
                print(f"  DB Error [{dbp}]: {e}", flush=True)

    assert total_theses > 0, "No ThesisNode entities found in SuperGraph databases"
    assert total_protocols > 0, "No ProtocolNode entities found in SuperGraph databases"
    assert total_causes > 0, "No CAUSES edges found in SuperGraph databases"
    assert total_contradicts > 0, "No CONTRADICTS edges found in SuperGraph databases"
    print("  -> Database Graph Nodes & Edges Verified: PASS", flush=True)

    wiki_dir = r"C:\vazus\services\memory\semantic\wiki"
    all_wiki_notes = glob.glob(os.path.join(wiki_dir, "*.md"))
    zettel_notes = [f for f in all_wiki_notes if os.path.basename(f).startswith("Zettel_")]
    
    print(f"\n  Inspecting Zettelkasten Markdown notes in {wiki_dir}:", flush=True)
    print(f"  Total wiki files: {len(all_wiki_notes)} | Zettelkasten atomic notes (Zettel_*): {len(zettel_notes)}", flush=True)
    assert len(zettel_notes) > 0, "No Zettelkasten atomic notes (Zettel_*.md) found"

    valid_notes_count = 0
    for note_path in zettel_notes:
        with open(note_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        wikilinks = re.findall(r'\[\[([^\]]+)\]\]', content)
        has_checklist = "- [ ]" in content or "- [x]" in content
        has_yaml = content.startswith("---") and "id:" in content and "status:" in content

        if len(wikilinks) >= 3 and has_checklist and has_yaml:
            valid_notes_count += 1
            print(f"    - [{os.path.basename(note_path)}]: {len(wikilinks)} wikilinks, checklist OK, YAML OK", flush=True)

    print(f"  -> Valid Zettelkasten Notes (>=3 [[Wikilinks]] + Action Checklist + YAML): {valid_notes_count}/{len(zettel_notes)}", flush=True)
    assert valid_notes_count >= len(zettel_notes) * 0.80, "Fewer than 80% of Zettel notes meet strict Zettelkasten criteria"
    print("  -> Zettelkasten Markdown Note Inspection: PASS", flush=True)


def main():
    print("============================================================", flush=True)
    print("   VAZUS SUPERGRAPH OS EXTENSION - VICTORY AUDITOR SUITE", flush=True)
    print("============================================================\n", flush=True)

    results = []

    for label, cmd in TEST_COMMANDS:
        print(f"Executing: {label}", flush=True)
        print(f"Command: {' '.join(cmd)}", flush=True)
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300,
                cwd=PROJECT_ROOT,
                env=ENV
            )
            stdout_str = res.stdout.decode('utf-8', errors='replace').strip()
            stderr_str = res.stderr.decode('utf-8', errors='replace').strip()
            status = "PASS" if res.returncode == 0 else "FAIL"
            print(f"Exit Code: {res.returncode} -> [{status}]", flush=True)
            if stdout_str:
                print("--- STDOUT ---", flush=True)
                print(stdout_str[:1500], flush=True)
            if stderr_str:
                print("--- STDERR ---", flush=True)
                print(stderr_str[:1500], flush=True)
            print("=" * 60 + "\n", flush=True)
            results.append({
                "label": label,
                "cmd": " ".join(cmd),
                "exit_code": res.returncode,
                "status": status,
            })
        except Exception as e:
            print(f"Execution Error: {e}", flush=True)
            print("=" * 60 + "\n", flush=True)
            results.append({
                "label": label,
                "cmd": " ".join(cmd),
                "exit_code": -1,
                "status": "ERROR",
            })

    try:
        verify_database_and_notes()
        results.append({
            "label": "9. Database Graph Topology & Zettelkasten Verification",
            "cmd": "internal DB & note scanner",
            "exit_code": 0,
            "status": "PASS"
        })
    except Exception as e:
        print(f"  DB & Note Verification Error: {e}", flush=True)
        results.append({
            "label": "9. Database Graph Topology & Zettelkasten Verification",
            "cmd": "internal DB & note scanner",
            "exit_code": 1,
            "status": "FAIL"
        })

    print("============================================================", flush=True)
    print("SUMMARY AUDIT RESULTS:", flush=True)
    print("============================================================", flush=True)
    all_passed = True
    for r in results:
        print(f"  [{r['status']}] Exit {r['exit_code']} - {r['label']}", flush=True)
        if r["status"] != "PASS":
            all_passed = False

    print("============================================================", flush=True)
    if all_passed:
        print("OVERALL VICTORY AUDIT VERDICT: ALL CHECKS PASSED CLEANLY", flush=True)
    else:
        print("OVERALL VICTORY AUDIT VERDICT: VERIFICATION REJECTED", flush=True)
    print("============================================================", flush=True)


if __name__ == "__main__":
    main()
