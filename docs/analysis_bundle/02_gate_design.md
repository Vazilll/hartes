# GATE_SYSTEM_DESIGN — Система проверок и анализа кода Vazus (as-built vs intent)

> Дата: 17.08.2026. Источники: precommit_gate.py (житвой код), AG2_CODE_INTELLIGENCE_5LAYERS.md
> (ПРЕДЛОЖЕНИЕ 15.08 — что задумывали), evidence_jury/dual_jury/critic_jury (код), сессия 14.08 (аудит V-1..V-7).
> Согласование с AG2: архитектурные правки — в рамках существующего контура «долго, но полно».

---

## 1. КАК ЗАДУМЫВАЛИ (5 слоёв, AG2_CODE_INTELLIGENCE_5LAYERS.md, 15.08)

| Слой | Назначение | Рекомендованный инструмент | Статус 17.08 |
|---|---|---|---|
| **L1** Граф структуры/вызовов | полный контроль «кто вызывает / кого вызывают», impact, BFS | **cbm v0.10.5** (DeusData, MIT, tree-sitter 158 языков, search_graph/trace_path/query_graph/detect_changes/ingest_traces) | ❌ НЕ внедрено. CKB = частично (ТОЛЬКО символы, без BFS; Fair Use; getStatus висит) |
| **L2** Паттерны ИСПОЛНЕНИЯ | что реально вызывается, мёртвый код по факту, горячие пути | viztracer + pyinstrument + coverage, cbm ingest_traces | ❌ НЕ внедрено (только coverage внутри pytest) |
| **L3** Паттерны очистки | находить и применять очистку AST-безопасно | GritQL (grit), **ast-grep (уже стоит)**, semgrep (+MCP) | 🔶 Частично: ast-grep стоит; grit/semgrep нет; vulture/ruff/deptry/bandit УЖЕ в гейте |
| **L4** Безопасное изменение | worktree → тесты → гейты → jury → promote | собственный precommit_gate + worktree_sandbox (Job Object) + SMT Z3 + rebase | ✅ ЕСТЬ, сегодня усилен (см. §2-3) |
| **L5** Глубокие агентные системы | авторемонт/рефлексия | собственный контур: agy + rlm_code_engineer + reflexion + auto_improver | ✅ ЕСТЬ |

Главный вывод intent-документа: **L4 было сильнее аналогов уже тогда**; пробелы — L1 (call-graph BFS) и L2 (динамика). Приоритет обсуждения с AG2: cbm (закрытый C-бинарь, MIT, Defender-FP, дублирование своего supergraph) — внедрять поэтапно после проверки.

---

## 2. СЛОИ ПРОВЕРКИ ПЕРЕД GIT — КАК ЕСТЬ (6-tier precommit_gate, живой код)

| # | Гейт | Что делает | Когда БЛОКИРУЕТ | Параметры (env) |
|---|---|---|---|---|
| 1 | AST + Security | ast.parse всех staged .py; regex секретов (AIzaSy/sk-); AST-скан os.system, shell=True; Reward-Hacking-гвард в тестах (пустые `pass`, `assert True`) | ошибка синтаксиса/секрет/опасный вызов/фейковый тест | — (всегда) |
| 2 | Targeted pytest | тесты, покрывающие staged-модули (новый маппер: exact имя + **AST-импорты**) | падение целевых тестов | `VAZUS_GATE_TEST_TIMEOUT` (300), `VAZUS_GATE_MAX_TARGET_TESTS` (8) |
| 3 | SMT Z3 контракты | Hoare-контракты (@requires/@ensures), контрпримеры, depth=10 | **только SAT** = жёсткое доказательство нарушения; ERROR/UNKNOWN = advisory (честная абстенция! не выдаём за нарушение) | `VAZUS_GATE_STRICT_SMT` (0) |
| 4 | Critic-Jury (LLM, BATCH) | туда идут только UNVERIFIED после 4a; батчем = 2 LLM-вызова на все файлы; fail-closed: ABSTAIN/mock ≠ одобрение, любой CONTRADICT = reject | неодобрение/абстенция по UNVERIFIED | `VAZUS_GATE_STRICT_JURY` (0 — при отсутствии жюри не блокирует с предупреждением) |
| 4a | EvidenceJury (0 LLM) | pass1 быстрые эвиденции (AST/security/ruff/vulture/SMT), pass2 — целевые тесты для UNVERIFIED; только оставшиеся UNVERIFIED идут в LLM | fail по твёрдым эвиденциям | — |
| 5 | Vulture | мёртвый код | только ≥90% confidence; skip labs/tests/inference/scratch | — |
| 6 | Ruff | F401/F841/E9 | да | — |
| 6b | Deep scan (opt-in) | deptry + pip-audit (CVE) + bandit | advisory, блок при `VAZUS_GATE_STRICT_DEEP=1` | `VAZUS_GATE_DEEP_SCAN`, `VAZUS_GATE_STRICT_DEEP` |

LLM-слой гейта теперь ходит через Tier-0 адаптера :5001 (agy IDE-квоты) — `VAZUS_LLM_ADAPTER_URL`, `VAZUS_LLM_SKIP_ADAPTER`, `VAZUS_LLM_MAX_TOKENS`.

---

## 3. ДОКРУЧЕНО СЕГОДНЯ (17.08, вечер — параметры и покрытие)

1. `find_targeted_tests` — НОВЫЙ маппер: exact-имя + **AST-анализ импортов** (тесты, реально импортирующие staged-модуль: `from pkg.mod import x` / `import pkg.mod` / `from pkg import mod`). Эффект: тестов на staged-набор выросло с 1 до 7 → меньше UNVERIFIED → меньше LLM-эскалаций, гейт быстрее и детерминированнее. Кэп: `VAZUS_GATE_MAX_TARGET_TESTS`.
2. Таймаут целевых тестов — через `VAZUS_GATE_TEST_TIMEOUT`; subprocess с utf-8/errors=replace (кириллица).
3. llm_client Tier-0 = адаптер :5001 (изменил источник 429 на рабочие IDE-квоты).
4. Закрыты 2 дефекта из LLM-критики: Z3 Bool/Int sort-mismatch (safety_guardrail), detach-HEAD (git_provenance.revert).

---

## 4. ОПТИМАЛЬНЫЕ ПАТТЕРНЫ АНАЛИЗА КОДА (наше решение, обоснованное практикой)

1. **Evidence-first, дешёвое-достаточное**: сначала 0-LLM детерминированные проверки (AST, static, целевые тесты), LLM — ТОЛЬКО для действительно UNVERIFIED, причём БАТЧОМ (2 вызова на всё). Правило: не платить за то, что доказывается бесплатно.
2. **Fail-closed абстенция**: mock/ошибка/нерешительность == НЕ одобрение. Никогда не принимать кандидата без доказательства. (Принято в dual/critic/evidence jury.)
3. **AST вместо regex** для семантики (импорты, опасные вызовы, структура тестов); regex — только для секретов-примитивов. AST — точнее, regex — быстрее; выбор по задаче.
4. **Твёрдое vs мягкое доказательство**: SMT — только SAT = нарушение (обнаружение контрпримера); ERROR/UNKNOWN — честная advisory, НЕ блок. Это отличает «доказано плохо» от «не смогли решить».
5. **Верификация через исполнение** (L2-дух): целевые тесты как доказательство поведения; для UNVERIFIED — повтор с тестами до эскалации. Динамика > статики там, где тесты возможны.
6. **Граф-маппинг вместо пофайлового**: cbm trace_path/search_graph (L1) + AST-маппер импортов в гейте — «кто на кого влияет» определяется графом, а не названиями.
7. **Паттерн-очистка AST-безопасно** (L3-дух): ast-grep/grit/semgrep применяют переписывания по правилам, а не по тексту.
8. **Точки докрутки по закрытым петлям**: гейт-замечания → патч → повторный гейт (сегодня: гейт трижды находил реальные проблемы — петля работает).

---

## 5. СЛЕДУЮЩИЕ ШАГИ (для AG2/доработки — отсортировано по цене/риску)

| Приоритет | Действие | Что даёт | Риск/работа |
|---|---|---|---|
| 1 | cbm v0.10.5 (L1) — проверка Defender/checksums на жив. машине, замена CKB | call-graph BFS, blast radius, query_graph | закрытый C-бинарь (доверие→checksums); 30-60 мин |
| 2 | viztracer цикл (L2): прогон тестов → трасса → кандидаты в очистку | мёртвый код по факту | pip install; средняя |
| 3 | semgrep + semgrep/mcp (L3) для уязвимостей импортов/функций | taint/паттерн-безопасность | pip/uvx; малая |
| 4 | grit stdlib-паттерны (L3) при массовых рефакторингах | декларативная очистка | cargo/npm; малая |
| 5 | 6b в CI-режиме по расписанию (не на кадный коммит) | deptry/pip-audit/bandit регулярно | env-флаги; малая |

Критерии приёмки L1 (из intent-дока): trace_path на llm_client.py < 1s; query_graph «функции без вызовов» находит реальный мёртвый код; цикл очистки кандидата проходит все гейты.