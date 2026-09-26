## 2025-02-23 - Arbitrary Code Execution in Quality Engine
**Vulnerability:** The QualityEvaluationEngine used `exec(candidate_code, sandbox_ns)` to execute inline tests from candidate code within the main process memory space.
**Learning:** This is a critical security vulnerability that allows any untrusted candidate code to have full access to the current process, potentially leaking secrets or corrupting the process.
**Prevention:** Always isolate the execution of untrusted code using isolated subprocesses with timeouts.
