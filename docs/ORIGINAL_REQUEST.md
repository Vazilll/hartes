# Original User Request

## Initial Request — 2026-09-04T02:24:31Z

Комплексный рефрейминг и глубокий рефакторинг архитектуры Vazus OS: формализация парадигмы самообучающегося суперорганизма в Obsidian Wiki и сквозная оптимизация кодовой базы (замыкание контуров Eval Quality Flywheel, устранение деградации ОЗУ/индексации, ликвидация регрессий в SPEC.md и 100% прохождение гейтов верификации).

Key Requirements:
R1. Концептуальный рефрейминг в Obsidian Wiki:
- Создать и интегрировать в SuperGraph иерархическое дерево заметок в C:\vazus\services\memory\semantic\wiki\ с валидным YAML-frontmatter и двусторонними ссылками [[wikilinks]].
- Темы: Eval Quality Flywheel, метрики авто-судей (LLM-as-a-Judge, Trajectory Quality, Tool Use Quality), семантическая кластеризация потерь и таксономия ошибок, 3-уровневая модель оптимизации (Prompt Auto-Tuning, Dynamic Few-Shot In-Context DPO, SFT/LoRA), арбитраж и защита от регрессий (AutoSxS, Concordia Jury).
- Интегрировать граф смыслов с SuperGraph OS через векторные узлы (без dangling references).

R2. Ликвидация утечки ОЗУ и защита от мультиплексирования процессов индексации:
- Оптимизировать C:\vazus\pyrightconfig.json, исключив тяжелые сторонние библиотеки (services/inference/llama.cpp/**, tests/**, tools/**, scratch/**), сократив число индексируемых файлов с 1 154 до ~150.
- Внедрить Concurrency Mutex / Lock (.ckb/indexing.lock) и системную проверку активных процессов в C:\vazus\vazus_core\maintenance\auto_index_runner.py, запрещающую запуск параллельных копий ckb index / scip-python.
- Изолировать вызов SCIP-индексации от микро-хука C:\vazus\vazus_core\hooks\post_tool_hook.py, чтобы редактирование отдельных файлов не запускало компиляцию глобального индекса.
- Гарантировать: время полной фоновой индексации ckb index <= 30 с; не более 1 одновременного процесса scip-python/node.exe; память <= 300 МБ.

R3. Устранение циклической регрессии в генераторе SPEC.md:
- Модифицировать метод generate_spec_markdown в C:\vazus\vazus_core\maintenance\auto_index_runner.py, добавив автогенерацию ключевых разделов (## Mission & Domain Scope, ## Level 1..5 Capability Maturity, ## Known Bottlenecks & Failure Modes).
- Синхронизировать спецификации C:\vazus\vazus_core\engine\SPEC.md, C:\vazus\vazus_core\memory\SPEC.md и C:\vazus\vazus_core\hooks\SPEC.md.
- Гарантировать прохождение теста tests/test_skill_tree_system_e2e.py::TestTier1FeatureCoverage::test_r2_domain_spec_contracts_structure_and_criteria (100% PASSED).

R4. Программное замыкание контуров обратной связи (Feedback Loops):
- Обеспечить трансформацию детекции ошибок из тестов и рантайма в структурированные уроки памяти (reflexion_lessons / mem0_facts).
- Сквозной набор тестов pytest tests/ должен выполняться без ошибок и регрессий.

Orchestrator Protocol:
- Maintain plan.md, progress.md, context.md in C:\vazus\.agents\orchestrator_1.
- Update progress.md regularly with milestones and mtime.
- Dispatch subagents as needed for parallel audit, implementation, and verification.
- When all acceptance criteria are met and verified, report completion to the Sentinel.

## 2026-09-04T10:31:55Z — Lead Architect Notice

[Lead Architect Notice to teamwork_preview]:
The canonical database SHA-256 updated to `4a7d1cef7106bb8a81c64d7aa7881051fe2ca1ee75391d973e4134b5dc2fa967` because the user explicitly mandated recording the MIREA pedagogical tutoring policy (`fact_1788515403046` in mem0_facts and `insight_8ec4ba8754c09169` in organic_insights) into vazus.db during this session, followed by a clean WAL checkpoint + VACUUM.
The `EXPECTED_SHA256` constant in `tests/benchmarks/test_challenger_final_3_adversarial.py` should be updated to `4a7d1cef7106bb8a81c64d7aa7881051fe2ca1ee75391d973e4134b5dc2fa967` as the new verified baseline. All 48 tables and user data remain 100% intact with zero AST bloat.

## Follow-up — 2026-09-04T13:27:22Z

# Teamwork Project Prompt

> Status: Launched
> Goal: Execute 3-stage architectural evolution with zero-stub proven mechanisms
> Requested team: Полномасштабная команда агентов (SMT formal verifiers, engine engineers, test auditors)

Комплексная реализация и интеграция 8 доказанных математических механизмов верификации, оптимизации и непрерывного самоулучшения (AlphaProof SMT Gate, Self-Anchored Consensus, O(1) RES Runtime, OmegaPRM MCTS, Hardened Sandbox, FunSearch) в архитектуру Vazus SuperGraph OS v5.2 с абсолютным запретом на упрощения и заглушки.

Working directory: C:\vazus
Integrity mode: development

## 🔒 Ключевой Инвариант: Только Доказанные Механизмы (Zero-Stub Invariant)
Запрещены любые заглушки (stubs), симуляции, моки (mocks) или упрощенные эвристики вместо реальных алгоритмов:
1. **SMT Z3**: Реальное решение систем ограничений в Z3 C-API / Python API с генерацией и валидацией доказательств выполнимости (SAT) и невыполнимости (UNSAT) с вычислением Minimal Unsatisfiable Cores (MUC).
2. **SAC (Self-Anchored Consensus)**: Честная $(F+1)$-робастная топология графа и Receiver-Side перекрестная оценка, а не доверие к самооценке отправителя.
3. **RES Runtime**: Честное разделение $\mathcal{O}(1)$ контекста: Reasoner $\to$ детерминированный Executor $\to$ Synthesizer с Ephemeral Reasoning Ejection.
4. **Эволюция кода**: Честный дисковый оверлей в `darwinian_evolver.py` с гарантированным прогоном `pytest` над реальным измененным байт-кодом мутанта.

---

## Requirements

### R1. Детерминированная Песочница, Устранение Бага в `darwinian_evolver.py` и SMT-Шлюз
- **R1.1. Изоляция мутаций в `darwinian_evolver.py`**: Устранить дефект строк 214–219. Записывать `mutated_code` в изолированный виртуальный каталог (`tmp_path`) с подменой `PYTHONPATH` перед вызовом `evaluate_variant_pytest()`. Доказать тестом, что `pytest` фиксирует результат исполнения именно мутированного кода, а не базового репозитория.
- **R1.2. Аппаратный контроллер Windows Sandbox (`wsb.exe`)**: Реализовать программный контроллер сессий `wsb_sandbox_controller.py` с принудительными директивами: `<ProtectedClient>Enable</ProtectedClient>`, полным физическим отключением сети `<Networking>Disable</Networking>` (защита от APT-эксфильтрации) и Read-Only кэшем зависимостей `pip`.
- **R1.3. Шлюз безопасности `substrate-guard` (SMT Z3 Hard Gate)**: Реализовать модуль `vazus_core/verification/substrate_guard.py`. Все аргументы инструментов субагентов строго типизировать (Pydantic) и транслировать в предикаты SMT-LIB2. Время проверки $\le 2$ мс. При нарушении инварианта генерировать Minimal Unsatisfiable Core (MUC) для детерминированной одношаговой коррекции.

### R2. Инвариантный Рантайн $O(1)$ Состояний и Робастный Консенсус SAC
- **R2.1. Рантайн $O(1)$ SKILL.state & Паттерн Reasoner-Executor-Synthesizer (RES)**: Реализовать `vazus_core/engine/skill_state_runtime.py`. Изолировать контекст LLM от сырых записей базы данных и дампов AST: детерминированный исполнитель агрегирует выборку в срез фиксированного размера $\le 1500$ токенов. После фиксации дельты $\Delta \Sigma_t$ производить Ephemeral Reasoning Ejection (стирание CoT), исключая квадратичный рост затрат токенов.
- **R2.2. Self-Anchored Consensus (SAC) для Concordia Jury**: Модифицировать `vazus_core/verification/concordia_jury.py`. Устранить зависимость от заявленной уверенности отправителя. Внедрить Receiver-Side Evaluation в $(F+1)$-робастном графе с MSR-фильтрацией выбросов, гарантирующей устойчивость к византийским и галлюцинирующим агентам.
- **R2.3. Символический интерфейс AMTFV (Tool-Flow Verification)**: Реализовать интерфейс `<tool_flow>` для математических и логических преобразований, передающий символические вычисления в SymPy и Z3 вместо генерации монолитных хрупких скриптов проверки.

### R3. Пошаговая Модель Наград (OmegaPRM) и Авто-Формализация
- **R3.1. Инлайн Process Reward Model (OmegaPRM) в MCTS (Test-Time Compute)**: Интегрировать в `vazus_core/engine/reasoning_effort_controller.py` пошаговый скорер веток рассуждений. В режиме высокого усилия (`xhigh`/`ultra`) дерево MCTS оценивает каждый шаг $r_t \in [0, 1]$ и отсекает ветви с $r_t < 0.6$ до обращения к внешним инструментам или компилятору.
- **R3.2. Авто-формализатор AlphaProof / Google CEL**: Реализовать `vazus_core/compiler/auto_formalizer.py` для автоматической трансляции бизнес-требований и спецификаций в формальные леммы Z3 и предикаты Google CEL.
- **R3.3. Островная модель популяций FunSearch**: Расширить генетический движок поддержкой независимых популяционных островов с периодической миграцией элитных особей.

---

## Acceptance Criteria

### Security & Formal Verification (SMT & SAC)
- [ ] Все операции модификации файлов и выполнения системных команд валидируются через `substrate_guard` за $\le 5$ мс с гарантией Fail-Closed.
- [ ] При попытке выхода за пределы jail-периметра Z3 вычисляет и возвращает корректный MUC.
- [ ] При инжекции византийского агента с фиктивной максимальной уверенностью 1.0 протокол SAC сохраняет $\ge 90\%$ честный консенсус (в отличие от старого CP-WBFT).

### Runtime Performance & Context Invariance
- [ ] Расход токенов в многошаговых сессиях с RES-рантаймом инвариантен к размеру выборки БД ($\mathcal{O}(1)$, плотность $\le 2000$ токенов на шаг).
- [ ] Эволюционный цикл `darwinian_evolver.py` подтвержден тестом: мутированный код изолируется в `tmp_path`, а `pytest` фиксирует реальные изменения покрытия/результатов мутанта.

### Repository Health & Stability
- [ ] 100% прохождение сквозного набора тестов репозитория (`pytest tests/`).
- [ ] Нулевая деградация существующего SuperGraph (873 узла, 1 890 связей, 0 dangling edges).
- [ ] Полное соответствие инвариантам формальной логики Челпанова и Zero-Artifact Protocol (0 временных файлов на диске после завершения).

## 2026-09-20T14:02:32Z

<USER_REQUEST>
An automated, fail-closed academic verification and synchronization engine for Vazus OS that binds student profile, academic debts, live schedules, and Moodle tests to authoritative university endpoints (LKS SSO, Moodle LMS, schedule-of.mirea.ru).

Working directory: C:\vazus\services\academic_verification
Integrity mode: development

## Requirements

### R1. Authoritative Identity & Debt Synchronization
Implement a single-source-of-truth sync pipeline that authenticates against `lk.mirea.ru` via Keycloak SSO session and pulls the verified student profile (Жуков Максим Дмитриевич, `ИВБО-22-25`, личный номер `25И0566`, направление `09.03.01`) and the 18 active academic debts with their official Stage 1 deadline (15.10.2026).

### R2. Official Live Schedule Ingestion (schedule-of.mirea.ru)
Integrate the official RTU MIREA schedule API (`https://schedule-of.mirea.ru/schedule/api/ical/1/5528?includeMeta=true` and `api/baseinfo?id=5528`), replacing all legacy/defunct scrapers (`api.mirea.ninja`). Sync parsed lectures, labs, and classrooms into `vazus.db` (`mirea_schedule`).

### R3. Moodle LMS Course & Test Discovery (Read-Only)
Query `online-edu.mirea.ru` using authenticated Moodle 4 AJAX API (`core_course_get_enrolled_courses_by_timeline_classification`) to resolve real course IDs (e.g. 16479, 16480, 16486, 16017) instead of examination sheet numbers, and extract available quiz/test links.

### R4. Read-Only Safety Guardrail (Strict Invariant)
Under no circumstances may the system submit answers, complete quizzes, or upload files to the user's remote MIREA account without explicit, interactive confirmation. All operations against university servers must remain strictly read-only and exploratory.

### R5. Dead Code & Stub Scrubber
Purge all hardcoded `ИКБО-01-23` fallback constants and dummy schedules across `vazus_core/integrations/mirea_student_manager.py` and test suites, enforcing fail-closed behavior when session tokens are absent.

## Acceptance Criteria

### Automated Verification
- [ ] Pytest integration suite (`tests/test_academic_truth_engine.py`) executes and passes with 100% success.
- [ ] Zero instances of hardcoded `ИКБО-01-23` or `api.mirea.ninja` remain in active `vazus_core` code (verified via ripgrep).
- [ ] Validated local SQLite storage: `mirea_milestones` and `mirea_schedule` in `vazus.db` contain verified `ИВБО-22-25` records.
- [ ] Read-only invariant: Unit tests assert that no HTTP POST mutating remote course submissions or file uploads can execute without explicit override flags.
</USER_REQUEST>
