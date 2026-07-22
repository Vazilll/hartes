# Original User Request

## 2026-07-22T16:23:04Z

Implement the full integration of DNTS OS SuperGraph Architecture connecting GitHub wrappers (MIT RLM, Open Deep Research), 768D Gemini Embeddings, Graphify AST Pruning, Karpathy Memory Wiki, and Verifier Worker into a unified system with native subagents.

Working directory: C:\vazus
Integrity mode: development

## Requirements

### R1. Native Subagents & GitHub Wrappers Bridge
Create Python bridge scripts in C:\vazus\pyenv\scripts linking the native subagents (open_deep_researcher, rlm_code_engineer, verifier_worker) directly to the downloaded GitHub repositories in C:\vazus\pyenv\rlm-mit, C:\vazus\pyenv\open-deep-research, and C:\vazus\pyenv\dnts_core.

### R2. Unified SuperGraph & 768D Embeddings Integration
Integrate C:\vazus\pyenv\dnts_core\embeddings.py (768D Google Gemini Embeddings) with codebase-memory-mcp (Graphify AST Code Topology) and C:\vazus\services\memory\semantic\wiki (Karpathy Memory Wiki) using the hybrid node-linking metric.

### R3. DeepMind Token Economy & Prompt Compression
Implement AST Pruning for python files and context caching prefix structures to minimize token usage across agent calls.

## Acceptance Criteria

### Execution & Verification
- [ ] RLM bridge C:\vazus\pyenv\scripts\subagent_rlm_bridge.py executes successfully in C:\vazus\pyenv\.venv.
- [ ] Open Deep Research bridge C:\vazus\pyenv\scripts\subagent_research_bridge.py executes successfully in C:\vazus\pyenv\.venv.
- [ ] OpenVINO NPU verification script C:\vazus\verify_ov_npu.py and 768D Embeddings embeddings.py run with Exit Code 0.
- [ ] AGENTS.md and configuration files accurately reference the updated subagent roles and repository paths.
