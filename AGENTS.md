# vazus SuperGraph OS & Native Antigravity Subagent Architecture

## Overview
This document specifies the native subagent roles, responsibilities, bridge interfaces, repository locations, and tool bindings within the **vazus SuperGraph OS** running on Antigravity CLI and IDE.

---

## System Repositories & Path Directory

| Component / Subsystem | Directory Path | Description |
|---|---|---|
| **System Root** | `C:\vazus` | Root workspace for vazus SuperGraph OS |
| **Python Virtual Environment** | `C:\vazus\.venv` | Python 3.11 virtualenv (PyTorch CPU/NPU, OpenVINO, Optimum, pyNeuroML) |
| **vazus Core Module** | `C:\vazus\vazus_core` | Core engine, AST pruner, embeddings, database, model selector, verifier |
| **MIT RLM Engine** | `C:\vazus\vazus_core\workers\rlm` | Recursive Language Modeling (RLM) engine with LocalREPL environment |
| **Open Deep Research** | `C:\vazus\scripts\subagent_research_bridge.py` | LangGraph multi-step research workflow with Google Search Grounding |
| **Scripts & Subagent Bridges** | `C:\vazus\scripts` | Subagent bridge scripts and memory/vector index tools |
| **Go Core MCP Monolith** | `C:\vazus\gomcp\dnts-brain.exe` | 44 Go MCP tools for Mythos Reasoning, RAG FTS5, Graph Memory, Obsidian |

---

## Native Antigravity Subagent Roles & System Prompts

Subagents are invoked natively in the Antigravity UI using `invoke_subagent` (or registered via `define_subagent`), allowing the user to observe real-time progress and subagent tool cards.

### 1. `open_deep_researcher`
* **Role**: Open Deep Researcher Subagent
* **Description**: LangGraph Open Deep Research + Google Search Grounding for web longreads & research synthesis.
* **Bridge Script**: `C:\vazus\scripts\subagent_research_bridge.py`
* **Execution Command**: `C:\vazus\.venv\Scripts\python.exe C:\vazus\scripts\subagent_research_bridge.py -q "<query>"`
* **Responsibilities**:
  - Executes multi-step web research workflows.
  - Integrates Google Search Grounding with fallback search providers.
  - Synthesizes findings into structured Markdown research reports.

### 2. `rlm_code_engineer`
* **Role**: RLM Code Engineer Subagent
* **Description**: MIT RLM for REPL-based self-healing code generation, refactoring, and execution testing.
* **Bridge Script**: `C:\vazus\scripts\subagent_rlm_bridge.py`
* **Execution Command**: `C:\vazus\.venv\Scripts\python.exe C:\vazus\scripts\subagent_rlm_bridge.py -p "<prompt>"`
* **Responsibilities**:
  - Executes recursive code rollouts in LocalREPL environment.
  - Performs automated bug fixing and self-healing refactoring.
  - Validates AST signatures and code compliance.

### 3. `verifier_worker`
* **Role**: Jules Verifier Worker Subagent
* **Description**: Static AST verifier, contract testing, isolated execution, and Git provenance tracking.
* **Bridge Script**: `C:\vazus\scripts\subagent_verifier_bridge.py`
* **Execution Command**: `C:\vazus\.venv\Scripts\python.exe C:\vazus\scripts\subagent_verifier_bridge.py -f "<target_file>"`
* **Responsibilities**:
  - Performs AST syntax parsing and signature verification.
  - Executes isolated code verification via `CodeVerifier`.
  - Tracks Git provenance across feature branches (`vazus-main`, `vazus-dev`, `feature/subagent-bridges`).

---

## Governance & Verification Protocol
1. **Antigravity First**: All subagent actions are visible in the Antigravity UI dashboard and logs.
2. **Absolute Path Standard**: All internal components reference `C:\vazus` and `C:\vazus\.venv`.
3. **No Facades**: Subagent bridges invoke real execution engines and return verifiable status.
