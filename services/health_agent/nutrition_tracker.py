"""
Vazus SuperGraph OS - Nutrition & Meal Tracker
Parses meal photos via Google Gemini Multimodal Vision & text prompts into macros & calories
"""

import sys
import os
import json
import re
import sqlite3
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")

try:
    import vazus_core.integrations.google_multimodal_vision as google_multimodal_vision
except ImportError:
    try:
        import services.vision.google_multimodal_vision as google_multimodal_vision
    except ImportError:
        google_multimodal_vision = None

def analyze_lab_report_image(image_path, user_prompt=None, extract_layout=True):
    """
    Module-level function delegating to google_multimodal_vision.analyze_lab_report_image,
    allowing module-level patching on either nutrition_tracker or google_multimodal_vision.
    """
    return google_multimodal_vision.analyze_lab_report_image(
        image_path, user_prompt=user_prompt, extract_layout=extract_layout
    )

DB_PATH = r"C:\vazus\services\memory\vazus.db"

def _safe_float(val, default=0.0):
    """
    Safely converts val to a non-negative float.
    Handles None/null, numeric types, and string numbers with units (e.g. "500 kcal", "48g").
    Clamps negative values to non-negative floats (max(0.0, ...)).
    """
    if val is None:
        return max(0.0, float(default))
    
    if isinstance(val, (int, float)):
        try:
            return max(0.0, float(val))
        except (ValueError, TypeError):
            return max(0.0, float(default))
            
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("none", "null", "n/a", "nan", "unknown"):
        return max(0.0, float(default))
        
    try:
        res = float(val_str)
        return max(0.0, res)
    except (ValueError, TypeError):
        pass

    match = re.search(r"[-+]?\d*\.?\d+", val_str)
    if match:
        try:
            res = float(match.group(0))
            return max(0.0, res)
        except (ValueError, TypeError):
            pass
            
    return max(0.0, float(default))

def init_nutrition_db(db_path=None):
    """
    Initializes SQLite table for nutrition log with error handling for database corruption.
    """
    target_db = db_path if db_path is not None else DB_PATH
    conn = None
    try:
        conn = sqlite3.connect(target_db)
        cur = conn.cursor()
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
        conn.commit()
        conn.close()
        conn = None
    except sqlite3.DatabaseError as e:
        print(f"⚠️ [Nutrition DB] Database error encountered ({e}). Attempting database reset...")
        if conn:
            try:
                conn.close()
            except Exception:
                pass
            conn = None
        try:
            if os.path.exists(target_db):
                os.remove(target_db)
            conn = sqlite3.connect(target_db)
            cur = conn.cursor()
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
            conn.commit()
            conn.close()
            conn = None
        except Exception as ex:
            print(f"❌ [Nutrition DB] Failed to recreate database: {ex}")


def log_meal(meal_name, calories, protein, carbs, fat, photo_path=None, notes="", db_path=None):
    calories_clean = _safe_float(calories)
    protein_clean = _safe_float(protein)
    carbs_clean = _safe_float(carbs)
    fat_clean = _safe_float(fat)

    target_db = db_path if db_path is not None else DB_PATH
    init_nutrition_db(target_db)
    conn = sqlite3.connect(target_db)
    cur = conn.cursor()
    ts = datetime.now().isoformat()
    cur.execute("""
    INSERT INTO nutrition_log (timestamp, meal_name, calories_kcal, protein_g, carbs_g, fat_g, photo_path, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ts, meal_name, calories_clean, protein_clean, carbs_clean, fat_clean, photo_path, notes))
    conn.commit()
    conn.close()
    print(f"✅ [Nutrition Tracker] Logged meal: {meal_name} ({calories_clean} kcal, P:{protein_clean}g C:{carbs_clean}g F:{fat_clean}g)")

def analyze_meal_photo_gemini(image_path, auto_log=True):
    """
    Uses Google Gemini Vision to estimate calories and macros from meal photo,
    parses JSON payload, and auto-logs to DB when auto_log=True
    """
    prompt = (
        "Оцени блюдо на фотографии. "
        "Определи примерный вес, калорийность (ккал), белки (г), жиры (г), углеводы (г) "
        "и дай краткий состав в формате JSON: {\"meal\": \"...\", \"kcal\": 0, \"protein\": 0, \"carbs\": 0, \"fat\": 0}"
    )
    raw_res = analyze_lab_report_image(image_path, user_prompt=prompt)

    
    if raw_res.get("status") in ["SUCCESS", "PIX2TEXT_SUCCESS"]:
        text_content = raw_res.get("analysis_text") or raw_res.get("analysis") or raw_res.get("extracted_text", "")
        json_match = re.search(r"\{.*\}", text_content, re.DOTALL)
        parsed_data = {}
        if json_match:
            try:
                parsed_data = json.loads(json_match.group(0))
            except Exception:
                parsed_data = {}
        
        meal_name = parsed_data.get("meal", "Блюдо с фотографии")
        if not meal_name or not isinstance(meal_name, str):
            meal_name = "Блюдо с фотографии"

        kcal = _safe_float(parsed_data.get("kcal", 0))
        protein = _safe_float(parsed_data.get("protein", 0))
        carbs = _safe_float(parsed_data.get("carbs", 0))
        fat = _safe_float(parsed_data.get("fat", 0))
        
        result = {
            "status": raw_res["status"],
            "meal_name": meal_name,
            "calories_kcal": kcal,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
            "photo_path": image_path,
            "raw_analysis": text_content
        }
        
        if auto_log and (kcal > 0 or meal_name != "Блюдо с фотографии"):
            log_meal(meal_name, kcal, protein, carbs, fat, photo_path=image_path, notes="Gemini Photo Analysis")
            
        return result
    else:
        return raw_res

def get_daily_nutrition_summary(date_str=None):
    """
    Returns aggregated nutrition totals (date, total_calories, total_protein, total_carbs, total_fat, meal_count) for given date (YYYY-MM-DD)
    """
    init_nutrition_db()
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    SELECT SUM(calories_kcal), SUM(protein_g), SUM(carbs_g), SUM(fat_g), COUNT(*)
    FROM nutrition_log
    WHERE timestamp LIKE ?
    """, (f"{date_str}%",))
    row = cur.fetchone()
    conn.close()
    
    return {
        "date": date_str,
        "total_calories": row[0] or 0.0,
        "total_protein": row[1] or 0.0,
        "total_carbs": row[2] or 0.0,
        "total_fat": row[3] or 0.0,
        "meal_count": row[4] or 0
    }

if __name__ == '__main__':
    init_nutrition_db()
    log_meal("Куриная грудка с гречкой и салатом", 520, 48, 55, 12, notes="После тренировки")


