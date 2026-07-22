# PROJECT PLAN: DNTS OS SuperGraph Architecture Integration

## Architecture Overview
DNTS OS SuperGraph Architecture unifies:
1. GitHub Wrappers: `rlm-mit` (C:\vazus\pyenv\rlm-mit), `open-deep-research` (C:\vazus\pyenv\open-deep-research), `dnts_core` (C:\vazus\pyenv\dnts_core)
2. Native Subagents: `open_deep_researcher`, `rlm_code_engineer`, `verifier_worker`
3. Embeddings & Graph Memory: 768D Gemini Embeddings (`embeddings.py`), AST Code Topology (`codebase-memory-mcp`), Karpathy Memory Wiki (`C:\vazus\memory\semantic\wiki`)
4. Token Economy: AST Pruning & Context Caching

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Mapping | Explore existing files in `pyenv\scripts`, `pyenv\rlm-mit`, `pyenv\open-deep-research`, `pyenv\dnts_core`, `verify_ov_npu.py`, `embeddings.py`, `AGENTS.md` | None | DONE |
| 2 | R1: Native Subagents & GitHub Wrappers Bridge | Implement Python bridge scripts in `C:\vazus\pyenv\scripts\subagent_rlm_bridge.py`, `subagent_research_bridge.py`, and verifier bridge connecting native subagents to repositories | M1 | DONE |
| 3 | R2: Unified SuperGraph & 768D Embeddings Integration | Integrate 768D Google Gemini Embeddings (`embeddings.py`) with codebase-memory-mcp (Graphify AST) and Karpathy Memory Wiki using hybrid node-linking metric | M1, M2 | DONE |
| 4 | R3: DeepMind Token Economy & Prompt Compression | Implement AST Pruning for Python files and prefix context caching structures to minimize token usage across subagents | M1, M3 | DONE |
| 5 | E2E Verification & Forensic Audit | Run `verify_ov_npu.py`, `embeddings.py`, `subagent_rlm_bridge.py`, `subagent_research_bridge.py` in `C:\vazus\pyenv\.venv`, update `AGENTS.md` and configuration files, run Forensic Auditor | M2, M3, M4 | DONE |

## Interface Contracts & Paths
- Python Executable: `C:\vazus\pyenv\.venv\Scripts\python.exe`
- Scripts Directory: `C:\vazus\pyenv\scripts\`
- RLM Repository: `C:\vazus\pyenv\rlm-mit\`
- Open Deep Research Repository: `C:\vazus\pyenv\open-deep-research\`
- DNTS Core: `C:\vazus\pyenv\dnts_core\`
- Memory Wiki: `C:\vazus\memory\semantic\wiki\`
- Verification Script: `C:\vazus\verify_ov_npu.py`
