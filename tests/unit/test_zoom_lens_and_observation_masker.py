"""
Tests for vazus_core.verification.ast_pruner ZoomLensPruner and vazus_core.hooks.observation_masker.
"""

from vazus_core.verification.ast_pruner import ASTPruner, ZoomLensPruner
from vazus_core.hooks.observation_masker import ObservationMasker


SAMPLE_CODE = """def calculate_metrics(a: int, b: int) -> int:
    x = a * 2
    y = b * 3
    return x + y

def generate_report(data: dict) -> str:
    lines = []
    for k, v in data.items():
        lines.append(f"{k}: {v}")
    return "".join(lines)
"""


def test_zoom_lens_wide():
    pruned, stats = ASTPruner.prune_with_zoom(SAMPLE_CODE, zoom_level="wide")
    assert stats["is_valid"] is True
    assert "def calculate_metrics" in pruned
    assert "def generate_report" in pruned
    assert "..." in pruned
    assert stats["reduction_percentage"] > 20.0


def test_zoom_lens_close_target():
    pruned, stats = ASTPruner.prune_with_zoom(
        SAMPLE_CODE, zoom_level="close", target_symbol="calculate_metrics"
    )
    assert stats["is_valid"] is True
    assert "x = a * 2" in pruned
    assert "y = b * 3" in pruned
    assert "generate_report" in pruned


def test_observation_masker_pytest_success():
    raw_pytest = (
        "============================= test session starts =============================\n"
        "collecting ... collected 42 items\n"
        "test_a.py ...\n"
        "============================== 42 passed in 1.12s =============================="
    )
    masked = ObservationMasker.mask_tool_output("run_command", raw_pytest, max_chars=100)
    assert "42 passed" in masked


def test_observation_masker_long_output():
    long_text = "\n".join([f"Log line {i}" for i in range(100)])
    masked = ObservationMasker.mask_tool_output("run_command", long_text, max_chars=100)
    assert "lines masked to prevent context rot" in masked
