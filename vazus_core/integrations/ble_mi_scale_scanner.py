import sys
try:
    import services.health_agent.ble_mi_scale_scanner as _sh_ble
except ImportError as e:
    raise ImportError(
        f"vazus_core.ble_mi_scale_scanner: cannot import from "
        f"'C:/vazus/services/health_agent/ble_mi_scale_scanner.py'. "
        f"Ensure the file exists and has no syntax errors. Original error: {e}"
    ) from e

DB_PATH = _sh_ble.DB_PATH
USER_PROFILE = _sh_ble.USER_PROFILE
BleakScanner = getattr(_sh_ble, "BleakScanner", None)

def calculate_bia_metrics(*args, **kwargs):
    _sh_ble.DB_PATH = getattr(sys.modules[__name__], "DB_PATH", _sh_ble.DB_PATH)
    return _sh_ble.calculate_bia_metrics(*args, **kwargs)

def save_weighin_to_db(*args, **kwargs):
    _sh_ble.DB_PATH = getattr(sys.modules[__name__], "DB_PATH", _sh_ble.DB_PATH)
    return _sh_ble.save_weighin_to_db(*args, **kwargs)

def parse_mi_scale_v2_data(*args, **kwargs):
    _sh_ble.DB_PATH = getattr(sys.modules[__name__], "DB_PATH", _sh_ble.DB_PATH)
    return _sh_ble.parse_mi_scale_v2_data(*args, **kwargs)

async def scan_mi_scale(*args, **kwargs):
    _sh_ble.DB_PATH = getattr(sys.modules[__name__], "DB_PATH", _sh_ble.DB_PATH)
    _sh_ble.BleakScanner = getattr(sys.modules[__name__], "BleakScanner", getattr(_sh_ble, "BleakScanner", None))
    return await _sh_ble.scan_mi_scale(*args, **kwargs)

__all__ = [
    "DB_PATH",
    "USER_PROFILE",
    "BleakScanner",
    "calculate_bia_metrics",
    "save_weighin_to_db",
    "parse_mi_scale_v2_data",
    "scan_mi_scale",
]

