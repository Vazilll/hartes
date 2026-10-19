# Задача для AG2: CKB getStatus/getHotspots — починить или заменить

> ⚠️ ОБНОВЛЕНО 15.08: сначала обсуди docs/AG2_CODE_INTELLIGENCE_5LAYERS.md.
> Приоритет сместился с «чинить CKB» на «заменить cbm (codebase-memory-mcp)»
> в рамках 5-слойной архитектуры. Этот бриф держим как fallback-план:
> применяй его ТОЛЬКО если решение по cbm отклонено в обсуждении.

> Отправь это в Antigravity 2 (AG2) как самостоятельную задачу. Работать в C:\vazus.

## Проблема

CKB (Code Knowledge Backend, ckb.cmd MCP-сервер, v9.3.0) висит на холодном
старте на тяжёлых инструментах:
- `getStatus` — молчит >60s (проверено вручную по JSON-RPC 14.08: `initialize`
  отвечает мгновенно, `tools/call getStatus` — нет ответа).
- `getHotspots` — висит до 300s-таймаута (обрывается по таймауту клиента).
Лёгкие инструменты (searchSymbols, explore, symbolExists, getSymbol, batchSearch)
работают. Проблема известна с 14.08, не чинилась. Твоя задача — ЛИБО починить,
ЛИБО найти/внедрить более хороший инструмент кодового графа с обоснованием.

## Факты окружения (собраны 15.08, проверяй и дополняй)

- ОС: Windows 11, репозиторий C:\vazus (Python 3.14 venv: C:\vazus\.venv).
- CKB: установлен через npm — C:\Users\Vaz\AppData\Roaming\npm\ckb.cmd, v9.3.0.
- Конфиг: C:\vazus\.ckb\config.json (version 5, repoRoot ".", SCIP enabled
  indexPath "index.scip", LSP enabled: dart/go(gopls)/python(pylsp)/typescript,
  есть секции daemon, budget, backendLimits, lspSupervisor, queryPolicy, llm,
  telemetry, logging, cache, importScan, coverage, review, compliance).
- Данные: C:\vazus\.ckb\ckb.db (14.5MB) + ckb.db-wal (42MB, БОЛЬШОЙ),
  jobs.db, index.lock (содержит PID 21108, дата 13.08 03:29 — ПОДОЗРИТЕЛЬНО
  старая блокировка), логи C:\vazus\.ckb\logs\mcp.log.
- SCIP-индекс: C:\vazus\index.scip (20MB, в корне репо, НЕ в .ckb/).
- Логи mcp.log: постоянные "SCIP index is stale" (незакоммиченные изменения),
  ошибки сканирования .venv/playwright JS (bufio token too long), одна ошибка
  "write to stdout failed: pipe is being closed" (14.08 18:01).
- Демон на порту 9120 СЕЙЧАС НЕ слушает (netstat пусто) — демон поднимается
  on-demand при вызове MCP.
- Порт 9120, каталог .ckb/ в .gitignore. Auth в конфиге отсутствует (None).

## Гипотезы (проверь каждую, не считай истиной)

1. Stale index.lock (PID 21108 от 13.08) — если процесс мёртв, lock может
   блокировать операции индекса/health.
2. LSP-холодный старт: getStatus может ждать health ВСЕХ LSP-серверов
   (dart, gopls, pylsp, typescript-language-server). Проверь, какие из них
   вообще установлены на машине (`where pylsp gopls dart typescript-language-server`).
   Если pylsp/gopls отсутствуют — supervisor может висеть на их запуске.
3. Большой WAL (42MB) + stale SCIP-индекс — тяжёлый cold start.
4. getStatus/getHotspots выполняют полный скан/health-чек репозитория с
   учётом незакоммиченных изменений (репо «никогда не чистое» из-за
   wiki-файлов, генерируемых хуками — см. ниже).
5. Бюджеты/лимиты в config.json (budget, backendLimits) могут делать
   операции медленными или блокировать.

## Задача A — починить CKB (предпочтительно)

1. Воспроизведи ханг сам: JSON-RPC поверх stdio (initialize → initialized →
   tools/call getStatus), замерь время. Также попробуй прогреть: вызови
   лёгкий инструмент (searchSymbols) ДО getStatus — уходит ли ханг.
2. Проверь и устрани stale index.lock (если PID мёртв). Почисти/уменьши
   WAL (checkpoint), если это безопасно.
3. Настрой LSP: отключи серверы, которых нет на машине (python→pylsp и т.п.),
   или включи ленивый старт LSP (lspSupervisor/workspaceStrategy настройки).
4. Изучи секции daemon/budget/backendLimits/queryPolicy в config.json —
   настрой таймауты и лимиты так, чтобы getStatus/getHotspots отвечали.
5. Проверь, не блокирует ли что-то переиндексацию SCIP; обнови индекс
   (ckb index / ckb.cmd) и убедись, что mcp.log чист от новых ошибок.
6. НЕ удаляй .ckb/ и index.scip без необходимости — это данные.

Критерий A: `getStatus` отвечает < 10s на холодном старте (или после
документированного прогрева), `getHotspots` < 30s, лёгкие инструменты
продолжают работать. Все изменения — отдельным коммитом с описанием.

## Задача B — если починить не удалось: найди замену

Сравни и выбери ЛУЧШИЙ инструмент кодового графа/анализа для C:\vazus:

Кандидаты (не ограничивайся):
- ast-grep (sg) — AST-поиск, быстрый, cross-language (в т.ч. Python);
- semgrep — rule-based анализ;
- tree-sitter CLI;
- scip-cli + Sourcegraph — SCIP-индексация (формат уже используется);
- наш СОБСТВЕННЫЙ кодовый граф: vazus_core/engine/ast_repo_mapper.py +
  vazus_core/engine/supergraph_linker.py (AST-топология + 768D векторный
  граф в services/memory/vazus.db) — возможно, CKB вообще не нужен,
  а нужен MCP-мост поверх своего графа;
- любой другой инструмент, который ты найдёшь и докажешь.

Критерии сравнения (таблица): холодный старт, скорость типовых запросов
(поиск символа, ссылки, impact), точность по Python-кодовой базе, наличие
MCP-интеграции или лёгкость её добавления, ресурсы (RAM/CPU), сложность
внедрения. Прогони бенчмарк на реальных запросах (например: findReferences
для функции из vazus_core/engine/llm_client.py, callGraph для
concordia_jury.py) и приведи замеры.

Критерий B: выбранный инструмент установлен, работает в C:\vazus, отвечает
на те же запросы быстрее CKB, подключён (MCP или CLI-скрипт в scripts/),
с задокументированной интеграцией. CKB при этом НЕ удаляй — оставь
отключённым в конфиге MCP (или в .mcp.json), чтобы можно было вернуть.

## Ограничения

- Репозиторий «никогда не чистое»: хуки при каждом коммите пишут
  services/memory/semantic/wiki/Commits/<sha>.md — это НОРМА, не считай
  это проблемой индексации, но учти при SCIP-переиндексации (исключай
  services/memory/semantic и .venv из сканирования, если возможно).
- Не трогай .ckb/token.txt (если появится), не создавай секреты.
- Не удаляй и не переписывай vazus_core/* — только если задача требует
  минимальной правки для интеграции, и то с отдельным коммитом.
- Не качай тяжёлые модели, не ставь ollama.
- НЕ выдавай mock/dry_run за решение: каждый пункт — с живым выводом
  команд и замерами времени (было/стало).
- Полный pytest должен оставаться зелёным (664 passed, до 10 минут).
- Каждый пункт (A1–A6, B1–B3) — отдельный коммит с описанием.

## Формат отчёта

Таблица: пункт | что сделано | как проверено (команда/вывод) | замер времени
(было >60s / стало X) | коммит. В конце — вердикт: CKB починен ИЛИ выбран
инструмент X с обоснованием по критериям. Если ничего не получилось —
честно напиши, что именно не удалось и какие гипотезы остались.
