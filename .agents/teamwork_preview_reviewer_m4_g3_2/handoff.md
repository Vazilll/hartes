# Milestone 4 (R4: Active Learning Engine & SuperMemo SM-2 Engine) Review Report

## 1. Observation

- **Target Files Inspected**:
  - `vazus_core/cognitive_tutor_engine.py` (742 lines)
  - `scripts/personal_tutor.py` (277 lines)
  - `tests/test_cognitive_tutor_engine.py` (246 lines)

- **Implementation Details**:
  - `calculate_sm2_update()` in `vazus_core/cognitive_tutor_engine.py:65-117` implements SuperMemo SM-2 algorithm:
    - Ease Factor formula: `EF' = max(1.3, round(ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)), 4))`
    - Milestone intervals for $Q \ge 3$: $n'=1 \rightarrow 1.0$, $n'=2 \rightarrow 3.0$, $n'=3 \rightarrow 7.0$, $n'=4 \rightarrow 21.0$, $n' > 4 \rightarrow \text{round}(I \times EF')$.
    - Failed review lapse ($Q < 3$): $n'=0, I'=1.0$.
  - `ResponseEvaluator` in `vazus_core/cognitive_tutor_engine.py:303-396` combines 768D semantic cosine similarity (weight 0.50), keyword recall (weight 0.35), and character sequence matching (weight 0.15). Handles embedding quota/network fallback gracefully by flooring semantic similarity with lexical overlap ($0.6 \times \text{kw\_recall} + 0.4 \times \text{seq\_match}$).
  - `CognitiveTutorEngine._get_connection()` in `vazus_core/cognitive_tutor_engine.py:483-489`:
    - `sqlite3.connect(self.db_path, timeout=30.0)`
    - `conn.execute("PRAGMA journal_mode=WAL;")`
  - Parameter bindings verified across all queries (`INSERT INTO tutor_cards`, `SELECT FROM tutor_cards`, `INSERT INTO tutor_reviews`, etc.) — 100% parameterization using `?` placeholders.
  - Non-TTY fallback in CLI `scripts/personal_tutor.py:179-191`:
    - Checks `if not sys.stdin.isatty():`
    - Prints non-interactive note, runs 1 simulated card review with ground truth, logs review, and exits cleanly.

- **Test Execution Results**:
  - Unit Test Execution:
    `C:\vazus\.venv\Scripts\python.exe -m unittest tests/test_cognitive_tutor_engine.py`
    Output: `Ran 13 tests in 23.062s — OK`
  - CLI Self-Test Execution:
    `C:\vazus\.venv\Scripts\python.exe scripts/personal_tutor.py --test`
    Output: `[SELF-TEST PASSED] All Cognitive Tutor Engine checks OK.` (Exit code 0)
  - CLI Stats Execution:
    `C:\vazus\.venv\Scripts\python.exe scripts/personal_tutor.py --stats`
    Output: Exit code 0, formatted mastery stats displayed.
  - Non-Interactive Review Execution:
    `C:\vazus\.venv\Scripts\python.exe scripts/personal_tutor.py --review`
    Output: Detected non-TTY environment, executed 1 simulated review, updated DB, exited cleanly with Exit Code 0.

## 2. Logic Chain

1. **SM-2 Algorithmic Correctness**:
   - `calculate_sm2_update()` correctly increments repetitions $n$, updates Ease Factor $EF$ clamped at lower bound $1.3$, and sets initial interval milestones ($1, 3, 7, 21$ days) for passing grades ($Q \ge 3$). Lapses ($Q < 3$) correctly reset $n \rightarrow 0$ and $I \rightarrow 1.0$ day while lowering $EF$.
2. **SQLite Concurrency & Safety**:
   - Connections open with `timeout=30.0` to avoid database lock failures under concurrent writes.
   - WAL mode (`PRAGMA journal_mode=WAL;`) is explicitly set on every connection.
   - Parameterized queries eliminate all SQL injection vectors.
   - Database indexes on `(next_review_at, ease_factor)` optimize due-card query performance.
3. **Robustness & Non-TTY Fallback**:
   - `ResponseEvaluator` automatically catches embedding exceptions / HTTP 429 quota exhaustion and falls back to text similarity without breaking evaluation.
   - CLI script handles non-TTY `sys.stdin` gracefully, avoiding hanging or unhandled `EOFError`.
4. **Integrity & Code Quality**:
   - Zero hardcoded test outputs or facade implementations detected.
   - Question generation dynamically processes `ThesisNode`, `ProtocolNode`, and `ZettelNote` structures.
   - All 13 unit tests pass cleanly against independent execution.

## 3. Caveats

- **API Quota Usage**:
  - When the Google GenAI embedding service exceeds rate limits (HTTP 429), `ResponseEvaluator` logs a fallback notice and uses token/sequence matching. This is expected behavior and handled safely by design.
- No other caveats.

## 4. Conclusion

**Verdict**: **APPROVE**

Milestone 4 (R4: Active Learning Engine & SuperMemo SM-2 Engine) satisfies all functional, mathematical, concurrency, performance, and CLI requirements. Code quality is high, error handling is robust, non-TTY execution operates cleanly, and unit/CLI test suites pass completely without integrity violations.

## 5. Verification Method

To independently verify this verdict:

1. **Run Unit Tests**:
   ```powershell
   C:\vazus\.venv\Scripts\python.exe -m unittest tests/test_cognitive_tutor_engine.py
   ```
   *Expected output*: `Ran 13 tests in ... s` -> `OK`.

2. **Run CLI Self-Test**:
   ```powershell
   C:\vazus\.venv\Scripts\python.exe scripts/personal_tutor.py --test
   ```
   *Expected output*: `[SELF-TEST PASSED] All Cognitive Tutor Engine checks OK.` (Exit code 0).

3. **Run Non-TTY Review Simulation**:
   ```powershell
   C:\vazus\.venv\Scripts\python.exe scripts/personal_tutor.py --review
   ```
   *Expected output*: `[Note] Running in non-interactive environment. Simulating 1 card review...` followed by complete session log and clean exit.

4. **Inspect Source Code Files**:
   - Check `vazus_core/cognitive_tutor_engine.py:483-489` for WAL mode & timeout = 30.0.
   - Check `vazus_core/cognitive_tutor_engine.py:65-117` for SM-2 math formula and milestones (1, 3, 7, 21 days).
