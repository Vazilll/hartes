## 2024-09-30 - Prevent Shell Injection with subprocess.run
**Vulnerability:** Found `subprocess.run` calls using `shell=True` and unvalidated strings in `tasks/builtin/code_optimizer.py` and `vazus_autonomous_harness/verification/quality_engine.py`, creating command injection risks.
**Learning:** `shell=True` allows shell metacharacters in strings to execute arbitrary commands. Even if tests pass locally, it's a critical vulnerability when taking variable inputs like `test_command`.
**Prevention:** Always use `shell=False` (default) and pass arguments as a list. Use `shlex.split(command)` to safely parse shell strings into lists before passing them to `subprocess.run()`.

## 2025-02-23 - Arbitrary Code Execution in Quality Engine
**Vulnerability:** The QualityEvaluationEngine used `exec(candidate_code, sandbox_ns)` to execute inline tests from candidate code within the main process memory space.
**Learning:** This is a critical security vulnerability that allows any untrusted candidate code to have full access to the current process, potentially leaking secrets or corrupting the process.
**Prevention:** Always isolate the execution of untrusted code using isolated subprocesses with timeouts.

## 2024-05-24 - [Fix Path Traversal in AcademicSovereigntyGuard.check_path_jail]
**Vulnerability:** Path traversal verification for Windows environments (like `C:\vazus`) failed when the application runs on a Linux host because `pathlib.Path(path).resolve()` uses POSIX parsing, interpreting Windows drive prefixes and backslashes simply as invalid or regular characters rather than directory delimiters.
**Learning:** Hardcoding standard `pathlib.Path` for cross-platform file validation introduces a vulnerability where input representing paths from a different OS can bypass the directory traversal protections. In this case, Windows-style directory jumps (`..\`) in strings sent to the Linux server were not accurately resolved or rejected.
**Prevention:** For paths that may come from other Operating Systems or rely on a different OS format, use explicit parsers (`pathlib.PureWindowsPath` or `pathlib.PurePosixPath`) and sanitize traversals before validating if they fall within an approved directory constraint.

## 2026-10-28 - Prevent Arbitrary Code Execution in Optimizer
**Vulnerability:** Code Optimizer executed AI-generated candidate code without validation, risking arbitrary code execution.
**Learning:** AI-generated files must be filtered through a security preflight gate before execution.
**Prevention:** Added PreFlightFilter().check_negative_constraints(code) before executing tests.

## 2025-02-23 - Prevent Path Traversal in Vault File Exports
**Vulnerability:** Found `record.category` being used directly in f-strings to construct file paths for Markdown Zettelkasten exports (`vazus_autonomous_harness/memory/episodic_store.py` and `tests/e2e/contract_loader.py`), creating path traversal risks if the category contained `../`.
**Learning:** Hardcoding string formatting for file paths without sanitizing the variables introduces vulnerabilities, especially when those variables can be dynamically set or loaded.
**Prevention:** Always sanitize dynamically loaded string variables using `clean_var = re.sub(r"[^\w\-]", "_", var)` or using explicit Path parsers (e.g. `Path(var).name`) before using them to build paths or filenames.
## 2025-02-24 - Pre-Flight Security Check on AI Generated Code
**Vulnerability:** `quality_engine.py` evaluated the quality of candidate AI generated code by running the `evaluate` method. During this evaluation, the code was tested (which includes `subprocess.run`), but the candidate code had not been filtered for arbitrary code execution constraints.
**Learning:** Any component that executes or evaluates untrusted AI generated code must run it through the negative constraints filter *before* testing. The previous fix in the `quality_engine.py` prevented `exec`, but a pre-flight filter on the content before test is still required.
**Prevention:** Added `is_blocked, violation_msg = PreFlightFilter().check_negative_constraints(candidate_code)` in the `evaluate` method to block malicious AI code before evaluating it via SMT or testing it inline.
