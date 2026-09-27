"""
vazus_autonomous_harness.context — Anti-Context-Rot Subsystem.
"""

from vazus_autonomous_harness.context.session_sharder import (
    DEFAULT_BASELINE_CHARS,
    DEFAULT_MAX_BASELINE_CHARS,
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_ENTROPY,
    DEFAULT_MAX_TURNS,
    DEFAULT_RAW_TOOL_MAX_LINES,
    DEFAULT_STALE_ASSISTANT_MAX_LEN,
    DEFAULT_UNMASKED_TURN_LAG,
    EntropyGovernor,
    GovernorEvaluation,
    ObservationMasker,
    SessionSharder,
    StageContextManager,
    compute_attention_entropy,
    compute_shannon_entropy,
)

__all__ = [
    "DEFAULT_BASELINE_CHARS",
    "DEFAULT_MAX_BASELINE_CHARS",
    "DEFAULT_MAX_CHARS",
    "DEFAULT_MAX_ENTROPY",
    "DEFAULT_MAX_TURNS",
    "DEFAULT_RAW_TOOL_MAX_LINES",
    "DEFAULT_STALE_ASSISTANT_MAX_LEN",
    "DEFAULT_UNMASKED_TURN_LAG",
    "EntropyGovernor",
    "GovernorEvaluation",
    "ObservationMasker",
    "SessionSharder",
    "StageContextManager",
    "compute_attention_entropy",
    "compute_shannon_entropy",
]
