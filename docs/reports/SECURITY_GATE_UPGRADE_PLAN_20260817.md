# SECURITY GATE UPGRADE PLAN & AUDIT REPORT (2026-08-17)

> **Система:** Vazus SuperGraph OS + Hermes Ecosystem  
> **Окружение:** Windows 11, Intel CPU/NPU, Python 3.14 + venv `C:\vazus\.venv`, CKB SCIP (20 585 символов), fastmcp (91+ tools)  
> **Базовый коммит аудита:** `7253a8d` (ветка `vazus-dev` / `feature/subagent-bridges`)  
> **Методология:** Zero-Assumption Verification (100% компонентов проверены чтением файлов, AST-парсингом, запусками тестов и скриптов в реальной среде).

---

## 1. ВЕРДИКТЫ ПЕРЕПРОВЕРКИ ПРЕДЫДУЩЕГО АУДИТА (V-1 .. V-7)

| ID | Уязвимость / Описание | Статус на 17.08.2026 | Эмпирическое доказательство (Файл / Строка / Команда) |
|---|---|---|---|
| **V-1** | **CRITICAL**: Antigravity wildcard grants `command(*)`, `unsandboxed(*)`, `autoApproveSubagents: true` | **ИСПРАВЛЕНО** | Проверены `~/.gemini/config/config.json` и `~/.gemini/antigravity-cli/settings.json`. Глобальные маски `*` и `autoApproveSubagents` отсутствуют. Все разрешения в секции `permissions.allow` зафиксированы в виде явных индивидуальных командных строк. |
| **V-2** | **CRITICAL**: `.env` с реальными API-ключами в Git-истории | **НЕ ИСПРАВЛЕНО (Активная утечка в истории)** | `git ls-files` чист (в рабочей копии только `.env.example`). Однако команда `git log --all --oneline -- .env` выявила коммиты `47ab20d`, `a1c47e0`, `8582fba`. В коммите `47ab20d` зафиксированы реальные ключи: `OPENCODE_GO_API_KEY=sk-YpY9...`, `JULES_API_KEY=AQ.Ab8...`, `GEMINI_API_KEY=AIzaSyDlqAn...`. Ключи остаются в объектах истории `.git/objects/`. Требуется `git-filter-repo` и ротация. |
| **V-3** | **HIGH**: `pre_tool_hook` fail-open и отсутствие покрытия `run_command` / `call_mcp_tool` | **ЧАСТИЧНО ИСПРАВЛЕНО** | Сам скрипт `C:\vazus\vazus_core\hooks\pre_tool_hook.py` переписан на Fail-Closed (`except: return {"decision": "deny"}` на строках 56, 80, 85). **Но в конфигурации** `~/.gemini/config/hooks.json` matcher задан как `"replace_file_content\|write_to_file\|multi_replace_file_content"`, из-за чего вызовы `run_command` и `call_mcp_tool` хуком физически не перехватываются. |
| **V-4** | **HIGH**: Неконтролируемая само-мутация `AGENTS.md` через `post_task_evolver` | **ИСПРАВЛЕНО** | Модуль `post_task_evolver.py` удален. `AGENTS.md` защищен в `pre_tool_hook.py` (строки 32-34: `FORBIDDEN_PATTERNS`). `stop_hook.py` изолирует выученные шаблоны строго в `~/.gemini/config/skills/auto-lesson-*` с валидацией выхода за пределы каталога (`skill_author.py`, строки 30-37). |
| **V-5** | **HIGH**: Слепой mock-PASS жюри при падении/отсутствии API-ключа | **ИСПРАВЛЕНО** | В `vazus_core/verification/concordia_jury.py` (строки 20-31, 506-510, 571-574) и `critic_jury.py` (строки 192-194, 268-270) внедрен фильтр `is_mock_response`. При падении LLM или возврате mock-заглушки возвращается `ABSTAIN` (fail-closed, `approved=False`), что блокирует пропуск непроверенного кода. |
| **V-6** | **HIGH**: Persist-инъекция в память через нефильтрованные уроки Reflexion | **ЧАСТИЧНО ИСПРАВЛЕНО** | В `vazus_core/memory/auto_improver.py` (строка 273) внедрено ограничение длины (`error_sig[:200]`, `lesson_text[:1000]`, `fix_hint[:500]`). Однако отсутствует фильтрация промпт-инъекций (`Ignore previous instructions`, маркеры смены системного контекста) перед подстановкой в `_llm_fix_fn`. |
| **V-7** | **HIGH**: Исполнение мутированного кода без песочницы в `darwinian_evolver` | **ИСПРАВЛЕНО** | В `vazus_core/evolution/darwinian_evolver.py` (строки 60-86) и `vazus_core/workers/subprocess_repl.py` (строки 19-65) внедрены Win32 Job Objects (`create_win32_sandbox_job`, лимит 1GB RAM, `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, блокировка сети, очистка окружения от секретов через `_sanitized_pytest_env`). |

---

## 2. МАТРИЦА РИСКОВ VAZUS SUPERGRAPH OS (17.08.2026)

| Компонент / Механизм | Вектор угрозы | Вероятность (1-5) | Ущерб (1-5) | Score (P = В × У) | Приоритет |
|---|---|---|---|---|---|
| **Git History Objects** | Утечка реальных ключей (`AIza...`, `sk-...`, `AQ.Ab8...`) через публичные форки/бэкапы | 5 | 5 | **25** | **P0 (CRITICAL)** |
| **Antigravity hooks.json** | Обход `pre_tool_hook` через `run_command` из-за узкого matcher'а | 4 | 5 | **20** | **P0 (CRITICAL)** |
| **Dependency Supply Chain** | Уязвимость `diskcache 5.6.3` (`PYSEC-2026-2447`) + 67 устаревших пакетов | 4 | 4 | **16** | **P1 (HIGH)** |
| **Reflexion Lesson Injection** | Внедрение управляющих промпт-инъекций в `reflexion_lessons` DB | 3 | 4 | **12** | **P1 (HIGH)** |
| **Git Client Commit Bypass** | Возможность обойти локальный прекоммит через `git commit --no-verify` | 4 | 3 | **12** | **P1 (HIGH)** |
| **Critic Jury Model Fallback** | 429 Quota Exhaustion при запросах к устаревшим алиасам (`gemini-3.6-flash`) | 4 | 3 | **12** | **P1 (HIGH)** |
| **Local MCP Server Stdio** | Выполнение RCE через unescaped CLI параметры в MCP серверах (CVE-2026-30623) | 2 | 5 | **10** | **P2 (MEDIUM)** |
| **Git Provenance Signing** | Отсутствие GPG/SSH подписи коммитов агентов (`commit.gpgsign=false`) | 3 | 3 | **9** | **P2 (MEDIUM)** |

---

## 3. ДЕТАЛЬНЫЕ ПАТЧИ И УЛУЧШЕНИЯ ГЕЙТОВ (DIFF-ПЛАН)

### 3.1. Патч P0-1: Расширение `hooks.json` на `run_command` и `call_mcp_tool`
**Файл:** `C:\Users\Vaz\.gemini\config\hooks.json`  
**Проблема:** `pre_tool_hook.py` содержит логику `_is_dangerous_command`, но вызывается только для операций записи файлов.
```diff
--- a/C:/Users/Vaz/.gemini/config/hooks.json
+++ b/C:/Users/Vaz/.gemini/config/hooks.json
@@ -3,7 +3,7 @@
     "PreToolUse": [
       {
-        "matcher": "replace_file_content|write_to_file|multi_replace_file_content",
+        "matcher": "replace_file_content|write_to_file|multi_replace_file_content|run_command|call_mcp_tool",
         "hooks": [
           {
             "type": "command",
```

### 3.2. Патч P0-2: Санитизация уроков от Prompt Injection в `auto_improver.py`
**Файл:** `C:\vazus\vazus_core\memory\auto_improver.py`  
**Функция:** `LessonMemoryBank.save_lesson` и `_format_lessons_for_prompt`
```python
# vazus_core/memory/auto_improver.py
import re

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(previous|all)\s+instructions"),
    re.compile(r"(?i)system\s*:\s*you\s+are"),
    re.compile(r"(?i)disregard\s+(constraints|rules)"),
    re.compile(r"```(?:python)?\s*(?:os\.system|subprocess|shutil\.rmtree)"),
]

def sanitize_lesson_text(text: str) -> str:
    """Strips dangerous injection patterns and escapes markdown delimiters."""
    if not text:
        return ""
    sanitized = text.replace("---", "—").replace("```", "'''")
    for pat in PROMPT_INJECTION_PATTERNS:
        sanitized = pat.sub("[REDACTED_INJECTION_PATTERN]", sanitized)
    return sanitized.strip()
```

### 3.3. Патч P1-1: Автономный апгрейд уязвимого `diskcache` и закрепление хешей
**Команда:**
```powershell
C:\vazus\.venv\Scripts\pip.exe install --upgrade "diskcache>=5.6.4"
```

### 3.4. Патч P1-2: Обновление модели по умолчанию на `gemini-3.7-flash` во всех компонентах жюри
**Файлы:** `vazus_core/verification/concordia_jury.py`, `vazus_core/verification/critic_jury.py`, `vazus_core/engine/subagent_framework.py`  
**Результат:** Замена вызова rate-limited `gemini-3.6-flash` (20 req/day) на актуальную сессионную квоту Antigravity `gemini-3.7-flash` (5 000 req/day).

---

## 4. ЧЕК-ЛИСТ ВНЕДРЕНИЯ SOTA BEST-PRACTICES 2026

| Технология / Практика 2026 | Статус в Vazus | Решение | Обоснование |
|---|---|---|---|
| **MCP Env Filtering & Path Allowlisting** | Защита от CVE-2026-30623 (OX Security) | **ПРИНЯТЬ** | Фильтрация опасных переменных окружения (`AWS_*`, `TOKEN`) при спавне stdio-серверов fastmcp и проверка путей на Path Traversal. |
| **Memory Provenance & Bi-Temporal Facts** | mem0 Dream + `memory_facts_v2` | **ПРИНЯТЬ** | В `vazus.db` уже развернута bi-temporal модель (`valid_at`/`invalid_at`). Добавить фоновую консолидацию противоречивых фактов. |
| **Dependency Hash-Checking Mode & pip-audit Gate** | `pip-audit --require-hashes` | **ПРИНЯТЬ** | Включить `pip-audit` в `precommit_gate.py` (Gate 6b) как обязательный блокирующий гейт перед релизными ветками. |
| **Symbolic SMT Contracts (CrossHair/Z3)** | `@requires` / `@ensures` с Z3 | **ПРИНЯТЬ** | Текущий `smt_z3_verifier.py` расширяется до поддержки AST-документированных контрактов с генерацией контрпримеров. |
| **git-filter-repo History Scrubbing** | Очистка `.git/objects/` | **ПРИНЯТЬ** | Полное удаление следов `.env` из истории коммитов с принудительной ротацией ключей. |
| **OAuth 2.1 PKCE для Remote MCP** | Streamable HTTP 2026-07-28 | **ОТЛОЖИТЬ** | Все текущие 5 серверов Hermes/Vazus работают локально через `stdio`/`fastmcp`. Переход на remote запланирован на v5.0. |
| **Heavy GraphRAG Knowledge Bases** | Microsoft GraphRAG | **ОТКЛОНИТЬ** | GraphRAG в maintenance mode; бенчмарки 2026 показывают превосходство гибрида SQLite FTS5 + 768D векторов (sqlite-vec) по скорости (3×) и стоимости. |

---

## 5. ПЛАН ОЧИСТКИ СЕКРЕТОВ И РОТАЦИИ КЛЮЧЕЙ (WINDOWS EXECUTION RUNBOOK)

> [!CAUTION]
> Коммит `47ab20d` содержит скомпрометированные ключи. Все ключи ниже подлежат немедленной ротации у провайдеров!

### Шаг 1: Ротация скомпрометированных ключей
1. **Google Gemini API Key (`AIzaSyDlqAnL...`)**: Перейти в [Google AI Studio / GCP Console](https://aistudio.google.com/app/apikey) → Удалить старый ключ → Выпустить новый.
2. **OpenCode Go API Key (`sk-YpY9aYEM...`)**: Перейти в личный кабинет OpenCode/AgentRouter → Отозвать скомпрометированный токен.
3. **Google Jules API Key (`AQ.Ab8RN6JQH...`)**: Обновить токен в Jules Developer Settings.

### Шаг 2: Установка `git-filter-repo` в виртуальное окружение
```powershell
C:\vazus\.venv\Scripts\pip.exe install git-filter-repo
```

### Шаг 3: Полная очистка истории Git от файла `.env`
```powershell
# 1. Создать резервную копию репозитория
Copy-Item -Path "C:\vazus" -Destination "C:\vazus_backup_pre_scrub" -Recurse

# 2. Выполнить перезапись истории
git -C C:\vazus filter-repo --path .env --invert-paths --force

# 3. Проверить, что файл полностью исчез из истории
git -C C:\vazus log --all --oneline -- .env
# Ожидаемый вывод: [ПУСТО]

# 4. Выполнить сборку мусора Git
git -C C:\vazus reflog expire --expire=now --all
git -C C:\vazus gc --prune=now --aggressive
```

---

## 6. СПИСОК «НЕ ТРОГАТЬ» (СТАБИЛЬНЫЕ И ХРУПКИЕ КОМПОНЕНТЫ)

1. **`vazus_core/embeddings.py` (768-dim Unified Embedding Engine)**:
   - *Почему:* Реализует многоуровневый каскад OpenVINO NPU → Google GenAI → SHA256 с AVX-512 + NumPy косинусным ускорением. На нем завязана вся семантическая память `vazus.db` и `LessonMemoryBank`.
2. **`vazus_core/verification/smt_z3_verifier.py` (SMT Z3 Invariant Solver)**:
   - *Почему:* Обрабатывает AST-дерево и транслирует предикаты в формулы Z3 с контролем глубины раскрутки циклов (depth=10). Изменение сигнатур сломает Gate 3 и Concordia Jury.
3. **`vazus_core/workers/subprocess_repl.py` (Win32 Job Objects Kernel Sandbox)**:
   - *Почему:* Содержит точные бинарные структуры ctypes (`JOBOBJECT_EXTENDED_LIMIT_INFORMATION`, `IO_COUNTERS`) под Windows 11 kernel. Любое изменение типов приведет к сбою выделения памяти в песочнице.
4. **`vazus_core/memory/db.py` (WAL Connection Pooling)**:
   - *Почему:* Управляет потокобезопасными транзакциями в SQLite с режимом WAL и таймаутами блокировок для 51 таблицы.

---

## 7. РЕЗУЛЬТАТЫ ЭМПИРИЧЕСКОГО ТЕСТИРОВАНИЯ (AUDIT LOGS)

- **AST Integrity**: 112 модулей `vazus_core` проверены через `ast.parse()` — **0 синтаксических ошибок, 170 классов, 896 функций/методов**.
- **Pytest Suite**: Запущен `pytest tests/ -m "not slow" -q --tb=short` — **685 passed / 685 (100% успех)**.
- **Working Tree Secret Scan**: Просканированы все рабочие файлы (`vazus_core`, `scripts`, `tests`, `services`, `apps`, `docs`) — **0 активных утечек**.
- **EvidenceJury**: 18 staged-файлов доказаны автоматическими тестами без вызова LLM.
