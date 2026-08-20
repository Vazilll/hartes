r"""
Unified Health Sync Bridge: Google Health Connect + Zepp/Mi Band + Mi Scale BLE
Integrates into Vazus SuperGraph Database (C:\vazus\memory\vazus.db or local db)
"""

import sys
import os
import sqlite3
import json
from datetime import datetime
from health_load_engine import MiScaleBioimpedanceDecoder

DB_PATH = r"C:\vazus\services\memory\vazus.db"

def init_health_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table for daily load tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS health_daily_load (
        date TEXT PRIMARY KEY,
        trimp REAL,
        atl_fatigue REAL,
        ctl_fitness REAL,
        tsb_form REAL,
        steps INTEGER,
        sleep_hours REAL,
        updated_at TEXT
    )
    """)
    
    # Table for Mi Scale weigh-ins
    cursor.execute("""
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

def record_mi_scale_reading(payload_hex: str = None, weight_kg: float = None, impedance: int = 480, height_cm: float = 178, age: int = 28, gender: str = "male"):
    init_health_db()
    
    if payload_hex:
        parsed = MiScaleBioimpedanceDecoder.parse_ble_raw_payload(payload_hex)
        weight_kg = parsed["weight_kg"]
        impedance = parsed["impedance_ohms"]
        
    metrics = MiScaleBioimpedanceDecoder.calculate_body_metrics(weight_kg, height_cm, age, gender, impedance)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO mi_scale_weighins (timestamp, weight_kg, impedance_ohms, bmi, body_fat_pct, muscle_mass_kg, water_pct, visceral_fat, bmr_kcal, source)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        weight_kg,
        impedance,
        metrics["bmi"],
        metrics["body_fat_pct"],
        metrics["muscle_mass_kg"],
        metrics["water_pct"],
        metrics["visceral_fat"],
        metrics["bmr_kcal"],
        "BLE_MiScale_2"
    ))
    conn.commit()
    conn.close()
    
    print(f"Recorded Mi Scale reading: Weight={weight_kg}kg, Fat={metrics['body_fat_pct']}%, Muscle={metrics['muscle_mass_kg']}kg")
    return metrics

if __name__ == "__main__":
    init_health_db()
    res = record_mi_scale_reading(weight_kg=74.5, impedance=485)
    print("Health Bridge Initialized Successfully.")
