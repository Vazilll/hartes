## 2026-07-24T16:02:18Z
You are Worker 1 for Milestone 4 (R4: Active Learning SM-2 Engine & Spaced Repetition Tutor).

Working Directory: C:\vazus\.agents\worker_m4_tutor
Project Workspace: C:\vazus

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Task:
Implement the Active Learning Engine in `vazus_core/cognitive_tutor_engine.py`, the CLI runner in `scripts/personal_tutor.py`, and unit test suite in `tests/test_cognitive_tutor_engine.py`.

Please review the Explorer analysis report for detailed design specifications:
`C:\vazus\.agents\teamwork_preview_explorer_m4_1\analysis.md`

Requirements:
1. `vazus_core/cognitive_tutor_engine.py`:
   - Implement `calculate_sm2_update(repetitions: int, ease_factor: float, interval_days: float, quality_rating: int) -> Tuple[int, float, float]` implementing SuperMemo SM-2 algorithm (EF min 1.3, milestone intervals 1, 3, 7, 21 days).
   - Implement `generate_active_recall_question(entity_dict: Dict) -> Dict` generating Socratic active recall questions from `ThesisNode`, `ProtocolNode`, and Zettelkasten Markdown notes.
   - Implement `evaluate_answer(question_dict: Dict, user_answer: str) -> Dict` evaluating user response with 0–100% accuracy score, quality rating Q (0–5), feedback rationale, and SM-2 update calculations.
   - Implement SQLite persistence for `tutor_cards` and `tutor_reviews` tables in `vazus.db`.

2. `scripts/personal_tutor.py`:
   - CLI script with flags: `--test` (runs non-interactive self-test returning Exit Code 0), `--review` (interactive recall review session), `--stats` (prints mastery stats).

3. `tests/test_cognitive_tutor_engine.py`:
   - Unit test suite verifying SM-2 math for Q=0..5, Ease Factor min bound (1.3), Socratic question generation, answer evaluation, SQLite persistence, and `personal_tutor.py --test` execution cleanly returning Exit Code 0.

4. Build & Test Verification:
   - Run `C:\vazus\.venv\Scripts\python.exe -m unittest tests/test_cognitive_tutor_engine.py` using `run_command`.
   - Run `C:\vazus\.venv\Scripts\python.exe scripts/personal_tutor.py --test` using `run_command`.
   - Ensure all commands return Exit Code 0.

5. Handoff:
   - Write completion report to `C:\vazus\.agents\worker_m4_tutor\handoff.md`. Send a message to parent when complete.
