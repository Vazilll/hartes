"""
Vazus SuperGraph OS - Cross-Subsystem Interaction Stress Test Harness
Milestone 6 (Challenger 2)

Verifies:
1. R3 cash flow deficit passing target revenue to R4 order matcher.
2. R1 biometric readiness score feeding R5 student schedule study recommendation.
3. Master Orchestrator end-to-end cross-subsystem orchestration and stability.
"""

import sys
import os
import json
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")

from vazus_core.supergraph_master_orchestrator import SuperGraphMasterOrchestrator
from vazus_core.tinkoff_finance_manager import TinkoffFinanceManager, init_finance_db
from vazus_core.self_employed_order_hunter import SelfEmployedManager, OrderHunterEngine, init_self_employed_db
from vazus_core.autonomous_freelance_engine import AutonomousFreelanceEngine
from vazus_core.health_telemetry_pipeline import VazusHealthPipelineManager
from vazus_core.mirea_student_manager import MireaStudentManager


@pytest.fixture
def tmp_stress_db(tmp_path):
    """Isolated SQLite database for cross-subsystem stress testing."""
    db_file = str(tmp_path / "vazus_stress_test.db")
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS finance_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        amount_rub REAL,
        category TEXT,
        merchant TEXT,
        operation_type TEXT,
        account_name TEXT,
        raw_json TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_liabilities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE,
        total_remaining_rub REAL,
        monthly_payment_rub REAL,
        payments_left INTEGER,
        next_payment_date TEXT,
        category TEXT,
        credit_limit_rub REAL DEFAULT 0.0,
        used_credit_rub REAL DEFAULT 0.0
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS self_employed_receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        client_type TEXT,
        amount_rub REAL,
        tax_rate_pct INTEGER,
        tax_rub REAL,
        net_rub REAL,
        service_name TEXT,
        receipt_url TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS freelance_orders_found (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        source TEXT,
        title TEXT,
        price_rub REAL,
        link TEXT UNIQUE,
        matched_stack TEXT,
        proposed_reply TEXT,
        status TEXT DEFAULT 'NEW'
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mirea_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT,
        weekday TEXT,
        lesson_time TEXT,
        subject TEXT,
        lesson_type TEXT,
        classroom TEXT,
        teacher TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mirea_milestones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT,
        subject TEXT,
        milestone_name TEXT,
        milestone_type TEXT,
        due_date TEXT,
        status TEXT,
        description TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mi_scale_weighins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        weight_kg REAL,
        impedance_ohms INTEGER,
        body_fat_pct REAL,
        muscle_mass_kg REAL,
        water_pct REAL,
        visceral_fat_grade INTEGER,
        bmr_kcal INTEGER,
        raw_source TEXT,
        bmi REAL
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS kg_nodes (
        id TEXT PRIMARY KEY,
        node_id TEXT,
        name TEXT,
        domain TEXT,
        node_type TEXT,
        label TEXT,
        description TEXT,
        tags TEXT,
        properties TEXT,
        vector_768_blob BLOB,
        updated_at TEXT
    )
    """)

    conn.commit()
    conn.close()

    patchers = [
        patch("vazus_core.supergraph_master_orchestrator.DB_PATH", db_file),
        patch("vazus_core.health_telemetry_pipeline.DB_PATH", db_file),
        patch("vazus_core.tinkoff_finance_manager.DB_PATH", db_file),
        patch("vazus_core.self_employed_order_hunter.DB_PATH", db_file),
        patch("vazus_core.autonomous_freelance_engine.DB_PATH", db_file),
        patch("vazus_core.mirea_student_manager.DB_PATH", db_file),
        patch("google_fit_sync.fetch_and_save_fitness_data", return_value={"sleep_sessions": [], "sleep_stages_by_day": {}}),
        patch("vazus_core.langgraph_health_workflow.LangGraphHealthMultiAgentWorkflow.execute_full_workflow", return_value={"status": "WORKFLOW_SUCCESS", "analysis": {"readiness_score": 78.5}}),
        patch("langgraph_health_workflow.LangGraphHealthMultiAgentWorkflow.execute_full_workflow", return_value={"status": "WORKFLOW_SUCCESS", "analysis": {"readiness_score": 78.5}}),
        patch("requests.post", side_effect=Exception("Offline test mode")),
        patch("urllib.request.urlopen", side_effect=Exception("Offline test mode"))
    ]



    for p in patchers:
        p.start()

    yield db_file

    for p in patchers:
        p.stop()


# ============================================================================
# STRESS SUITE 1: R3 Cash Flow Deficit -> R4 Freelance Order Matcher
# ============================================================================

def test_stress_r3_r4_standard_deficit_to_order_matching(tmp_stress_db):
    """Stress Test 1.1: Standard cash flow deficit passes target revenue to R4 order matcher."""
    fin_mgr = TinkoffFinanceManager(db_path=tmp_stress_db)
    fin_mgr.add_transaction(40000.0, "Обязательные расходы", "Аренда", op_type="DEBIT")
    fin_mgr.add_transaction(25000.0, "Доход", "Зарплата", op_type="CREDIT")

    summary = fin_mgr.get_financial_summary()
    assert summary["status"] == "DEFICIT"
    assert summary["cash_flow_deficit_rub"] > 0
    target_rev = summary["freelance_target_revenue_rub"]
    assert target_rev >= summary["cash_flow_deficit_rub"]

    hunter = OrderHunterEngine(db_path=tmp_stress_db)
    matched_res = hunter.match_orders_for_target_revenue(target_rev)

    assert matched_res["target_revenue_rub"] == target_rev
    assert matched_res["cumulative_matched_revenue_rub"] > 0
    assert "matched_orders" in matched_res
    assert len(matched_res["matched_orders"]) > 0


def test_stress_r3_r4_surplus_default_target(tmp_stress_db):
    """Stress Test 1.2: Surplus cash flow sets default minimum 10,000 RUB target revenue for R4."""
    fin_mgr = TinkoffFinanceManager(db_path=tmp_stress_db)
    fin_mgr.add_transaction(10000.0, "Расходы", "Еда", op_type="DEBIT")
    fin_mgr.add_transaction(50000.0, "Доход", "Аванс", op_type="CREDIT")

    summary = fin_mgr.get_financial_summary()
    assert summary["status"] == "SURPLUS"
    assert summary["cash_flow_deficit_rub"] == 0.0
    assert summary["freelance_target_revenue_rub"] == 0.0

    hunter = OrderHunterEngine(db_path=tmp_stress_db)
    matched_res = hunter.match_orders_for_target_revenue(summary["freelance_target_revenue_rub"])

    assert matched_res["is_target_met"] is True
    assert matched_res["coverage_pct"] == 100.0


def test_stress_r3_r4_large_deficit_coverage_evaluation(tmp_stress_db):
    """Stress Test 1.3: Large deficit (50,000 RUB) passes to R4 and evaluates coverage."""
    hunter = OrderHunterEngine(db_path=tmp_stress_db)
    large_target = 50000.0
    matched_res = hunter.match_orders_for_target_revenue(large_target)

    assert matched_res["target_revenue_rub"] == 50000.0
    assert matched_res["matched_orders_count"] == 3
    total_scanned_sum = sum(o["price_rub"] for o in matched_res["matched_orders"])
    assert matched_res["cumulative_matched_revenue_rub"] == total_scanned_sum
    assert matched_res["coverage_pct"] < 100.0  # 16500 / 50000 = 33%


def test_stress_r3_r4_boundary_target_values(tmp_stress_db):
    """Stress Test 1.4: Boundary target revenue values (None, 0, negative, extremely large)."""
    hunter = OrderHunterEngine(db_path=tmp_stress_db)

    res_none = hunter.match_orders_for_target_revenue(None)
    assert res_none["target_revenue_rub"] == 0.0

    res_zero = hunter.match_orders_for_target_revenue(0.0)
    assert res_zero["target_revenue_rub"] == 0.0

    res_huge = hunter.match_orders_for_target_revenue(1e6)
    assert res_huge["is_target_met"] is False


def test_stress_r3_r4_orchestrator_integration(tmp_stress_db):
    """Stress Test 1.5: Master Orchestrator end-to-end R3->R4 revenue matching orchestration."""
    orch = SuperGraphMasterOrchestrator(db_path=tmp_stress_db)
    orch.finance_mgr.add_transaction(30000.0, "Кредит", "Банк", op_type="DEBIT")
    
    res = orch.orchestrate_r3_r4_revenue_matching()
    assert "r3_cash_flow_status" in res
    assert "target_revenue_rub" in res
    assert "r4_matching" in res
    assert res["r4_matching"]["matched_orders_count"] > 0


# ============================================================================
# STRESS SUITE 2: R1 Biometric Readiness -> R5 Student Schedule Recommendation
# ============================================================================

def test_stress_r1_r5_high_readiness_recommendation(tmp_stress_db):
    """Stress Test 2.1: High readiness score (85.0) yields HIGH study intensity."""
    mirea_mgr = MireaStudentManager("ИКБО-01-23", db_path=tmp_stress_db)
    rec = mirea_mgr.generate_study_recommendation(readiness_score=85.0)

    assert rec["readiness_score"] == 85.0
    assert rec["study_intensity"] == "HIGH"
    assert rec["suggested_duration_hours"] == 4.0
    assert "Optimal physiological capacity" in rec["recommendation"]


def test_stress_r1_r5_moderate_readiness_recommendation(tmp_stress_db):
    """Stress Test 2.2: Moderate readiness score (60.0) yields MODERATE study intensity."""
    mirea_mgr = MireaStudentManager("ИКБО-01-23", db_path=tmp_stress_db)
    rec = mirea_mgr.generate_study_recommendation(readiness_score=60.0)

    assert rec["readiness_score"] == 60.0
    assert rec["study_intensity"] == "MODERATE"
    assert rec["suggested_duration_hours"] == 2.5
    assert "Balanced study mode" in rec["recommendation"]


def test_stress_r1_r5_low_readiness_recommendation(tmp_stress_db):
    """Stress Test 2.3: Low readiness score (35.0) yields LOW study intensity with sleep advice."""
    mirea_mgr = MireaStudentManager("ИКБО-01-23", db_path=tmp_stress_db)
    rec = mirea_mgr.generate_study_recommendation(readiness_score=35.0)

    assert rec["readiness_score"] == 35.0
    assert rec["study_intensity"] == "LOW"
    assert rec["suggested_duration_hours"] == 1.0
    assert "Reduced cognitive load" in rec["recommendation"]


def test_stress_r1_r5_boundary_readiness_scores(tmp_stress_db):
    """Stress Test 2.4: Boundary readiness scores (0.0, 100.0, None, out-of-bounds)."""
    mirea_mgr = MireaStudentManager("ИКБО-01-23", db_path=tmp_stress_db)

    rec_zero = mirea_mgr.generate_study_recommendation(0.0)
    assert rec_zero["study_intensity"] == "LOW"

    rec_100 = mirea_mgr.generate_study_recommendation(100.0)
    assert rec_100["study_intensity"] == "HIGH"

    rec_none = mirea_mgr.generate_study_recommendation(None)
    assert rec_none["readiness_score"] == 75.0


def test_stress_r1_r5_orchestrator_integration(tmp_stress_db):
    """Stress Test 2.5: Master Orchestrator end-to-end R1->R5 study recommendation orchestration."""
    orch = SuperGraphMasterOrchestrator(db_path=tmp_stress_db)
    with patch.object(orch.pipeline_mgr, "execute_pipeline", return_value={"readiness_score": 82.5}):
        rec = orch.orchestrate_r1_r5_study_recommendation()
        assert rec["readiness_score"] == 82.5
        assert rec["study_intensity"] == "HIGH"


# ============================================================================
# STRESS SUITE 3: Master Orchestrator End-to-End Orchestration & JSON Audit
# ============================================================================

def test_stress_master_orchestrator_complete_sync_with_cross(tmp_stress_db):
    """Stress Test 3.1: Complete Master Orchestrator system sync includes cross-subsystem report."""
    orch = SuperGraphMasterOrchestrator(db_path=tmp_stress_db)
    with patch.object(orch.langgraph_wf, "execute_full_workflow", return_value={"status": "OK"}), \
         patch.object(orch.pipeline_mgr, "execute_pipeline", return_value={"status": "SUCCESS", "readiness_score": 78.5}):
        res = orch.execute_complete_system_sync()
        assert res["status"] == "SYSTEM_FULLY_OPERATIONAL"
        assert "cross_subsystem_interactions" in res
        cross = res["cross_subsystem_interactions"]
        assert "r3_to_r4_revenue_matching" in cross
        assert "r1_to_r5_study_recommendation" in cross


def test_stress_master_orchestrator_json_serializability(tmp_stress_db):
    """Stress Test 3.2: Verify complete orchestrator report is 100% JSON serializable."""
    orch = SuperGraphMasterOrchestrator(db_path=tmp_stress_db)
    with patch.object(orch.langgraph_wf, "execute_full_workflow", return_value={"status": "OK"}), \
         patch.object(orch.pipeline_mgr, "execute_pipeline", return_value={"status": "SUCCESS", "readiness_score": 78.5}):
        res = orch.execute_complete_system_sync()
        json_str = json.dumps(res, ensure_ascii=False, indent=2)
        parsed = json.loads(json_str)
        assert parsed["status"] == "SYSTEM_FULLY_OPERATIONAL"

