import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
import sqlite3
from vazus_core.utils import normalize_russian_text, format_timestamp, parse_selection, fast_json_dumps, fast_json_loads
from vazus_core.db import get_db_connection


def test_fast_json():
    data = {"name": "vazus", "nodes": [1, 2, 3], "metadata": {"active": True}}
    encoded = fast_json_dumps(data)
    assert isinstance(encoded, str)
    decoded = fast_json_loads(encoded)
    assert decoded["name"] == "vazus"
    assert decoded["nodes"] == [1, 2, 3]




def test_normalize_russian_text():
    raw_text = " Привет [МУЗЫКА] (смех) мир! \xa0 \u200b Это (инерция) тест. "
    normalized = normalize_russian_text(raw_text)
    assert normalized == "Привет мир! Это (инерция) тест."
    assert normalize_russian_text("") == ""


def test_format_timestamp():
    ts_float = 1700000000.0
    formatted = format_timestamp(ts_float)
    assert "2023" in formatted
    assert "UTC" in formatted


def test_parse_selection():
    parsed = parse_selection("1, 3, 5-7, 10", max_val=8)
    assert parsed == [1, 3, 5, 6, 7]
    assert parse_selection("") == []


def test_vector_packing():
    from vazus_core.db import pack_vector_f32, unpack_vector_f32
    original_vec = [0.123, -0.456, 0.789] * 256  # 768D float vector
    packed = pack_vector_f32(original_vec)
    assert len(packed) == 768 * 4  # 3072 bytes
    unpacked = unpack_vector_f32(packed)
    assert len(unpacked) == 768
    assert abs(unpacked[0] - 0.123) < 1e-4


def test_concurrent_db_writes(tmp_path):
    import concurrent.futures
    from vazus_core.db import get_db_connection
    test_db = tmp_path / "concurrent.db"
    
    with get_db_connection(test_db) as conn:
        conn.execute("CREATE TABLE concurrent_test (id INT PRIMARY KEY, val TEXT);")
        conn.commit()

    def worker_write(worker_id):
        with get_db_connection(test_db) as conn:
            conn.execute("INSERT OR REPLACE INTO concurrent_test VALUES (?, ?)", (worker_id, f"worker_{worker_id}"))
            conn.commit()
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker_write, i) for i in range(20)]
        results = [f.result() for f in futures]

    assert all(results)
    with get_db_connection(test_db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM concurrent_test").fetchone()[0]
        assert count == 20

