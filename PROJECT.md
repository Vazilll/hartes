# Project: Vazus OS Core Engine SOTA Upgrade

## Architecture
Vazus OS Core Engine (`vazus_core`) architecture refactoring upgrade.
Four primary sub-systems:
1. `asyncio`-Native Core Architecture: Non-blocking async runtime loop, subagent framework with `asyncio.timeout(300)` guards, async reasoning pipeline (`execute_pipeline`), async auto improver (`improve`), async model selector, and async hooks.
2. LLM-Powered Reflexion Loop & Real Concordia Jury: Replace stub `_ast_fix_fn` with async `_llm_fix_fn` querying Gemini 3.6 Flash with error critiques & failure lessons. Upgrade Concordia jury to execute 3 real independent LLM evaluation calls in parallel via `asyncio.gather` (Planner, RLM_Coder, Verifier_Worker) enforcing >=66% consensus.
3. 768-Dim Vector Embeddings Wiring & Cosine Lesson Retrieval: Wire `vazus_core/embeddings.py` directly into `LessonMemoryBank` in `auto_improver.py`. Schema migration (`embedding_json TEXT`), 768D vector generation on `save_lesson`, top-k cosine similarity retrieval in `retrieve_relevant`.
4. SOTA Resilience & Optimization Engine (R5): Deep component interaction auditing across 5 sequential auditing waves, verifying zero over-simplified stubs and testing real inter-module interactions under high concurrency and failure injection.

## Web Intelligence & Antigravity Compliance Protocol
Every milestone must incorporate a Web Intelligence & Antigravity Compliance audit step:
1. **Web Research & SOTA Benchmarking**: Search for existing high-performance open-source solutions, libraries, or patterns before custom code implementation. Adopt superior design patterns and PyPI/GitHub libraries where beneficial.
2. **Antigravity Rule & Plugin Alignment**: Audit every architectural decision against official Google Antigravity standards (plugin schema, hooks.json, MCP server specs, skill standards) ensuring 100% compliance without violating Antigravity rules.
3. **Feature Integration**: Integrate pre-existing SOTA solutions rather than rebuilding from scratch when available.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Async Subagent Engine | `run_subagent` async def, async hooks, `asyncio.timeout(300)` guards in `subagent_framework.py` | M1 | R1 |
| 2 | Async Reasoning Pipeline | `execute_pipeline` async def, `asyncio.timeout(300)`, thread-offloaded Z3 solver calls in `unified_reasoning_pipeline.py` | M1 | R1 |
| 3 | Async Auto Improver | `improve` async def, `asyncio.timeout(300)`, async DB helpers in `auto_improver.py` | M1 | R1 |
| 4 | Async Model Selector | `set_agent_configuration_async` and non-blocking file I/O in `model_selector.py` | M1 | R1 |
| 5 | LLM Reflexion Fixer (`_llm_fix_fn`) | Replace `_ast_fix_fn` stub with async `_llm_fix_fn` passing critiques and past lessons to Gemini 3.6 Flash | M2 | R2 |
| 6 | Concordia Real Jury Voting | 3 real parallel LLM evaluation calls (Planner, RLM_Coder, Verifier) via `asyncio.gather` enforcing >=66% consensus | M2 | R2 |
| 7 | Vector Lesson DB Schema | Add `embedding_json TEXT` column auto-migration to `reflexion_lessons` DB in `auto_improver.py` | M3 | R3 |
| 8 | Vector Embedding Generation | Compute 768D embedding vectors on `save_lesson` using `UnifiedEmbeddingManager` | M3 | R3 |
| 9 | Cosine Similarity Retrieval | Replace SQL `LIKE` queries in `retrieve_relevant` with batch top-k cosine similarity search | M3 | R3 |
| 10 | Regression Test Suite & Verification | Ensure 100% test pass rate with zero regressions across `tests/` and new unit tests | M4 | AC |
| 11 | Web Intelligence & Antigravity Audit | Perform web research on SOTA patterns + verify 100% Antigravity rule/plugin alignment per milestone | M1, M2, M3, M4, M5 | User Directive |
| 12 | SOTA Resilience & Optimization Engine (R5) | Deep component interaction auditing (5 waves), zero over-simplified stubs, real inter-module resilience | M5 | Directive R5 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: asyncio-Native Core Architecture | `subagent_framework.py`, `unified_reasoning_pipeline.py`, `auto_improver.py`, `model_selector.py` async refactoring, timeout guards & Web/Antigravity audit | none | DONE (45/45 core tests, CLEAN audit) |
| 2 | M2: LLM Reflexion Loop & Real Concordia Jury | `_llm_fix_fn` async LLM repair function, parallel 3-subagent Concordia jury evaluation via `asyncio.gather()`, & Web/Antigravity audit | M1 | DONE (33/33 tests, CLEAN audit) |
| 3 | M3: Vector Embeddings Wiring & Cosine Retrieval | `LessonMemoryBank` DB schema migration, 768D vector embedding on save, batch cosine similarity retrieval, & Web/Antigravity audit | M1 | DONE (24/24 tests, CLEAN audit) |
| 4 | M4: Final Verification & Test Suite Integration | Full unit & integration testing, zero regressions (693/693 passed), AST validation, & Web/Antigravity audit | M1, M2, M3 | DONE (693/693 passed, CLEAN) |
| 5 | M5: SOTA Resilience & Memory Governance | 5-Tier Pre-Commit Gate (AST, Pytest, Z3, Jury, Vulture), memory_facts_v2 Bi-Temporal Governance, Hermes MCP native integration | M1, M2, M3, M4 | DONE (CLEAN 5-Tier Gate) |

## Interface Contracts
### Subagent Framework ↔ Auto Improver
- `auto_improver_on_complete_hook(ctx: SubagentContext) -> None`: async function invoking `await improver.improve(...)` with `fix_fn=_llm_fix_fn`.
- `_llm_fix_fn(code: str, critique: str, lessons: List[str], task_description: str = "") -> str`: async function returning repaired code string.

### Unified Reasoning Pipeline ↔ Concordia Jury
- `ConcordiaJury.evaluate_code_proposal_async(file_path: str, code_content: str, agent_votes: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]`: async method returning jury verdict dict with `consensus_ratio`, `approved`, `votes`.

### Auto Improver ↔ Embeddings Manager
- `LessonMemoryBank.save_lesson(task_type: str, error_sig: str, lesson_text: str, fix_hint: str) -> str`: computes 768D embedding `vec = UnifiedEmbeddingManager().get_embedding(...)` and stores `json.dumps(vec)` in `embedding_json`.
- `LessonMemoryBank.retrieve_relevant(error_sig: str, task_type: str = "", top_k: int = 3) -> List[Dict[str, Any]]`: computes query embedding `query_vec`, fetches candidates, calculates batch cosine similarity via `UnifiedEmbeddingManager().compute_batch_similarity(...)`, returns top-k.

## Code Layout
- `vazus_core/subagent_framework.py`: Subagent framework, template registry, hook registry, declarative engine.
- `vazus_core/unified_reasoning_pipeline.py`: Unified 4-phase reasoning pipeline, AST pruning, SMT Z3 contract verification, Concordia jury.
- `vazus_core/auto_improver.py`: Reflexion evaluator, skill usage tracker, lesson memory bank, auto improver session.
- `vazus_core/model_selector.py`: Model selector, effort level controller, settings persistence.
- `vazus_core/concordia_jury.py`: Concordia multi-agent jury quorum evaluator.
- `vazus_core/llm_client.py`: Async LLM generation wrapper with test mock fallback support.
- `vazus_core/embeddings.py`: 768-dim vector embedding engine (OpenVINO NPU, Google GenAI, SHA256 fallback, AVX-512 & NumPy cosine similarity).
