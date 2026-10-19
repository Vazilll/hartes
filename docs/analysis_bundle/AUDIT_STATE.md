# AUDIT_STATE — чекпоинт аудита analysis_bundle (сессия 18.08 #2, gpt-5.6-sol→kimi-k3)

> Точка входа для НОВОЙ сессии. Всё проверено с доказательством на диске.
> Методика: system-report-audit + technical-claim-audit. Предыдущие чекпоинты: 17.08, 18.08 #1.

## РЕЗЮМЕ СЕССИИ 18.08 #2 (одной строкой)
Оба открытых вопроса прошлого чекпоинта ЗАКРЫТЫ доказательствами: (1) sync_keep_notes не покрыт
НИ ОДНИМ тестом (73 файла просканированы; единственный тест движка — scan_and_sync); silent
permanent failure воспроизведён ЖИВЬЁМ с fake-Drive: 2 файла найдены → status=error
"name 'synced' is not defined". (2) L2/L3 — claim бандла «НЕ внедрено» ЧАСТИЧНО устарел:
telemetry/codemods-модули существуют и работают (smoke OK), telemetry_call_edges в vazus.db
содержит 2646 живых рёбер (last_seen 18.08) — НО wiring-петля разорвана: все 5 ключевых
модулей — orphans вне self_check_5layers.py (никто в продакшн-путях их не вызывает).
Re-verify P0/P1: НИЧЕГО не исправлено (5×F821 на месте, Gate-6 всё ещё F401,F841,E9,
gateway NOT running, 4 wildcard-гранта на месте: config.json:21-24).

## НОВЫЕ ДОКАЗАТЕЛЬСТВА НА ДИСКЕ (сессия 18.08 #2)
- _audit_sync_coverage.py / .log — Q1: свип 73 тестов (0 упоминаний sync-движка кроме
  test_performance_refactoring.py:27 — импортирует GoogleSyncEngine-мост, но тестирует
  ТОЛЬКО scan_and_sync, строки 174-203), живой вызов с _FakeDrive (2 файла) →
  {'status': 'error', 'error': "name 'synced' is not defined"}; prod-вызывателей
  sync_keep_notes кроме __main__ блока НЕТ (2 ссылки: def:231 + __main__:301).
- _audit_l23_wiring.py / .log — Q2: wiring-свип 9 модулей + telemetry-таблицы RO +
  vacuous-check тестов 5-слоёв (assertTrue=0, barepass=0 везде) + live smoke
  DynamicTraceCollector (OK) и CodemodRouter.run_ruff_hygiene (success=True).
  Атрибуция telemetry в БД: последняя запись ведёт в testgen_engine._is_reward_hacking
  → данные пишет тестовый контур/self_check, а НЕ продакшн-рантайм.

## ВЕРДИКТЫ ПО ОТКРЫТЫМ ВОПРОСАМ (закрыты)
Q1 Покрытие sync_keep_notes: ОТВЕЧЕНО. Покрытия нет вообще (0 тестов). 685 passed не
  поймали потому, что (а) функция никем не импортируется в тестах, (б) единственный
  вызов — __main__ блок, который pytest не исполняет, (в) NameError прячется внутри
  try/except Exception → возвращается dict со status=error, а не краш — даже случайный
  вызов выглядел бы как «ожидаемая ошибка API». Баг НЕ обнаружим ни одним текущим
  механизмом кроме F821-линта — что и подтверждает приоритет фикса Gate-6.
Q2 Валидность L2/L3: УТОЧНЕНО. Терминология бандла («L2 НЕ внедрено») верна по ДУХУ
  (нет viztracer-цикла, нет продакшн-потребителей, нет cbm), но ФАКТИЧЕСКИ неполна:
  собственная реализация telemetry (PEP 669 tracer) и codemods (ruff/ast-grep/libcst)
  существует, работает и пишет в vazus.db (2646 рёбер, 1754 function hits).
  Разрыв: модули — orphans для всего кроме scripts/self_check_5layers.py
  (dynamic_trace_collector, upstream_scanner, codemod_router, candidate_harvester,
  smt_equivalence_prover — каждый ссылается ТОЛЬКО из self_check). supergraph_bridge —
  исключение: 5 продакшн-вызывателей. Claim «telemetry подключён только к
  self_check_5layers.py» — TRUE и подтверждён свипом.

## RE-VERIFY P0/P1 (состояние на 18.08 #2 — НИЧЕГО НЕ СДЕЛАНО)
- F821 ×5: ВСЕ НА МЕСТЕ (ruff --select F821 vazus_core/ scripts/ → 5 errors, exit=1):
  embeddings.py:495 Dict; google_super_sync_engine.py:246 synced; precommit_gate.py:34
  _resolve_workspace_root; playwright_interactive_2fa.py:35,45 re.
- Gate-6: всё ещё хардкод `--select F401,F841,E9` (precommit_gate.py:452).
- Gateway: `hermes gateway status` = NOT running → крон/watchdog мертвы (heartbeat с 12.08).
- V-1 wildcard: 4 гранта НА МЕСТЕ — ~/.gemini/config/config.json:21-24
  (view_file(*), read_file(*), replace_file_content(*), write_to_file(*)).
- V-2 секреты: не проверялись в этой сессии (ротация — действие пользователя вне репо).

## МАТРИЦА ДЕЙСТВИЙ (актуализирована)
- P0: ротация 7 ключей + git filter-repo (V-2) — без изменений, не сделано.
- P1: Gate-6 --select F (или +F821) + фикс 5 мест. ПОДКРЕПЛЕНО: Q1 доказал, что F821-
  класс ловит баги, невидимые для ВСЕХ остальных механизмов (тесты слепы, try/except
  маскирует). Это единственная линия защиты — и она отключена.
- P1: hermes gateway install — иначе крон/watchdog мертвы навсегда.
- P1: удалить 4 wildcard-гранта (config.json:21-24) — заменить точечными.
- P2: sync_keep_notes — либо починить (`"notes": [f["name"] for f in files]`), либо
  удалить как неиспользуемый (prod-вызывателей нет, Drive OAuth не настроен).
- P2: L2/L3-петля — подключить telemetry/codemods к реальному циклу (pre-commit или
  расписание) ИЛИ признать их demo-only и зафиксировать в бандле. Сейчас они дают
  ложное ощущение «5 слоёв работают» при orphan-wiring.
- P2: 44с на :5001 — принято как свойство канала (18.08 #1).
- P2: colab-mcp login / отключить; легаси ~/.hermes/config.yaml; counterexample в
  smt_equivalence_prover — без изменений.

## ГЛАВНЫЙ ВЕРДИКТ (18.08 #2)
- Бандл на ~85% правдив — подтверждается. Добавка: «L2/L3 не внедрено» = PARTIAL
  (реализация есть и живая, но wiring разорван — честнее «внедрено как demo, не как петля»).
- Самый дешёвый высокоэффективный фикс системы: Gate-6 +F821 (1 строка) — единственный
  механизм, способный видеть целый класс багов, невидимых для тестов и AST-гейта.
- Health score: 75/100 (без изменений: ни один P1 не закрыт; +информационная ясность).

## КАК ПРОДОЛЖИТЬ В НОВОЙ СЕССИИ
Скажи: «продолжи аудит по C:\vazus\docs\analysis_bundle\AUDIT_STATE.md». Все доказательства
на диске. Открытые вопросы для следующей сессии:
1. Если пользователь применил фиксы (F821/Gate-6/wildcard/gateway) — ре-верифицировать
   каждый по живому коду, не по словам (скрипты переиспользуемы).
2. Проверить claim бандла 01_system_map.md о «72+/91+ инструментах» против живого
   `hermes mcp list` в новой сессии (MCP-инструменты меняются).
3. По желанию: реальный Gate-4 раунд с VAZUS_LLM_SKIP_ADAPTER=0 (жжёт квоту).

---
# АРХИВ — чекпоинт сессии 18.08 #1 (deepseek-v4-pro)

## РЕЗЮМЕ #1
Все незакрытые пункты сессии 17.08 проверены. Главное новое: (1) класс F821 — 5 мест в own code, гейт их НЕ видит; 2 из них живые баги (sync_keep_notes никогда не успешен;
import vazus_core падает на py3.11). (2) Gate-4 fail-closed доказан живьём 9/9 (0 LLM-вызовов).
(3) 44с на :5001 — не адаптер (0.0с overhead), это латентность канала agy/IDE-gateway.
(4) V-1: command(*)-грантов нет, НО есть 4 файловых wildcard (write_to_file(*)!).
(5) Playwright-браузеры УСТАНОВЛЕНЫ (бандл занижает). (6) Крон: тикер живёт только
в gateway-процессе, а gateway не запущен → watchdog не стрельнёт.

## ДОКАЗАТЕЛЬСТВА НА ДИСКЕ (скрипты аудита, переиспользуемы)
- _audit_v1_grants.py / _audit_v1_grants.log — полный свип 294 allow-грантов Antigravity
- _audit_gate4_jury.py / _audit_gate4_jury.log — fail-injection Gate-4: 9/9 PASS, 0 LLM-вызовов
- _audit_adapter_latency.py / _audit_adapter_latency.log — атрибуция 44с: agy=43.2с, адаптер=0.0с
- _audit_f821_findings.py / _audit_f821_findings.log — 5×F821 + почему гейт слеп
- Наследие 17.08: _audit_pytest.log (685 passed), _audit_env_check.py, _audit_jury_probe.py,
  _audit_smt_gate.py, _audit_wiring.sh, _audit_hermes.sh

## ПОДТВЕРЖДЕНО / ИЗМЕНЕНО В ЭТОЙ СЕССИИ
1. **Gate-4 (Concordia/critic jury) FAIL-CLOSED ДОКАЗАН**: 9/9 fail-injection на реальном коде
   critic_jury.py + precommit_gate.py: mock-ответ→ABSTAIN+reject; LLM-исключение→ABSTAIN+reject;
   мусорный ответ→ABSTAIN; вердикт не о том пути→ABSTAIN; split CONFIRM+ABSTAIN→ABSTAIN
   (нужно единогласие); любой CONTRADICT→REJECT; positive control: 2×CONFIRM→approved=True.
   Обёртка run_gate_4_concordia_jury на mock→ok=False (коммит блокируется). 0 реальных LLM-вызовов.
2. **44с на :5001 переатрибутировано**: агy.exe --version=0.4с; agy prompt (warm)=43.5с;
   adapter POST=42.7с → адаптер добавляет 0.0с. Вся задержка — в agy CLI/IDE-шлюзе.
   НЕ баг адаптера. (Кстати: у адаптера ТОЛЬКО один роут POST /v1/chat/completions —
   /health и /v1/models дают 404, это ожидаемо; watchdog трактует 404 как «alive» — корректно.)
3. **vazus_organic_mcp.py содержит ровно 13 @MCP.tool** (15 с list_prompts/list_resources).
   Счёт «72+» = все MCP-инструменты Hermes (ckb 27 + colab 5 + playwright 24 + seq-thinking 1 +
   vazus-organic 15); «91+» = 72 MCP + ~21 core-инструментов Hermes. Оба числа сходятся,
   но бандл не пояснил методику счёта. Сам файл: 13 инструментов, никаких заглушек.
4. **watchdog-скрипт рабочий**: vazus_health_watchdog.py --verbose → всё OK, EXIT=0
   (адаптер 404=alive, :5012 401=alive, обе БД integrity=ok).
5. **Playwright: браузеры УСТАНОВЛЕНЫ** (~/AppData/Local/ms-playwright: chromium-1228,
   chromium_headless_shell-1228, ffmpeg-1011). Заявление бандла «браузеры не установлены» — FALSE.
   Живой browser_exec тоже отработал (Example Domain OK).
6. **colab-mcp**: exe установлен (.venv/Scripts/colab-mcp.exe), НО credential-файлов нет нигде
   (~/.colab-mcp, ~/AppData/Local/colab*, токены). Авторизация не выполнена — бандл ПРАВ.
7. **cbm**: не на PATH. РЕШЕНИЕ: не внедрять — CKB жив и отвечает (getStatus healthy),
   L1-потребность закрыта, закрытый бинарь не нужен.
8. **Крон (корень найден)**: тикер запускается ТОЛЬКО из gateway-процесса
   (web_server.py::_start_desktop_cron_ticker / cron.scheduler_provider.start).
   `hermes gateway status` = NOT running → heartbeat мёртв с 12.08 и watchdog-крон
   (next 18.08 09:00) НЕ выстрелит. Решение: `hermes gateway install` (Windows Scheduled Task).

## НОВАЯ КРИТИЧЕСКАЯ НАХОДКА: класс F821 (undefined names), гейт слеп
Свип `ruff --select F821` по own code: 5 ошибок. Gate-1 (ast.parse) ловит только синтаксис,
Gate-6 хардкодит `--select F401,F841,E9` — F821 не входит. pyproject выбирает «F» (включая
F821), но гейт его игнорирует. Т.е. undefined names проходят pre-commit НЕЗАМЕЧЕННЫМИ.
1. **vazus_core/memory/embeddings.py:495** — `Dict` не импортирован (typing imports: Any, Optional).
   На venv py3.14.6 живёт только из-за PEP 649 (ленивые аннотации); `__annotations__`/get_type_hints
   → NameError. НА СИСТЕМНОМ PYTHON 3.11.15 `import vazus_core` ПАДАЕТ (NameError).
   pyproject: requires-python>=3.11, target=py311 → на минимальной заявленной версии пакет мёртв.
2. **vazus_core/integrations/google_super_sync_engine.py:246** — `synced` нигде не присваивается;
   ссылка ВНУТРИ try/except → NameError глотается, sync_keep_notes() НИКОГДА не возвращает success
   (silent permanent failure). Вызывается из строки 301. Тесты это не ловят (функция не покрыта
   либо покрыта моком — проверить покрытие отдельно).
3. **vazus_core/verification/precommit_gate.py:34** — `_resolve_workspace_root()` используется до
   определения. Работает только потому, что `Path('')` всегда truthy и `or` коротко замыкается —
   т.е. строка никогда не вызывает функцию, которую «вызывает». Landmine: изменение обработки
   VAZUS_WORKSPACE_DIR уронит pre-commit хуком каждый коммит.
4. **scripts/playwright_interactive_2fa.py:35,45** — `re` не импортирован (вспомогательный скрипт).
ФИКС (тривиален): Gate-6 `--select F` (или +F821) + починить 5 мест.
Почему 685 passed не поймали: тесты бегут на 3.14 (PEP 649), синк не покрыт.

## КРИТИЧЕСКИЕ НАХОДКИ (консолидировано, с 17.08)
- **V-2 CRITICAL (P0)**: 7 секретов в git-истории, sha256 = текущему .env (НЕ ротированы):
  GEMINI_API_KEY, JULES_API_KEY, OPENCODE_GO_API_KEY, DEEPSEEK_API_KEY, TELEGRAM_BOT_TOKEN,
  YANDEX_APP_PASSWORD, MIREA_PASSWORD. Коммиты 47ab20d, a1c47e0; .env убран из трека в 8582fba.
  Ремоутов нет, но ротация + filter-repo обязательны.
- **V-1 (P1, УТОЧНЕНО)**: command(*)/unsandboxed(*) нет, autoApproveSubagents=false — НО есть
  4 файловых wildcard-гранта: write_to_file(*), replace_file_content(*), view_file(*), read_file(*).
  write_to_file(*) = агент может перезаписать ЛЮБОЙ файл без запроса. Плюс точечные «опасные»:
  5× agy --dangerously-skip-permissions, powershell -ExecutionPolicy Bypass, Remove-Item -Force,
  pip install. Всего 294 записи allow (не 274), deny=0.
- **F821-класс (P1, НОВЫЙ)**: см. выше — гейт слеп + 2 живых бага + мёртвый импорт на py3.11.
- **Крон-тикер мёртв (P1)**: gateway не запущен; тикер существует только в нём.
- **TERMINAL_CWD «вычищен» — PARTIAL**: в Hermes .env строка 214 закомментирована;
  легаси ~/.hermes/config.yaml (305B) жив.
- **smt_equivalence_prover DISPROVEN с пустым counterexample={}** — вердикт честный,
  контрпример не возвращается (P2).

## МАТРИЦА ДЕЙСТВИЙ P0/P1/P2
- P0: ротация 7 ключей + git filter-repo (V-2). Доказано, не сделано.
- P1: Gate-6 --select F + фикс 5×F821 (особенно sync_keep_notes и embeddings.py).
- P1: `hermes gateway install` — иначе крон-джобы мертвы навсегда.
- P1: удалить 4 wildcard-гранта из globalPermissionGrants (особенно write_to_file(*),
  replace_file_content(*)) — заменить точечными.
- P2: 44с на :5001 — принять как свойство канала (agy/IDE-gateway); при потребности
  в скорости исследовать альтернативный маршрут, не чинить адаптер.
- P2: colab-mcp login (нужен OAuth в браузере Google) — или отключить сервер.
- P2: убрать легаси ~/.hermes/config.yaml, раскрыть TERMINAL_CWD.
- P2: counterexample в smt_equivalence_prover.

## РЕШЕНИЯ ПРИНЯТЫЕ
- cbm (L1): НЕ внедрять. CKB покрывает потребность.
- Крон: не копать дальше (по решению Vaz); причина зафиксирована, действие в матрице.
- Playwright: браузеры уже стоят — пункт «npx playwright install» закрыт.
- Gate-4: дополнительная проверка с РЕАЛЬНЫМ LLM не нужна (fail-closed 9/9 + positive control).

## ГЛАВНЫЙ ВЕРДИКТ
- Бандл на ~85% правдив; занижает Playwright и завышает собственную непогрешимость гейта.
- Система работает, верификация реальна, Gate-4 честно fail-closed — это сильное место.
- Слабое место: гейт слеп к undefined names (F821), и это уже накопило 2 живых бага.
- Health score: 75/100 (было 78-82; минус F821-класс и слепой Gate-6, минус V-1 wildcard write;
  плюс — Gate-4 доказан живьём, Playwright на месте).

## КАК ПРОДОЛЖИТЬ В НОВОЙ СЕССИИ
Скажи: «продолжи аудит по C:\vazus\docs\analysis_bundle\AUDIT_STATE.md». Все доказательства
на диске. Открытые вопросы для следующей сессии:
1. Покрытие тестами sync_keep_notes (почему 685 passed не поймали вечный NameError).
2. Валидность claim «L2/L3» в связке с тем, что telemetry подключён только к self_check_5layers.py.
3. При желании: реальный Gate-4 раунд с VAZUS_LLM_SKIP_ADAPTER=0 (жжёт квоту — не обязательно).
