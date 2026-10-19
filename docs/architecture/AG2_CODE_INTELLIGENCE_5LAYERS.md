# Полный контроль структур кода — архитектура из 5 слоёв

> План для обсуждения с Antigravity 2 (AG2). Версия 1.0, 2026-08-15.
> Автор: Hermes (Vazus OS). Статус: ПРЕДЛОЖЕНИЕ — не внедрено, требует обсуждения.

## 1. Цель и требования

Нужна система ПОЛНОГО КОНТРОЛЯ структур кода в C:\vazus:

1. Анализировать систему: вызовы файлов и функций, полный граф структуры.
2. Сравнивать варианты вызовов и ИЗМЕНЯТЬ их так, чтобы система не ломалась.
3. Нативно находить улучшения и очистку кода ПО ПАТТЕРНАМ ИСПОЛНЕНИЯ
   (не только статически, но и по факту того, что реально вызывается).
4. Скорость вторична: готовы на долгие операции, если они полные и
   безопасные (worktree → тесты → гейты → коммит).
5. Всё локально (privacy-first), Windows 11.

Диагноз текущего: CKB (SimplyLiz/ckb v9.3.0, 109★, Go, npm @tastehub/ckb)
даёт только слой 1 (SCIP-символы: searchSymbols, findReferences, analyzeImpact)
и частично слой 4 (impact). Чего НЕТ: полноценного графа с обходами
(«кто вызывает X и что вызывает X» по BFS), динамики исполнения, нативного
поиска улучшений/очистки по паттернам. Плюс известные баги: getStatus
висит >60s (health всех бэкендов SCIP/LSP/Git на холодном старте),
getHotspots до 300s (по сути git churn за 30 дней — internal/query/navigation.go).
Лицензия CKB — Fair Use (не MIT), что ограничивает использование.

## 2. Архитектура: 5 слоёв

### Слой 1 — Граф структуры и вызовов (КОНТРОЛЬ)
Назначение: полный граф «файл → функции → вызовы», поиск символов, ссылок,
impact-анализ, обходы графа.

Инструмент (рекомендуется): codebase-memory-mcp (cbm) v0.10.5
- DeusData/codebase-memory-mcp, 39 079★, ядро на C, лицензия MIT, активен
  (релиз v0.10.5 — 15.08.2026, свежий каждый день)
- Нативный бинарь Windows amd64 (~39MB), без рантаймов и Docker
- 158 языков через tree-sitter; индексация среднего репо — миллисекунды,
  Linux kernel (28M LOC, 75K файлов) — 3 минуты; запросы <1ms
- Инструменты MCP: index_repository (с auto-sync watcher), search_graph,
  trace_path — BFS «кто вызывает / что вызывается» (глубина 1-5),
  detect_changes — git diff → затронутые символы + blast radius + класс риска,
  query_graph — openCypher (read-only: MATCH, WHERE, EXISTS — можно писать
  «найди функции без вызовов»), get_code_snippet, get_architecture,
  search_code, manage_adr (ADR), ingest_traces (трассы → рёбра HTTP_CALLS)
- Модель графа: 15 типов узлов (Project, Package, Module, Class, Function,
  Method, Route...), 20 типов рёбер (CALLS, CALL_REFERENCE, IMPORTS,
  HTTP_CALLS, ASYNC_CALLS, IMPLEMENTS, TESTS, FILE_CHANGES_WITH...)
- Privacy: ноль фоновых сетевых запросов; CBM_ALLOWED_ROOT — песочница путей
- Бенчмарки: arXiv 2603.27277 — 83% качество ответов, 10× меньше токенов,
  2.1× меньше вызовов инструментов против пофайлового чтения
- Риск: Defender может пометить бинарь Trojan:Script/Wacatac.B!ml (известный
  false positive, 61/62 антивирусов чисто; та же метка у gh и llama.cpp).
  Обязательна проверка checksums.txt с релиза.

Альтернативы слоя 1:
- CKB (оставить как fallback, лёгкие инструменты работают) — Fair Use
- graphify (Graphify-Labs, 106 927★, Python, Apache-2.0) — но это SKILL для
  Claude/Cursor/Codex/Gemini, не MCP-сервер; интеграция с Hermes слабее
- code-review-graph (tirth8205, 30 312★, Python, MIT) — local-first граф,
  ~65× медианное сокращение токенов, но Python-реализация медленнее нативных
- Собственный supergraph (vazus_core/engine/ast_repo_mapper.py +
  supergraph_linker.py, 768D в vazus.db) — уже есть, но без call-graph BFS

### Слой 2 — Паттерны ИСПОЛНЕНИЯ (динамика)
Назначение: что РЕАЛЬНО вызывается в рантайме, мёртвый код по факту,
горячие пути. Этого нет ни у CKB, ни у cbm из коробки.

Инструменты:
- viztracer (7 721★, Python, pip) — трассировка исполнения: JSON-граф вызовов
  с аргументами, временем, частотами → можно импортировать в граф cbm
  (ingest_traces) или анализировать напрямую
- coverage.py (уже используется в pytest) — мёртвые ветки по факту исполнения
- pyinstrument (8 000★, Python) — стек-профайлер для горячих путей
- cbm ingest_traces — приём готовых трасс в граф (рёбра HTTP_CALLS и т.п.)

Цикл: прогон тестов/демо под трассировкой → список реально исполненных
вызовов → сравнение со статическим графом (слой 1) → кандидаты на очистку.

### Слой 3 — Нативный поиск улучшений и очистки ПО ПАТТЕРНАМ
Назначение: автоматическое нахождение и ПРИМЕНЕНИЕ паттернов очистки
(мёртвый код, unused imports, дублирование, устаревшие API), синтаксически
безопасно (AST, не regex).

Инструменты:
- GritQL (biomejs/gritql, 4 574★, Rust, Apache/MIT) — декларативный язык
  «найди паттерн → перепиши» (grit query + `=>`), 200+ готовых паттернов
  stdlib (включая Python: рефакторинги, миграции API), grit check — свои
  линты, AST-безопасно, языки: Python, JS/TS, JSON, Java, Go, Rust, SQL и др.
- ast-grep (15 539★, Rust) — УЖЕ УСТАНОВЛЕН (@ast-grep в глобальном npm):
  sg run с YAML-правилами + rewrite; быстрый паттерн-матчинг
- semgrep (16 237★) + официальный semgrep/mcp (683★) — правила-паттерны для
  уязвимостей импортов/функций, taint-анализ; сканирование через MCP
- Уже в гейтах vazus: vulture (dead code), ruff F401/F841 (unused imports),
  deptry (лишние зависимости), bandit (security)
- SonarQube MCP (623★) — полный code quality, но тянет Java-сервер (тяжело)

### Слой 4 — Безопасное изменение (НЕ ЛОМАТЬ СИСТЕМУ)
Назначение: любое изменение (из слоя 3 или от AG2) проходит через
верификацию. УЖЕ ЕСТЬ в vazus — сильнее, чем у найденных аналогов:
- precommit_gate: 6 уровней (AST → pytest → SMT Z3 → Concordia Jury ≥66% →
  vulture → ruff) + 6b (deptry/pip-audit/bandit при VAZUS_GATE_DEEP_SCAN=1)
- worktree_sandbox: Job Object + эфемерные ветки, promote только после тестов
- smt_z3_verifier (UNSAT-теоремы, контрпримеры → pytest-фикстуры)
- rollback_guardrail, REPL-песочница (fail-closed)
- Контур «долго, но безопасно»: паттерн (слой 3) → worktree → тесты →
  гейты → jury → promote → коммит

### Слой 5 — Глубокие агентные системы (обзор, НЕ рекомендуется сейчас)
- AutoCodeRover (NUS, SWE-bench) — авторемонт багов; репо ушло из публичного
  доступа, исследовательский уровень
- CodeQL (9 945★) — самый глубокий статический анализ (QL-запросы,
  уязвимости, dead code), но тяжёлая сборка БД и не MCP
- OpenRewrite (3 649★) — массовые рефакторинги, JVM-мир (не Python)
- graphiti (29 970★) — temporal knowledge graph, но для памяти агентов,
  не для кода
- Вывод: для vazus слой 5 = собственный агентный контур (llm_client на agy +
  rlm_code_engineer + reflexion + auto_improver), а не внешние «глубокие» системы

## 3. Рекомендуемая сборка (что поставить)

1. cbm v0.10.5 (замена CKB на слое 1; CKB отключить, не удалять)
   - Скачать codebase-memory-mcp-windows-amd64.zip + checksums.txt с релиза,
     сверить SHA256, распаковать, install.ps1 (или вручную в C:\vazus\bin\)
   - Проверить бинарь: certutil/Get-FileHash сверка с checksums
   - Настроить .mcp.json / Hermes MCP: command + args
   - index_repository C:\vazus → trace_path/search_graph/detect_changes
2. grit (GritQL) — установка (cargo/npm), настроить паттерны Python-очистки
3. viztracer + pyinstrument — pip в C:\vazus\.venv
4. semgrep + semgrep/mcp — pip + MCP-регистрация (или в бриф AG2)
5. Связать с существующим: скрипты в scripts/ для цикла «трасса → граф →
   паттерн → worktree → гейты»

## 4. Рабочий цикл (как слои взаимодействуют)

1. Слой 2: прогон тестов/демо под viztracer + coverage → трасса исполнения
2. Слой 1: cbm граф (trace_path) — кто вызывает, кто вызывается; query_graph
   (Cypher) — функции без CALLS-рёбер, файлы без IMPORTS-потребителей
3. Слой 3: grit/ast-grep/semgrep — паттерны очистки по найденным кандидатам
4. Слой 4: изменения в worktree → pytest → 6 гейтов → jury → promote
5. Повтор: после коммита цикл повторяется (инкрементально, auto-sync cbm)

## 5. Риски и открытые вопросы (для обсуждения с AG2)

1. cbm — закрытый бинарь (C), хоть и MIT: код не читаем. Готовы ли мы
   доверять бинарю? (проверка checksums + отсутствие сети в бинаре)
2. Defender false positive — надо проверить на живой машине до установки.
3. Дублирование: у нас уже есть собственный supergraph (768D) — cbm
   перекрывает его частично. Стоит ли развивать свой или брать cbm?
   (предложение: cbm для call-graph, свой supergraph для семантики/памяти)
4. CKB: оставить fallback'ом или выпилить из MCP-реестра полностью?
5. grit vs ast-grep: оба уже/будут доступны; выбрать основной движок
   очистки (предложение: ast-grep для точечного, grit для массовых
   рефакторингов с stdlib-паттернами).
6. Стоимость: cbm индексация быстрая, но полный цикл с динамикой —
   долгий. Это принято (требование «пусть работает долго, но полно»).
7. Критерии приёмки: trace_path на llm_client.py отвечает <1s; query_graph
   «функции без вызовов» находит реальный мёртвый код; цикл очистки
   одного кандидата проходит гейты без падений тестов.

## 6. Что уже проверено (факты, не гипотезы)

- CKB v9.3.0: getStatus = health SCIP/LSP/Git (internal/query/status.go),
  getHotspots = git churn 30 дней (internal/query/navigation.go:2553) —
  прочитано в исходниках; лицензия Fair Use
- cbm: README + релизы + бенчмарки arXiv; Windows-инсталлятор существует
- grit/ast-grep/semgrep/viztracer: README, звёзды, лицензии (см. выше)
- ЖИВОГО теста на C:\vazus ещё не было — это задача для AG2 (см. бриф
  AG2_CKB_FIX_BRIEF.md, который теперь устарел в части «чинить CKB» —
  приоритет: cbm)
