# Google Jules REST API & Cloud VM Verification Architecture

## 📌 Context & Purpose
Google Jules REST API (`https://jules.googleapis.com/v1alpha/`) provides async cloud VM pre-commit analysis and code verification.
In Vazus OS, `vazus_core/jules_client.py` handles end-to-end authentication, session creation, activity polling, and graceful fallback when `JULES_API_KEY` is not present or HTTP 429 rate limit is hit.

## 🚀 Environment & Setup
1. **API Key Environment Variable**: `JULES_API_KEY`
2. **Base URL**: `https://jules.googleapis.com/v1alpha`
3. **Core Module**: [`vazus_core/jules_client.py`](file:///C:/vazus/vazus_core/jules_client.py)
4. **Test Suite**: [`tests/test_jules_client.py`](file:///C:/vazus/tests/test_jules_client.py)

## 🛠️ API Payload Specs
- **Create Session (`POST /sessions`)**:
  ```json
  {
    "prompt": "Pre-commit verification prompt",
    "title": "Cloud VM Verification Session"
  }
  ```
- **Fallback Protocol**: If `JULES_API_KEY` is not set or network/rate-limit occurs, `JulesClient` returns `{"fallback": True, "reason": "...", "verified": False}`, allowing local REPL and SMT Z3 verifiers to take over smoothly without crashing.

## ⚡ Integration Points
- `vazus_core/jules_client.py`
- `vazus_core/unified_reasoning_pipeline.py`
- `vazus_core/safety_guardrail.py`
- `vazus_core/subagent_framework.py`
- `vazus_core/post_task_evolver.py`
