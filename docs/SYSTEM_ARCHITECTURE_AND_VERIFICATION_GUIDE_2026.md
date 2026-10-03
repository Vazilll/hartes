# 🌌 Полное Руководство по Архитектуре, Верификации и Системам Vazus SuperGraph OS

> **Дата**: Август 2026  
> **Окружение**: Windows 11, Intel CPU+GPU, Python 3.14 (`C:\vazus\.venv`), Go 1.23+, C/C++ Tree-Sitter  
> **База данных и память**: `C:\vazus\services\memory\vazus.db` (SQLite WAL, vec0 768D, FTS5, SuperGraph KG)  
> **Пакет ядра**: `vazus_core` (`C:\vazus\vazus_core`)  

---

## 1. 🏛️ Архитектура Системы Vazus SuperGraph OS

### 1.1 Единый SuperGraph Слой (Two-Layer + 768D Vector Alignment)
```
                      ┌──────────────────────────────────────────────┐
                      │          SuperGraph Alignment Layer          │
                      │  Google Gemini Embedding 2 (768-dim Vectors) │
                      └──────────────┬────────────────┬──────────────┘
                                     │                │
             ┌───────────────────────┴─┐            ┌─┴───────────────────────┐
             ▼                         ▼            ▼                         ▼
   ┌───────────────────┐    ┌────────────────────┐ ┌───────────────────┐   ┌───────────────────┐
   │ Layer A: AST Code │    │ Layer B: Karpathy  │ │ Bi-Temporal Facts │   │ Polyglot CPG Graph│
   │ Topology (SCIP)   │    │ Semantic Wiki KB   │ │ (memory_facts_v2) │   │ Python, Go, C/C++ │
   │ 408,170 узлов     │    │ services/memory/   │ │ valid_at /        │   │ Tree-Sitter AST   │
   │ 548,994 рёбер     │    │ wiki/*.md          │ │ invalid_at        │   │ Skeletons (>75%)  │
   └───────────────────┘    └────────────────────┘ └───────────────────┘   └───────────────────┘
```

### 1.2 Модульная Структура Подсистем (`vazus_core`)

| Подсистема | Путь | Назначение и ключевые компоненты |
|---|---|---|
| **Verification** | `vazus_core/verification/` | `polyglot_verifier.py` (полиглотный шлюз Py/Go/C), `precommit_gate.py` (**11 уровней проверок**), `smt_z3_verifier.py` (SMT Z3 Hoare контракты), `evidence_jury.py` (0-LLM жюри), `critic_jury.py` (Fail-Closed LLM жюри), `ast_pruner.py` (Tree-Sitter сжатие токенов >75%) |
| **Engine** | `vazus_core/engine/` | `subagent_framework.py` (async сабагенты), `reasoning_effort_controller.py` (динамический бюджет рассуждений), `dynamic_skill_dispatcher.py` (инжекция навыков Hermes), `system_discovery_engine.py` (поиск возможностей и чистка) |
| **Workers** | `vazus_core/workers/` | `self_healing_repl.py` (Z3 Angelic Repair $\le 1.4$ iters), `repl_engine.py` (песочница с защитой от циклов), `jules_client.py` (Google Jules Async Worker), `daemon_sidecar.py` |
| **Memory** | `vazus_core/memory/` | `embeddings.py` (768D OpenVINO NPU), `db.py` (SQLite WAL 256MB MMAP), `organic_memory_bridge.py` (связывание Karpathy Wiki), `memory_facts_v2` (bi-temporal facts) |
| **Synthesis & Evolution** | `vazus_core/synthesis/`, `vazus_core/evolution/` | `map_elites_archive.py` (MAP-Elites 2D Pareto-Grid), `darwinian_evolver.py` (генетическая мутация кода) |
| **Missions & Transactions** | `vazus_core/missions/` | `research_obsidian_sync.py` (Zettelkasten + SymPy Proofs), `saga_checkpointer.py` (Undo-лог транзакций), `circuit_breaker.py` |
| **Analysis** | `vazus_core/analysis/` | `reverse_engineer.py` (C/Go память и выравнивание), `pattern_miner.py` (Code Health 0-10), `clone_detector.py` (`jscpd` v5), `proactive_suggestion_engine.py` |
| **Integrations** | `vazus_core/integrations/` | `cognitive_tutor_engine.py` (SM-2 Spaced Repetition + 768D Recall), `mirea_student_manager.py`, `google_super_sync_engine.py`, `tinkoff_finance_manager.py` |
| **Services** | `services/` | `gomcp/` (Go Symbol Interning Pool & SharedMemoryBus), `health_agent/` (BLE Mi Scale 2 Scanner, gRPC), `finance_agent/`, `vision/` |

---

## 2. 🛡️ 11-Tier Система Верификации (`precommit_gate.py`)

Каждая мутация кода обязана пройти 11 независимых уровней верификации:

```
[git commit / code mutation]
    │
    ├─► Gate 1: AST Syntax & Anti-Pattern / Secret Scan (0 API keys, no shell=True, no stubs)
    │
    ├─► Gate 2: Targeted Pytest (AST Import Tracing: точечный запуск всех зависящих тестов)
    │
    ├─► Gate 3: SMT Z3 Formal Contract Proofs (Hoare Logic: @requires/@ensures, SAT = блокировка)
    │
    ├─► Gate 4a: Deterministic EvidenceJury (0-LLM: математический вердикт по объективным эвиденциям)
    │     │
    ├─► Gate 4: Critic Jury (Fail-Closed, VAZUS_GATE_JURY_TIMEOUT=120 для нерешённых случаев)
    │
    ├─► Gate 5: Vulture Dead Code Elimination (≥90% confidence, пропуск labs/tests)
    │
    ├─► Gate 6: Fast Static Linting via Ruff (F401 unused imports, F821 undefined names, E9)
    │
    ├─► Gate 7: Strict Mypy Typechecking
    │
    ├─► Gate 8: AST Token-Optimized Signature Extraction (Docstring compression)
    │
    ├─► Gate 10: Radon Cyclomatic Complexity (Строгий инвариант: CC ≤ 10 для всех функций)
    │
    └─► Gate 11: Graph Structural Invariants & Phantom Import Detector (CPG / The Patchwork Problem)
```

---

## 3. 🌐 Полиглотная Верификация: Python, Go, C/C++ (`polyglot_verifier.py`)

| Параметр | Python (`.py`, `.pyi`) | Golang (`.go`) | C / C++ (`.c`, `.cpp`, `.h`, `.hpp`) |
|---|---|---|---|
| **Движок парсинга** | Python `ast` + SMT Z3 | Tree-Sitter (`tree_sitter_go`) | Tree-Sitter (`tree_sitter_c`) |
| **AST Прунинг** | `DocstringAndBodyPruner` | `GoTreeSitterPruner` | `CTreeSitterPruner` |
| **Заглушка тела** | `...` (Ellipsis) | `panic("skeleton")` | `/* ... */` |
| **Стандарт качества** | Code Health $\ge 9.5$ | Code Health $\ge 9.5$ | Code Health $\ge 9.5$ |
| **Лимит сложности** | McCabe $CC \le 10$ | Ветвления $CC \le 15$ | Ветвления $CC \le 20$ |

---

## 4. 🤖 Матрица Субагентов и Мостов

1. **`teamwork_preview` (Autonomous Mission Architect)**: 4-стадийная координация по протоколу консенсуса Кондорсе ($\ge 66\%$).
2. **`verifier_worker` (Google Jules Verifier)**: Автономный аудит синтаксиса, цикломатической сложности, SMT Z3 контрактов и фиксация в Git Provenance (`scripts/subagent_verifier_bridge.py`).
3. **`open_deep_researcher`**: Мульти-агентный веб-поиск и синтез через Google NotebookLM MCP (`gemini-notebook-mcp` / `nlm CLI`).
4. **`rlm_code_engineer`**: Рекурсивный исполнитель кода с локальным изолированным самоисцелением (`vazus_core/workers/rlm.py`).

---

## 5. 🧪 Тестовая Инфраструктура (984 Теста, 100% Успех, 0 Ошибок)

- **Полный прогон pytest**: 984 пройденных теста в 104 файлах (Unit, Integration, Benchmarks, E2E).
- `tests/test_foundations_2026.py` (18 тестов SOTA-модулей 2026)
- `tests/test_invariants_pbt.py` (12 PBT тестов на инварианты Хоара и AST)
- `tests/test_gate_invariants_pbt.py` (36 тестов безопасности, секретов и гейтов)
- `tests/test_advanced_patterns_sota.py` (13 тестов: Stateful, Metamorphic, Mutation)
- `tests/test_graph_invariants_sota.py` (8 тестов Gate 11 CPG Invariants)
- `tests/test_polyglot_verifier.py` (5 тестов полиглотного шлюза Py, Go, C)
- `tests/integration/test_e2e_requirements.py` (Сквозные тесты R1-R4)
