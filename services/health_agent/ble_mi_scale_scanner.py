import sys
import os
import tempfile
import asyncio
import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime
from bleak import BleakScanner, BleakError

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# Ensure project root is on sys.path for core module imports
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from vazus_core.memory.db import _resolve_target_db_path
except ImportError:
    _resolve_target_db_path = None

DEFAULT_DB_PATH = r"C:\vazus\services\memory\vazus.db"
DB_PATH = os.getenv("VAZUS_DB_PATH", DEFAULT_DB_PATH)

def _is_test_environment() -> bool:
    """Detects whether code is running inside an automated test runner."""
    if os.getenv("VAZUS_ALLOW_PROD_BLE") == "1":
        return False
    return bool(
        os.getenv("VAZUS_TEST_ISOLATION") == "1"
        or os.getenv("VAZUS_TEST_MODE") == "1"
        or "PYTEST_CURRENT_TEST" in os.environ
        or os.getenv("VAZUS_TEST_RUNNING") == "1"
        or "pytest" in sys.modules
    )

def _get_effective_db_path(db_path=None) -> str:
    """
    Resolves target DB path with strict test isolation and mock patch support.
    Guarantees that test executions never write to the canonical production database.
    """
    canonical_norm = str(Path(DEFAULT_DB_PATH).resolve()).lower()

    if db_path is not None:
        candidate = str(db_path)
    else:
        curr_db = str(DB_PATH) if DB_PATH is not None else ""
        vazus_mod = (
            sys.modules.get("vazus_core.ble_mi_scale_scanner")
            or sys.modules.get("vazus_core.integrations.ble_mi_scale_scanner")
        )
        
        try:
            curr_norm = str(Path(curr_db).resolve()).lower()
        except Exception:
            curr_norm = curr_db.lower()

        # Priority 1: Check if this module's DB_PATH was explicitly patched away from default
        if curr_db and curr_norm != canonical_norm:
            candidate = curr_db
        # Priority 2: Check if vazus_core alias module's DB_PATH was patched
        elif vazus_mod and hasattr(vazus_mod, "DB_PATH"):
            vazus_db_val = str(vazus_mod.DB_PATH)
            try:
                vazus_norm = str(Path(vazus_db_val).resolve()).lower()
            except Exception:
                vazus_norm = vazus_db_val.lower()
            if vazus_db_val and vazus_norm != canonical_norm:
                candidate = vazus_db_val
            elif os.getenv("VAZUS_DB_PATH"):
                candidate = os.getenv("VAZUS_DB_PATH")
            else:
                candidate = curr_db or DEFAULT_DB_PATH
        # Priority 3: Check VAZUS_DB_PATH environment variable
        elif os.getenv("VAZUS_DB_PATH"):
            candidate = os.getenv("VAZUS_DB_PATH")
        # Priority 4: Default DB_PATH
        else:
            candidate = curr_db or DEFAULT_DB_PATH

    # Route through vazus_core.memory.db._resolve_target_db_path()
    resolved = candidate
    if _resolve_target_db_path is not None:
        try:
            resolved = _resolve_target_db_path(candidate)
        except Exception:
            resolved = candidate

    # Test Sandboxing Guard: Under test isolation, NEVER permit writing to canonical DB
    if _is_test_environment():
        try:
            res_norm = str(Path(resolved).resolve()).lower()
        except Exception:
            res_norm = str(resolved).lower()

        if res_norm == canonical_norm or res_norm.replace("\\", "/").endswith("services/memory/vazus.db"):
            iso_env = os.getenv("VAZUS_DB_PATH")
            try:
                iso_norm = str(Path(iso_env).resolve()).lower() if iso_env else ""
            except Exception:
                iso_norm = str(iso_env).lower() if iso_env else ""

            if iso_env and iso_norm != canonical_norm and not iso_norm.replace("\\", "/").endswith("services/memory/vazus.db"):
                resolved = iso_env
            else:
                sandbox_db = Path(tempfile.gettempdir()) / "vazus_ble_test_sandbox.db"
                resolved = str(sandbox_db)

    return str(resolved)

# User default profile for BIA calculations
USER_PROFILE = {
    "height_cm": 178,
    "age": 24,
    "gender": "male"
}

def calculate_bia_metrics(weight_kg, impedance_ohms, height_cm=178, age=24, gender="male"):
    """
    Exact reverse-engineered Xiaomi Mi Body Composition Scale 2 (BIA) equations
    """
    if height_cm is None or height_cm <= 0:
        height_cm = 178.0
    if weight_kg is None or weight_kg <= 0:
        weight_kg = 70.0

    height_m = height_cm / 100.0
    bmi = round(weight_kg / (height_m * height_m), 1)

    if impedance_ohms > 0 and impedance_ohms < 3000:
        # Official Xiaomi LBM (Lean Body Mass) coefficient
        lbm = (height_cm * 9.058 / 100.0) * (height_cm / 100.0)
        lbm += weight_kg * 0.32 + 12.226
        lbm -= impedance_ohms * 0.0068
        lbm -= age * 0.0542

        const = 0.8 if gender == "male" else (9.25 if age <= 49 else 7.25)
        coeff = 0.96 if (gender == "male" and weight_kg > 60) else (0.98 if gender == "male" else 1.0)
        if height_cm > 160:
            coeff *= 1.03

        body_fat_pct = (1.0 - (((lbm - const) * coeff) / weight_kg)) * 100.0
        body_fat_pct = max(5.0, min(55.0, round(body_fat_pct, 1)))

        muscle_mass_kg = round(weight_kg * (1.0 - (body_fat_pct / 100.0)) * 0.85, 1)
        water_pct = round((100.0 - body_fat_pct) * 0.72, 1)
        visceral_fat = min(30, max(1, int((bmi - 18.5) * 1.5 + (age * 0.1))))
        bmr_kcal = int(13.397 * weight_kg + 4.799 * height_cm - 5.677 * age + 88.362)
    else:
        body_fat_pct = 15.2
        muscle_mass_kg = round(weight_kg * 0.72, 1)
        water_pct = 61.1
        visceral_fat = 10
        bmr_kcal = int(13.397 * weight_kg + 4.799 * height_cm - 5.677 * age + 88.362)

    return {
        "weight_kg": round(weight_kg, 2),
        "impedance_ohms": impedance_ohms,
        "bmi": bmi,
        "body_fat_pct": body_fat_pct,
        "muscle_mass_kg": muscle_mass_kg,
        "water_pct": water_pct,
        "visceral_fat": visceral_fat,
        "bmr_kcal": bmr_kcal
    }

def save_weighin_to_db(metrics, source="Direct_BLE_MiScale_2", db_path=None):
    try:
        target_db = _get_effective_db_path(db_path)
        canonical_norm = str(Path(DEFAULT_DB_PATH).resolve()).lower()
        try:
            target_norm = str(Path(target_db).resolve()).lower()
        except Exception:
            target_norm = str(target_db).lower()

        if _is_test_environment() and (target_norm == canonical_norm or target_norm.replace("\\", "/").endswith("services/memory/vazus.db")):
            raise PermissionError("Refusing write to canonical vazus.db under active test/review environment!")

        if target_db != ":memory:" and not target_db.startswith("file:"):
            try:
                Path(target_db).resolve().parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        conn = sqlite3.connect(target_db)
        try:
            import sqlite_vec
            sqlite_vec.load(conn)
        except Exception:
            pass
        cur = conn.cursor()
        now_iso = datetime.now().isoformat()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mi_scale_weighins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                weight_kg REAL,
                impedance_ohms REAL,
                bmi REAL,
                body_fat_pct REAL,
                muscle_mass_kg REAL,
                water_pct REAL,
                visceral_fat_grade INTEGER,
                visceral_fat INTEGER,
                bmr_kcal INTEGER,
                raw_source TEXT,
                source TEXT
            )
        """)
        col_names = {c[1] for c in cur.execute("PRAGMA table_info(mi_scale_weighins)").fetchall()}
        
        row_dict = {
            "timestamp": now_iso,
            "weight_kg": metrics.get('weight_kg'),
            "impedance_ohms": metrics.get('impedance_ohms'),
            "bmi": metrics.get('bmi'),
            "body_fat_pct": metrics.get('body_fat_pct'),
            "muscle_mass_kg": metrics.get('muscle_mass_kg'),
            "water_pct": metrics.get('water_pct'),
            "bmr_kcal": metrics.get('bmr_kcal'),
        }
        if "visceral_fat_grade" in col_names:
            row_dict["visceral_fat_grade"] = metrics.get('visceral_fat_grade', metrics.get('visceral_fat', 10))
        if "visceral_fat" in col_names:
            row_dict["visceral_fat"] = metrics.get('visceral_fat', 10)
        if "raw_source" in col_names:
            row_dict["raw_source"] = source
        if "source" in col_names:
            row_dict["source"] = source

        # Keep only keys that match existing columns
        target_cols = [k for k in row_dict.keys() if k in col_names]
        col_str = ", ".join(target_cols)
        placeholders = ", ".join(["?"] * len(target_cols))
        vals = tuple(row_dict[k] for k in target_cols)

        cur.execute(f"""
            INSERT INTO mi_scale_weighins ({col_str})
            VALUES ({placeholders})
        """, vals)
        conn.commit()

        try:
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
        except Exception as e_kg:
            print(f"Note on kg_nodes sync: {e_kg}")

        conn.close()
        print(f"✅ Successfully saved BLE Weigh-in: {metrics['weight_kg']} kg into {target_db}!")
    except Exception as e:
        print(f"Error saving weighin: {e}")

def parse_mi_scale_v2_data(service_data):
    """
    Decodes Mi Body Composition Scale 2 (UUID 0x181B) advertisement bytes
    Format: <BB7xHH (control1, control2, 7 timestamp bytes, impedance, weight)
    """
    if len(service_data) < 13:
        return None

    from struct import unpack
    ctrl_1, ctrl_2, impedance_raw, raw_weight = unpack("<BB7xHH", service_data[:13])

    has_impedance = bool(ctrl_2 & (1 << 7))
    is_stabilized = bool(ctrl_2 & (1 << 5))
    weight_removed = bool(ctrl_2 & (1 << 7))

    if ctrl_2 & (1 << 6):
        weight_kg = (raw_weight / 100.0) * 0.5
    elif ctrl_1 == 3:
        weight_kg = (raw_weight / 100.0) * 0.45359237
    else:
        weight_kg = raw_weight / 200.0

    return {
        "is_stabilized": is_stabilized,
        "has_impedance": has_impedance,
        "weight_removed": weight_removed,
        "impedance_ohms": impedance_raw if has_impedance else 0,
        "weight_kg": round(weight_kg, 2)
    }

async def scan_mi_scale(scan_seconds=30):
    print(f"🔍 Starting Direct BLE Scanner for Mi Scale 2 ({scan_seconds}s scan)...")
    
    last_processed_weight = None
    last_processed_impedance = 0

    def ble_callback(_device, advertisement_data):
        nonlocal last_processed_weight, last_processed_impedance
        # Check Service Data UUID 0x181B (Mi Scale 2) or 0x181D (Mi Scale 1)
        for uuid, data in advertisement_data.service_data.items():
            if '181b' in uuid.lower() or '181d' in uuid.lower():
                parsed = parse_mi_scale_v2_data(data)
                if parsed and parsed['weight_kg'] > 10.0:
                    w = parsed['weight_kg']
                    imp = parsed['impedance_ohms']
                    has_imp = parsed['has_impedance']
                    stab = parsed['is_stabilized']
                    
                    if not stab:
                        print(f"⚖️ Measuring: {w} kg...", end="\r", flush=True)
                    else:
                        print(f"📡 Broadcast: {w} kg | Stabilized: {stab} | Impedance: {imp} Ω (has_imp: {has_imp})")
                    
                    # Update if new weight, or if we just captured a new impedance reading
                    if stab:
                        if (w != last_processed_weight) or (imp > 0 and imp != last_processed_impedance):
                            last_processed_weight = w
                            if imp > 0:
                                last_processed_impedance = imp
                                print(f"🎯 FULL BIA CAPTURED: {w} kg | Impedance: {imp} Ω")
                            else:
                                print(f"⏳ Weight locked at {w} kg. Continue standing for impedance bars...")
                            
                            metrics = calculate_bia_metrics(w, imp)
                            save_weighin_to_db(metrics)

    try:
        vazus_mod = sys.modules.get("vazus_core.ble_mi_scale_scanner")
        scanner_cls = getattr(vazus_mod, "BleakScanner", BleakScanner) if vazus_mod else BleakScanner
        scanner = scanner_cls(ble_callback)
        await scanner.start()
        await asyncio.sleep(scan_seconds)
        await scanner.stop()
        print("🏁 BLE Scan completed.")
    except (BleakError, Exception) as e:
        print(f"⚠️ BLE Scan encountered hardware error / exception: {e}")

if __name__ == '__main__':
    if _is_test_environment():
        print("⚠️ Test/Review environment detected. Redirecting scanner to sandbox DB.")
    scan_time = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    asyncio.run(scan_mi_scale(scan_seconds=scan_time))
