# AGENTS.md — Autonomous Coding Agent Guidelines & Environment Contract

Welcome to **Vazus SuperGraph OS**. This document serves as the formal specification and execution contract for all autonomous coding agents (Google Jules, Claude Code, OpenCode, Antigravity Subagents).

---

## 🏗️ 1. Active Environment & Paths

- **Root Directory**: `C:\vazus`
- **Python Virtualenv**: `C:\vazus\.venv\Scripts\python.exe` (PyTorch, OpenVINO, Beautifulsoup4, sqlite-vec, cv2)
- **Primary Package**: `vazus_core` (`C:\vazus\vazus_core`)
- **Database / Memory**: `C:\vazus\services\memory\vazus.db`
- **Configuration & Hooks**: `C:\Users\Vaz\.gemini\config\hooks.json`

---

## 🧪 2. Test Execution & Quality Gates

All code modifications must satisfy the automated quality gates before committing.

### Fast Test Command (Recommended for TDD Loop):
```powershell
C:\vazus\.venv\Scripts\python.exe -m pytest tests/ -m "not slow" -q --tb=short
```

### Single Module Test Command:
```powershell
C:\vazus\.venv\Scripts\python.exe -m pytest tests/test_<module_name>.py -v
```

### Pre-Commit Gate Command:
```powershell
C:\vazus\.venv\Scripts\python.exe C:\vazus\vazus_core\verification\precommit_gate.py
```

---

## 🛡️ 3. Verification Gates & Prohibited Patterns

The Pre-Commit Quality Gate enforces the following strict checks:
1. **AST Syntax Integrity**: `ast.parse()` must succeed with 0 syntax errors on all `.py` files.
2. **Zero Hardcoded Secrets**: Prohibited embedding of raw API keys (`AIzaSy...`, `sk-...`).
3. **No Dangerous System Calls**: Never use `os.system()` or `subprocess.Popen(..., shell=True)`. Always use explicit list arguments.
4. **Module Package Integrity**: Never use flat imports like `import tinkoff_finance_manager`. Always use the canonical package namespace `from vazus_core.tinkoff_finance_manager import ...` or `from vazus_core.integrations...`.
5. **No Broken Imports or Dangling References**: All modules must be importable without collection errors.

---

## 🔁 4. TDD Workflow Protocol (Red-Green-Refactor)

1. **Phase 1 (Red)**: Write or update the unit test in `tests/test_<feature>.py` to define the expected behavior.
2. **Phase 2 (Green)**: Implement the minimal code in `vazus_core/` to make the test pass.
3. **Phase 3 (Verify)**: Run `post_tool_hook.py` / `precommit_gate.py` to ensure 0 test regressions.
4. **Phase 4 (Clean)**: Delete all temporary scratch scripts and artifacts.
