"""
vazus_core.utils - Centralized Shared Utility Functions
Eliminates code duplication across vazus_core modules and scripts.
"""

import re
import logging
from datetime import datetime, timezone
from typing import List, Union, Optional, Any

logger = logging.getLogger(__name__)


def normalize_russian_text(text: str) -> str:
    """
    Cleans noise tags ([МУЗЫКА], [АПЛОДИСМЕНТЫ], etc.),
    preserves parenthetical spoken text like '(инерции)' or '(Пятигорск)',
    removes noise parentheses like '(смех)', '(музыка)', '(аплодисменты)', '(шум)',
    normalizes whitespace and formatting for Russian speech transcripts and notes.
    """
    if not text:
        return ""
    text = re.sub(r'\[[^\]]*\]', ' ', text)
    text = re.sub(
        r'\(\s*(?:музыка|смех|аплодисменты|шум|кашель|вздох|пауза|тишина|laughter|music|applause)\s*\)',
        ' ',
        text,
        flags=re.I,
    )
    text = text.replace('\xa0', ' ').replace('\u200b', '')
    return re.sub(r'\s+', ' ', text).strip()


def format_timestamp(timestamp: Union[float, int, str, datetime]) -> str:
    """Consolidated timestamp formatting helper to ISO 8601 UTC representation."""
    if isinstance(timestamp, (int, float)):
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    elif isinstance(timestamp, datetime):
        return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(timestamp)


def parse_selection(selection_str: str, max_val: Optional[int] = None) -> List[int]:
    """
    Parses user selection input like '1,2,5-8,10' into sorted list of integers.
    Used by CLI exporter tools and downloading scripts.
    """
    if not selection_str or not selection_str.strip():
        return []

    selected_indices = set()
    parts = selection_str.replace(" ", "").split(",")

    for part in parts:
        if not part:
            continue
        if "-" in part:
            try:
                start, end = map(int, part.split("-", 1))
                for i in range(min(start, end), max(start, end) + 1):
                    if max_val is None or 1 <= i <= max_val:
                        selected_indices.add(i)
            except ValueError as exc:
                logger.debug("Failed to parse integer range token '%s': %s", part, exc)
        else:
            try:
                idx = int(part)
                if max_val is None or 1 <= idx <= max_val:
                    selected_indices.add(idx)
            except ValueError as exc:
                logger.debug("Failed to parse integer token '%s': %s", part, exc)

    return sorted(list(selected_indices))


def compute_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes cosine similarity between two 768D vector embeddings with BLAS acceleration."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    import math
    try:
        import numpy as np
        arr1 = np.array(vec1, dtype=np.float32)
        arr2 = np.array(vec2, dtype=np.float32)
        if np.isnan(arr1).any() or np.isnan(arr2).any() or np.isinf(arr1).any() or np.isinf(arr2).any():
            return 0.0
        norm1 = float(np.linalg.norm(arr1))
        norm2 = float(np.linalg.norm(arr2))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        res = float(np.dot(arr1, arr2) / (norm1 * norm2))
        return 0.0 if math.isnan(res) or math.isinf(res) else res
    except Exception as exc:
        logger.debug("Numpy cosine similarity computation failed, falling back to pure Python: %s", exc)
        if any(math.isnan(x) or math.isinf(x) for x in vec1) or any(math.isnan(y) or math.isinf(y) for y in vec2):
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude_a = math.sqrt(sum(a * a for a in vec1))
        magnitude_b = math.sqrt(sum(b * b for b in vec2))
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        res = dot_product / (magnitude_a * magnitude_b)
        return 0.0 if math.isnan(res) or math.isinf(res) else res


def fast_json_dumps(obj: Any) -> str:
    """High-speed Rust orjson serialization fallback to stdlib json."""
    try:
        import orjson
        return orjson.dumps(obj).decode("utf-8")
    except ImportError as exc:
        logger.debug("Optional module orjson unavailable, using stdlib json: %s", exc)
        import json
        return json.dumps(obj)


def fast_json_loads(json_str: Union[str, bytes]) -> Any:
    """High-speed Rust orjson deserialization fallback to stdlib json."""
    try:
        import orjson
        return orjson.loads(json_str)
    except ImportError as exc:
        logger.debug("Optional module orjson unavailable, using stdlib json: %s", exc)
        import json
        return json.loads(json_str)


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Centralized socket port status inspector to prevent bind collisions."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0




