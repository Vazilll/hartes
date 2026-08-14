---
name: vazus-supergraph-daemon
description: Long-Running Autonomous Sidecar Daemon for Vazus OS. Monitors workspace changes, executes continuous unit test suites, detects regressions, and triggers self-healing LocalREPL repair without user intervention.
---

# Long-Running SuperGraph Sidecar Daemon (`vazus-supergraph-daemon`)

This skill enables continuous, multi-hour background execution and autonomous code repair for Antigravity sessions.

## 🔄 Autonomous Multi-Hour Execution Protocol

1. **Continuous Workspace Watching**:
   Monitors `C:\vazus` file modifications via `system_daemon.py` and `watchdog`.

2. **Automated Verification Loop**:
   Runs `pytest` and `ast.parse` in quiet background threads on file save.

3. **Autonomous Self-Healing**:
   When errors occur, invokes `SelfHealingREPLManager` with `AntiLoopCircuitBreaker` and `SMTZ3Verifier` to repair code in LocalREPL.

4. **Multi-Agent Consensus**:
   Submits repaired proposals to `vazus-concordia-team` for $\ge 66\%$ jury vote before committing to Git provenance.
