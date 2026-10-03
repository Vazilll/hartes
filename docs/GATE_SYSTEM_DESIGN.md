# GATE_SYSTEM_DESIGN — Система проверок и анализа кода Vazus (11-Tier Precommit Pipeline & Polyglot Engine)

> Дата: 18.08.2026. Источники: `vazus_core/verification/precommit_gate.py`, `polyglot_verifier.py`, `evidence_jury.py`, `critic_jury.py`, `smt_z3_verifier.py`, `ast_pruner.py`.

---

## 1. АРХИТЕКТУРА 5 СЛОЁВ CODE INTELLIGENCE (L1–L5)

| Слой | Назначение | Реализация в Vazus | Статус |
|---|---|---|---|
| **L1** Граф структуры/вызовов | Контроль графа зависимостей, call-graph, blast radius, CPG инварианты | `CKB` + `PolyglotVerificationService` + `Gate 11 Graph Invariants` | ✅ SOTA 2026 |
| **L2** Паттерны исполнения | Трассировка вызовов, hotspot profiling, сбор телеметрии | `sys.monitoring` (PEP 669) + `pyinstrument` + `vazus.db.telemetry_call_edges` | ✅ Работает |
| **L3** Паттерны очистки | Поиск и применение AST-трансформаций, Tree-Sitter прунинг | `FastMCP code-quality` (`ast-grep`, `grit`, `ruff --fix`, `semgrep`, Tree-Sitter) | ✅ Работает |
| **L4** Безопасное изменение | 11-уровневый pre-commit гейт, SMT Z3 инварианты, Jury консенсус | `precommit_gate.py` + `smt_z3_verifier.py` + `evidence_jury.py` + Jules Worker | ✅ SOTA 2026 |
| **L5** Самообучающиеся системы | Авторемонт, рефлексия, память уроков, Karpathy Wiki | `llm_client` + `rlm_code_engineer` + `auto_improver.py` (768D) + `NotebookLM RAG` | ✅ Работает |

---

## 2. 11-УРОВНЕВАЯ СИСТЕМА ПРЕКОММИТ-ГЕЙТОВ (precommit_gate.py)

| # | Гейт | Что делает | Когда БЛОКИРУЕТ | Переменные / Параметры |
|---|---|---|---|---|
| **1** | **AST + Security** | `ast.parse()` всех staged файлов; скан API-ключей; запрет `os.system()` / `shell=True`; anti-reward-hacking (пустые `pass`, `assert True`) | Синтаксическая ошибка, секрет, опасный syscall, фейковый тест | Всегда активен |
| **2** | **Targeted Pytest** | Целевой запуск тестов: exact match + **AST-импорты** (тесты, реально импортирующие staged-модуль) | Падение хотя бы одного теста | `VAZUS_GATE_TEST_TIMEOUT` (300с), `VAZUS_GATE_MAX_TARGET_TESTS` (8) |
| **3** | **SMT Z3 Contracts** | Формальная верификация инвариантов (@requires/@ensures), depth=10 | **Только SAT** (доказанное нарушение инварианта) | `VAZUS_GATE_STRICT_SMT` (0/1) |
| **4a** | **EvidenceJury (0 LLM)** | Детерминированное жюри: AST, security, ruff, vulture, SMT, targeted tests | FAIL по объективным эвиденциям; UNVERIFIED переходят в Gate 4 | Всегда активен |
| **4** | **Critic Jury (LLM Batch)** | LLM-жюри для UNVERIFIED файлов: 1 раунд, fail-closed | Неодобрение, таймаут, абстенция | `VAZUS_GATE_JURY_TIMEOUT` (120с), `VAZUS_GATE_STRICT_JURY` (0/1) |
| **5** | **Dead Code (Vulture)** | Обнаружение мертвого кода с доверием ≥90% | Мертвый код в own codebase (skip labs/tests/scratch) | Всегда активен |
| **6** | **Fast Lint (Ruff)** | Проверка F401 (unused imports), **F821 (undefined names)**, F841, E9 | Ошибки линтера | Всегда активен |
| **7** | **Static Type (mypy)** | `mypy --python-version 3.11 --ignore-missing-imports` | Ошибки типов (при строгом режиме) | `VAZUS_GATE_MYPY=1` |
| **8** | **AST Signature Pruning** | Сжатие токенов (>75%) с сохранением сигнатур и docstrings | Синтаксическая невалидность скелета | Всегда активен |
| **10** | **Radon Complexity (CC $\le 10$)** | Ограничение цикломатической сложности функций по Маккейбу | Любая функция с $CC > 10$ | Всегда активен |
| **11** | **Graph Invariants & Phantom Imports** | Проверка реэкспортов символов и графа вызовов (The Patchwork Problem) | Несуществующий импортируемый символ/модуль | Всегда активен |

---

## 3. ПОЛИГЛОТНЫЙ ДВИЖОК ВЕРИФИКАЦИИ (polyglot_verifier.py)

Включает специализированные верификаторы:
- **`PythonVerifier`**: `ast`, SMT Z3, McCabe CC, Code Health $\ge 9.5$.
- **`GoVerifier`**: `tree_sitter_go`, парсинг пакетов, структур, интерфейсов, подсчет ветвлений, генерация скелетов `panic("skeleton")`.
- **`CVerifier`**: `tree_sitter_c`, парсинг заголовков, структур, typedefs, прототипов, генерация скелетов `/* ... */`.