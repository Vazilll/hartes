# 07. SECURITY STATE — уязвимости V-1..V-7 (аудит 14.08) и статус 17.08

Источник: аудит сессии 14.08 (оценка зрелости 5/10). Ниже — статус КАЖДОГО пункта на 17.08.
Правило: вердикты только по факту (файл/команда). Аналитику: перепроверить командой перед подтверждением.

## V-1 CRITICAL — Antigravity grants `command(*)`, `unsandboxed(*)`, `mcp(*)`, autoApproveSubagents
Статус 14.08: был. Что сталось: требует проверки `cat ~/.gemini/config/config.json` — аналитик обязан перепроверить живой конфиг. (В диалоге 14.08 AntiGravity «исправлял большинство систем» — подтвердить.)
## V-2 CRITICAL — .env в git-истории, ключи в коммитах
Статус: `.env` в .gitignore (список git ls-files чистый от .env на 17.08 — подтверждено при аудите). ИСТОРИЯ: ротация/rewrite не делалась — перепроверить `git log --all --oneline -- .env` и принять решение (filter-repo + ротация).
## V-3 HIGH — pre_tool_hook fail-open (`except: allow`), не покрывал command/mcp
Статус: нужно перепроверить C:\vazus\vazus_core\hooks\pre_tool_hook.py на fail-closed (это файл Vazus[sh], не антигравити). Открытый вопрос.
## V-4 HIGH — self-mutation AGENTS.md через post_task_evolver/stop_hook
Статус: карантин `knowledge/quarantine/` существует; политика промоушена через review — подтвердить наличие на 17.08.
## V-5 HIGH — слепой mock-PASS жюри при отсутствии API-ключа
Статус: ИСПРАВЛЕНО/УЛУЧШЕНО 17.08 — dual_jury/critic_jury fail-closed (mock/ошибка = ABSTAIN = не одобрение); новы тест test_concordia_jury_fail_closed_on_mock_fallback. Проверка критиком взрослого кода подтвердила fail-closed в 3 раундах.
## V-6 HIGH — persist-инъекция в память через нефильтрованные уроки
Статус: auto_improver.save_lesson + memory_facts_v2 bi-temporal (valid_at/invalid_at) — оставить подтвердить и продумать консолидацию (аналог mem0 Dream из исследования agent_memory).
## V-7 HIGH — исполнение мутированного кода без песочницы (darwinian)
Статус: windows-process-sandboxing / REPL-песочница (Job Object) существуют; darwinian эволюция — подтвердить, что запускается в песочнице.

## Защитные механизмы на месте (подтверждено 17.08)
- EvidenceJury (0 LLM) → dual → critic (fail-closed) в precommit_gate; 4 раунда отказов = реальные дефекты найдены
- SMT Z3: SAT = жёсткое нарушение (блок), ERROR/UNKNOWN = advisory
- vulture ≥90%, ruff F401/F841/E9, bandit (opt-in), deptry/pip-audit (opt-in 6b)
- Reward-hacking гвард в тестах (пустые pass / assert True в staged тестах)
- utf-8 везде в subprocess (фикс cp1252); секреты-паттерны в Gate 1

## Что аналитик ДОЛЖЕН сделать
1. Перепроверить V-1 (config.json grants), V-3 (fail-closed), V-4 (quarantine), V-7 (sandbox) на живой машине командами.
2. Дать заключение по V-2 (нужна ли ротация ключей + filter-repo).
3. Обновить матрицу рисков (P0/P1/P2) и дать список «не трогать».