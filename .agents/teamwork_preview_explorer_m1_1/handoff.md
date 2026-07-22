# Handoff Report: R1 (Native Subagents & GitHub Wrappers Bridge) Investigation

**Explorer**: Explorer 1  
**Milestone**: Milestone 1 - DNTS OS SuperGraph Architecture Integration  
**Working Directory**: `C:\dnts\.agents\teamwork_preview_explorer_m1_1`  
**Project Root**: `C:\dnts`  

---

## 1. Observation

### 1.1 `C:\dnts\pyenv\rlm-mit` (MIT Recursive Language Models)
- **Package & Meta**:
  - `pyproject.toml` (lines 2, 6, 21-30): Package name `rlms` (v0.1.3), `requires-python = ">=3.11"`. Core dependencies: `anthropic>=0.75.0`, `google-genai>=1.56.0`, `openai>=2.14.0`, `portkey-ai>=2.1.0`, `pytest>=9.0.2`, `python-dotenv>=1.2.1`, `requests>=2.32.5`, `rich>=13.0.0`. Optional dependencies include `ipython`, `modal`, `e2b`, `daytona`, `prime`.
  - Exposed module: imported via Python as `import rlm` or `from rlm import RLM` (`rlm/__init__.py` lines 1-18).
- **Core Engine & Architecture**:
  - `rlm/core/rlm.py`: Main `RLM` class (lines 41-180). Manages execution loops, context limits, depth control (`depth`, `max_depth`), iteration bounds (`max_iterations`), custom tool injection (`custom_tools`), prompt construction (`build_rlm_system_prompt`), and sub-call thread pools (`max_concurrent_subcalls`).
  - `rlm/clients/`: Client abstractions (`base_lm.py`, `openai.py`, `anthropic.py`, `gemini.py`, `azure_openai.py`, `portkey.py`).
  - `rlm/environments/`: Sandbox REPLs (`local_repl.py` running host `exec`, `ipython_repl.py`, `docker_repl.py`, `modal_repl.py`, `e2b_repl.py`, `daytona_repl.py`, `prime_repl.py`).
- **Interfaces & Entrypoints**:
  - Python API: `from rlm import RLM`; `rlm = RLM(backend="openai", environment="local")`; `res = rlm.completion(prompt)`.
  - CLI: No binary script in `pyproject.toml`; uses Makefile (`make quickstart`, `make check`).

### 1.2 `C:\dnts\pyenv\open-deep-research` (Open Deep Research Agent)
- **Package & Meta**:
  - `pyproject.toml` (lines 2-3, 11-47): Package name `open_deep_research` (v0.0.16), requires Python `>=3.10`.
  - Dependencies: `langgraph>=0.5.4`, `langchain-community`, `langchain-openai`, `langchain-anthropic`, `langchain-google-vertexai`, `langchain-google-genai`, `langchain-mcp-adapters`, `tavily-python`, `duckduckgo-search`, `exa-py`, `azure-search-documents`, `mcp`, `linkup-sdk`, `pandas`, `beautifulsoup4`, `markdownify`, `requests`, `rich`, `langgraph-cli`.
- **Core Architecture & Graph Topology**:
  - `src/open_deep_research/deep_researcher.py` (lines 1-100): Implements `deep_researcher_builder` using LangGraph `StateGraph(AgentState)`. Nodes handle user clarification (`clarify_with_user`), research brief generation, supervisor distribution across concurrent research units (`max_concurrent_research_units`), research execution with web tools (`ddg`, `google`, `tavily`, `exa`), document compression, and final report formatting.
  - `src/open_deep_research/configuration.py`: Dataclass for configurable parameters (`research_model`, `search_api`, `max_researcher_iterations`, etc.).
  - `langgraph.json`: Points deployment graph to `open_deep_research.deep_researcher:deep_researcher_builder`.
- **Interfaces & Entrypoints**:
  - Python API: `from open_deep_research.deep_researcher import deep_researcher_builder`; `graph = deep_researcher_builder.compile(...)`; `await graph.ainvoke({"messages": [...]}, config)`.
  - Scripts: `run_research.py`, `run_google_research.py`, `run_evolution_research.py`, `run_harness_research.py`, `run_hybrid_research.py`, `run_prompt_research.py`, `run_self_evolution_research.py`.

### 1.3 `C:\dnts\pyenv\dnts_core` (DNTS OS Core V2)
- **Structure & Modules**:
  - `config.py`: System configuration (`WORKSPACE_DIR`, `EMBEDDING_DIM = 768`, model endpoint settings).
  - `embeddings.py`: `UnifiedGoogleEmbedder` (lines 12-42) implementing a 768-dim DeepMind vector space using `SentenceTransformer` with deterministic sha256 fallback.
  - `unified_graph.py`: SuperGraph orchestrator (lines 68-94) building a `StateGraph(UnifiedState)`. Uses `unified_router` to route tasks to `deep_research` or `nexus`.
  - `nexus_graph.py`: SuperGraph coding sub-graph.
  - `git_provenance.py`: `GitProvenanceManager` (lines 11-57) managing automatic Git branches with institutional provenance (`feature/<org>/<feature_name>`) and automated commits.
  - `mcp_client.py` & `mcp_server.py`: FastMCP integration and tool autowiring.
  - `subagents/roles.py`: Visual subagent specifications (`research_coordinator`, `rlm_code_engineer`, `hermes_evolution_agent`) configured for Antigravity IDE UI with `enable_subagent_tools=True`.
  - `workers/rlm.py`: RLM worker executing cognitive reflection phase + MIT RLM loop, autowiring compiled tools + MCP tools, and supporting workspace rollback via `HypothesisGraph`.
  - `workers/ldr.py`: Long-Distance Retrieval / Open Deep Research worker wrapper.
  - `evolution/jules_verifier.py`: `JulesCloudEscalator` (lines 12-50) for background code repairs via Google DeepMind Jules VM / CLI, staging tasks to `jules/auto-proposals` branch.

### 1.4 `C:\dnts\pyenv\scripts` & Environment Setup (`C:\dnts\pyenv\.venv`)
- **Scripts Directory** (`C:\dnts\pyenv\scripts`):
  - Contains 43 files including MCP wrappers (`rlm_mcp.py`, `ldr_mcp.py`, `agy_bridge_mcp.py`, `evolution_mcp.py`, `hybrid_search_mcp.py`, `langgraph-mcp.py`, `leann-mcp.py`, `shell_mcp.py`), pipeline tests (`test_unified_graph.py`, `test_nexus_graph.py`, `run_rlm_local_test.py`), and system services (`unified_worker.py`, `worker_monitor.py`, `dnts_rag.py`).
- **Environment Setup** (`C:\dnts\pyenv\.venv`):
  - Created at `C:\dnts\pyenv\.venv` using Python 3.12.10 (`pyvenv.cfg`).
  - Pre-installed packages verified in `Lib/site-packages`:
    - PyTorch CPU: `torch-2.13.0+cpu`, `torchaudio`, `torchvision`
    - OpenVINO: `openvino-2026.2.1`, `openvino_tokenizers-2026.2.1.0`
    - Optimum Intel: `optimum-2.2.0`, `optimum_intel-2.0.0`
    - EasyOCR: `easyocr-1.7.2`
    - PyNeuroML: `pyneuroml-1.3.22`, `libneuroml-0.6.7`
    - LLM & Graph Frameworks: `langgraph`, `langchain`, `open_deep_research`, `rlms`, `fastmcp`, `pydantic`, `rich`.

---

## 2. Logic Chain

1. **Observation 1.1** establishes that `rlm-mit` provides the core REPL execution engine (`RLM`), supporting local and isolated sandboxes, tool autowiring, and sub-LM recursive invocation.
2. **Observation 1.2** establishes that `open-deep-research` provides the deep research subagent architecture (`deep_researcher_builder`) powered by LangGraph, with configurable search APIs (Google, DuckDuckGo, Tavily, Exa) and multi-unit research synthesis.
3. **Observation 1.3** demonstrates that `dnts_core` serves as the SuperGraph integration layer:
   - `unified_graph.py` orchestrates routing between `deep_research` and `nexus`.
   - `subagents/roles.py` defines the 3 visual subagents (`research_coordinator`, `rlm_code_engineer`, `hermes_evolution_agent`) matching the system rules.
   - `git_provenance.py` and `evolution/jules_verifier.py` implement provenance tracking and fallback repair loops (Jules cloud escalation).
   - `embeddings.py` unifies semantic indexing into a 768-dim vector space.
4. **Observation 1.4** verifies that `scripts` directory contains existing FastMCP server wrappers (`rlm_mcp.py`, `ldr_mcp.py`, `agy_bridge_mcp.py`) bridging these Python packages into the MCP tool ecosystem, and that `C:\dnts\pyenv\.venv` is fully configured with Python 3.12.10, PyTorch, OpenVINO, EasyOCR, PyNeuroML, and all required packages.

---

## 3. Caveats

- **Network Execution**: Investigation was executed under CODE_ONLY read-only constraints. Web searches and external API endpoints (OpenAI/Gemini/Jules CLI calls) were not tested live.
- **MCP Server Runtime**: `FastMCP` servers in `scripts/` were inspected statically; live process startup of `dnts-brain.exe` or `dnts-rlm` was not executed during this read-only pass.

---

## 4. Conclusion

The repository structure across `rlm-mit`, `open-deep-research`, `dnts_core`, and `scripts` forms a complete foundation for R1 (Native Subagents & GitHub Wrappers Bridge):
- `open_deep_research.deep_researcher` handles `open_deep_researcher` tasks.
- `rlm.core.rlm.RLM` handles `rlm_code_engineer` tasks in LocalREPL with cognitive reflection and SEAL Hebbian compilation.
- `dnts_core.evolution.jules_verifier.JulesCloudEscalator` handles `verifier_worker` / Jules verification.
- `dnts_core.git_provenance.GitProvenanceManager` guarantees source tracking across Git branches.
- `dnts_core.unified_graph.unified_graph` serves as the primary entrypoint for SuperGraph task routing.

---

## 5. Verification Method

To independently verify these findings:
1. **Inspect package configuration**:
   - `C:\dnts\pyenv\rlm-mit\pyproject.toml`
   - `C:\dnts\pyenv\open-deep-research\pyproject.toml`
   - `C:\dnts\pyenv\.venv\pyvenv.cfg`
2. **Inspect SuperGraph entrypoints**:
   - `C:\dnts\pyenv\dnts_core\unified_graph.py`
   - `C:\dnts\pyenv\dnts_core\subagents\roles.py`
   - `C:\dnts\pyenv\dnts_core\workers\rlm.py`
   - `C:\dnts\pyenv\dnts_core\evolution\jules_verifier.py`
3. **Verify `.venv` site-packages**:
   - Check directory existence of `C:\dnts\pyenv\.venv\Lib\site-packages\torch`
   - Check directory existence of `C:\dnts\pyenv\.venv\Lib\site-packages\openvino`
   - Check directory existence of `C:\dnts\pyenv\.venv\Lib\site-packages\easyocr`
   - Check directory existence of `C:\dnts\pyenv\.venv\Lib\site-packages\pyneuroml`
