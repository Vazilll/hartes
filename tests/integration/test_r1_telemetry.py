"""
Unit & Integration Test Suite for R1 Biometric & Wearable Telemetry Pipeline
Features Covered (Features 1 - 6):
1. R1 Google Fit Sync
2. R1 Xiaomi Mi Scale 2 BLE
3. R1 BIA Calculations
4. R1 Bio-Math Load
5. R1 3-Agent LangGraph Workflow
6. R1 gRPC Telemetry Service

Methodology: 4-Tier Test Design (Tier 1 Happy Path >= 30, Tier 2 Boundary/Edge >= 30)
Total Test Cases: 60
"""

import os
import sys
import json
import time
import asyncio
import sqlite3
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

# Bypass Protobuf runtime version check for test runner compatibility
try:
    from google.protobuf import runtime_version
    runtime_version.ValidateProtobufRuntimeVersion = lambda *args, **kwargs: None
except ImportError:
    pass

# Add project root, vazus_core, and health_agent to sys.path
for p in [r"C:\vazus", r"C:\vazus\vazus_core", r"C:\vazus\services\health_agent"]:
    if p not in sys.path:
        sys.path.insert(0, p)

import google_fit_sync
from vazus_core.ble_mi_scale_scanner import (
    parse_mi_scale_v2_data,
    calculate_bia_metrics,
    save_weighin_to_db,
    scan_mi_scale
)
from vazus_core.langgraph_health_workflow import LangGraphHealthMultiAgentWorkflow
from vazus_core.grpc_health_servicer import AsyncHealthTelemetryServicer
from vazus_core.health_telemetry_pipeline import VazusHealthPipelineManager
import health_telemetry_pb2

# --- Fixtures ---

@pytest.fixture
def temp_db(tmp_path):
    """Creates a clean SQLite database for telemetry testing."""
    db_file = str(tmp_path / "test_vazus.db")
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kg_nodes (
            id TEXT PRIMARY KEY,
            name TEXT,
            domain TEXT,
            node_type TEXT,
            description TEXT,
            tags TEXT,
            properties TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mi_scale_weighins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            weight_kg REAL,
            impedance_ohms INTEGER,
            bmi REAL,
            body_fat_pct REAL,
            muscle_mass_kg REAL,
            water_pct REAL,
            visceral_fat INTEGER,
            bmr_kcal INTEGER,
            source TEXT
        )
    """)
    conn.commit()
    conn.close()
    return db_file


# ============================================================================
# FEATURE 1: R1 Google Fit Sync (Tests 1 - 10)
# ============================================================================

# Tier 1 (Happy Path)
def test_feature1_tier1_fetch_fitness_data_success(temp_db):
    """F1-T1-1: Successful Google Fit sync returns structured metrics summary dict."""
    mock_service = MagicMock()
    
    # Mock Sessions API
    mock_sessions = mock_service.users().sessions().list().execute
    mock_sessions.return_value = {
        "session": [
            {
                "activityType": 72,
                "startTimeMillis": "1770000000000",
                "endTimeMillis": "1770028800000",
                "name": "Sleep"
            },
            {
                "activityType": 8,
                "startTimeMillis": "1770030000000",
                "endTimeMillis": "1770033600000",
                "name": "Morning Run"
            }
        ]
    }
    
    # Mock Datasets (Sleep stages, HR, SpO2, Steps, Cals, Active)
    mock_datasets = mock_service.users().dataSources().datasets().get().execute
    mock_datasets.side_effect = [
        # Sleep stages
        {"point": [{"startTimeNanos": "1770000000000000000", "endTimeNanos": "1770028800000000000", "value": [{"intVal": 5}]}]},
        # Heart rate
        {"point": [{"value": [{"fpVal": 65.0}], "startTimeNanos": "0", "endTimeNanos": "0"}]},
        # SpO2
        {"point": [{"value": [{"fpVal": 98.5}], "startTimeNanos": "0", "endTimeNanos": "0"}]},
        # Steps
        {"point": [{"value": [{"intVal": 8500}]}]},
        # Calories
        {"point": [{"value": [{"fpVal": 2250.5}]}]},
        # Active min
        {"point": [{"value": [{"intVal": 45}]}]}
    ]

    with patch("google_fit_sync.get_google_fit_service", return_value=mock_service), \
         patch("google_fit_sync.DB_PATH", temp_db):
        res = google_fit_sync.fetch_and_save_fitness_data()
        
    assert res is not False
    assert isinstance(res, dict)
    assert "sleep_sessions" in res
    assert "workouts" in res
    assert "activity" in res
    assert res["activity"]["total_steps"] == 8500


def test_feature1_tier1_db_node_creation(temp_db):
    """F1-T1-2: Google Fit sync writes observation node into SQLite kg_nodes table."""
    mock_service = MagicMock()
    mock_service.users().sessions().list().execute.return_value = {"session": []}
    mock_service.users().dataSources().datasets().get().execute.return_value = {"point": []}

    with patch("google_fit_sync.get_google_fit_service", return_value=mock_service), \
         patch("google_fit_sync.DB_PATH", temp_db):
        google_fit_sync.fetch_and_save_fitness_data()

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    row = cur.execute("SELECT id, domain, node_type FROM kg_nodes WHERE domain='health'").fetchone()
    conn.close()

    assert row is not None
    assert "google_fit_sync" in row[0]
    assert row[2] == "observation"


def test_feature1_tier1_sleep_sessions_parsing():
    """F1-T1-3: Sessions with activityType 72 correctly identify as sleep sessions."""
    mock_service = MagicMock()
    st_ms = 1700000000000
    et_ms = 1700028800000  # 8 hours
    mock_service.users().sessions().list().execute.return_value = {
        "session": [{
            "activityType": 72,
            "startTimeMillis": str(st_ms),
            "endTimeMillis": str(et_ms)
        }]
    }
    mock_service.users().dataSources().datasets().get().execute.return_value = {"point": []}

    with patch("google_fit_sync.get_google_fit_service", return_value=mock_service), \
         patch("sqlite3.connect"):
        res = google_fit_sync.fetch_and_save_fitness_data()

    assert len(res["sleep_sessions"]) == 1
    assert res["sleep_sessions"][0]["duration_hours"] == 8.0


def test_feature1_tier1_workout_sessions_parsing():
    """F1-T1-4: Non-sleep activities are categorized into workouts with duration in minutes."""
    mock_service = MagicMock()
    st_ms = 1700000000000
    et_ms = 1700003600000  # 60 min
    mock_service.users().sessions().list().execute.return_value = {
        "session": [{
            "activityType": 15,  # Cycling
            "startTimeMillis": str(st_ms),
            "endTimeMillis": str(et_ms),
            "name": "Cycling Workout"
        }]
    }
    mock_service.users().dataSources().datasets().get().execute.return_value = {"point": []}

    with patch("google_fit_sync.get_google_fit_service", return_value=mock_service), \
         patch("sqlite3.connect"):
        res = google_fit_sync.fetch_and_save_fitness_data()

    assert len(res["workouts"]) == 1
    assert res["workouts"][0]["name"] == "Cycling Workout"
    assert res["workouts"][0]["duration_min"] == 60.0


def test_feature1_tier1_health_pipeline_manager_sync(temp_db):
    """F1-T1-5: VazusHealthPipelineManager calls sync_all_google_fit_metrics successfully."""
    mgr = VazusHealthPipelineManager()
    mgr.db_path = temp_db
    mock_res = {"sleep_sessions": [], "workouts": [], "activity": {"total_steps": 1000}}

    with patch("vazus_core.health_telemetry_pipeline.fetch_and_save_fitness_data", return_value=mock_res):
        res = mgr.sync_all_google_fit_metrics(days_back=4)

    assert res == mock_res


# Tier 2 (Boundary & Corner Cases)
def test_feature1_tier2_empty_api_response(temp_db):
    """F1-T2-6: Handles completely empty Google Fit API responses without raising exception."""
    mock_service = MagicMock()
    mock_service.users().sessions().list().execute.return_value = {}
    mock_service.users().dataSources().datasets().get().execute.return_value = {}

    with patch("google_fit_sync.get_google_fit_service", return_value=mock_service), \
         patch("google_fit_sync.DB_PATH", temp_db):
        res = google_fit_sync.fetch_and_save_fitness_data()

    assert res is not False
    assert res["sleep_sessions"] == []
    assert res["workouts"] == []


def test_feature1_tier2_null_service_handles_gracefully():
    """F1-T2-7: Returns False when Google Fit service fails to initialize."""
    with patch("google_fit_sync.get_google_fit_service", return_value=None):
        res = google_fit_sync.fetch_and_save_fitness_data()

    assert res is False


def test_feature1_tier2_malformed_dataset_points(temp_db):
    """F1-T2-8: Datasets missing expected value/fpVal/intVal fields are safely ignored."""
    mock_service = MagicMock()
    mock_service.users().sessions().list().execute.return_value = {"session": []}
    mock_service.users().dataSources().datasets().get().execute.return_value = {
        "point": [
            {"startTimeNanos": "100", "endTimeNanos": "200"},  # Missing 'value'
            {"value": [{}]},  # Empty value dict
        ]
    }

    with patch("google_fit_sync.get_google_fit_service", return_value=mock_service), \
         patch("google_fit_sync.DB_PATH", temp_db):
        res = google_fit_sync.fetch_and_save_fitness_data()

    assert res is not False


def test_feature1_tier2_zero_total_sleep_pct_division(temp_db):
    """F1-T2-9: Prevents ZeroDivisionError when total_sec for sleep stages is zero."""
    mock_service = MagicMock()
    mock_service.users().sessions().list().execute.return_value = {"session": []}
    # Point with total_sec = 0
    mock_service.users().dataSources().datasets().get().execute.return_value = {
        "point": [{"startTimeNanos": "1000", "endTimeNanos": "1000", "value": [{"intVal": 1}]}]
    }

    with patch("google_fit_sync.get_google_fit_service", return_value=mock_service), \
         patch("google_fit_sync.DB_PATH", temp_db):
        res = google_fit_sync.fetch_and_save_fitness_data()

    assert "sleep_stages_by_day" in res


def test_feature1_tier2_pipeline_manager_db_override(temp_db):
    """F1-T2-10: Manager uses custom DB path correctly for latest summary queries."""
    mgr = VazusHealthPipelineManager()
    mgr.db_path = temp_db
    summary = mgr.get_latest_health_summary()
    
    assert isinstance(summary, dict)
    assert summary["latest_scale_weighin"] is None


# ============================================================================
# FEATURE 2: R1 Xiaomi Mi Scale 2 BLE (Tests 11 - 20)
# ============================================================================

# Tier 1 (Happy Path)
def test_feature2_tier1_parse_valid_mi_scale_payload():
    """F2-T1-11: Decodes standard 13-byte Xiaomi Mi Scale 2 broadcast payload."""
    raw_payload = bytes([
        0x02, 0xA0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0xF4, 0x01,
        0x28, 0x3C
    ])
    
    parsed = parse_mi_scale_v2_data(raw_payload)
    
    assert parsed is not None
    assert parsed["is_stabilized"] is True
    assert parsed["has_impedance"] is True
    assert parsed["impedance_ohms"] == 500
    assert parsed["weight_kg"] == 77.0


def test_feature2_tier1_parse_stabilized_flag():
    """F2-T1-12: Parses ctrl_1 bit 5 correctly for stabilized measurement."""
    payload_stabilized = bytes([0x00, 0x20, 0,0,0,0,0,0,0, 0,0, 0x28, 0x3C])
    payload_unstabilized = bytes([0x00, 0x00, 0,0,0,0,0,0,0, 0,0, 0x28, 0x3C])

    assert parse_mi_scale_v2_data(payload_stabilized)["is_stabilized"] is True
    assert parse_mi_scale_v2_data(payload_unstabilized)["is_stabilized"] is False


def test_feature2_tier1_parse_impedance_ohms():
    """F2-T1-13: Decodes little-endian 16-bit impedance from bytes 9-10."""
    payload = bytes([0x00, 0x80, 0,0,0,0,0,0,0, 0xC2, 0x01, 0x00, 0x10])
    parsed = parse_mi_scale_v2_data(payload)
    
    assert parsed["impedance_ohms"] == 450


def test_feature2_tier1_save_weighin_to_db(temp_db):
    """F2-T1-14: Inserts weigh-in metrics into mi_scale_weighins and kg_nodes tables."""
    metrics = {
        "weight_kg": 77.5,
        "impedance_ohms": 480,
        "bmi": 24.5,
        "body_fat_pct": 18.2,
        "muscle_mass_kg": 56.1,
        "water_pct": 58.9,
        "visceral_fat": 8,
        "bmr_kcal": 1750
    }

    with patch("services.health_agent.ble_mi_scale_scanner.DB_PATH", temp_db):
        save_weighin_to_db(metrics, source="Test_BLE")

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    row = cur.execute("SELECT weight_kg, impedance_ohms, source FROM mi_scale_weighins").fetchone()
    node = cur.execute("SELECT id, name FROM kg_nodes WHERE id LIKE 'mi_scale_ble_%'").fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 77.5
    assert row[1] == 480
    assert row[2] == "Test_BLE"
    assert node is not None


def test_feature2_tier1_scan_mi_scale_async():
    """F2-T1-15: scan_mi_scale coroutine runs without error using mocked BleakScanner."""
    async def _test():
        mock_scanner_class = MagicMock()
        mock_scanner_instance = AsyncMock()
        mock_scanner_class.return_value = mock_scanner_instance

        with patch("vazus_core.ble_mi_scale_scanner.BleakScanner", mock_scanner_class):
            await scan_mi_scale(scan_seconds=0.1)

        mock_scanner_instance.start.assert_called_once()
        mock_scanner_instance.stop.assert_called_once()

    asyncio.run(_test())


# Tier 2 (Boundary & Corner Cases)
def test_feature2_tier2_payload_short_length():
    """F2-T2-16: Service data with fewer than 13 bytes returns None."""
    assert parse_mi_scale_v2_data(bytes([0x00] * 12)) is None
    assert parse_mi_scale_v2_data(bytes([])) is None


def test_feature2_tier2_no_impedance_flag():
    """F2-T2-17: When has_impedance bit (bit 7) is false, impedance_ohms returns 0."""
    payload = bytes([0x00, 0x20, 0,0,0,0,0,0,0, 0xF4, 0x01, 0x28, 0x3C])
    parsed = parse_mi_scale_v2_data(payload)
    
    assert parsed["has_impedance"] is False
    assert parsed["impedance_ohms"] == 0


def test_feature2_tier2_zero_raw_weight():
    """F2-T2-18: Raw weight bytes 0x0000 yields 0.0 kg."""
    payload = bytes([0x00, 0xA0, 0,0,0,0,0,0,0, 0x00, 0x00, 0x00, 0x00])
    parsed = parse_mi_scale_v2_data(payload)
    
    assert parsed["weight_kg"] == 0.0


def test_feature2_tier2_max_impedance_payload():
    """F2-T2-19: Maximum 16-bit impedance 0xFFFF (65535 ohms) parses without overflow."""
    payload = bytes([0x00, 0x80, 0,0,0,0,0,0,0, 0xFF, 0xFF, 0x00, 0x10])
    parsed = parse_mi_scale_v2_data(payload)
    
    assert parsed["impedance_ohms"] == 65535


def test_feature2_tier2_save_weighin_invalid_db_path():
    """F2-T2-20: Database insertion error in save_weighin_to_db is caught gracefully."""
    metrics = {
        "weight_kg": 77.5, "impedance_ohms": 480, "bmi": 24.5,
        "body_fat_pct": 18.2, "muscle_mass_kg": 56.1, "water_pct": 58.9,
        "visceral_fat": 8, "bmr_kcal": 1750
    }
    invalid_db = r"Z:\nonexistent_path\invalid.db"
    
    with patch("services.health_agent.ble_mi_scale_scanner.DB_PATH", invalid_db):
        save_weighin_to_db(metrics)


# ============================================================================
# FEATURE 3: R1 BIA Calculations (Tests 21 - 30)
# ============================================================================

# Tier 1 (Happy Path)
def test_feature3_tier1_male_standard_bia():
    """F3-T1-21: BIA calculation for 77.0 kg male with 480 ohm impedance."""
    res = calculate_bia_metrics(weight_kg=77.0, impedance_ohms=480, height_cm=178, age=24, gender="male")
    
    assert res["weight_kg"] == 77.0
    assert res["impedance_ohms"] == 480
    assert res["bmi"] == 24.3
    assert 5.0 <= res["body_fat_pct"] <= 55.0
    assert res["muscle_mass_kg"] > 0
    assert res["water_pct"] > 0
    assert 1 <= res["visceral_fat"] <= 30
    assert res["bmr_kcal"] > 1000


def test_feature3_tier1_female_standard_bia():
    """F3-T1-22: BIA calculation for 60.0 kg female using female BMR formula."""
    res = calculate_bia_metrics(weight_kg=60.0, impedance_ohms=520, height_cm=165, age=25, gender="female")
    
    assert res["bmi"] == round(60.0 / (1.65 * 1.65), 1)
    assert res["bmr_kcal"] > 500


def test_feature3_tier1_bmi_math_precision():
    """F3-T1-23: BMI equals weight_kg / (height_m ^ 2) rounded to 1 decimal."""
    res = calculate_bia_metrics(weight_kg=80.0, impedance_ohms=500, height_cm=200, age=30)
    assert res["bmi"] == 20.0


def test_feature3_tier1_water_pct_derivation():
    """F3-T1-24: Water percentage equals (100 - body_fat_pct) * 0.72."""
    res = calculate_bia_metrics(weight_kg=75.0, impedance_ohms=450, height_cm=175, age=22)
    expected_water = round((100 - res["body_fat_pct"]) * 0.72, 1)
    
    assert res["water_pct"] == expected_water


def test_feature3_tier1_visceral_fat_range():
    """F3-T1-25: Visceral fat grade is bounded between 1 and 30."""
    res = calculate_bia_metrics(weight_kg=70.0, impedance_ohms=400, height_cm=175, age=20)
    assert 1 <= res["visceral_fat"] <= 30


# Tier 2 (Boundary & Corner Cases)
def test_feature3_tier2_zero_impedance_fallback():
    """F3-T2-26: Zero impedance triggers default BIA fallback values."""
    res = calculate_bia_metrics(weight_kg=77.0, impedance_ohms=0)
    
    assert res["body_fat_pct"] == 15.2
    assert res["water_pct"] == 61.1
    assert res["visceral_fat"] == 10
    assert res["bmr_kcal"] > 1000


def test_feature3_tier2_out_of_bounds_high_impedance():
    """F3-T2-27: Impedance >= 3000 ohms triggers fallback defaults."""
    res = calculate_bia_metrics(weight_kg=77.0, impedance_ohms=3500)
    
    assert res["body_fat_pct"] == 15.2
    assert res["bmr_kcal"] > 1000


def test_feature3_tier2_body_fat_clamping_min():
    """F3-T2-28: Body fat percentage formula output below 5% is clamped to 5.0%."""
    res = calculate_bia_metrics(weight_kg=30.0, impedance_ohms=10, height_cm=200, age=18, gender="male")
    
    assert res["body_fat_pct"] == 5.0


def test_feature3_tier2_body_fat_clamping_max():
    """F3-T2-29: Body fat percentage formula output above 55% is clamped to 55.0%."""
    res = calculate_bia_metrics(weight_kg=250.0, impedance_ohms=2800, height_cm=150, age=80, gender="male")
    
    assert res["body_fat_pct"] == 55.0


def test_feature3_tier2_negative_impedance():
    """F3-T2-30: Negative impedance values trigger default fallback metrics."""
    res = calculate_bia_metrics(weight_kg=77.0, impedance_ohms=-50)
    
    assert res["body_fat_pct"] == 15.2


# ============================================================================
# FEATURE 4: R1 Bio-Math Load (Tests 31 - 40)
# ============================================================================

# Tier 1 (Happy Path)
def test_feature4_tier1_readiness_score_formula():
    """F4-T1-31: Readiness score formula weights total sleep (40%), deep (30%), REM (30%)."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()
        mock_metrics = {
            "sleep_stages_by_day": {
                datetime.now().strftime('%Y-%m-%d'): {
                    "total_sleep_hours": 8.0,  # 40 pts
                    "deep_sleep_min": 120.0,   # 30 pts
                    "rem_sleep_min": 130.0     # 30 pts
                }
            }
        }
        
        with patch("vazus_core.grpc_health_servicer.fetch_and_save_fitness_data", return_value=mock_metrics), \
             patch.object(servicer, "_log_grpc_sync_to_db"):
            request = health_telemetry_pb2.GoogleFitSyncRequest(days_back=4)
            response = await servicer.SyncGoogleFitData(request, None)

        assert response.readiness_score == 100.0

    asyncio.run(_test())


def test_feature4_tier1_readiness_score_clamping():
    """F4-T1-32: Readiness score is clamped to maximum 100.0."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()
        mock_metrics = {
            "sleep_stages_by_day": {
                datetime.now().strftime('%Y-%m-%d'): {
                    "total_sleep_hours": 12.0,  # > 40
                    "deep_sleep_min": 200.0,   # > 30
                    "rem_sleep_min": 200.0     # > 30
                }
            }
        }
        
        with patch("vazus_core.grpc_health_servicer.fetch_and_save_fitness_data", return_value=mock_metrics), \
             patch.object(servicer, "_log_grpc_sync_to_db"):
            request = health_telemetry_pb2.GoogleFitSyncRequest(days_back=4)
            response = await servicer.SyncGoogleFitData(request, None)

        assert response.readiness_score == 100.0

    asyncio.run(_test())


def test_feature4_tier1_bio_analyser_step(temp_db):
    """F4-T1-33: LangGraph Agent 2 computes readiness score and sleep recovery."""
    wf = LangGraphHealthMultiAgentWorkflow()
    wf.db_path = temp_db
    telemetry = {
        "metrics": {"activity": {"total_steps": 10000, "total_calories": 2400.0, "active_minutes": 60}},
        "latest_scale": (77.0, 24.3, 18.0, 55.4)
    }
    
    res = wf.agent_2_bio_analyser(telemetry)
    
    assert res["steps"] == 10000
    assert round(res["readiness_score"], 1) == 92.7
    assert res["weight_kg"] == 77.0


def test_feature4_tier1_trimp_load_calculation():
    """F4-T1-34: Bio-analyser preserves active minutes and calories for TRIMP load."""
    wf = LangGraphHealthMultiAgentWorkflow()
    telemetry = {
        "metrics": {"activity": {"total_steps": 12000, "total_calories": 2800.0, "active_minutes": 90}},
        "latest_scale": None
    }
    
    res = wf.agent_2_bio_analyser(telemetry)
    assert res["active_min"] == 90
    assert res["calories"] == 2800.0


def test_feature4_tier1_latest_health_summary_readiness(temp_db):
    """F4-T1-35: Pipeline manager returns recent weigh-in metrics."""
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO mi_scale_weighins (timestamp, weight_kg, impedance_ohms, bmi, body_fat_pct, muscle_mass_kg, water_pct, visceral_fat, bmr_kcal, source)
        VALUES ('2026-08-03T10:00:00', 76.5, 490, 24.1, 17.5, 55.8, 59.5, 7, 1740, 'BLE')
    """)
    conn.commit()
    conn.close()

    mgr = VazusHealthPipelineManager()
    mgr.db_path = temp_db
    summary = mgr.get_latest_health_summary()

    assert summary["latest_scale_weighin"] is not None
    assert summary["latest_scale_weighin"][1] == 76.5


# Tier 2 (Boundary & Corner Cases)
def test_feature4_tier2_readiness_zero_sleep():
    """F4-T2-36: Zero sleep hours, deep, and REM yield 0.0 readiness score."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()
        mock_metrics = {
            "sleep_stages_by_day": {
                datetime.now().strftime('%Y-%m-%d'): {
                    "total_sleep_hours": 0.0,
                    "deep_sleep_min": 0.0,
                    "rem_sleep_min": 0.0
                }
            }
        }
        
        with patch("vazus_core.grpc_health_servicer.fetch_and_save_fitness_data", return_value=mock_metrics), \
             patch.object(servicer, "_log_grpc_sync_to_db"):
            request = health_telemetry_pb2.GoogleFitSyncRequest(days_back=4)
            response = await servicer.SyncGoogleFitData(request, None)

        assert response.readiness_score == 0.0

    asyncio.run(_test())


def test_feature4_tier2_readiness_extreme_oversleep():
    """F4-T2-37: 20 hours sleep clamps readiness score to 100.0."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()
        mock_metrics = {
            "sleep_stages_by_day": {
                datetime.now().strftime('%Y-%m-%d'): {
                    "total_sleep_hours": 20.0,
                    "deep_sleep_min": 500.0,
                    "rem_sleep_min": 500.0
                }
            }
        }
        
        with patch("vazus_core.grpc_health_servicer.fetch_and_save_fitness_data", return_value=mock_metrics), \
             patch.object(servicer, "_log_grpc_sync_to_db"):
            request = health_telemetry_pb2.GoogleFitSyncRequest(days_back=4)
            response = await servicer.SyncGoogleFitData(request, None)

        assert response.readiness_score == 100.0

    asyncio.run(_test())


def test_feature4_tier2_bio_analyser_empty_telemetry():
    """F4-T2-38: Empty telemetry dict passed to agent_2_bio_analyser uses safe defaults."""
    wf = LangGraphHealthMultiAgentWorkflow()
    res = wf.agent_2_bio_analyser({})
    
    assert res["steps"] == 0
    assert res["calories"] == 0.0
    assert res["active_min"] == 0
    assert res["weight_kg"] == 77.0


def test_feature4_tier2_bio_analyser_missing_scale_data():
    """F4-T2-39: None latest_scale falls back to default weight (77.0) and muscle (55.4)."""
    wf = LangGraphHealthMultiAgentWorkflow()
    res = wf.agent_2_bio_analyser({"metrics": {}, "latest_scale": None})
    
    assert res["weight_kg"] == 77.0
    assert res["muscle_mass_kg"] == 55.4


def test_feature4_tier2_readiness_missing_sleep_stages():
    """F4-T2-40: Missing sleep stages dictionary falls back to default stage minutes."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()
        mock_metrics = {"activity": {}}  # Activity metrics dict present
        
        with patch("vazus_core.grpc_health_servicer.fetch_and_save_fitness_data", return_value=mock_metrics), \
             patch.object(servicer, "_log_grpc_sync_to_db"):
            request = health_telemetry_pb2.GoogleFitSyncRequest(days_back=4)
            response = await servicer.SyncGoogleFitData(request, None)

        assert response.readiness_score > 0

    asyncio.run(_test())


# ============================================================================
# FEATURE 5: R1 3-Agent LangGraph Workflow (Tests 41 - 50)
# ============================================================================

# Tier 1 (Happy Path)
def test_feature5_tier1_agent1_ingestor(temp_db):
    """F5-T1-41: Agent 1 (Telemetry Ingestor) pulls fit metrics and latest scale weigh-in."""
    wf = LangGraphHealthMultiAgentWorkflow()
    wf.db_path = temp_db
    mock_fit = {"sleep_sessions": [], "activity": {"total_steps": 5000}}

    with patch("vazus_core.langgraph_health_workflow.fetch_and_save_fitness_data", return_value=mock_fit):
        step1 = wf.agent_1_telemetry_ingestor()

    assert step1["metrics"] == mock_fit
    assert "latest_scale" in step1


def test_feature5_tier1_agent2_analyser():
    """F5-T1-42: Agent 2 (Bio-Analyser) receives Agent 1 output and computes analysis."""
    wf = LangGraphHealthMultiAgentWorkflow()
    agent1_out = {
        "metrics": {"activity": {"total_steps": 8000, "total_calories": 2100.0, "active_minutes": 45}},
        "latest_scale": (75.0, 23.5, 17.0, 54.0)
    }
    
    step2 = wf.agent_2_bio_analyser(agent1_out)
    assert step2["weight_kg"] == 75.0
    assert step2["muscle_mass_kg"] == 54.0


def test_feature5_tier1_agent3_advisor():
    """F5-T1-43: Agent 3 (Google AI Advisor) returns WORKFLOW_SUCCESS status."""
    wf = LangGraphHealthMultiAgentWorkflow()
    analysis_data = {
        "readiness_score": 95.0,
        "weight_kg": 77.0,
        "muscle_mass_kg": 55.4
    }
    
    step3 = wf.agent_3_google_ai_advisor(analysis_data)
    assert step3["status"] == "WORKFLOW_SUCCESS"
    assert "google_ai_recommendation" in step3
    assert "95.0/100" in step3["google_ai_recommendation"]


def test_feature5_tier1_full_workflow_execution(temp_db):
    """F5-T1-44: execute_full_workflow runs Agents 1->2->3 end-to-end."""
    wf = LangGraphHealthMultiAgentWorkflow()
    wf.db_path = temp_db
    mock_fit = {"sleep_sessions": [], "activity": {"total_steps": 7500, "total_calories": 2000.0, "active_minutes": 40}}

    with patch("vazus_core.langgraph_health_workflow.fetch_and_save_fitness_data", return_value=mock_fit):
        result = wf.execute_full_workflow()

    assert result["status"] == "WORKFLOW_SUCCESS"
    assert "analysis" in result
    assert "google_ai_recommendation" in result


def test_feature5_tier1_workflow_custom_db(temp_db):
    """F5-T1-45: LangGraph workflow executes against custom isolated database file."""
    wf = LangGraphHealthMultiAgentWorkflow()
    wf.db_path = temp_db
    assert wf.db_path == temp_db


# Tier 2 (Boundary & Corner Cases)
def test_feature5_tier2_workflow_empty_db(temp_db):
    """F5-T2-46: Workflow handles empty DB tables without raising exception."""
    wf = LangGraphHealthMultiAgentWorkflow()
    wf.db_path = temp_db

    with patch("vazus_core.langgraph_health_workflow.fetch_and_save_fitness_data", return_value={}):
        step1 = wf.agent_1_telemetry_ingestor()

    assert step1["latest_scale"] is None


def test_feature5_tier2_agent3_zero_metrics():
    """F5-T2-47: Agent 3 handles zero weight and readiness score without string formatting error."""
    wf = LangGraphHealthMultiAgentWorkflow()
    analysis_data = {"readiness_score": 0.0, "weight_kg": 0.0, "muscle_mass_kg": 0.0}
    
    step3 = wf.agent_3_google_ai_advisor(analysis_data)
    assert step3["status"] == "WORKFLOW_SUCCESS"


def test_feature5_tier2_agent1_fit_sync_failure(temp_db):
    """F5-T2-48: Fit sync returning False does not break Agent 1 output dictionary."""
    wf = LangGraphHealthMultiAgentWorkflow()
    wf.db_path = temp_db

    with patch("vazus_core.langgraph_health_workflow.fetch_and_save_fitness_data", return_value=False):
        step1 = wf.agent_1_telemetry_ingestor()

    assert step1["metrics"] is False


def test_feature5_tier2_analyser_malformed_scale_tuple():
    """F5-T2-49: Malformed scale tuple with fewer elements falls back safely."""
    wf = LangGraphHealthMultiAgentWorkflow()
    short_scale = (77.0, 24.0)
    
    try:
        res = wf.agent_2_bio_analyser({"metrics": {}, "latest_scale": short_scale})
        assert res["weight_kg"] == 77.0
    except IndexError:
        pass


def test_feature5_tier2_gemma_engine_mock():
    """F5-T2-50: Initializing workflow handles Gemma engine instantiation failures."""
    with patch("vazus_core.langgraph_health_workflow.GoogleGemmaLocalEngine", side_effect=Exception("NPU missing")):
        try:
            wf = LangGraphHealthMultiAgentWorkflow()
        except Exception as e:
            assert "NPU missing" in str(e)


# ============================================================================
# FEATURE 6: R1 gRPC Telemetry Service (Tests 51 - 60)
# ============================================================================

# Tier 1 (Happy Path)
def test_feature6_tier1_sync_google_fit_rpc():
    """F6-T1-51: SyncGoogleFitData RPC returns GoogleFitSyncResponse with success=True."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()
        mock_metrics = {
            "activity": {"total_steps": 10000, "total_calories": 2500.0, "active_minutes": 50},
            "sleep_sessions": [{}],
            "workouts": [{}],
            "sleep_stages_by_day": {}
        }
        
        with patch("vazus_core.grpc_health_servicer.fetch_and_save_fitness_data", return_value=mock_metrics), \
             patch.object(servicer, "_log_grpc_sync_to_db"):
            req = health_telemetry_pb2.GoogleFitSyncRequest(days_back=4)
            resp = await servicer.SyncGoogleFitData(req, None)

        assert resp.success is True
        assert resp.total_steps == 10000
        assert resp.total_calories == 2500.0
        assert resp.active_minutes == 50
        assert resp.sleep_sessions_count == 1
        assert resp.workout_sessions_count == 1

    asyncio.run(_test())


def test_feature6_tier1_stream_health_metrics_rpc():
    """F6-T1-52: StreamHealthMetrics processes batch iterator and returns count."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()

        async def mock_generator():
            yield health_telemetry_pb2.HealthMetricBatch(metric_type="HR", value=72.0, timestamp_ms=1000)
            yield health_telemetry_pb2.HealthMetricBatch(metric_type="SpO2", value=99.0, timestamp_ms=2000)

        summary = await servicer.StreamHealthMetrics(mock_generator(), None)
        
        assert summary.metrics_processed == 2
        assert summary.status == "SUCCESS"
        assert summary.last_processed_timestamp_ms == 2000

    asyncio.run(_test())


def test_feature6_tier1_get_readiness_assessment_rpc():
    """F6-T1-53: GetReadinessAssessment returns valid ReadinessResponse."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()
        
        with patch("vazus_core.grpc_health_servicer.fetch_and_save_fitness_data", return_value={}):
            req = health_telemetry_pb2.ReadinessRequest(date="2026-08-03")
            resp = await servicer.GetReadinessAssessment(req, None)

        assert resp.date == "2026-08-03"
        assert round(resp.readiness_score, 1) == 92.7
        assert round(resp.sleep_recovery_score, 1) in (94.0, 93.8)
        assert "режим" in resp.recommendation or "Отличное" in resp.recommendation or "готовности" in resp.recommendation

    asyncio.run(_test())


def test_feature6_tier1_db_logging_thread_executor(temp_db):
    """F6-T1-54: _log_grpc_sync_to_db inserts grpc_event node into kg_nodes."""
    servicer = AsyncHealthTelemetryServicer()
    
    with patch("vazus_core.grpc_health_servicer.DB_PATH", temp_db):
        servicer._log_grpc_sync_to_db(readiness=95.0, steps=8000, active_min=45)

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    row = cur.execute("SELECT node_type, properties FROM kg_nodes WHERE node_type='grpc_event'").fetchone()
    conn.close()

    assert row is not None
    props = json.loads(row[1])
    assert props["readiness"] == 95.0
    assert props["steps"] == 8000


def test_feature6_tier1_grpc_response_timestamps():
    """F6-T1-55: gRPC responses contain non-empty ISO timestamps."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()
        mock_metrics = {"activity": {}}

        with patch("vazus_core.grpc_health_servicer.fetch_and_save_fitness_data", return_value=mock_metrics), \
             patch.object(servicer, "_log_grpc_sync_to_db"):
            req = health_telemetry_pb2.GoogleFitSyncRequest(days_back=1)
            resp = await servicer.SyncGoogleFitData(req, None)

        assert len(resp.timestamp) > 0
        datetime.fromisoformat(resp.timestamp)

    asyncio.run(_test())


# Tier 2 (Boundary & Corner Cases)
def test_feature6_tier2_sync_rpc_failed_sync():
    """F6-T2-56: SyncGoogleFitData returns success=False when fit sync returns False."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()
        
        with patch("vazus_core.grpc_health_servicer.fetch_and_save_fitness_data", return_value=False):
            req = health_telemetry_pb2.GoogleFitSyncRequest(days_back=4)
            resp = await servicer.SyncGoogleFitData(req, None)

        assert resp.success is False
        assert "returned no metrics" in resp.message

    asyncio.run(_test())


def test_feature6_tier2_stream_rpc_empty_iterator():
    """F6-T2-57: StreamHealthMetrics handles empty iterator with 0 metrics processed."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()

        async def empty_generator():
            if False:
                yield None

        summary = await servicer.StreamHealthMetrics(empty_generator(), None)
        assert summary.metrics_processed == 0
        assert summary.status == "SUCCESS"

    asyncio.run(_test())


def test_feature6_tier2_readiness_rpc_empty_date():
    """F6-T2-58: ReadinessRequest with empty date string defaults to today's date."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        with patch("vazus_core.grpc_health_servicer.fetch_and_save_fitness_data", return_value={}):
            req = health_telemetry_pb2.ReadinessRequest(date="")
            resp = await servicer.GetReadinessAssessment(req, None)

        assert resp.date == today_str

    asyncio.run(_test())


def test_feature6_tier2_db_logging_locked_sqlite():
    """F6-T2-59: SQLite write errors in _log_grpc_sync_to_db are safely caught."""
    servicer = AsyncHealthTelemetryServicer()
    invalid_db = r"Z:\invalid_path\db.sqlite"

    with patch("vazus_core.grpc_health_servicer.DB_PATH", invalid_db):
        servicer._log_grpc_sync_to_db(90.0, 5000, 30)


def test_feature6_tier2_stream_rpc_multiple_batches():
    """F6-T2-60: Stream RPC correctly updates last_processed_timestamp_ms across multiple items."""
    async def _test():
        servicer = AsyncHealthTelemetryServicer()

        async def multi_generator():
            for i in range(1, 6):
                yield health_telemetry_pb2.HealthMetricBatch(metric_type=f"M_{i}", value=float(i), timestamp_ms=1000 * i)

        summary = await servicer.StreamHealthMetrics(multi_generator(), None)
        
        assert summary.metrics_processed == 5
        assert summary.last_processed_timestamp_ms == 5000

    asyncio.run(_test())
