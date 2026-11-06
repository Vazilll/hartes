## 2026-10-28 - Fix Arbitrary Code Execution in quality_engine.py
**Vulnerability:** Untrusted candidate code was executed via a raw `subprocess.run` call, allowing arbitrary system command execution.
**Learning:** Hard-coded `subprocess.run` invocations bypassing the internal sandboxing mechanism fail to isolate the execution environment.
**Prevention:** Always use `LocalReplSandbox().execute_code()` or equivalent dedicated sandbox environments for executing dynamically generated or untrusted code snippets.
