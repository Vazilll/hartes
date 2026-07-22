# DNTS Unified SuperGraph OS & Subagent Architecture

## Overview
This document specifies the native subagent roles, responsibilities, bridge interfaces, repository locations, and tool bindings within the DNTS SuperGraph OS architecture.

---

## System Repositories & Path Directory

| Component / Subsystem | Directory Path | Description |
|---|---|---|
| **System Root** | `C:\dnts` | Root workspace for DNTS SuperGraph OS |
| **Python Environment & Core** | `C:\dnts\pyenv` | Python 3.11 virtualenv, core modules, scripts, and logs |
| **DNTS Core Module** | `C:\dnts\pyenv\dnts_core` | Core engine, AST pruner, embeddings, database, workers, and verifier |
| **MIT RLM Engine** | `C:\dnts\pyenv\rlm-mit` | Recursive Language Modeling (RLM) engine with LocalREPL environment |
| **Open Deep Research** | `C:\dnts\pyenv\open-deep-research` | LangGraph multi-step research workflow with Google Search Grounding |
| **Scripts & Subagent Bridges** | `C:\dnts\pyenv\scripts` | Bridge execution scripts connecting subagents to target engines |
| **Go Core MCP Monolith** | `C:\dnts\gomcp` / `C:\dnts\gomcp\dnts-brain.exe` | 44 Go MCP tools for Mythos Reasoning, RAG FTS5, Graph Memory, Obsidian |

---

## Native Subagent Roles & Responsibilities

### 1. `open_deep_researcher`
* **Role**: Open Deep Researcher Subagent
* **Description**: LangGraph Open Deep Research + Google Search Grounding for web longreads & research synthesis. Performs multi-step web research, query clarification, and structured report synthesis.
* **Repository Path**: `C:\dnts\pyenv\open-deep-research`
* **Bridge Script**: `C:\dnts\pyenv\scripts\subagent_research_bridge.py`
* **Responsibilities**:
  - Compiles and executes LangGraph StateGraph research workflows.
  - Integrates Google Search Grounding with fallback search providers (DuckDuckGo, Tavily).
  - Synthesizes findings into comprehensive markdown research reports.

### 2. `rlm_code_engineer`
* **Role**: RLM Code Engineer Subagent
* **Description**: MIT RLM for REPL-based self-healing code generation, refactoring, and execution testing. Runs recursive code rollouts in LocalREPL.
* **Repository Path**: `C:\dnts\pyenv\rlm-mit`
* **Bridge Script**: `C:\dnts\pyenv\scripts\subagent_rlm_bridge.py`
* **Responsibilities**:
  - Connects directly to the MIT RLM engine and `dnts_core.workers.rlm`.
  - Executes recursive code analysis, self-healing bug fixes, and REPL test execution.
  - Manages LocalREPL environments and structured prompt optimization.

### 3. `verifier_worker`
* **Role**: Jules Verifier Worker Subagent
* **Description**: Jules Verifier worker for syntax verification, contract testing, isolated execution testing, and Git provenance tracking.
* **Repository Path**: `C:\dnts\pyenv\dnts_core`
* **Bridge Script**: `C:\dnts\pyenv\scripts\subagent_verifier_bridge.py`
* **Responsibilities**:
  - Performs static AST syntax parsing and signature/contract compliance testing.
  - Runs code in isolated subprocess execution via `CodeVerifier`.
  - Manages Git provenance tracking (`GitProvenanceManager`) across DeepMind feature branches.
  - Escalates persistent failures to Google DeepMind Jules Cloud VM (`JulesCloudEscalator`).

### 4. Auxiliary & Coordination Roles
* **`research_coordinator`**: High-level coordinator for multi-step scientific research and web synthesis, spawning `open_deep_researcher` and code inspectors.
* **`hermes_evolution_agent`**: Prompt optimization agent utilizing GEPA (Genetic-Pareto Evolution) and Hebbian Plasticity to compile execution traces into Fast-Path tools.

---

## Subagent Bridge Execution Interfaces

| Subagent Role | Bridge File | Command Line Example |
|---|---|---|
| `open_deep_researcher` | `C:\dnts\pyenv\scripts\subagent_research_bridge.py` | `python C:\dnts\pyenv\scripts\subagent_research_bridge.py -q "SuperGraph Architecture" --dry-run` |
| `rlm_code_engineer` | `C:\dnts\pyenv\scripts\subagent_rlm_bridge.py` | `python C:\dnts\pyenv\scripts\subagent_rlm_bridge.py -p "Verify prime algorithms" --dry-run` |
| `verifier_worker` | `C:\dnts\pyenv\scripts\subagent_verifier_bridge.py` | `python C:\dnts\pyenv\scripts\subagent_verifier_bridge.py -f C:\dnts\pyenv\dnts_core\utils.py` |

---

## Governance & Verification Rules
1. **Integrity Mandate**: No hardcoded test stubs or facade implementations. All subagent bridges must invoke real engines and return verified state.
2. **Minimal Change Principle**: Modifications must be surgical and directly traceable to specific architectural requirements.
3. **Subagent Tooling**: All subagents registered in `dnts_core.subagents.roles` must have `enable_mcp_tools: true` and appropriate permission flags.
