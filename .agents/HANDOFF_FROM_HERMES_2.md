# HANDOFF FROM HERMES → ANTIGRAVITY 2 (№2)
Дата: 2026-08-15
От: Hermes Agent (аудит + апгрейд качества)
Кому: Antigravity 2.0 / Vazus SuperGraph OS

---

## 1. ЗАМКНИ ПЕТЛЮ САМОУЛУЧШЕНИЯ (главное предложение)

Сейчас у тебя есть: dynamic_skill_dispatcher (768D-матчинг скиллов из
~/.gemini/config/skills + C:\vazus), post_task_evolver (рефлексия),
hebbian_compiler (композитные тулзы). Чего нет: ПОСТ-СЕССИОННОЙ
дистилляции «сложная успешная работа → новый скилл».

Предложение — добавить в stop_hook.py шаг генерации скилла:
1. Если сессия содержала нестандартную успешную работу (новый паттерн,
   обход граблей, >5 инструмент-вызовов, задача закрыта верификацией) —
   сгенерировать SKILL.md по шаблону Hermes (пример: скилл
   windows-process-sandboxing у Hermes, создан куратором из работы над
   песочницей Job Objects).
2. Шаблон:
   - YAML-фронтматтер: name, description (первая строка = триггер, ≤57
     символов), version, license, tags.
   - Тело: When to use / шаги с точными командами / Pitfalls / проверка.
   - Опционально scripts/ с готовым скриптом.
3. Класть в ~/.gemini/config/skills/ — dispatcher подхватит и
   заиндексирует сам (768D), ничего регистрировать не надо.
4. Гварды (обязательно):
   - Только после Victory-аудита/верификации; из провальных сессий — нет.
   - Лимит 1 скилл/сессия, dedup по sha256 контента (не плодить дубли).
   - Не писать в AGENTS.md — только в каталог скиллов.

## 2. ГЕЙТ: ДОБАВЛЕН УРОВЕНЬ 6 (Hermes, уже в git)

precommit_gate.py теперь 6-тировневый:
- Gate 6 (блокирующий): ruff F401/F841/E9 по своим файлам (быстрый,
  детерминированный; ловит то, что vulture пропускает — например,
  пропущенный Path в subprocess_repl).
- Gate 6b (опциональный, VAZUS_GATE_DEEP_SCAN=1): deptry (лишние/недостающие
  зависимости), pip-audit (известные CVE), bandit (AST-безопасность).
  По умолчанию advisory; VAZUS_GATE_STRICT_DEEP=1 делает блокирующим.
- Установлены в .venv: ruff 0.16.3, deptry 0.25.1, pip-audit 2.10.1,
  bandit 1.9.4. Добавлены в pyproject dev-deps.
- [tool.ruff] конфиг в pyproject.toml (exclude: labs, services/inference,
  scratch, bin, apps, knowledge, data, .venv, pyenv, worktrees).
- Hermes вычистил 299 ruff-нарушений по своему коду (F401/F841/E9):
  259 автофиксом, 35 переименованием неиспользуемых переменных
  (_-префикс). llama.cpp (вендор) не трогал — он в exclude.

## 3. ПОТЕРЯ R2 (важно)

Артефакты Milestone 2 роя Sentinel — auto_skill_engine.py,
TranscriptAnalyzer, SkillGenerator — удалены при чистке 14-15.08 и в git
отсутствуют. Их функции частично закрывают dynamic_skill_dispatcher +
hebbian_compiler. Если модуль нужен — пересобрать; R3 context_memory_engine
и R4 E2E-тесты тоже стоит проверить (tests/test_r2_skill_autogen.py и
test_r3_memory_recall.py могут ссылаться на удалённое).

## 4. ПОРТЫ (актуально)

- system_daemon (vazus_core/workers/system_daemon.py): HTTP health 8765.
- Vision WS (services/vision/vazus_vision_daemon.py): ПЕРЕНЕСЁН на 8766
  (коллизия устранена), env-оверрайд VAZUS_VISION_WS_PORT.
- Документация PROJECT.md и тест-скрипты m3 обновлены.

## 5. ЧИСТКА — ОТКРЫТЫЕ ВОПРОСЫ

- ~/.gemini/antigravity-cli (6.4GB: conversations 5.8GB + brain 324MB) —
  архив после миграции; ждёт решения (сжать/перенести/удалить).
- knowledge/ (23GB) — пользовательские данные, не мусор.
- Ветки: удалены feature/lab-*, embedding-models, arch_test-*; остались
  только antigravity-tui-vision, subagent-bridges, vazus-dev, vazus-main.
- wiki-файлы (services/memory/semantic/wiki/**) при каждом коммите
  регенерируются хуками — коммитить их бессмысленно.
- Конфиг: гранты почищены (18 одноразовых команд миграции удалены).
  Если приложение перезаписало config.json при выходе — прогони чистку
  повторно (бэкап: config.json.bak-20260815).

## 6. ЧТО HERMES ОТ AG2 УЖЕ ВЗЯЛ (статус)

MCP vazus-organic + ckb, скилл vazus-os-integration, Job Object-паттерн
(скилл windows-process-sandboxing). Рекомендованные инструменты
внедрены в гейт (п.2).
