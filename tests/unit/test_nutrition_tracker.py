"""
Unit tests for vazus_core/nutrition_tracker.py
"""

import os
import sys
import sqlite3
import unittest
import tempfile
import shutil
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")

from vazus_core.nutrition_tracker import (
    init_nutrition_db,
    log_meal,
    analyze_meal_photo_gemini,
    get_daily_nutrition_summary,
)


class TestNutritionTracker(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="nutrition_test_")
        self.test_db = os.path.join(self.temp_dir, "test_nutrition.db")
        self.patch_core = patch("vazus_core.nutrition_tracker.DB_PATH", self.test_db)
        self.patch_serv = patch("services.health_agent.nutrition_tracker.DB_PATH", self.test_db)
        self.patch_core.start()
        self.patch_serv.start()
        init_nutrition_db()

    def tearDown(self):
        self.patch_core.stop()
        self.patch_serv.stop()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_initialization(self):
        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        columns = [row[1] for row in cur.execute("PRAGMA table_info(nutrition_log)").fetchall()]
        conn.close()

        expected_columns = ["id", "timestamp", "meal_name", "calories_kcal", "protein_g", "carbs_g", "fat_g", "photo_path", "notes"]
        for col in expected_columns:
            self.assertIn(col, columns)

    def test_log_meal_with_photo_path_db_verification(self):
        test_photo = r"C:\vazus\test_photo_meal_123.jpg"
        unique_note = f"UnitTest_LogMeal_{datetime.now().timestamp()}"
        
        log_meal("Протеиновый коктейль", 250, 30, 10, 5, photo_path=test_photo, notes=unique_note)

        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute(
            "SELECT meal_name, calories_kcal, protein_g, carbs_g, fat_g, photo_path, notes FROM nutrition_log WHERE notes=?",
            (unique_note,)
        )
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Протеиновый коктейль")
        self.assertEqual(row[1], 250)
        self.assertEqual(row[2], 30)
        self.assertEqual(row[3], 10)
        self.assertEqual(row[4], 5)
        self.assertEqual(row[5], test_photo)
        self.assertEqual(row[6], unique_note)

    @patch("vazus_core.nutrition_tracker.analyze_lab_report_image")
    def test_analyze_meal_photo_gemini_json_parsing_and_autolog(self, mock_vision):
        mock_vision.return_value = {
            "status": "SUCCESS",
            "engine": "gemini-2.5-flash",
            "analysis_text": 'Вот оценка блюда:\n```json\n{"meal": "Овсянка с ягодами", "kcal": 320, "protein": 12, "carbs": 55, "fat": 6}\n```',
            "image": r"C:\vazus\test_oats.jpg"
        }

        unique_photo = r"C:\vazus\test_oats.jpg"
        res = analyze_meal_photo_gemini(unique_photo, auto_log=True)

        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertEqual(res.get("meal_name"), "Овсянка с ягодами")
        self.assertEqual(res.get("calories_kcal"), 320.0)
        self.assertEqual(res.get("protein_g"), 12.0)
        self.assertEqual(res.get("carbs_g"), 55.0)
        self.assertEqual(res.get("fat_g"), 6.0)

        # Check DB auto-log
        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute(
            "SELECT meal_name, calories_kcal, photo_path FROM nutrition_log WHERE photo_path=? AND notes='Gemini Photo Analysis' ORDER BY id DESC LIMIT 1",
            (unique_photo,)
        )
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Овсянка с ягодами")
        self.assertEqual(row[1], 320.0)
        self.assertEqual(row[2], unique_photo)

    def test_get_daily_nutrition_summary_aggregation(self):
        target_date = "2026-08-03"
        
        # Log a known meal with timestamp formatted for target_date
        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO nutrition_log (timestamp, meal_name, calories_kcal, protein_g, carbs_g, fat_g, photo_path, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"{target_date}T08:00:00", "Завтрак Спец", 400, 20, 50, 10, None, "UnitTestSummary")
        )
        cur.execute(
            "INSERT INTO nutrition_log (timestamp, meal_name, calories_kcal, protein_g, carbs_g, fat_g, photo_path, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"{target_date}T13:00:00", "Обед Спец", 600, 40, 70, 15, None, "UnitTestSummary")
        )
        conn.commit()
        conn.close()

        summary = get_daily_nutrition_summary(target_date)

        self.assertEqual(summary.get("date"), target_date)
        self.assertGreaterEqual(summary.get("total_calories"), 1000.0)
        self.assertGreaterEqual(summary.get("total_protein"), 60.0)
        self.assertGreaterEqual(summary.get("total_carbs"), 120.0)
        self.assertGreaterEqual(summary.get("total_fat"), 25.0)
        self.assertGreaterEqual(summary.get("meal_count"), 2)

    def test_safe_float_helper_and_units_sanitization(self):
        from vazus_core.nutrition_tracker import _safe_float
        self.assertEqual(_safe_float(None), 0.0)
        self.assertEqual(_safe_float("500 kcal"), 500.0)
        self.assertEqual(_safe_float("48g"), 48.0)
        self.assertEqual(_safe_float("25.5 g"), 25.5)
        self.assertEqual(_safe_float("-100"), 0.0)
        self.assertEqual(_safe_float("N/A"), 0.0)
        self.assertEqual(_safe_float("unknown"), 0.0)

    @patch("vazus_core.nutrition_tracker.google_multimodal_vision.analyze_lab_report_image")
    def test_analyze_meal_photo_gemini_with_units_and_nulls(self, mock_vision):
        mock_vision.return_value = {
            "status": "SUCCESS",
            "engine": "gemini-2.5-flash",
            "analysis_text": '{"meal": "Пицца", "kcal": "500 kcal", "protein": "20g", "carbs": null, "fat": "unknown"}',
            "image": r"C:\vazus\test_pizza.jpg"
        }

        res = analyze_meal_photo_gemini(r"C:\vazus\test_pizza.jpg", auto_log=False)
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertEqual(res.get("meal_name"), "Пицца")
        self.assertEqual(res.get("calories_kcal"), 500.0)
        self.assertEqual(res.get("protein_g"), 20.0)
        self.assertEqual(res.get("carbs_g"), 0.0)
        self.assertEqual(res.get("fat_g"), 0.0)

    def test_database_corruption_recovery(self):
        test_corrupted_db = os.path.join(self.temp_dir, "test_corrupt_temp.db")
        with patch("vazus_core.nutrition_tracker.DB_PATH", test_corrupted_db), \
             patch("services.health_agent.nutrition_tracker.DB_PATH", test_corrupted_db):
            with open(test_corrupted_db, "w", encoding="utf-8") as f:
                f.write("CORRUPTED_SQLITE_FILE_GARBAGE_DATA")

            init_nutrition_db()
            conn = sqlite3.connect(test_corrupted_db)
            cur = conn.cursor()
            table_exists = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nutrition_log'").fetchone()
            conn.close()
            self.assertIsNotNone(table_exists)


if __name__ == "__main__":
    unittest.main()
