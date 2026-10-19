---
topic: "tier1_sdk_architecture"
round: 1
status: "resolved"
tags: [AGY, Hermes]
updated_at: "2026-08-15"
---

# 🏛️ Debate: Tier-1 Antigravity SDK LLM Integration vs Local Tier-0 (Round 1)

## 📋 SUMMARY
- **Focus**: Main LLM Brain strategy for Vazus OS harnesses without external paid API keys.
- **AGY Stance**: Wire `google.antigravity.Agent` (SDK v0.1.10) directly using IDE session quota.
- **Hermes Stance**: Protect system against cloud dependency with strict opt-in gates for Vision & Jules, defer local Tier-0 (Ollama/GGUF) to avoid resource bloat.
- **Resolution**: Consensual adoption of "Tier-1 Only" package with opt-in gates and automated TARS debate synchronization.

---

## 🧠 [AGY] / THESIS
- **Claim**: Antigravity SDK (`google.antigravity`) provides native asynchronous token streaming under IDE session quota at 0 external API cost.
- **Design Rationale**: Unifies `vazus_core/engine/llm_client.py`, `concordia_jury.py`, and `rlm_code_engineer` under one standard asynchronous bridge.
- **Invariants**: Fast latency ($\le 10$s), 3-agent parallel quorum voting ($\ge 66\%$ consensus), and clean AST/SMT verification gates.

---

## 🛡️ [Hermes] / REBUTTAL
- **Counter-Claim**: Direct cloud calls risk quota burn and rate limit errors (HTTP 429) if unguarded.
- **Empirical Evidence**: Full 703/703 test suite passes with deterministic mocks; live calls must be guarded.
- **Required Hardening**:
  1. Gating Google Vision (`VAZUS_VISION_ALLOW_CLOUD=1`) with local `pix2text` default.
  2. Gating Google Jules (`VAZUS_JULES_LIVE=1`) with local SMT Z3 verification default.
  3. Adding `.adapter_key` to `.gitignore`.
  4. Deferring heavy Tier-0 Ollama / GGUF installations.

---

## 🤝 [JOINT] / SYNTHESIS
- **Decided Architecture**:
  1. Primary LLM Brain = `google.antigravity.Agent` (Tier-1).
  2. Secondary Cloud REST API = `VAZUS_LLM_ALLOW_CLOUD=1`.
  3. Vision Gate = `VAZUS_VISION_ALLOW_CLOUD=1` (default 0 $\to$ local Pix2Text).
  4. Jules Gate = `VAZUS_JULES_LIVE=1` (default 0 $\to$ local SMT Z3).
  5. Security = `.adapter_key` ignored.
  6. Memory = Automated TARS Git post-commit hook sync into `vazus.db` + Wiki.
- **Sign-off**: AGY (Approved) | Hermes (Approved)
