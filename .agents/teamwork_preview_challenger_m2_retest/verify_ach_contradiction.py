"""
C:\\vazus\\.agents\\teamwork_preview_challenger_m2_retest\\verify_ach_contradiction.py
Empirical Test Script for ACH Contradiction Resolution Verification
"""

import sys
import os
import tempfile
import json

sys.stdout.reconfigure(encoding='utf-8')

# Ensure vazus path is in sys.path
sys.path.insert(0, r"C:\vazus")

from vazus_core.kgb_analytical_extractor import (
    extract_kgb_analytics,
    evaluate_ach_hypotheses,
    KGBAnalyticalExtractor,
    ThesisNode
)

def run_empirical_tests():
    temp_db = tempfile.mktemp(suffix=".db")
    results = []
    
    print("=== EMPIRICAL TEST 1: Opposing Claims with CONTRADICTS edge ===")
    sample_1 = {
        "scene_id": "test_scene_emp_01",
        "transcript": "Утверждение 1: Приём омега-3 жирных кислот абсолютно безопасен в любых дозах. Утверждение 2: Приём высоких доз омега-3 противоречит безопасному приёму и вызывает опасные кровотечения."
    }
    out1 = extract_kgb_analytics(sample_1, db_path=temp_db)
    theses1 = out1["thesis_nodes"]
    claim_theses1 = [t for t in theses1 if not (t.get("properties", {}).get("container") or t.get("id", "").startswith("scene_"))]
    contradicts1 = out1["contradicts_edges"]
    
    res1 = {
        "test": "Opposing claims with CONTRADICTS edge",
        "contradicts_edges_count": len(contradicts1),
        "contradicts_edges": contradicts1,
        "thesis_count": len(claim_theses1),
        "thesis_statuses": [(t["id"], t["statement"][:40], t["ach_status"], t["confidence"]) for t in claim_theses1],
        "pass": len(contradicts1) > 0 and any(t["ach_status"] in ("REJECTED", "DISPROVED") for t in claim_theses1) and not (all(t["ach_status"] == "ACCEPTED" for t in claim_theses1))
    }
    results.append(res1)
    print(json.dumps(res1, indent=2, ensure_ascii=False))
    
    print("\n=== EMPIRICAL TEST 2: Contradictory Claims with Unequal Confidence ===")
    sample_2 = {
        "scene_id": "test_scene_emp_02",
        "transcript": "Доказано 100%: Приём креатина безопасен для почек. Второе мнение: Приём креатина возможно противоречит безопасности почек."
    }
    out2 = extract_kgb_analytics(sample_2, db_path=temp_db)
    theses2 = out2["thesis_nodes"]
    claim_theses2 = [t for t in theses2 if not (t.get("properties", {}).get("container") or t.get("id", "").startswith("scene_"))]
    contradicts2 = out2["contradicts_edges"]
    
    res2 = {
        "test": "Contradictory claims with unequal confidence",
        "contradicts_edges_count": len(contradicts2),
        "contradicts_edges": contradicts2,
        "thesis_count": len(claim_theses2),
        "thesis_statuses": [(t["id"], t["statement"][:40], t["ach_status"], t["confidence"]) for t in claim_theses2],
        "pass": any(t["ach_status"] in ("REJECTED", "DISPROVED") for t in claim_theses2)
    }
    results.append(res2)
    print(json.dumps(res2, indent=2, ensure_ascii=False))

    print("\n=== EMPIRICAL TEST 3: evaluate_ach_hypotheses Direct Matrix Verification ===")
    hypotheses = [
        {"id": "H1", "label": "Витамин D3 снижает воспаление"},
        {"id": "H2", "label": "Витамин D3 вызывает воспаление"}
    ]
    evidence = [
        {"id": "E1", "statement": "Исследование показывает что Витамин D3 снижает воспаление", "confidence": 0.95},
        {"id": "E2", "statement": "Альтернативный отчет заявляет что Витамин D3 не снижает воспаление", "confidence": 0.50}
    ]
    ach_out = evaluate_ach_hypotheses(hypotheses, evidence)
    ranked = ach_out["ranked_hypotheses"]
    statuses = {r["hypothesis_id"]: r["ach_status"] for r in ranked}
    
    res3 = {
        "test": "evaluate_ach_hypotheses direct evaluation",
        "ranked_hypotheses": ranked,
        "inconsistency_scores": ach_out["inconsistency_scores"],
        "contradictions_detected": ach_out["contradictions_detected"],
        "pass": statuses.get("H1") == "ACCEPTED" and statuses.get("H2") in ("REJECTED", "DISPROVED")
    }
    results.append(res3)
    print(json.dumps(res3, indent=2, ensure_ascii=False))

    all_passed = all(r["pass"] for r in results)
    print(f"\nOVERALL EMPIRICAL VERDICT: {'PASS' if all_passed else 'FAIL'}")
    
    # Cleanup temp db
    if os.path.exists(temp_db):
        try:
            os.remove(temp_db)
        except Exception:
            pass

if __name__ == "__main__":
    run_empirical_tests()
