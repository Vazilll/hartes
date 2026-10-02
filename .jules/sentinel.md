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

