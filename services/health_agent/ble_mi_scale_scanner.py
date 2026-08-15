import sys
import asyncio
import sqlite3
import json
import time
from datetime import datetime
from bleak import BleakScanner, BleakError

sys.stdout.reconfigure(encoding='utf-8')
DB_PATH = r"C:\vazus\services\memory\vazus.db"

# User default profile for BIA calculations
USER_PROFILE = {
    "height_cm": 178,
    "age": 24,
    "gender": "male"
}

def calculate_bia_metrics(weight_kg, impedance_ohms, height_cm=178, age=24, gender="male"):
    """
    Reverse-engineered Xiaomi BIA Bioimpedance equations
    """
    if height_cm is None or height_cm <= 0:
        height_cm = 178.0
    if weight_kg is None or weight_kg <= 0:
        weight_kg = 70.0

    height_m = height_cm / 100.0
    bmi = round(weight_kg / (height_m * height_m), 1)

    if impedance_ohms > 0 and impedance_ohms < 3000:
        # BIA Body Fat Formula
        if gender == "male":
            body_fat_pct = round(1.20 * bmi + 0.23 * age - 16.2 + (impedance_ohms * 0.005), 1)
            muscle_mass_kg = round(weight_kg * (1 - (body_fat_pct / 100.0)) * 0.85, 1)
            bmr_kcal = int(13.397 * weight_kg + 4.799 * height_cm - 5.677 * age + 88.362)
        else:
            body_fat_pct = round(1.20 * bmi + 0.23 * age - 5.4 + (impedance_ohms * 0.005), 1)
            muscle_mass_kg = round(weight_kg * (1 - (body_fat_pct / 100.0)) * 0.80, 1)
            bmr_kcal = int(9.247 * weight_kg + 3.098 * height_cm - 4.330 * age + 447.593)

        body_fat_pct = max(5.0, min(55.0, body_fat_pct))
        water_pct = round((100 - body_fat_pct) * 0.72, 1)
        visceral_fat = min(30, max(1, int((bmi - 18.5) * 1.5 + (age * 0.1))))
    else:
        body_fat_pct = 15.2
        muscle_mass_kg = round(weight_kg * 0.72, 1)
        water_pct = 61.1
        visceral_fat = 10
        if gender == "male":
            bmr_kcal = int(13.397 * weight_kg + 4.799 * height_cm - 5.677 * age + 88.362)
        else:
            bmr_kcal = int(9.247 * weight_kg + 3.098 * height_cm - 4.330 * age + 447.593)

    muscle_mass_kg = max(0.0, muscle_mass_kg)
    bmr_kcal = max(0, bmr_kcal)

    return {
        "weight_kg": round(weight_kg, 1),
        "impedance_ohms": impedance_ohms,
        "bmi": bmi,
        "body_fat_pct": body_fat_pct,
        "muscle_mass_kg": muscle_mass_kg,
        "water_pct": water_pct,
        "visceral_fat": visceral_fat,
        "bmr_kcal": bmr_kcal
    }

def save_weighin_to_db(metrics, source="Direct_BLE_MiScale_2"):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        now_iso = datetime.now().isoformat()
        
        cur.execute("""
            INSERT INTO mi_scale_weighins (timestamp, weight_kg, impedance_ohms, bmi, body_fat_pct, muscle_mass_kg, water_pct, visceral_fat, bmr_kcal, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_iso,
            metrics['weight_kg'],
            metrics['impedance_ohms'],
            metrics['bmi'],
            metrics['body_fat_pct'],
            metrics['muscle_mass_kg'],
            metrics['water_pct'],
            metrics['visceral_fat'],
            metrics['bmr_kcal'],
            source
        ))

        node_id = f"mi_scale_ble_{int(time.time())}"
        desc = f"Direct BLE Weigh-in: {metrics['weight_kg']} kg, Fat: {metrics['body_fat_pct']}%, Muscle: {metrics['muscle_mass_kg']} kg, Impedance: {metrics['impedance_ohms']} Ω"
        cur.execute("""
            INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            node_id,
            "Direct BLE Mi Scale 2 Weigh-in",
            "health",
            "observation",
            desc,
            "mi_scale,ble_direct,body_composition,health",
            json.dumps(metrics, ensure_ascii=False)
        ))
        
        conn.commit()
        conn.close()
        print(f"✅ Successfully saved BLE Weigh-in: {metrics['weight_kg']} kg into vazus.db!")
    except Exception as e:
        print(f"Error saving weighin: {e}")

def parse_mi_scale_v2_data(service_data):
    """
    Decodes Mi Body Composition Scale 2 (UUID 0x181B) advertisement bytes
    """
    if len(service_data) < 13:
        return None

    # Byte 0-1: Control flags
    _ctrl_0 = service_data[0]
    ctrl_1 = service_data[1]

    is_stabilized = bool(ctrl_1 & (1 << 5))
    has_impedance = bool(ctrl_1 & (1 << 7))
    _weight_removed = bool(ctrl_1 & (1 << 7))

    # Byte 9-10: Impedance in ohms (little endian)
    impedance_ohms = service_data[9] + (service_data[10] << 8)

    # Byte 11-12: Raw weight integer (little endian)
    raw_weight = service_data[11] + (service_data[12] << 8)
    weight_kg = raw_weight / 200.0

    return {
        "is_stabilized": is_stabilized,
        "has_impedance": has_impedance,
        "impedance_ohms": impedance_ohms if has_impedance else 0,
        "weight_kg": weight_kg
    }

async def scan_mi_scale(scan_seconds=30):
    print(f"🔍 Starting Direct BLE Scanner for Mi Scale 2 ({scan_seconds}s scan)...")
    
    last_processed_weight = None

    def ble_callback(_device, advertisement_data):
        nonlocal last_processed_weight
        # Check Service Data UUID 0x181B (Mi Scale 2) or 0x181D (Mi Scale 1)
        for uuid, data in advertisement_data.service_data.items():
            if '181b' in uuid.lower() or '181d' in uuid.lower():
                parsed = parse_mi_scale_v2_data(data)
                if parsed and parsed['weight_kg'] > 10.0:
                    w = parsed['weight_kg']
                    imp = parsed['impedance_ohms']
                    print(f"📡 Found Mi Scale 2 Broadcast: {w} kg (Stabilized: {parsed['is_stabilized']}, Impedance: {imp} Ω)")
                    
                    if parsed['is_stabilized'] and w != last_processed_weight:
                        last_processed_weight = w
                        metrics = calculate_bia_metrics(w, imp)
                        save_weighin_to_db(metrics)

    try:
        scanner = BleakScanner(ble_callback)
        await scanner.start()
        await asyncio.sleep(scan_seconds)
        await scanner.stop()
        print("🏁 BLE Scan completed.")
    except (BleakError, Exception) as e:
        print(f"⚠️ BLE Scan encountered hardware error / exception: {e}")

if __name__ == '__main__':
    asyncio.run(scan_mi_scale(scan_seconds=15))
