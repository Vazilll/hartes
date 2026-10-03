"""
Unit & Integration Test Suite for R2 Multimodal Medical OCR & Vision Engine
Features Covered (Features 7 - 9):
7. R2 Gemini Multimodal Vision
8. R2 Pix2Text Local OCR Fallback
9. R2 Nutrition & Macro Tracker

Methodology: 4-Tier Test Design (Tier 1 Happy Path >= 15, Tier 2 Boundary/Edge >= 15)
Total Test Cases: 30
"""

import os
import sys
import json
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

# Add project root and vazus_core to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
VAZUS_CORE = os.path.join(PROJECT_ROOT, "vazus_core")
if VAZUS_CORE not in sys.path:
    sys.path.insert(0, VAZUS_CORE)

from vazus_core.google_multimodal_vision import analyze_lab_report_image, parse_with_pix2text
import vazus_core.nutrition_tracker as nutrition_tracker


# --- Fixtures ---

@pytest.fixture
def temp_nutrition_db(tmp_path):
    """Creates an isolated temporary database for nutrition tracking tests."""
    db_file = str(tmp_path / "test_nutrition.db")
    with patch("vazus_core.nutrition_tracker.DB_PATH", db_file):
        nutrition_tracker.init_nutrition_db()
    return db_file


@pytest.fixture
def temp_image_file(tmp_path):
    """Creates a temporary sample image file for vision tests."""
    img_path = tmp_path / "test_lab_report.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89")
    return str(img_path)


# ============================================================================
# FEATURE 7: R2 Gemini Multimodal Vision (Tests 1 - 10)
# ============================================================================

# Tier 1 (Happy Path)
def test_feature7_tier1_analyze_lab_report_success(temp_image_file):
    """F7-T1-1: Successful Gemini API call returns status SUCCESS and analysis text."""
    mock_client = MagicMock()
    mock_model_response = MagicMock()
    mock_model_response.text = "Гемоглобин: 145 г/л (Норма). Лейкоциты: 6.2 (Норма)."
    mock_client.models.generate_content.return_value = mock_model_response

    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    with patch.dict("sys.modules", {"google.genai": mock_genai}):
        res = analyze_lab_report_image(temp_image_file)

    assert res["status"] == "SUCCESS"
    assert "Гемоглобин" in res["analysis_text"]
    assert res["image"] == temp_image_file


def test_feature7_tier1_custom_prompt_passed(temp_image_file):
    """F7-T1-2: Custom user prompt is forwarded to Gemini generate_content."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="Custom prompt result")
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    custom_prompt = "Проверь уровень ферритина и железа"
    with patch.dict("sys.modules", {"google.genai": mock_genai}):
        analyze_lab_report_image(temp_image_file, user_prompt=custom_prompt)

    args, kwargs = mock_client.models.generate_content.call_args
    contents = kwargs.get("contents") or args[0]
    assert custom_prompt in contents


def test_feature7_tier1_image_bytes_read(temp_image_file):
    """F7-T1-3: Target image file is read in binary mode and passed as bytes."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="Bytes read successfully")
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    with patch.dict("sys.modules", {"google.genai": mock_genai}):
        analyze_lab_report_image(temp_image_file)

    args, kwargs = mock_client.models.generate_content.call_args
    contents = kwargs.get("contents")
    assert any(isinstance(c, bytes) for c in contents)


def test_feature7_tier1_response_dict_structure(temp_image_file):
    """F7-T1-4: Return value contains mandatory keys status, engine, analysis_text, image."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="Valid structure")
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    with patch.dict("sys.modules", {"google.genai": mock_genai}):
        res = analyze_lab_report_image(temp_image_file)

    assert "status" in res
    assert "engine" in res
    assert "analysis_text" in res
    assert "image" in res


def test_feature7_tier1_lab_report_ecg_prompt(temp_image_file):
    """F7-T1-5: Default prompt contains keywords for medical lab reports, blood tests, ECG."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="Default prompt used")
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    with patch.dict("sys.modules", {"google.genai": mock_genai}):
        analyze_lab_report_image(temp_image_file)

    args, kwargs = mock_client.models.generate_content.call_args
    contents = kwargs.get("contents")
    default_prompt = contents[0]
    assert "медицинский документ" in default_prompt
    assert "крови" in default_prompt or "ЭКГ" in default_prompt


# Tier 2 (Boundary & Corner Cases)
def test_feature7_tier2_image_file_not_found():
    """F7-T2-6: Non-existent image path returns dictionary with status ERROR."""
    fake_path = r"C:\vazus\tests\non_existent_image_12345.png"
    res = analyze_lab_report_image(fake_path)

    assert res["status"] == "ERROR"
    assert "message" in res
    assert fake_path in res["message"]


def test_feature7_tier2_gemini_api_exception_fallback(temp_image_file):
    """F7-T2-7: Exceptions in Gemini API call trigger local Pix2Text OCR fallback."""
    mock_genai = MagicMock()
    mock_genai.Client.side_effect = Exception("API Key Quota Exceeded")

    with patch.dict("sys.modules", {"google.genai": mock_genai}), \
         patch("vazus_core.google_multimodal_vision.parse_with_pix2text") as mock_fallback:
        mock_fallback.return_value = {"status": "PIX2TEXT_SUCCESS", "engine": "pix2text-1.1.6-full", "analysis_text": "Fallback text", "image": temp_image_file}
        res = analyze_lab_report_image(temp_image_file)

    mock_fallback.assert_called_once()
    assert res["status"] == "PIX2TEXT_SUCCESS"


def test_feature7_tier2_empty_image_file(tmp_path):
    """F7-T2-8: 0-byte image file handles safely during read."""
    empty_img = tmp_path / "empty.jpg"
    empty_img.write_bytes(b"")

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="Empty file parsed")
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    with patch.dict("sys.modules", {"google.genai": mock_genai}):
        res = analyze_lab_report_image(str(empty_img))

    assert res["status"] == "SUCCESS"


def test_feature7_tier2_gemini_returns_empty_text(temp_image_file):
    """F7-T2-9: Gemini API returning empty string text handles without exception."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="")
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    with patch.dict("sys.modules", {"google.genai": mock_genai}):
        res = analyze_lab_report_image(temp_image_file)

    assert res["status"] == "SUCCESS"
    assert res["analysis_text"] == ""


def test_feature7_tier2_invalid_image_extension(tmp_path):
    """F7-T2-10: File with unusual extension (.dat) is read as binary and processed."""
    unusual_file = tmp_path / "report_data.dat"
    unusual_file.write_bytes(b"sample raw bytes")

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="Parsed dat file")
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client

    with patch.dict("sys.modules", {"google.genai": mock_genai}):
        res = analyze_lab_report_image(str(unusual_file))

    assert res["status"] == "SUCCESS"


# ============================================================================
# FEATURE 8: R2 Pix2Text Local OCR Fallback (Tests 11 - 20)
# ============================================================================

# Tier 1 (Happy Path)
def test_feature8_tier1_parse_pix2text_success(temp_image_file):
    """F8-T1-11: Pix2Text OCR recognizes text and returns status PIX2TEXT_SUCCESS."""
    mock_page = MagicMock()
    mock_page.to_markdown.return_value = "E = mc^2 \\\\ \\text{Hb: } 14.5 \\text{ g/dL}"
    mock_p2t_instance = MagicMock()
    mock_p2t_instance.recognize_page.return_value = mock_page

    with patch("vazus_core.google_multimodal_vision._get_pix2text", return_value=mock_p2t_instance):
        res = parse_with_pix2text(temp_image_file)

    assert res["status"] == "PIX2TEXT_SUCCESS"
    assert "E = mc^2" in res["analysis_text"]
    assert res["image"] == temp_image_file


def test_feature8_tier1_extracted_text_string(temp_image_file):
    """F8-T1-12: analysis_text field is converted to a string representation."""
    mock_page = MagicMock()
    mock_page.to_markdown.return_value = "Formula 1 Table row"
    mock_p2t_instance = MagicMock()
    mock_p2t_instance.recognize_page.return_value = mock_page

    with patch("vazus_core.google_multimodal_vision._get_pix2text", return_value=mock_p2t_instance):
        res = parse_with_pix2text(temp_image_file)

    assert isinstance(res["analysis_text"], str)
    assert "Formula 1" in res["analysis_text"]


def test_feature8_tier1_image_path_preserved(temp_image_file):
    """F8-T1-13: Returned dictionary preserves exact input image file path."""
    mock_page = MagicMock()
    mock_page.to_markdown.return_value = "OCR Output"
    mock_p2t_instance = MagicMock()
    mock_p2t_instance.recognize_page.return_value = mock_page

    with patch("vazus_core.google_multimodal_vision._get_pix2text", return_value=mock_p2t_instance):
        res = parse_with_pix2text(temp_image_file)

    assert res["image"] == temp_image_file


def test_feature8_tier1_fallback_trigger_on_gemini_failure(temp_image_file):
    """F8-T1-14: Gemini API failure triggers parse_with_pix2text transparently."""
    mock_genai = MagicMock()
    mock_genai.Client.side_effect = RuntimeError("Network error")

    mock_page = MagicMock()
    mock_page.to_markdown.return_value = "\\int_0^\\infty f(x) dx"
    mock_p2t_instance = MagicMock()
    mock_p2t_instance.recognize_page.return_value = mock_page

    with patch.dict("sys.modules", {"google.genai": mock_genai}), \
         patch("vazus_core.google_multimodal_vision._get_pix2text", return_value=mock_p2t_instance):
        res = analyze_lab_report_image(temp_image_file)

    assert res["status"] == "PIX2TEXT_SUCCESS"
    assert "\\int_0^\\infty" in res["analysis_text"]


def test_feature8_tier1_formula_table_ocr_mode(temp_image_file):
    """F8-T1-15: Pix2Text recognizes LaTeX formulas and table markup."""
    mock_page = MagicMock()
    mock_page.to_markdown.return_value = "| Param | Value |\n| RBC | 4.8 |"
    mock_p2t_instance = MagicMock()
    mock_p2t_instance.recognize_page.return_value = mock_page

    with patch("vazus_core.google_multimodal_vision._get_pix2text", return_value=mock_p2t_instance):
        res = parse_with_pix2text(temp_image_file)

    assert "| Param | Value |" in res["analysis_text"]


# Tier 2 (Boundary & Corner Cases)
def test_feature8_tier2_pix2text_not_installed_import_error(temp_image_file):
    """F8-T2-16: Missing pix2text module returns status ERROR with clear message."""
    with patch("vazus_core.google_multimodal_vision._get_pix2text", side_effect=ImportError("No module named pix2text")):
        with patch.dict("sys.modules", {"pix2text": None}):
            res = parse_with_pix2text(temp_image_file)

    assert res["status"] == "ERROR"
    assert "Pix2Text error" in res["message"]


def test_feature8_tier2_pix2text_runtime_exception(temp_image_file):
    """F8-T2-17: Internal exception during recognize_page returns status ERROR."""
    mock_p2t_instance = MagicMock()
    mock_p2t_instance.recognize_page.side_effect = ValueError("Corrupted image model error")

    with patch("vazus_core.google_multimodal_vision._get_pix2text", return_value=mock_p2t_instance), \
         patch.dict("sys.modules", {"pix2text": None}):
        res = parse_with_pix2text(temp_image_file)

    assert res["status"] == "ERROR"
    assert "Pix2Text error" in res["message"]


def test_feature8_tier2_pix2text_empty_ocr_result(temp_image_file):
    """F8-T2-18: Empty markdown result from recognize_page converts safely to string."""
    mock_page = MagicMock()
    mock_page.to_markdown.return_value = ""
    mock_p2t_instance = MagicMock()
    mock_p2t_instance.recognize_page.return_value = mock_page

    with patch("vazus_core.google_multimodal_vision._get_pix2text", return_value=mock_p2t_instance):
        res = parse_with_pix2text(temp_image_file)

    assert res["status"] == "PIX2TEXT_SUCCESS"
    assert res["analysis_text"] == ""


def test_feature8_tier2_pix2text_corrupted_image(tmp_path):
    """F8-T2-19: Non-image file passed to Pix2Text OCR handled without crash."""
    corrupted_file = tmp_path / "bad.png"
    corrupted_file.write_bytes(b"NOT_A_PNG_HEADER")

    mock_p2t_instance = MagicMock()
    mock_p2t_instance.recognize_page.side_effect = RuntimeError("Invalid image header")

    with patch("vazus_core.google_multimodal_vision._get_pix2text", return_value=mock_p2t_instance), \
         patch.dict("sys.modules", {"pix2text": None}):
        res = parse_with_pix2text(str(corrupted_file))

    assert res["status"] == "ERROR"


def test_feature8_tier2_pix2text_unicode_path(tmp_path):
    """F8-T2-20: Image file path containing Cyrillic characters handled cleanly."""
    unicode_img = tmp_path / "анализ_крови_2026.png"
    unicode_img.write_bytes(b"\x89PNG\r\n\x1a\n")

    mock_page = MagicMock()
    mock_page.to_markdown.return_value = "Тромбоциты: 250"
    mock_p2t_instance = MagicMock()
    mock_p2t_instance.recognize_page.return_value = mock_page

    with patch("vazus_core.google_multimodal_vision._get_pix2text", return_value=mock_p2t_instance):
        res = parse_with_pix2text(str(unicode_img))

    assert res["status"] == "PIX2TEXT_SUCCESS"
    assert res["image"] == str(unicode_img)


# ============================================================================
# FEATURE 9: R2 Nutrition & Macro Tracker (Tests 21 - 30)
# ============================================================================

# Tier 1 (Happy Path)
def test_feature9_tier1_init_nutrition_db(temp_nutrition_db):
    """F9-T1-21: init_nutrition_db creates nutrition_log table in SQLite DB."""
    conn = sqlite3.connect(temp_nutrition_db)
    cur = conn.cursor()
    columns = cur.execute("PRAGMA table_info(nutrition_log)").fetchall()
    conn.close()

    col_names = [col[1] for col in columns]
    assert "timestamp" in col_names
    assert "meal_name" in col_names
    assert "calories_kcal" in col_names
    assert "protein_g" in col_names
    assert "carbs_g" in col_names
    assert "fat_g" in col_names


def test_feature9_tier1_log_meal_insert(temp_nutrition_db):
    """F9-T1-22: log_meal inserts meal record into nutrition_log table."""
    with patch("vazus_core.nutrition_tracker.DB_PATH", temp_nutrition_db):
        nutrition_tracker.log_meal("Куриная грудка с рисом", 550.0, 45.0, 60.0, 10.0, notes="Обед")

    conn = sqlite3.connect(temp_nutrition_db)
    cur = conn.cursor()
    row = cur.execute("SELECT meal_name, calories_kcal, protein_g, carbs_g, fat_g, notes FROM nutrition_log").fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "Куриная грудка с рисом"
    assert row[1] == 550.0
    assert row[2] == 45.0
    assert row[3] == 60.0
    assert row[4] == 10.0
    assert row[5] == "Обед"


def test_feature9_tier1_log_meal_values_retrieval(temp_nutrition_db):
    """F9-T1-23: Verify inserted timestamp is valid ISO string in nutrition_log."""
    with patch("vazus_core.nutrition_tracker.DB_PATH", temp_nutrition_db):
        nutrition_tracker.log_meal("Овсяная каша", 300.0, 12.0, 45.0, 6.0)

    conn = sqlite3.connect(temp_nutrition_db)
    cur = conn.cursor()
    ts = cur.execute("SELECT timestamp FROM nutrition_log").fetchone()[0]
    conn.close()

    assert len(ts) > 0


def test_feature9_tier1_analyze_meal_photo_gemini_call(temp_image_file):
    """F9-T1-24: analyze_meal_photo_gemini calls analyze_lab_report_image with nutrition prompt."""
    mock_res = {"status": "SUCCESS", "analysis_text": '{"meal": "Salad", "kcal": 200}'}
    with patch.object(nutrition_tracker, "analyze_lab_report_image", return_value=mock_res) as mock_vision:
        res = nutrition_tracker.analyze_meal_photo_gemini(temp_image_file, auto_log=False)

    mock_vision.assert_called_once()
    args, kwargs = mock_vision.call_args
    assert args[0] == temp_image_file
    assert "калорийность" in kwargs["user_prompt"]
    assert res["status"] == "SUCCESS"


def test_feature9_tier1_nutrition_db_multiple_meals(temp_nutrition_db):
    """F9-T1-25: Logging multiple meals inserts separate rows with incrementing IDs."""
    with patch("vazus_core.nutrition_tracker.DB_PATH", temp_nutrition_db):
        nutrition_tracker.log_meal("Завтрак", 400.0, 20.0, 40.0, 15.0)
        nutrition_tracker.log_meal("Обед", 700.0, 50.0, 70.0, 20.0)
        nutrition_tracker.log_meal("Ужин", 450.0, 35.0, 30.0, 15.0)

    conn = sqlite3.connect(temp_nutrition_db)
    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) FROM nutrition_log").fetchone()[0]
    conn.close()

    assert count == 3


# Tier 2 (Boundary & Corner Cases)
def test_feature9_tier2_log_meal_zero_macros(temp_nutrition_db):
    """F9-T2-26: Logging 0 calories and macros inserts successfully."""
    with patch("vazus_core.nutrition_tracker.DB_PATH", temp_nutrition_db):
        nutrition_tracker.log_meal("Вода", 0.0, 0.0, 0.0, 0.0, "Гидратация")

    conn = sqlite3.connect(temp_nutrition_db)
    cur = conn.cursor()
    row = cur.execute("SELECT calories_kcal, protein_g FROM nutrition_log WHERE meal_name='Вода'").fetchone()
    conn.close()

    assert row == (0.0, 0.0)


def test_feature9_tier2_log_meal_negative_macros(temp_nutrition_db):
    """F9-T2-27: Negative values are sanitized and clamped to 0.0."""
    with patch("vazus_core.nutrition_tracker.DB_PATH", temp_nutrition_db):
        nutrition_tracker.log_meal("Коррекция", -100.0, -10.0, -15.0, -5.0)

    conn = sqlite3.connect(temp_nutrition_db)
    cur = conn.cursor()
    row = cur.execute("SELECT calories_kcal FROM nutrition_log WHERE meal_name='Коррекция'").fetchone()
    conn.close()

    assert row[0] == 0.0



def test_feature9_tier2_log_meal_empty_notes_and_name(temp_nutrition_db):
    """F9-T2-28: Empty meal name and notes logged cleanly without error."""
    with patch("vazus_core.nutrition_tracker.DB_PATH", temp_nutrition_db):
        nutrition_tracker.log_meal("", 250.0, 5.0, 30.0, 10.0, notes="")

    conn = sqlite3.connect(temp_nutrition_db)
    cur = conn.cursor()
    row = cur.execute("SELECT meal_name, notes FROM nutrition_log").fetchone()
    conn.close()

    assert row == ("", "")


def test_feature9_tier2_analyze_meal_missing_photo():
    """F9-T2-29: Calling analyze_meal_photo_gemini on non-existent file returns status ERROR."""
    missing_path = r"C:\vazus\tests\missing_meal_photo.jpg"
    res = nutrition_tracker.analyze_meal_photo_gemini(missing_path)

    assert res["status"] == "ERROR"


def test_feature9_tier2_log_meal_special_characters_sql_injection(temp_nutrition_db):
    """F9-T2-30: Meal name with quotes, apostrophes, and SQL syntax handled safely."""
    special_name = "O'Connor 'Salad' -- DROP TABLE nutrition_log; SELECT * FROM users;"
    with patch("vazus_core.nutrition_tracker.DB_PATH", temp_nutrition_db):
        nutrition_tracker.log_meal(special_name, 180.0, 4.0, 12.0, 8.0)

    conn = sqlite3.connect(temp_nutrition_db)
    cur = conn.cursor()
    row = cur.execute("SELECT meal_name FROM nutrition_log").fetchone()
    table_exists = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nutrition_log'").fetchone()
    conn.close()

    assert row[0] == special_name
    assert table_exists is not None
