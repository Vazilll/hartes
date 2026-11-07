"""
Unit Test Suite for Milestone 3 (F8, F9) of Autonomous Absolute AI Flywheel.

Components Tested:
- F8: Anti-Thrashing Circuit Breaker (anti_thrashing.py)
  * TaskAttempt dataclass (schema, defaults, automatic AST hash derivation)
  * Location-independent AST hashing (normalize_ast, compute_ast_hash)
  * Active deadlock detector with 3 trip invariants:
    (1) Bounded retry budget (<= 3 consecutive failed cycles with non-positive score progression)
    (2) Structural oscillation deadlock (A -> B -> A) via AST structural hashes
    (3) Immediate fail-closed halt on missing external credentials / prerequisites (0 retries wasted)
  * State transitions (ACTIVE -> DEGRADED -> WARNING -> TRIPPED_*)
  * Thread-safety and task isolation
  * Unfreeze and reset capabilities
- F9: Human Escalation Diagnostic Briefing (escalation_gate.py)
  * Executive markdown diagnostic briefing generator
  * Failure progression & churn chronology table
  * Minimal Unsatisfiable Core (MUC) & SMT counterexample formatting
  * 3 push-button actionable human decision forks (Option A: manual patch, Option B: relax contract, Option C: abort & blacklist)
  * Markdown table injection sanitization and long stacktrace truncation
  * Multi-target publishing (Google Drive 30TB Vault + local telemetry mirrors)
"""

import threading

import pytest

from vazus_autonomous_harness.engine.anti_thrashing import (
    AntiThrashingCircuitBreaker,
    TaskAttempt,
    compute_ast_hash,
)
from vazus_autonomous_harness.engine.escalation_gate import (
    EscalationBriefingGenerator,
    HumanDecisionFork,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def temp_vault(tmp_path):
    """Provides isolated temporary vault directory for briefing tests."""
    vault_dir = tmp_path / "escalations"
    vault_dir.mkdir(parents=True, exist_ok=True)
    return vault_dir


@pytest.fixture
def circuit_breaker(temp_vault):
    """Provides an isolated AntiThrashingCircuitBreaker instance."""
    return AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(temp_vault))


# =====================================================================
# 1. TaskAttempt & AST Hashing Unit Tests (F8)
# =====================================================================

def test_task_attempt_schema_and_defaults():
    """Verifies TaskAttempt dataclass schema, types, and default values."""
    attempt = TaskAttempt(
        task_id="task_001",
        cycle_number=1,
        score=65.0,
        code_hash="sha256_dummy_hash",
        error_message="Contract violation",
    )
    assert attempt.task_id == "task_001"
    assert attempt.cycle_number == 1
    assert attempt.score == 65.0
    assert attempt.code_hash == "sha256_dummy_hash"
    assert attempt.error_message == "Contract violation"
    assert attempt.missing_prerequisite is None
    assert attempt.candidate_code is None
    assert attempt.smt_counterexample is None
    assert attempt.ast_bloat_ratio == 0.0
    assert isinstance(attempt.timestamp, float)
    assert attempt.timestamp > 0.0


def test_task_attempt_automatic_ast_hash_derivation():
    """Verifies that passing candidate_code automatically derives code_hash if omitted."""
    code = "def add(x, y):\n    return x + y\n"
    attempt = TaskAttempt(
        task_id="auto_hash_task",
        cycle_number=1,
        score=70.0,
        candidate_code=code,
    )
    assert attempt.code_hash != ""
    assert attempt.code_hash != "hash_empty"
    assert attempt.code_hash == compute_ast_hash(code)


def test_compute_ast_hash_whitespace_and_comment_invariance():
    """Verifies that formatting, indentation, and comments do not alter the AST hash."""
    code_v1 = """
def calculate_area(width: int, height: int) -> int:
    # Calculate rectangular area
    result = width * height
    return result
"""
    code_v2 = """
def calculate_area(width: int, height: int) -> int:

    # Different comment here
    result = width * height

    return result
"""
    code_v3 = "def calculate_area(width: int, height: int) -> int:\n    result = width * height\n    return result\n"

    hash_v1 = compute_ast_hash(code_v1)
    hash_v2 = compute_ast_hash(code_v2)
    hash_v3 = compute_ast_hash(code_v3)

    assert hash_v1 == hash_v2
    assert hash_v2 == hash_v3
    assert len(hash_v1) == 64  # SHA-256 hex string


def test_compute_ast_hash_structural_difference():
    """Verifies that distinct AST structures produce distinct SHA-256 hashes."""
    code_add = "def func(a, b):\n    return a + b\n"
    code_mul = "def func(a, b):\n    return a * b\n"
    code_sub = "def func(a, b):\n    return a - b\n"

    h_add = compute_ast_hash(code_add)
    h_mul = compute_ast_hash(code_mul)
    h_sub = compute_ast_hash(code_sub)

    assert h_add != h_mul
    assert h_add != h_sub
    assert h_mul != h_sub


def test_compute_ast_hash_syntax_error_resilience():
    """Verifies that malformed non-Python or syntax-error code falls back gracefully without throwing."""
    broken_code_1 = "def broken(:::"
    broken_code_2 = "def broken(:::"
    h1 = compute_ast_hash(broken_code_1)
    h2 = compute_ast_hash(broken_code_2)

    assert isinstance(h1, str)
    assert len(h1) == 64
    assert h1 == h2


def test_compute_ast_hash_empty_string():
    """Verifies empty or whitespace-only code handling."""
    h_empty = compute_ast_hash("")
    h_space = compute_ast_hash("   \n\t  ")
    assert h_empty == h_space
    assert len(h_empty) == 64


# =====================================================================
# 2. Circuit Breaker Invariant Tripping Tests (F8)
# =====================================================================

def test_three_consecutive_failed_cycles_trip(circuit_breaker):
    """Invariant 1: Trips after 3 consecutive failed cycles with downward score progression."""
    task_id = "stalled_01"

    # Cycle 1: 60.0 (fails threshold 75)
    t1 = circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 60.0, "h1", "Error 1"))
    assert t1 is False
    assert circuit_breaker.is_tripped(task_id) is False
    assert circuit_breaker.get_state(task_id) == "DEGRADED"

    # Cycle 2: 55.0 (downward progression)
    t2 = circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 55.0, "h2", "Error 2"))
    assert t2 is False
    assert circuit_breaker.is_tripped(task_id) is False
    assert circuit_breaker.get_state(task_id) == "WARNING"

    # Cycle 3: 50.0 (downward progression) -> TRIPPED
    t3 = circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 50.0, "h3", "Error 3"))
    assert t3 is True
    assert circuit_breaker.is_tripped(task_id) is True
    assert circuit_breaker.get_state(task_id) == "TRIPPED_THRASHING"
    assert "3 consecutive failed cycles" in circuit_breaker.get_trip_reason(task_id)


def test_flat_score_delta_consecutive_failures_trip(circuit_breaker):
    """Invariant 1: Trips when score delta is flat (stagnant delta = 0.0) across 3 attempts."""
    task_id = "flat_score_task"
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 62.0, "h_a"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 62.0, "h_b"))
    tripped = circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 62.0, "h_c"))

    assert tripped is True
    assert circuit_breaker.is_tripped(task_id) is True
    assert "non-positive progression" in circuit_breaker.get_trip_reason(task_id)


def test_score_progression_allows_continued_execution(circuit_breaker):
    """Invariant 1: Positive progression (>0 delta) allows execution to continue even below threshold."""
    task_id = "improving_task"
    # Attempt 1: 40.0
    assert circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 40.0, "h1")) is False
    # Attempt 2: 55.0 (+15.0 delta)
    assert circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 55.0, "h2")) is False
    # Attempt 3: 70.0 (+15.0 delta) -> Progressing upwards, must NOT trip
    assert circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 70.0, "h3")) is False
    assert circuit_breaker.is_tripped(task_id) is False


def test_score_reaching_threshold_clears_degradation(circuit_breaker):
    """Reaching >= admission_threshold (75.0) marks task as ACTIVE and healthy."""
    task_id = "succeeding_task"
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 40.0, "h1"))
    assert circuit_breaker.get_state(task_id) == "DEGRADED"

    circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 85.0, "h2"))
    assert circuit_breaker.is_tripped(task_id) is False
    assert circuit_breaker.get_state(task_id) == "ACTIVE"


def test_structural_oscillation_trip_a_b_a(circuit_breaker):
    """Invariant 2: Trips immediately on cycle 3 when code reverts to previous state (A -> B -> A)."""
    task_id = "osc_task_01"
    # Cycle 1: hash A
    assert circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 60.0, "hash_state_A")) is False
    # Cycle 2: hash B
    assert circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 60.0, "hash_state_B")) is False
    # Cycle 3: hash A again (reverted)
    tripped = circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 60.0, "hash_state_A"))

    assert tripped is True
    assert circuit_breaker.is_tripped(task_id) is True
    assert circuit_breaker.get_state(task_id) == "TRIPPED_DEADLOCK"
    assert "Structural oscillation deadlock" in circuit_breaker.get_trip_reason(task_id)
    assert "oscillation" in circuit_breaker.get_trip_reason(task_id).lower()


def test_structural_oscillation_with_candidate_code_asts(circuit_breaker):
    """Invariant 2: Verifies oscillation detection works with raw candidate code via AST hashes."""
    task_id = "code_osc_task"
    code_A1 = "def fn(x):\n    # First try\n    return x + 1\n"
    code_B = "def fn(x):\n    return x + 2\n"
    code_A2 = "def fn(x):\n    # Reverted with different comment\n    return x + 1\n"

    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 60.0, candidate_code=code_A1))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 60.0, candidate_code=code_B))
    tripped = circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 60.0, candidate_code=code_A2))

    assert tripped is True
    assert circuit_breaker.is_tripped(task_id) is True
    assert "oscillation" in circuit_breaker.get_trip_reason(task_id).lower()


def test_missing_prerequisite_immediate_trip(circuit_breaker):
    """Invariant 3: Trips immediately on cycle 1 with 0 retries on missing external credentials."""
    task_id = "auth_fail_task"
    tripped = circuit_breaker.record_attempt(TaskAttempt(
        task_id=task_id,
        cycle_number=1,
        score=0.0,
        code_hash="hash_0",
        missing_prerequisite="google_token.json not found on disk"
    ))

    assert tripped is True
    assert circuit_breaker.is_tripped(task_id) is True
    assert circuit_breaker.get_state(task_id) == "TRIPPED_CREDENTIALS"
    assert "missing external prerequisite" in circuit_breaker.get_trip_reason(task_id).lower()


@pytest.mark.parametrize("prereq", [
    "Google Drive G:\\ mount unavailable",
    "GitHub Actions token expired (HTTP 401)",
    "Cloud API quota exhausted (HTTP 429 ResourceExhausted)",
    "SSH key authentication failed to 157.228.174.15",
])
def test_missing_prerequisite_various_reasons(circuit_breaker, prereq):
    """Invariant 3: Tests multiple realistic missing prerequisites."""
    task_id = f"prereq_test_{abs(hash(prereq)) % 1000}"
    tripped = circuit_breaker.record_attempt(TaskAttempt(
        task_id=task_id,
        cycle_number=1,
        score=0.0,
        code_hash="h0",
        missing_prerequisite=prereq,
    ))
    assert tripped is True
    assert circuit_breaker.is_tripped(task_id) is True
    assert prereq in circuit_breaker.get_trip_reason(task_id)


def test_subsequent_attempts_on_tripped_task_remain_tripped(circuit_breaker):
    """Once a task is tripped, all subsequent record_attempt calls return True immediately."""
    task_id = "permanently_stalled"
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 50.0, "h1"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 45.0, "h2"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 40.0, "h3"))
    assert circuit_breaker.is_tripped(task_id) is True

    # 4th and 5th attempts attempted without unfreeze
    assert circuit_breaker.record_attempt(TaskAttempt(task_id, 4, 35.0, "h4")) is True
    assert circuit_breaker.record_attempt(TaskAttempt(task_id, 5, 30.0, "h5")) is True


def test_task_isolation(circuit_breaker):
    """Multiple tasks track independent failure counts and states."""
    circuit_breaker.record_attempt(TaskAttempt("task_X", 1, 50.0, "hx1"))
    circuit_breaker.record_attempt(TaskAttempt("task_X", 2, 45.0, "hx2"))
    circuit_breaker.record_attempt(TaskAttempt("task_X", 3, 40.0, "hx3"))

    assert circuit_breaker.is_tripped("task_X") is True
    assert circuit_breaker.is_tripped("task_Y") is False

    circuit_breaker.record_attempt(TaskAttempt("task_Y", 1, 70.0, "hy1"))
    assert circuit_breaker.is_tripped("task_Y") is False
    assert circuit_breaker.get_state("task_Y") == "DEGRADED"


def test_custom_failure_budget(temp_vault):
    """Verifies that max_failures parameter is respected for different budget sizes."""
    # Strict breaker: max_failures = 1
    strict_breaker = AntiThrashingCircuitBreaker(max_failures=1, vault_path=str(temp_vault))
    assert strict_breaker.record_attempt(TaskAttempt("strict", 1, 60.0, "hs1")) is True
    assert strict_breaker.is_tripped("strict") is True

    # Lenient breaker: max_failures = 5
    lenient_breaker = AntiThrashingCircuitBreaker(max_failures=5, vault_path=str(temp_vault))
    for i in range(1, 5):
        assert lenient_breaker.record_attempt(TaskAttempt("lenient", i, 50.0 - i, f"hl{i}")) is False
    # 5th attempt trips
    assert lenient_breaker.record_attempt(TaskAttempt("lenient", 5, 40.0, "hl5")) is True
    assert lenient_breaker.is_tripped("lenient") is True


def test_custom_admission_threshold(temp_vault):
    """Verifies custom admission_threshold behavior."""
    high_bar_breaker = AntiThrashingCircuitBreaker(max_failures=3, admission_threshold=85.0, vault_path=str(temp_vault))
    # Score 80.0 is below 85.0 threshold, so it counts as failure
    high_bar_breaker.record_attempt(TaskAttempt("high_bar", 1, 80.0, "h1"))
    high_bar_breaker.record_attempt(TaskAttempt("high_bar", 2, 78.0, "h2"))
    tripped = high_bar_breaker.record_attempt(TaskAttempt("high_bar", 3, 76.0, "h3"))

    assert tripped is True
    assert high_bar_breaker.is_tripped("high_bar") is True


def test_circuit_breaker_unfreeze(circuit_breaker):
    """Option A: Unfreeze removes task from tripped tasks and resets operational state."""
    task_id = "frozen_task"
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 50.0, "h1"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 45.0, "h2"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 40.0, "h3"))
    assert circuit_breaker.is_tripped(task_id) is True

    unfrozen = circuit_breaker.unfreeze(task_id)
    assert unfrozen is True
    assert circuit_breaker.is_tripped(task_id) is False
    assert circuit_breaker.get_state(task_id) == "ACTIVE"

    # Unfreezing an already active task returns False
    assert circuit_breaker.unfreeze(task_id) is False


def test_circuit_breaker_reset_single_and_all(circuit_breaker):
    """Verifies reset functionality for single task and entire breaker state."""
    circuit_breaker.record_attempt(TaskAttempt("t1", 1, 50.0, "h1"))
    circuit_breaker.record_attempt(TaskAttempt("t2", 1, 50.0, "h2"))

    # Reset t1 only
    circuit_breaker.reset(task_id="t1")
    assert len(circuit_breaker.get_attempts("t1")) == 0
    assert len(circuit_breaker.get_attempts("t2")) == 1

    # Reset all
    circuit_breaker.reset()
    assert len(circuit_breaker.get_attempts("t2")) == 0
    assert len(circuit_breaker.history) == 0


def test_circuit_breaker_thread_safety(temp_vault):
    """Verifies that concurrent record_attempt calls across threads are safe and consistent."""
    breaker = AntiThrashingCircuitBreaker(max_failures=10, vault_path=str(temp_vault))
    task_id = "concurrent_task"
    threads = []
    errors = []

    def worker(cycle_idx):
        try:
            attempt = TaskAttempt(task_id, cycle_idx, 60.0 - cycle_idx, f"hash_{cycle_idx}")
            breaker.record_attempt(attempt)
        except Exception as e:
            errors.append(e)

    for i in range(1, 11):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(breaker.get_attempts(task_id)) == 10
    assert breaker.is_tripped(task_id) is True


# =====================================================================
# 3. Escalation Briefing Generation Tests (F9)
# =====================================================================

def test_escalation_briefing_header_and_incident_id(circuit_breaker):
    """Verifies incident header, incident ID format, and critical severity markers."""
    task_id = "header_test_task"
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 60.0, "h1", "Contract SAT"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 50.0, "h2", "Regression"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 40.0, "h3", "Timeout"))

    briefing = circuit_breaker.generate_escalation_briefing(task_id)

    assert "# 🚨 EXECUTIVE ESCALATION BRIEFING: AUTONOMOUS FLYWHEEL HALTED" in briefing
    assert f"Incident ID**: ESC-{task_id}" in briefing
    assert "SEVERITY**: CRITICAL" in briefing or "CRITICAL -- AUTONOMOUS EXECUTION FROZEN" in briefing
    assert "Subsystem**: Anti-Thrashing Circuit Breaker (R3)" in briefing


def test_escalation_briefing_chronology_table_rendering(circuit_breaker):
    """Verifies that the churn chronology Markdown table renders accurate columns and rows."""
    task_id = "chronology_verify"
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 65.0, "hash_state_1", "SMT SAT violation"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 58.0, "hash_state_2", "IndexError out of bounds"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 50.0, "hash_state_3", "Regression on suite 2"))

    briefing = circuit_breaker.generate_escalation_briefing(task_id)

    assert "| Cycle | Code Hash | Score | Failure Reason |" in briefing
    assert "|:---:|:---:|:---:|:---|" in briefing
    assert "| 1 | hash_state_1 | 65.0 | SMT SAT violation |" in briefing
    assert "| 2 | hash_state_2 | 58.0 | IndexError out of bounds |" in briefing
    assert "| 3 | hash_state_3 | 50.0 | Regression on suite 2 |" in briefing


def test_escalation_briefing_three_actionable_forks(circuit_breaker):
    """Verifies that Option A, Option B, and Option C are explicitly rendered with exact CLI commands."""
    task_id = "decision_forks_task"
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 50.0, "hash_forks", "Failure"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 45.0, "hash_forks_2", "Failure"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 40.0, "hash_forks_3", "Failure"))

    briefing = circuit_breaker.generate_escalation_briefing(task_id)

    assert "## 4. Human Decision Gate (Push-Button Actionable Forks)" in briefing
    assert "[OPTION A] Manual Patch & Resume" in briefing
    assert f"--unfreeze --task-id {task_id}" in briefing

    assert "[OPTION B] Relax Contract Invariant" in briefing
    assert f"--relax-contract --task-id {task_id}" in briefing

    assert "[OPTION C] Abort & Blacklist Mutation Path" in briefing
    assert f"--abort --task-id {task_id} --record-reflexion" in briefing
    assert "hash_forks_3" in briefing


def test_escalation_briefing_minimal_unsatisfiable_core_with_smt_cex(circuit_breaker):
    """Verifies that SMT counterexamples are rendered as formatted JSON in section 3."""
    task_id = "smt_cex_task"
    cex_model = {"x": "-10", "y": "0", "capacity": "100"}
    attempt = TaskAttempt(
        task_id=task_id,
        cycle_number=1,
        score=20.0,
        code_hash="hash_cex",
        error_message="SMT SAT contract counterexample found",
        smt_counterexample=cex_model,
    )
    circuit_breaker.record_attempt(attempt)
    circuit_breaker.tripped_tasks[task_id] = "SMT disproof halt"

    briefing = circuit_breaker.generate_escalation_briefing(task_id)

    assert "Minimal Unsatisfiable Core" in briefing
    assert "counterexample" in briefing.lower() or "smt sat witness" in briefing.lower()
    assert '"capacity": "100"' in briefing
    assert '"x": "-10"' in briefing


def test_escalation_briefing_minimal_unsatisfiable_core_without_smt_cex(circuit_breaker):
    """Verifies graceful formatting when no SMT counterexample exists."""
    task_id = "no_cex_task"
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 30.0, "h_no_cex", "Simple test assertion failure"))
    circuit_breaker.tripped_tasks[task_id] = "Test assertion failure"

    briefing = circuit_breaker.generate_escalation_briefing(task_id)

    assert "Minimal Unsatisfiable Core" in briefing
    assert "None recorded" in briefing


def test_escalation_briefing_table_markdown_injection_sanitization(circuit_breaker):
    """Verifies that pipes and linebreaks in error messages do not break Markdown table syntax."""
    task_id = "inject_sanitize_task"
    malicious_err = "Error | pipe | column | \n and newline text `code`"
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 10.0, "h_inj", malicious_err))
    circuit_breaker.tripped_tasks[task_id] = "Sanitization test"

    briefing = circuit_breaker.generate_escalation_briefing(task_id)

    # Pipes should be escaped or stripped in table row
    for line in briefing.splitlines():
        if line.startswith("| 1 |"):
            # Table row should have exactly 5 pipe characters (start, 3 separators, end)
            assert line.count("|") == 5
            assert "\\|" in line or "pipe" in line


def test_escalation_briefing_table_long_error_truncation(circuit_breaker):
    """Verifies that extremely long stacktraces are truncated in table rows to preserve readability."""
    task_id = "huge_error_task"
    giant_trace = "Traceback (most recent call last):\n" + "\n".join([f"  File 'mod_{i}.py', line {i}" for i in range(300)])
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 15.0, "h_huge", giant_trace))
    circuit_breaker.tripped_tasks[task_id] = "Massive stacktrace"

    briefing = circuit_breaker.generate_escalation_briefing(task_id)

    for line in briefing.splitlines():
        if line.startswith("| 1 |"):
            assert len(line) < 350
            assert "..." in line


def test_escalation_briefing_empty_attempts_history(circuit_breaker):
    """Verifies that briefing generation succeeds even if no attempts were recorded."""
    task_id = "zero_attempt_task"
    circuit_breaker.tripped_tasks[task_id] = "Immediate manual operator freeze"

    briefing = circuit_breaker.generate_escalation_briefing(task_id)

    assert f"ESC-{task_id}" in briefing
    assert "No attempts recorded before halt" in briefing
    assert "[OPTION A] Manual Patch & Resume" in briefing


def test_escalation_briefing_file_persistence_in_vault(temp_vault, circuit_breaker):
    """Verifies that generate_escalation_briefing writes the file to the vault directory with size > 100 bytes."""
    task_id = "persistence_test_task"
    circuit_breaker.record_attempt(TaskAttempt(task_id, 1, 50.0, "hp1", "err1"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 2, 45.0, "hp2", "err2"))
    circuit_breaker.record_attempt(TaskAttempt(task_id, 3, 40.0, "hp3", "err3"))

    circuit_breaker.generate_escalation_briefing(task_id)

    expected_file = temp_vault / f"ESCALATION_{task_id}.md"
    assert expected_file.exists()
    assert expected_file.stat().st_size > 100
    file_content = expected_file.read_text(encoding="utf-8")
    assert f"ESC-{task_id}" in file_content
    assert "[OPTION A]" in file_content


def test_escalation_briefing_multi_target_publishing(tmp_path):
    """Verifies multi-target publication to primary vault, local fallback, and telemetry vault."""
    primary = tmp_path / "primary_vault"
    local = tmp_path / "local_vault"
    telem = tmp_path / "telem_vault"

    generator = EscalationBriefingGenerator(vault_path=primary, local_path=local, telemetry_path=telem)
    task_id = "multi_target_task"
    content, written_paths = generator.generate_and_publish(
        task_id=task_id,
        reason="Multi-target validation test",
        attempts=[TaskAttempt(task_id, 1, 50.0, "h_mt", "Test fail")],
    )

    assert len(written_paths) >= 2
    assert (primary / f"ESCALATION_{task_id}.md").exists()
    assert (local / f"ESCALATION_{task_id}.md").exists()
    assert (telem / f"ESCALATION_{task_id}.md").exists()


def test_escalation_briefing_deep_uncreated_directory_creation(tmp_path):
    """Verifies that uncreated nested target directories are created automatically."""
    deep_path = tmp_path / "nested" / "sub" / "vault"
    breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(deep_path))
    task_id = "deep_dir_task"
    breaker.record_attempt(TaskAttempt(task_id, 1, 10.0, "h1", "f1"))
    breaker.record_attempt(TaskAttempt(task_id, 2, 10.0, "h2", "f2"))
    breaker.record_attempt(TaskAttempt(task_id, 3, 10.0, "h3", "f3"))

    breaker.generate_escalation_briefing(task_id)

    assert (deep_path / f"ESCALATION_{task_id}.md").exists()


# =====================================================================
# 4. End-to-End Handshake Tests (F8 x F9 x CLI)
# =====================================================================

def test_full_anti_thrashing_to_escalation_briefing_flow(temp_vault):
    """End-to-end integration: 3 failed cycles -> trip -> briefing generation -> file in vault."""
    breaker = AntiThrashingCircuitBreaker(max_failures=3, vault_path=str(temp_vault))
    task_id = "e2e_stalled_flywheel"

    # Cycle 1
    assert breaker.record_attempt(TaskAttempt(task_id, 1, 65.0, "h_c1", "SMT contract violated")) is False
    # Cycle 2
    assert breaker.record_attempt(TaskAttempt(task_id, 2, 55.0, "h_c2", "Empirical tests failed")) is False
    # Cycle 3: Tripped!
    assert breaker.record_attempt(TaskAttempt(task_id, 3, 45.0, "h_c3", "Negative constraint blocked")) is True

    assert breaker.is_tripped(task_id) is True
    briefing = breaker.generate_escalation_briefing(task_id)

    assert f"ESC-{task_id}" in briefing
    assert "h_c1" in briefing
    assert "h_c2" in briefing
    assert "h_c3" in briefing
    assert "[OPTION A] Manual Patch & Resume" in briefing
    assert "[OPTION B] Relax Contract Invariant" in briefing
    assert "[OPTION C] Abort & Blacklist Mutation Path" in briefing

    # Verify disk persistence
    report_path = temp_vault / f"ESCALATION_{task_id}.md"
    assert report_path.exists()
    assert report_path.stat().st_size > 500


def test_oscillation_to_escalation_briefing_flow(temp_vault):
    """End-to-end integration: Oscillation (A -> B -> A) -> trip -> briefing contains Option C fingerprint."""
    breaker = AntiThrashingCircuitBreaker(max_failures=5, vault_path=str(temp_vault))
    task_id = "e2e_osc_flywheel"

    code_A = "def solve():\n    return 10\n"
    code_B = "def solve():\n    return 20\n"

    breaker.record_attempt(TaskAttempt(task_id, 1, 50.0, candidate_code=code_A))
    breaker.record_attempt(TaskAttempt(task_id, 2, 50.0, candidate_code=code_B))
    tripped = breaker.record_attempt(TaskAttempt(task_id, 3, 50.0, candidate_code=code_A))

    assert tripped is True
    briefing = breaker.generate_escalation_briefing(task_id)

    assert "Structural oscillation deadlock" in briefing
    assert "[OPTION C] Abort & Blacklist Mutation Path" in briefing
    hash_A = compute_ast_hash(code_A)
    assert hash_A in briefing


def test_human_decision_fork_dataclass():
    """Verifies HumanDecisionFork dataclass properties."""
    fork = HumanDecisionFork(
        option_key="[OPTION A]",
        title="Manual Patch & Resume",
        description="Apply patch manually in source file",
        action_command="python -m vazus_autonomous_harness.engine.anti_thrashing --unfreeze --task-id T1",
    )
    assert fork.option_key == "[OPTION A]"
    assert "Manual Patch" in fork.title
    assert "--unfreeze" in fork.action_command
