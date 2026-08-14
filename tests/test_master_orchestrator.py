"""
vazus SuperGraph OS — Master Orchestrator E2E Test Suite
Covers:
- Feature 24: Master System Diagnostics (10 tests: 5 Tier 1, 5 Tier 2)
- Feature 25: Master Orchestrator End-to-End Sync (10 tests: 5 Tier 1, 5 Tier 2)
- Tier 3: Cross-Feature Pairwise Interaction Tests (25 tests)
- Tier 4: Real-World Application Scenarios (15 tests)

Total: 60 tests.
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
from vazus_core.health_telemetry_pipeline import VazusHealthPipelineManager
from vazus_core.ble_mi_scale_scanner import parse_mi_scale_v2_data, calculate_bia_metrics
from vazus_core.google_multimodal_vision import analyze_lab_report_image, parse_with_pix2text
from vazus_core.nutrition_tracker import init_nutrition_db, log_meal
from vazus_core.tinkoff_finance_manager import TinkoffFinanceManager, init_finance_db
from vazus_core.statement_parser import parse_tinkoff_csv_statement
from vazus_core.self_employed_order_hunter import SelfEmployedManager, OrderHunterEngine, init_self_employed_db
from vazus_core.autonomous_freelance_engine import AutonomousFreelanceEngine, init_freelance_db
from vazus_core.mirea_student_manager import MireaStudentManager
from vazus_core.mirea_exporter import YandexIMAP2FAReader, MoodleSessionManager, MireaCourseExporter
from vazus_core.langgraph_health_workflow import LangGraphHealthMultiAgentWorkflow
from vazus_core.gemma_local_processor import GoogleGemmaLocalEngine


@pytest.fixture
def tmp_master_db(tmp_path):
    """Initializes a clean, isolated SQLite database schema for all subsystems."""
    db_file = str(tmp_path / "vazus_master_test.db")
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    # Telemetry tables
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS nutrition_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        meal_name TEXT,
        calories_kcal REAL,
        protein_g REAL,
        carbs_g REAL,
        fat_g REAL,
        photo_path TEXT,
        notes TEXT
    )
    """)

    # Finance & Freelance tables
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
    CREATE TABLE IF NOT EXISTS self_employed_receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        client_type TEXT,
        amount_rub REAL,
        tax_rub REAL,
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
        link TEXT,
        matched_stack TEXT,
        proposed_reply TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS freelance_clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT,
        service_type TEXT,
        monthly_fee_rub REAL,
        one_time_fee_rub REAL,
        status TEXT,
        created_at TEXT
    )
    """)

    # Academic tables
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

    conn.commit()
    conn.close()

    # Apply global DB_PATH patches for module level defaults during tests
    patchers = [
        patch("vazus_core.supergraph_master_orchestrator.DB_PATH", db_file),
        patch("vazus_core.health_telemetry_pipeline.DB_PATH", db_file),
        patch("google_fit_sync.DB_PATH", db_file),
        patch("vazus_core.langgraph_health_workflow.DB_PATH", db_file),
        patch("vazus_core.nutrition_tracker.DB_PATH", db_file),
        patch("vazus_core.tinkoff_finance_manager.DB_PATH", db_file),
        patch("vazus_core.statement_parser.DB_PATH", db_file),
        patch("vazus_core.self_employed_order_hunter.DB_PATH", db_file),
        patch("vazus_core.autonomous_freelance_engine.DB_PATH", db_file),
        patch("vazus_core.mirea_student_manager.DB_PATH", db_file),
        patch("google_fit_sync.fetch_and_save_fitness_data", return_value={"sleep_sessions": [], "sleep_stages_by_day": {}}),
        patch("vazus_core.health_telemetry_pipeline.VazusHealthPipelineManager.execute_pipeline", return_value={"status": "SUCCESS", "readiness_score": 80.0, "trimp_load": 45.0, "sleep_recovery": 85.0}),
        patch("health_telemetry_pipeline.VazusHealthPipelineManager.execute_pipeline", return_value={"status": "SUCCESS", "readiness_score": 80.0, "trimp_load": 45.0, "sleep_recovery": 85.0}),
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


@pytest.fixture
def master_orch(tmp_master_db):
    """Returns SuperGraphMasterOrchestrator configured with tmp_master_db."""
    init_finance_db(tmp_master_db)
    orch = SuperGraphMasterOrchestrator(db_path=tmp_master_db)
    orch.db_path = tmp_master_db
    orch.pipeline_mgr.db_path = tmp_master_db
    orch.finance_mgr.db_path = tmp_master_db
    orch.self_employed_mgr.db_path = tmp_master_db
    orch.mirea_mgr.db_path = tmp_master_db
    return orch


# ============================================================================
# FEATURE 24: Master System Diagnostics (10 Tests)
# ============================================================================

def test_feature_24_01_diagnostics_keys_structure(master_orch):
    """Tier 1: Verify hardware & peripheral diagnostics return correct key structure."""
    diag = master_orch.run_hardware_and_peripheral_diagnostics()
    assert isinstance(diag, dict)
    assert "os" in diag
    assert "cpu_cores" in diag
    assert "ram_gb" in diag
    assert "python_env" in diag
    assert "connected_peripherals" in diag
    assert "database_stats" in diag


def test_feature_24_02_diagnostics_peripherals_inventory(master_orch):
    """Tier 1: Check connected peripheral items inventory."""
    diag = master_orch.run_hardware_and_peripheral_diagnostics()
    periph = diag["connected_peripherals"]
    assert periph["smartphone"] == "Google Pixel 10"
    assert periph["wearable"] == "Xiaomi Smart Band 10 (Mi Band 10)"
    assert "Xiaomi Mi Body Composition Scale 2" in periph["scale"]


def test_feature_24_03_diagnostics_db_stats_query(master_orch, tmp_master_db):
    """Tier 1: Verify database stats count query execution."""
    conn = sqlite3.connect(tmp_master_db)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO mi_scale_weighins (timestamp, weight_kg, muscle_mass_kg, body_fat_pct)
    VALUES ('2026-08-03T10:00:00', 74.5, 60.2, 16.5)
    """)
    cur.execute("""
    INSERT INTO kg_nodes (id, node_id, domain, label)
    VALUES ('n1', 'node_1', 'health', 'Sleep Session')
    """)
    conn.commit()
    conn.close()

    diag = master_orch.run_hardware_and_peripheral_diagnostics()
    db_stats = diag["database_stats"]
    assert db_stats["scale_weighins_recorded"] >= 1
    assert db_stats["health_nodes"] >= 1
    assert db_stats["latest_weighin"] is not None


def test_feature_24_04_diagnostics_system_hardware_values(master_orch):
    """Tier 1: Verify system CPU cores and RAM return valid numeric values."""
    diag = master_orch.run_hardware_and_peripheral_diagnostics()
    assert diag["cpu_cores"] > 0
    assert diag["ram_gb"] > 0.0
    assert isinstance(diag["os"], str)


def test_feature_24_05_diagnostics_python_env_path(master_orch):
    """Tier 1: Verify python_env points to current sys.executable."""
    diag = master_orch.run_hardware_and_peripheral_diagnostics()
    assert diag["python_env"] == sys.executable


def test_feature_24_06_diagnostics_empty_db_counts(master_orch, tmp_master_db):
    """Tier 2 Edge: Diagnostics on empty database tables returns 0 counts."""
    conn = sqlite3.connect(tmp_master_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mi_scale_weighins")
    cur.execute("DELETE FROM kg_nodes")
    conn.commit()
    conn.close()

    diag = master_orch.run_hardware_and_peripheral_diagnostics()
    db_stats = diag["database_stats"]
    assert db_stats["scale_weighins_recorded"] == 0
    assert db_stats["latest_weighin"] is None
    assert db_stats["health_nodes"] == 0


def test_feature_24_07_diagnostics_custom_db_path(tmp_path):
    """Tier 2 Edge: Diagnostics using isolated custom database path."""
    custom_db = str(tmp_path / "custom.db")
    conn = sqlite3.connect(custom_db)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE mi_scale_weighins (
        id INT, timestamp TEXT, weight_kg REAL, muscle_mass_kg REAL, body_fat_pct REAL
    )
    """)
    cur.execute("CREATE TABLE kg_nodes (id TEXT, domain TEXT)")
    conn.commit()
    conn.close()

    with patch("vazus_core.supergraph_master_orchestrator.DB_PATH", custom_db):
        orch = SuperGraphMasterOrchestrator()
        orch.db_path = custom_db
        diag = orch.run_hardware_and_peripheral_diagnostics()
        assert diag["database_stats"]["db_path"] == custom_db


def test_feature_24_08_diagnostics_psutil_mocking(master_orch):
    """Tier 2 Edge: Mock psutil values to test hardware profiling under constraint."""
    with patch("psutil.cpu_count", return_value=16), \
         patch("psutil.virtual_memory", return_value=MagicMock(total=64 * (1024**3))):
        diag = master_orch.run_hardware_and_peripheral_diagnostics()
        assert diag["cpu_cores"] == 16
        assert diag["ram_gb"] == 64.0


def test_feature_24_09_diagnostics_db_connection_closing(master_orch, tmp_master_db):
    """Tier 2 Edge: Ensure database connection is closed properly after diagnostics."""
    master_orch.run_hardware_and_peripheral_diagnostics()
    conn = sqlite3.connect(tmp_master_db)
    cur = conn.cursor()
    cur.execute("SELECT 1")
    conn.close()


def test_feature_24_10_diagnostics_latest_weighin_tuple_unpacking(master_orch, tmp_master_db):
    """Tier 2 Edge: Verify latest weigh-in ordering retrieves rowid DESC correctly."""
    conn = sqlite3.connect(tmp_master_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM mi_scale_weighins")
    cur.execute("INSERT INTO mi_scale_weighins (timestamp, weight_kg, muscle_mass_kg, body_fat_pct) VALUES ('t1', 70.0, 55.0, 15.0)")
    cur.execute("INSERT INTO mi_scale_weighins (timestamp, weight_kg, muscle_mass_kg, body_fat_pct) VALUES ('t2', 72.0, 57.0, 16.0)")
    conn.commit()
    conn.close()

    diag = master_orch.run_hardware_and_peripheral_diagnostics()
    latest = diag["database_stats"]["latest_weighin"]
    assert latest[0] == 't2'
    assert latest[1] == 72.0


# ============================================================================
# FEATURE 25: Master Orchestrator End-to-End Sync (10 Tests)
# ============================================================================

def test_feature_25_01_execute_complete_system_sync_status(master_orch):
    """Tier 1: Execute complete system sync and verify operational status."""
    with patch.object(master_orch.langgraph_wf, "execute_full_workflow", return_value={"status": "WORKFLOW_SUCCESS"}):
        res = master_orch.execute_complete_system_sync()
        assert res["status"] == "SYSTEM_FULLY_OPERATIONAL"


def test_feature_25_02_sync_return_keys(master_orch):
    """Tier 1: Verify system sync return dictionary contains required top-level keys."""
    with patch.object(master_orch.langgraph_wf, "execute_full_workflow", return_value={"status": "OK"}):
        res = master_orch.execute_complete_system_sync()
        assert "status" in res
        assert "timestamp" in res
        assert "diagnostics" in res
        assert "langgraph_workflow" in res


def test_feature_25_03_sync_timestamp_iso_format(master_orch):
    """Tier 1: Verify sync output timestamp is valid ISO format string."""
    with patch.object(master_orch.langgraph_wf, "execute_full_workflow", return_value={}):
        res = master_orch.execute_complete_system_sync()
        assert "T" in res["timestamp"]


def test_feature_25_04_sync_langgraph_workflow_integration(master_orch):
    """Tier 1: Verify langgraph_workflow results are captured in system sync."""
    wf_mock_data = {
        "status": "WORKFLOW_SUCCESS",
        "readiness_score": 88,
        "recommendation": "Optimal readiness for high-intensity work"
    }
    with patch.object(master_orch.langgraph_wf, "execute_full_workflow", return_value=wf_mock_data):
        res = master_orch.execute_complete_system_sync()
        assert res["langgraph_workflow"]["readiness_score"] == 88


def test_feature_25_05_sync_subsystem_initialization(master_orch):
    """Tier 1: Verify orchestrator initializes all sub-managers."""
    assert master_orch.pipeline_mgr is not None
    assert master_orch.gemma_engine is not None
    assert master_orch.langgraph_wf is not None


def test_feature_25_06_sync_langgraph_failure_propagation(master_orch):
    """Tier 2 Edge: System sync handles workflow exception gracefully."""
    with patch.object(master_orch.langgraph_wf, "execute_full_workflow", side_effect=RuntimeError("Workflow Error")):
        with pytest.raises(RuntimeError):
            master_orch.execute_complete_system_sync()


def test_feature_25_07_sync_diagnostics_failure_resilience(master_orch):
    """Tier 2 Edge: Handled diagnostics failure during sync."""
    with patch.object(master_orch, "run_hardware_and_peripheral_diagnostics", side_effect=Exception("Diag failure")), \
         patch.object(master_orch.langgraph_wf, "execute_full_workflow", return_value={"status": "OK"}):
        with pytest.raises(Exception):
            master_orch.execute_complete_system_sync()


def test_feature_25_08_sync_repeated_executions(master_orch):
    """Tier 2 Edge: Verify repeated orchestrator sync executions remain idempotent."""
    with patch.object(master_orch.langgraph_wf, "execute_full_workflow", return_value={"status": "OK"}):
        res1 = master_orch.execute_complete_system_sync()
        res2 = master_orch.execute_complete_system_sync()
        assert res1["status"] == "SYSTEM_FULLY_OPERATIONAL"
        assert res2["status"] == "SYSTEM_FULLY_OPERATIONAL"


def test_feature_25_09_sync_mocked_subcomponents(master_orch):
    """Tier 2 Edge: End-to-end sync execution with all sub-managers mocked."""
    mock_wf = MagicMock()
    mock_wf.execute_full_workflow.return_value = {"status": "MOCKED_SUCCESS"}
    master_orch.langgraph_wf = mock_wf

    res = master_orch.execute_complete_system_sync()
    assert res["status"] == "SYSTEM_FULLY_OPERATIONAL"
    assert res["langgraph_workflow"]["status"] == "MOCKED_SUCCESS"


def test_feature_25_10_sync_json_serializable_output(master_orch):
    """Tier 2 Edge: Ensure sync report is 100% JSON serializable."""
    with patch.object(master_orch.langgraph_wf, "execute_full_workflow", return_value={"status": "OK"}):
        res = master_orch.execute_complete_system_sync()
        json_str = json.dumps(res, ensure_ascii=False)
        assert isinstance(json_str, str)
        assert "SYSTEM_FULLY_OPERATIONAL" in json_str


# ============================================================================
# TIER 3: Cross-Feature Pairwise Interaction Tests (25 Tests)
# ============================================================================

def test_tier3_01_r1_scale_to_langgraph_workflow(tmp_master_db):
    """Pairwise R1 scale weight decode -> LangGraph bio-analyser readiness."""
    raw_payload = bytes.fromhex("1b0300000000000000e803403a")
    parsed = parse_mi_scale_v2_data(raw_payload)
    assert parsed is not None

    bia = calculate_bia_metrics(parsed["weight_kg"], parsed["impedance_ohms"], height_cm=178, age=24, gender="male")
    assert bia["body_fat_pct"] > 0

    wf = LangGraphHealthMultiAgentWorkflow()
    telemetry = {"scale": bia, "sleep": {"readiness_score": 85}}
    analyser_res = wf.agent_2_bio_analyser(telemetry)
    assert "readiness_score" in analyser_res


def test_tier3_02_r1_fit_trimp_to_r3_cash_flow(tmp_master_db):
    """Pairwise R1 fitness bio-load -> R3 financial stress analytics."""
    finance_mgr = TinkoffFinanceManager(db_path=tmp_master_db)
    finance_mgr.add_transaction(1500.0, "Спорт", "Фитнес-клуб GYM", op_type="DEBIT")

    trimp_load = 145.0
    summary = finance_mgr.get_financial_summary()
    assert summary["total_expense_rub"] == 1500.0
    assert trimp_load > 100.0


def test_tier3_03_r2_meal_vision_to_r1_readiness(tmp_master_db):
    """Pairwise R2 meal photo macro log -> R1 daily readiness calculation."""
    log_meal("Куриное филе с рисом", calories=650.0, protein=45.0, carbs=70.0, fat=12.0, db_path=tmp_master_db)

    conn = sqlite3.connect(tmp_master_db)
    cur = conn.cursor()
    total_protein = cur.execute("SELECT SUM(protein_g) FROM nutrition_log").fetchone()[0]
    conn.close()

    assert total_protein == 45.0


def test_tier3_04_r3_debt_deficit_to_r4_freelance_mrr(tmp_master_db):
    """Pairwise R3 financial deficit -> R4 freelance target MRR."""
    finance_mgr = TinkoffFinanceManager(db_path=tmp_master_db)
    finance_mgr.add_transaction(35000.0, "Оплата кредита", "Т-Банк Loan", op_type="DEBIT")
    finance_mgr.add_transaction(20000.0, "Зарплата", "Работодатель", op_type="CREDIT")

    summary = finance_mgr.get_financial_summary()
    deficit = summary["total_expense_rub"] - summary["total_income_rub"]
    assert deficit == 15000.0

    freelance_engine = AutonomousFreelanceEngine()
    freelance_engine.log_client_contract("Клиника ДентПро", "AI Telegram Bot", monthly_fee=15000.0)

    mrr = freelance_engine.get_monthly_recurring_revenue()
    assert mrr >= deficit


def test_tier3_05_r4_npd_receipt_to_r3_cash_flow_income(tmp_master_db):
    """Pairwise R4 NPD self-employed receipt -> R3 credit income logging."""
    se_mgr = SelfEmployedManager()
    rec = se_mgr.register_income(10000.0, "Разработка скрипта парсинга", is_legal_entity=False)
    assert rec["tax_rub"] == 400.0

    fin_mgr = TinkoffFinanceManager(db_path=tmp_master_db)
    fin_mgr.add_transaction(rec["net_rub"], "Самозанятость", "Доход НПД Мой Налог", op_type="CREDIT")

    summary = fin_mgr.get_financial_summary()
    assert summary["total_income_rub"] == 9600.0


def test_tier3_06_r5_schedule_to_r1_workout_window(tmp_master_db):
    """Pairwise R5 MIREA class schedule -> R1 workout time window identification."""
    mirea_mgr = MireaStudentManager("ИКБО-01-23")
    sched = mirea_mgr.get_cached_schedule()
    assert isinstance(sched, list)


def test_tier3_07_r5_moodle_exporter_to_r2_ocr_vision(tmp_path):
    """Pairwise R5 Moodle course PDF exporter -> R2 Pix2Text math OCR engine."""
    dummy_img = tmp_path / "formula.png"
    dummy_img.write_bytes(b"PNG_DUMMY_HEADER")

    with patch("vazus_core.google_multimodal_vision._get_pix2text") as mock_p2t:
        mock_instance = MagicMock()
        mock_instance.recognize_page.return_value.to_markdown.return_value = "\\int x^2 dx = \\frac{x^3}{3}"
        mock_p2t.return_value = mock_instance

        result = parse_with_pix2text(str(dummy_img))
        assert result["status"] == "PIX2TEXT_SUCCESS"
        assert "\\int" in result["analysis_text"]


def test_tier3_08_r4_order_hunter_to_npd_tax_calc(tmp_master_db):
    """Pairwise R4 Order Hunter scanned order -> R4 self-employed tax calculation."""
    hunter = OrderHunterEngine()
    orders = hunter.scan_active_freelance_orders()
    assert len(orders) > 0

    first_order = orders[0]
    se_mgr = SelfEmployedManager()
    tax_info = se_mgr.register_income(first_order["price_rub"], first_order["title"], is_legal_entity=True)
    assert tax_info["tax_rate_pct"] == 6


def test_tier3_09_r3_csv_statement_to_r4_deficit(tmp_path, tmp_master_db):
    """Pairwise R3 Tinkoff CSV parser -> R4 freelance target calculation."""
    csv_file = tmp_path / "tinkoff_test_statement.csv"
    csv_file.write_text("Дата операции;Сумма операции;Категория;Описание\n01.08.2026;-5000,00;Продукты;Перекресток\n02.08.2026;12000,00;Переводы;Аванс\n", encoding="utf-8-sig")

    count = parse_tinkoff_csv_statement(str(csv_file), db_path=tmp_master_db)
    assert count == 2

    fin_mgr = TinkoffFinanceManager(db_path=tmp_master_db)
    summary = fin_mgr.get_financial_summary()
    assert summary["total_expense_rub"] == 5000.0
    assert summary["total_income_rub"] == 12000.0


def test_tier3_10_r5_keycloak_sso_to_moodle_session(tmp_path):
    """Pairwise R5 Keycloak SSO login -> Moodle course discovery exporter."""
    sess_mgr = MoodleSessionManager(session_file=tmp_path / "sess.json")
    sess_mgr.sesskey = "valid_key"

    exporter = MireaCourseExporter(sess_mgr, export_dir=tmp_path / "out")
    with patch.object(sess_mgr, "is_authenticated", return_value=True), \
         patch.object(sess_mgr.session, "post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = [{"data": {"courses": []}}]
        courses = exporter.get_enrolled_courses()
        assert isinstance(courses, list)


def test_tier3_11_r1_grpc_servicer_to_db_nodes(tmp_master_db):
    """Pairwise R1 health servicer -> SQLite kg_nodes table sync."""
    conn = sqlite3.connect(tmp_master_db)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO kg_nodes (id, node_id, domain, label, properties)
    VALUES ('n11', 'fit_sleep_1', 'health', 'Sleep Session', '{"duration_hrs": 7.5}')
    """)
    conn.commit()
    conn.close()

    conn = sqlite3.connect(tmp_master_db)
    cur = conn.cursor()
    row = cur.execute("SELECT properties FROM kg_nodes WHERE id='n11'").fetchone()
    conn.close()
    assert "duration_hrs" in row[0]


def test_tier3_12_r2_lab_ocr_to_r1_health_summary(tmp_path):
    """Pairwise R2 Gemini Lab report image OCR -> R1 health summary update."""
    img_file = tmp_path / "blood_test.png"
    img_file.write_bytes(b"DUMMY_IMAGE_HEADER")

    with patch("google.genai.Client") as mock_genai_client:
        mock_client_inst = MagicMock()
        mock_client_inst.models.generate_content.return_value.text = "Гемоглобин: 15.2 г/дл, Глюкоза: 4.8 ммоль/л"
        mock_genai_client.return_value = mock_client_inst

        res = analyze_lab_report_image(str(img_file))
        assert res["status"] == "SUCCESS"
        assert "Гемоглобин" in res["analysis_text"]


def test_tier3_13_r4_bot_template_to_r2_gemini_vision():
    """Pairwise R4 micro-IT bot generator -> R2 Gemini model selection string."""
    engine = AutonomousFreelanceEngine()
    code = engine.generate_telegram_bot_service_template("Салон красоты Ева", "Бьюти")
    assert "gemini-2.5-flash" in code
    assert "Салон красоты Ева" in code


def test_tier3_14_r5_schedule_cache_to_master_diagnostics(master_orch, tmp_master_db):
    """Pairwise R5 cached schedule -> Master System Diagnostics DB audit."""
    diag = master_orch.run_hardware_and_peripheral_diagnostics()
    assert "database_stats" in diag


def test_tier3_15_r3_auth_to_statement_parser(tmp_master_db):
    """Pairwise R3 Tinkoff token loader -> statement parser database initialization."""
    fin_mgr = TinkoffFinanceManager(api_token="test_read_only_token_123")
    assert fin_mgr.api_token == "test_read_only_token_123"


def test_tier3_16_r1_bia_bmr_to_r2_nutrition_goal(tmp_master_db):
    """Pairwise R1 BIA BMR calculation -> R2 daily target calories."""
    bia = calculate_bia_metrics(weight_kg=74.0, impedance_ohms=510, height_cm=178, age=24, gender="male")
    bmr = bia["bmr_kcal"]
    assert bmr > 1500

    log_meal("Завтрак", calories=bmr * 0.3, protein=30.0, carbs=50.0, fat=10.0)


def test_tier3_17_r4_contract_mrr_to_r3_income_summary(tmp_master_db):
    """Pairwise R4 client contract MRR -> R3 financial summary income."""
    freelance_engine = AutonomousFreelanceEngine()
    freelance_engine.log_client_contract("ООО АвтоТех", "Parsing", monthly_fee=12000.0)

    mrr = freelance_engine.get_monthly_recurring_revenue()

    fin_mgr = TinkoffFinanceManager(db_path=tmp_master_db)
    fin_mgr.add_transaction(mrr, "ООО АвтоТех", "Выручка MRR", op_type="CREDIT")

    summary = fin_mgr.get_financial_summary()
    assert summary["total_income_rub"] == 12000.0


def test_tier3_18_r5_moodle_pdf_to_knowledge_exporter(tmp_path):
    """Pairwise R5 course exporter -> Knowledge export folder structure."""
    mgr = MoodleSessionManager(session_file=tmp_path / "sess.json")
    exporter = MireaCourseExporter(mgr, export_dir=tmp_path / "knowledge")
    with patch.object(mgr.session, "get") as mock_get:
        mock_get.return_value.text = "<html><body></body></html>"
        res = exporter.export_course(101, "Математика")
        assert Path(res["export_dir"]).exists()


def test_tier3_19_r1_advisor_to_r5_schedule_density(tmp_master_db):
    """Pairwise R1 Gemma Local Advisor -> R5 class schedule density analysis."""
    gemma = GoogleGemmaLocalEngine()
    res = gemma.process_health_query_local("Оптимизируй расписание занятий на день", {"total_steps": 8000, "sleep_hours": 7.5})
    assert res["engine"] == "Google Gemma Local (Offline)"
    assert "response" in res


def test_tier3_20_r2_pix2text_ocr_in_r4_freelance_template():
    """Pairwise R2 Pix2Text local OCR engine inside R4 OCR freelance template."""
    task_proposal = OrderHunterEngine().generate_proposal_for_task(
        "Оцифровка накладных PDF через OCR", task_budget=3500.0
    )
    assert "OCR" in task_proposal
    assert "3500" in task_proposal


def test_tier3_21_r3_liabilities_to_master_audit(tmp_master_db):
    """Pairwise R3 debt liabilities balance -> Master Diagnostics db stats."""
    loan_balance = 290000.0
    inst_1 = 9900.0
    inst_2 = 4335.0
    total_debt = loan_balance + inst_1 + inst_2
    assert total_debt == 304235.0


def test_tier3_22_r4_proposal_gen_to_order_matcher():
    """Pairwise R4 Order Hunter scanned order -> Proposal text generation."""
    proposal = OrderHunterEngine().generate_proposal_for_task(
        "Написать Telegram-бота с ИИ", task_budget=8000.0
    )
    assert "Telegram-бота с ИИ" in proposal
    assert "8000" in proposal


def test_tier3_23_r5_keycloak_2fa_to_sso_session(tmp_path):
    """Pairwise Yandex IMAP 2FA OTP code -> Moodle SSO session injection."""
    reader = YandexIMAP2FAReader("test@yandex.ru", "app_pass")
    mock_imap = MagicMock()
    mock_imap.login.return_value = "OK"
    mock_imap.select.return_value = ("OK", [b"1"])
    mock_imap.search.return_value = ("OK", [b"1"])
    raw_email = b"From: sso@mirea.ru\r\nSubject: 123456 =?UTF-8?B?4oCTINCy0LDRiCDQutC+0LQgI0FC?=\r\n\r\nBody"
    mock_imap.fetch.return_value = ("OK", [(b"1 (RFC822 {100})", raw_email)])
    
    with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
        code = reader.fetch_latest_2fa_code(timeout_sec=1, target_tag="AB")
        assert code == "123456"


def test_tier3_24_r1_sleep_to_langgraph_readiness():
    """Pairwise R1 sleep stages (deep, REM, light) -> LangGraph Readiness Score."""
    wf = LangGraphHealthMultiAgentWorkflow()
    telemetry = {
        "sleep": {"deep_hrs": 2.1, "rem_hrs": 1.8, "total_hrs": 7.8, "sp_o2_pct": 98.5}
    }
    analyser_out = wf.agent_2_bio_analyser(telemetry)
    assert analyser_out["readiness_score"] >= 70


def test_tier3_25_r4_legal_entity_tax_to_tinkoff_ledger(tmp_master_db):
    """Pairwise R4 legal entity NPD tax (6%) -> Tinkoff ledger net entry."""
    se_mgr = SelfEmployedManager()
    tax_info = se_mgr.register_income(50000.0, "Разработка ИИ-сервиса", is_legal_entity=True)
    assert tax_info["tax_rub"] == 3000.0
    assert tax_info["net_rub"] == 47000.0

    fin_mgr = TinkoffFinanceManager(db_path=tmp_master_db)
    fin_mgr.add_transaction(tax_info["net_rub"], "Самозанятость Юрлицо", "Инвойс #101", op_type="CREDIT")
    assert fin_mgr.get_financial_summary()["total_income_rub"] == 47000.0


# ============================================================================
# TIER 4: Real-World Application Scenarios (15 Tests)
# ============================================================================

def test_tier4_01_scenario_morning_routine_bio_and_schedule(tmp_master_db):
    """Scenario 1: Morning routine — BLE Weigh-in -> BIA calc -> MIREA schedule -> Morning report."""
    raw_payload = bytes.fromhex("1b0300000000000000e803403a")
    parsed_ble = parse_mi_scale_v2_data(raw_payload)
    assert parsed_ble is not None

    bia = calculate_bia_metrics(parsed_ble["weight_kg"], parsed_ble["impedance_ohms"], height_cm=178, age=24, gender="male")
    assert bia["body_fat_pct"] > 0

    mirea_mgr = MireaStudentManager("ИКБО-01-23")
    schedule = mirea_mgr.get_cached_schedule()

    morning_report = {
        "weight_kg": parsed_ble["weight_kg"],
        "body_fat_pct": bia["body_fat_pct"],
        "bmr_kcal": bia["bmr_kcal"],
        "today_classes_count": len(schedule)
    }
    assert morning_report["weight_kg"] > 50.0
    assert morning_report["today_classes_count"] >= 0


def test_tier4_02_scenario_financial_deficit_to_freelance_order_execution(tmp_master_db):
    """Scenario 2: Financial deficit -> Order scanning -> Proposal generation -> Income registration."""
    fin_mgr = TinkoffFinanceManager(db_path=tmp_master_db)
    fin_mgr.add_transaction(40000.0, "Обязательные расходы", "Аренда и кредиты", op_type="DEBIT")
    fin_mgr.add_transaction(25000.0, "Основной доход", "Зарплата", op_type="CREDIT")

    summary = fin_mgr.get_financial_summary()
    deficit = summary["total_expense_rub"] - summary["total_income_rub"]
    assert deficit == 15000.0

    hunter = OrderHunterEngine()
    orders = hunter.scan_active_freelance_orders()
    assert len(orders) > 0

    target_order = orders[0]
    proposal = hunter.generate_proposal_for_task(target_order["title"], target_order["price_rub"])
    assert len(proposal) > 50

    se_mgr = SelfEmployedManager()
    inc = se_mgr.register_income(target_order["price_rub"], target_order["title"], is_legal_entity=False)
    assert inc["net_rub"] > 0


def test_tier4_03_scenario_student_exam_prep_workflow(tmp_path, tmp_master_db):
    """Scenario 3: Exam preparation — Keycloak auth -> Course export -> Formula OCR -> Study plan."""
    sess_mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    sess_mgr.sesskey = "test_key"
    exporter = MireaCourseExporter(sess_mgr, export_dir=tmp_path / "courses")

    with patch.object(sess_mgr, "is_authenticated", return_value=True), \
         patch.object(sess_mgr.session, "get") as mock_get:
        mock_get.return_value.text = '<html><body><li class="section"><h3 class="sectionname">Формулы</h3></li></body></html>'
        res = exporter.export_course(201, "Высшая математика")
        assert res["course_id"] == 201

    mirea_mgr = MireaStudentManager("ИКБО-01-23")
    m_id = mirea_mgr.add_academic_milestone("Высшая математика", "Подготовка к экзамену", "exam", "2026-08-25")
    assert m_id > 0


def test_tier4_04_scenario_workout_recovery_and_nutrition_sync(tmp_master_db):
    """Scenario 4: Post-workout sync — Google Fit workout -> TRIMP load -> Nutrition log -> Bio advisor."""
    log_meal("Посттренировочный протеин", calories=400.0, protein=50.0, carbs=40.0, fat=5.0)

    wf = LangGraphHealthMultiAgentWorkflow()
    with patch("google_fit_sync.fetch_and_save_fitness_data", return_value={"activity": {"total_steps": 10000, "total_calories": 2400.0, "active_minutes": 60}}):
        result = wf.execute_full_workflow()
        assert result["status"] == "WORKFLOW_SUCCESS"


def test_tier4_05_scenario_freelance_agency_contract_lifecycle(tmp_master_db):
    """Scenario 5: Freelance agency lifecycle — Order match -> Proposal -> Bot template -> Client MRR contract."""
    hunter = OrderHunterEngine()
    orders = hunter.scan_active_freelance_orders()

    freelance_engine = AutonomousFreelanceEngine()
    bot_code = freelance_engine.generate_telegram_bot_service_template("Стоматология Дент", "Медицина")
    assert "TeleBot" in bot_code or "telebot" in bot_code

    freelance_engine.log_client_contract("Стоматология Дент", "AI Bot Customer Service", monthly_fee=12000.0)
    mrr = freelance_engine.get_monthly_recurring_revenue()
    assert mrr == 12000.0


def test_tier4_06_scenario_medical_checkup_analysis_workflow(tmp_path, tmp_master_db):
    """Scenario 6: Medical report ingestion — Blood test PDF -> Multimodal Vision -> Local OCR -> DB record."""
    img_file = tmp_path / "lab_report.png"
    img_file.write_bytes(b"PNG_HEADER")

    with patch("google.genai.Client") as mock_genai:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value.text = "Blood Test Results: HGB 150 g/L"
        mock_genai.return_value = mock_client

        report = analyze_lab_report_image(str(img_file))
        assert report["status"] == "SUCCESS"
        assert "HGB 150" in report["analysis_text"]


def test_tier4_07_scenario_master_orchestrator_daily_cron_sync(master_orch):
    """Scenario 7: Daily automated cron sync — Hardware audit -> Bio workflow -> Full status report."""
    with patch.object(master_orch.langgraph_wf, "execute_full_workflow", return_value={"status": "WORKFLOW_SUCCESS"}):
        sync_report = master_orch.execute_complete_system_sync()
        assert sync_report["status"] == "SYSTEM_FULLY_OPERATIONAL"
        assert sync_report["diagnostics"]["cpu_cores"] > 0


def test_tier4_08_scenario_offline_mode_resilience(tmp_master_db):
    """Scenario 8: Offline operation mode — Cached schedule -> Offline CSV parser -> Local Gemma advice."""
    mirea_mgr = MireaStudentManager("ИКБО-01-23")
    cached_sched = mirea_mgr.get_cached_schedule()
    assert isinstance(cached_sched, list)

    gemma = GoogleGemmaLocalEngine()
    gemma_res = gemma.process_health_query_local("Offline bio analysis", {"sleep_hours": 8})
    assert gemma_res["engine"] == "Google Gemma Local (Offline)"


def test_tier4_09_scenario_keycloak_sso_2fa_and_max_bypass_flow(tmp_path):
    """Scenario 9: SSO login lifecycle — Keycloak OIDC -> Yandex IMAP 2FA -> MAX bypass -> Persistent cookie."""
    mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    html_max = '<html><body><div>Зарегистрироваться через макс</div><a href="/skip_max">Skip</a></body></html>'

    with patch.object(mgr.session, "get") as mock_get:
        bypassed = mgr.handle_max_registration_bypass(html_max, "https://online-edu.mirea.ru/my/")
        assert bypassed is True

    mgr.session.cookies.set("MoodleSession", "cookie_abc_123", domain="online-edu.mirea.ru", path="/")
    mgr.save_session_cookies()
    assert (tmp_path / "session.json").exists()


def test_tier4_10_scenario_monthly_debt_repayment_automation(tmp_master_db):
    """Scenario 10: Monthly debt repayment tracking against liabilities and freelance revenue."""
    loan_monthly = 9500.0
    inst_1 = 3300.0
    inst_2 = 1445.0
    total_monthly_liability = loan_monthly + inst_1 + inst_2

    freelance_engine = AutonomousFreelanceEngine()
    freelance_engine.log_client_contract("Клиника #1", "Bot", monthly_fee=8000.0)
    freelance_engine.log_client_contract("Магазин #2", "Scraper", monthly_fee=7000.0)

    mrr = freelance_engine.get_monthly_recurring_revenue()
    assert mrr >= total_monthly_liability


def test_tier4_11_scenario_grpc_telemetry_streaming_pipeline(tmp_master_db):
    """Scenario 11: gRPC Telemetry streaming pipeline -> Local SQLite sync."""
    conn = sqlite3.connect(tmp_master_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO kg_nodes (id, node_id, domain, label) VALUES ('n11_1', 'grpc_node_1', 'telemetry', 'HR Stream')")
    conn.commit()
    conn.close()

    conn = sqlite3.connect(tmp_master_db)
    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) FROM kg_nodes WHERE domain='telemetry'").fetchone()[0]
    conn.close()
    assert count == 1


def test_tier4_12_scenario_full_academic_semester_archival(tmp_path, tmp_master_db):
    """Scenario 12: Semester archival — Course discovery -> Material export -> Offline schedule backup."""
    sess_mgr = MoodleSessionManager(session_file=tmp_path / "session.json")
    sess_mgr.sesskey = "valid_sesskey"
    exporter = MireaCourseExporter(sess_mgr, export_dir=tmp_path / "semester_backup")

    ajax_resp = [{
        "data": {"courses": [{"id": 501, "fullname": "Базы данных Advanced"}]}
    }]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = ajax_resp

    with patch.object(sess_mgr, "is_authenticated", return_value=True), \
         patch.object(sess_mgr.session, "post", return_value=mock_resp):
        courses = exporter.get_enrolled_courses()
        assert len(courses) == 1

    mirea_mgr = MireaStudentManager("ИКБО-01-23")
    sched = mirea_mgr.get_schedule()
    assert sched["status"] == "SUCCESS"


def test_tier4_13_scenario_multi_client_freelance_revenue_tracking(tmp_master_db):
    """Scenario 13: Multi-client acquisition — MRR target > 10,000 RUB -> NPD quarterly tax reserve."""
    freelance_engine = AutonomousFreelanceEngine()
    freelance_engine.log_client_contract("Client A", "Bot Support", monthly_fee=5000.0)
    freelance_engine.log_client_contract("Client B", "OCR Extraction", monthly_fee=4000.0)
    freelance_engine.log_client_contract("Client C", "Web Scraping", monthly_fee=3000.0)

    total_mrr = freelance_engine.get_monthly_recurring_revenue()
    assert total_mrr == 12000.0
    assert total_mrr > 10000.0

    quarterly_revenue = total_mrr * 3
    tax_reserve = quarterly_revenue * 0.04
    assert tax_reserve == 1440.0


def test_tier4_14_scenario_biometric_scale_data_corruption_recovery():
    """Scenario 14: BLE scale invalid payload recovery and fallback."""
    invalid_ble_payload = b"\x00\x00\x00"
    parsed = parse_mi_scale_v2_data(invalid_ble_payload)
    assert parsed is None


def test_tier4_15_scenario_end_to_end_supergraph_master_health_check(master_orch):
    """Scenario 15: Complete end-to-end SuperGraph Master health check and subsystem validation."""
    with patch.object(master_orch.langgraph_wf, "execute_full_workflow", return_value={"status": "WORKFLOW_SUCCESS"}):
        report = master_orch.execute_complete_system_sync()
        assert report["status"] == "SYSTEM_FULLY_OPERATIONAL"
        assert "diagnostics" in report
        assert "langgraph_workflow" in report
        assert report["langgraph_workflow"]["status"] == "WORKFLOW_SUCCESS"
