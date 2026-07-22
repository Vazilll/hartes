# CONTEXT — DNTS OS SuperGraph Architecture

## System Environment
- **Root Directory**: `C:\dnts`
- **Python Virtualenv**: `C:\dnts\pyenv\.venv`
- **Go Core MCP**: `C:\dnts\gomcp\dnts-brain.exe`
- **Memory Storage**: `C:\dnts\memory\semantic\wiki\` and `C:\dnts\memory\graph.db`

## Target Architecture Integration
1. **R1: Native Subagents & GitHub Wrappers Bridge**
   - Native subagents: `open_deep_researcher`, `rlm_code_engineer`, `verifier_worker`
   - Target bridge scripts: `C:\dnts\pyenv\scripts\subagent_rlm_bridge.py`, `C:\dnts\pyenv\scripts\subagent_research_bridge.py`, and verifier worker bridge linking to `C:\dnts\pyenv\rlm-mit`, `C:\dnts\pyenv\open-deep-research`, and `C:\dnts\pyenv\dnts_core`.

2. **R2: Unified SuperGraph & 768D Embeddings Integration**
   - Bind `C:\dnts\pyenv\dnts_core\embeddings.py` (768D Gemini Embeddings) with `codebase-memory-mcp` (AST Code Topology) and `C:\dnts\memory\semantic\wiki` (Karpathy Memory Wiki).
   - Use hybrid node-linking metric to map AST code nodes and semantic memory nodes into a unified 768D vector space.

3. **R3: DeepMind Token Economy & Prompt Compression**
   - Implement AST Pruning for Python files.
   - Context caching prefix structures to minimize token usage across agent calls.

4. **Acceptance Criteria Verification**
   - `subagent_rlm_bridge.py` executes successfully in `C:\dnts\pyenv\.venv`.
   - `subagent_research_bridge.py` executes successfully in `C:\dnts\pyenv\.venv`.
   - `verify_ov_npu.py` and `embeddings.py` run with Exit Code 0.
   - `AGENTS.md` and configuration files accurately reference updated subagent roles and repository paths.
