# SECURITY GATE DEEP PROBE — Промпт для AG2 / agy (глубокое расследование)

> Назначение: улучшить систему проверки безопасности и гейты Vazus SuperGraph OS.
> Квота: практически безграничная (agy IDE + Antigravity 2) — можно проводить глубочайшее исследование в интернете и читать ВСЁ.
> Правила: НИКАКИХ выдуманных абстракций. Каждый компонент ДОЛЖЕН быть открыт и проверен вручную (файл прочитан, команда выполнена, тест запущен). Нельзя судить о компоненте, не открыв его. Нельзя искать наугад — проверять по чек-листу.
> Среда: Windows 11, C:\vazus, venv C:\vazus\.venv, Python 3.11. Hermes с MCP: vazus-organic, ckb, sequential-thinking, playwright-mcp, colab-mcp (91+ инструмент). Прошлый аудит: 14.08.2026 (5/10, уязвимости V-1..V-7, см. ниже — перепроверить каждый пункт).

---
## ФАЗА 0. ИНВЕНТАРИЗАЦИЯ БЕЗ ДОМЫСЛОВ (полная видимость)
1. Прочитай: C:\vazus\PROJECT.md, C:\vazus\AGENTS.md, C:\vazus\docs\MASTER_SYSTEM_REVIEW_2026.md, C:\vazus\docs\research\mcp_ecosystem_2026.md, C:\vazus\docs\research\agent_memory_2026.md, C:\vazus\docs\research\context_compression_2026.md.
2. Построй полную карту кода через ckb MCP: switchProject C:\vazus → getArchitecture, getModuleOverview, getHotspots, listKeyConcepts, searchSymbols для verification/memory/engine/hooks. Дополнительно: `find C:\vazus -name "*.py" | wc -l` и полный список модулей vazus_core (engine/, memory/, verification/, workers/, evolution/, hooks/, integrations/).
3. Выведи ВЕСЬ граф зависимостей пакета: `C:\vazus\.venv\Scripts\python.exe -c "import ast, pathlib; ..."` (AST по всем .py: функции, классы, импорты) — обязанность: 100% компонентов в списке, НИ ОДИН файл не судится вслепую.
4. Обнови SCIP-индекс CKB (если старше сегодняшнего дня) — полная видимость кода без «чёрных ящиков».

## ФАЗА 1. ПЕРЕПРОВЕРКА ПРЕДЫДУЩЕГО АУДИТА (14.08.2026, V-1..V-7) — по каждому пункту: ОТКРЫТЬ → ПРОВЕРИТЬ КОМАНДОЙ → ВЕРДИКТ
- V-1 CRITICAL: Antigravity config grants: `command(*)`, `unsandboxed(*)`, `mcp(*)`, `autoApproveSubagents: true` → Проверить: `cat ~/.gemini/config/config.json`, `cat ~/.gemini/antigravity-cli/settings.json`. Вердикт: исправлено/не исправлено/частично (докажи содержимым файла).
- V-2 CRITICAL: `.env` в git-истории → `git -C C:/vazus ls-files | grep .env`; `git log --all --oneline -- .env`; проверить .gitignore. Вердикт + команды ротации ключей, если не сделано.
- V-3 HIGH: pre_tool_hook fail-open (`except: allow`), не покрывает command/mcp/дочерние процессы → `grep -n "except\|decision\|shell" C:\vazus\vazus_core\hooks\pre_tool_hook.py` + прочитать файл целиком. Вердикт.
- V-4 HIGH: self-mutation AGENTS.md через post_task_evolver/stop_hook → прочитать `C:\vazus\vazus_core\memory\post_task_evolver.py` и стоп-хук (если существуют) + проверить у карантина (`knowledge/quarantine/`). Вердикт.
- V-5 HIGH: слепой mock-PASS жюри при отсутствии API-ключа → прочитать C:\vazus\vazus_core\engine\llm_client.py (цепочка agy → SDK → cloud; VAZUS_LLM_ALLOW_CLOUD; fallback) и concordia/critic/dual/evidence_jury (fail-closed). Вердикт: где ещё возможен непрошеный PASS.
- V-6 HIGH: persist-инъекция в память через нефильтрованные уроки → прочитать auto_improver.save_lesson + memory/ записи: есть ли санитизация перед записью (размер, тип, exec-опасные паттерны). Вердикт.
- V-7 HIGH: исполнение мутированного кода без песочницы в darwinian → прочитать vazus_core/evolution/darwinian_evolver.py + windows_process_sandboxing (Job Objects). Вердикт.

## ФАЗА 2. ГЛУБОКАЯ ПРОВЕРКА ГЕЙТОВ (ручной режим, по чек-листу)
Запустить КАЖДЫЙ гейт и зафиксировать РЕАЛЬНЫЙ вывод:
1. precommit_gate.py (5-tier: AST / секреты / Z3 / Evidence+Critic jury / pytest / vulture): `C:\vazus\.venv\Scripts\python.exe C:\vazus\vazus_core\verification\precommit_gate.py`
2. Полный pytest: `C:\vazus\.venv\Scripts\python.exe -m pytest tests/ -q --tb=short` (или -m "not slow")
3. AST-скан секретов по всему дереву (regex: AIza, sk-, AKIA, password=, Bearer) — написать скрипт и выполнить.
4. Зависимости: `C:\vazus\.venv\Scripts\pip list --outdated` + `pip-audit` если установлен — уязвимые версии пакетов.
5. Проверить, что гейт НЕЛЬЗЯ обойти: можно ли закоммитить через --no-verify? Есть ли post-commit хуки? Кто подписывает коммиты?
6. Права антигравити/агентов: полный список grants/approvals в ~/.gemini — минимально возможный? (см. V-1).

## ФАЗА 3. ГЛУБОКОЕ ИНТЕРНЕТ-ИССЛЕДОВАНИЕ (квота почти безгранична — используй на полную)
Темы (каждую — с цитированием первоисточников, 5+ источников на тему):
1. MCP-безопасность 2026: 14 CVE/30+ RCE, ~200K уязвимых серверов (The Agent Report, OX Security, AgentSeal awesome-mcp-security) — какие паттерны защищают клиентов (env-фильтрация, sampling off, allowlist, OAuth PKCE, sandboxing) — что из этого внедрить в Hermes+Vazus.
2. Промпт-инъекция в агентных системах 2026: новые векторы (tool poisoning, memory poisoning, agent-to-agent), практики защиты — что применимо к гейтам прекоммита и жюри.
3. Supply-chain безопасность Python/Node: pip-audit/OSV, закрепление версий, hash-пины, индексы для локальных venv — что внедрить в CI/гейт.
4. Формальная верификация Python: Z3-контракты, аннотации @requires/@ensures, bounded model checking, статический анализ (ruff/vulture/mypy strict) — что реально даёт proof-уровень для гейтов.
5. Секреты: git history rewriting (git filter-repo), pre-commit detect-secrets/gitleaks, ротация — порядок действий на Windows для Vazus.

## ФАЗА 4. ДЕЛИВЕРАБЛ (обязательно)
Создать C:\vazus\docs\SECURITY_GATE_UPGRADE_PLAN_<дата>.md на русском:
1. Вердикты по V-1..V-7 (исправлено/нет, с доказательствами — вывод команд).
2. Новая матрица рисков (вероятность × ущерб, приоритет P0/P1/P2) по ВСЕМ компонентам.
3. Улучшения гейтов: конкретные патчи (файл, функция, diff-план) для каждого пробела.
4. Внедрение best-practice 2026: чек-лист из Фазы 3, помеченный «принять/отложить/отклонить» с обоснованием.
5. Секрет-план: если .env в истории — точные команды очистки + ротация ключей.
6. Список «не трогать»: что работает и хрупко.

В финальном ответе: 15 строк — топ-5 приоритетных действий с ожидаемым эффектом.

ПРАВИЛА ПОВЕДЕНИЯ
- Каждое утверждение — с доказательством: путь к файлу + строка/вывод команды/URL источника.
- Если не проверил — пиши UNVERIFIED, не додумывай.
- Запрещено: выдумывать компоненты, которых нет; оценивать модуль по названию; предлагать абстракции без указания, какой реальный код они заменяют.
- Интернет-поиск — только в Фазе 3 и только тематический; в Фазах 0-2 — только локальные файлы и команды.