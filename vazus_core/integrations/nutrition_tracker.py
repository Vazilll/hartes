import sys
try:
    import services.health_agent.nutrition_tracker as _sh_nt
except ImportError as e:
    raise ImportError(
        f"vazus_core.nutrition_tracker: cannot import from "
        f"'/home/tarhes/Проекты/vazus/services/health_agent/nutrition_tracker.py'. "
        f"Ensure the file exists and has no syntax errors. Original error: {e}"
    ) from e

DB_PATH = _sh_nt.DB_PATH
google_multimodal_vision = _sh_nt.google_multimodal_vision
_safe_float = _sh_nt._safe_float
analyze_lab_report_image = _sh_nt.analyze_lab_report_image

def init_nutrition_db(*args, **kwargs):
    target_db = getattr(sys.modules[__name__], "DB_PATH", _sh_nt.DB_PATH)
    _sh_nt.DB_PATH = target_db
    return _sh_nt.init_nutrition_db(*args, **kwargs)

def log_meal(*args, **kwargs):
    target_db = getattr(sys.modules[__name__], "DB_PATH", _sh_nt.DB_PATH)
    _sh_nt.DB_PATH = target_db
    return _sh_nt.log_meal(*args, **kwargs)

def get_daily_nutrition_summary(*args, **kwargs):
    target_db = getattr(sys.modules[__name__], "DB_PATH", _sh_nt.DB_PATH)
    _sh_nt.DB_PATH = target_db
    return _sh_nt.get_daily_nutrition_summary(*args, **kwargs)

def analyze_meal_photo_gemini(*args, **kwargs):
    target_db = getattr(sys.modules[__name__], "DB_PATH", _sh_nt.DB_PATH)
    _sh_nt.DB_PATH = target_db
    _sh_nt.analyze_lab_report_image = sys.modules[__name__].analyze_lab_report_image
    return _sh_nt.analyze_meal_photo_gemini(*args, **kwargs)

__all__ = [
    "DB_PATH",
    "google_multimodal_vision",
    "_safe_float",
    "analyze_lab_report_image",
    "init_nutrition_db",
    "log_meal",
    "analyze_meal_photo_gemini",
    "get_daily_nutrition_summary",
]

