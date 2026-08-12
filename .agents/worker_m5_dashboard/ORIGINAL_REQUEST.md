## 2026-07-24T16:05:04Z

<USER_REQUEST>
You are Worker 1 for Milestone 5 (R5: Web Dashboard Cognitive & Mastery Tab).

Working Directory: C:\vazus\.agents\worker_m5_dashboard
Project Workspace: C:\vazus

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Task:
Implement the Web Dashboard Cognitive & Mastery Tab in `scripts/dashboard.html`, the backend REST API in `scripts/dashboard.py`, and test suite in `tests/test_dashboard_cognitive_tab.py`.

Please review the Explorer analysis report for detailed UI, API, and test specifications:
`C:\vazus\.agents\teamwork_preview_explorer_m5_1\analysis.md`

Requirements:
1. `scripts/dashboard.html`:
   - Add `.main-tab-bar` navigation header to switch between Multimodal Knowledge Hub and Cognitive & Mastery Workspace (`#view-cognitive`).
   - Implement Mastery Score progress bar (% mastered, SM-2 retention metrics).
   - Implement Interactive Question Trainer (active recall prompt, answer input textarea, submit button, 0–100% score gauge, SM-2 quality grade selector 0–5, target rationale card).
   - Implement Atomic Note Reader (Zettelkasten note viewer, clickable `[[Wikilinks]]` badges, interactive `- [ ]` action checkboxes).

2. `scripts/dashboard.py`:
   - Serve REST API endpoints:
     - `GET /api/v1/cognitive/stats` (global card counts, due count, average retention %).
     - `GET /api/v1/cognitive/next-question` (retrieves next due card via `cognitive_tutor_engine`).
     - `POST /api/v1/cognitive/evaluate-answer` (evaluates answer via `cognitive_tutor_engine`, updates SM-2 state, returns score & rationale).
     - `GET /api/v1/wiki/note?id=...` (reads Zettelkasten Markdown note).
     - `POST /api/v1/wiki/checkbox` (toggles checkbox state in note file).
   - Strict Path Boundary Security: Enforce `file_path.resolve().relative_to(Path("C:/vazus").resolve())` returning HTTP 403 Forbidden for any path traversal outside `C:\vazus`.

3. `tests/test_dashboard_cognitive_tab.py`:
   - Unit/integration test suite verifying server startup, REST API endpoints, HTML tab markup, and path traversal security enforcement (HTTP 403).

4. Build & Test Verification:
   - Run `C:\vazus\.venv\Scripts\python.exe -m unittest tests/test_dashboard_cognitive_tab.py` using `run_command`.
   - Ensure all tests pass cleanly with Exit Code 0.

5. Handoff:
   - Write completion report to `C:\vazus\.agents\worker_m5_dashboard\handoff.md`. Send a message to parent when complete.
</USER_REQUEST>
