# Vazus OS — User Profile (Lean Briefing Document)
# Anthropic pattern: static preferences + ADRs only. No backlogs.
# Backlog → C:\vazus\services\memory\BACKLOG.md

## Identity
- **Name**: Жуков Максим Дмитриевич (zhukov.m.d1@edu.mirea.ru)
- **University**: РТУ МИРЭА, Институт информационных технологий (ИИТ)
- **Group**: ИВБО-22-25 (2 курс, направление 09.03.01 Информатика и вычислительная техника, личный номер: 25И0566)
- **Platform**: Windows 10/11, Intel CPU + Intel Arc/iGPU (SYCL)
- **Stack**: Go (primary), Python (ML only), Intel SYCL/OpenVINO
- **IDE**: Opencode (terminal) + Antigravity (VS Code)
- **Language**: Русский

## Core Preferences
- Python → Go/Zig где критична скорость
- Privacy-first: всё локально, минимум внешних вызовов
- Obsidian для заметок
- Предпочитает действие, а не объяснения
- Нулевая толерантность к ошибкам, заглушкам и фасадам
- Видимые хуки (message, не ephemeralMessage)

## Active Architecture Decisions (ADRs)
- **PreInvocation Hook**: Progressive Disclosure, no blind AST dump, max USER.md 2000 chars
- **Memory Loop**: Anthropic pattern — Curation (stop_hook) → Write (Mem0) → JIT Retrieve (pre_invocation)
- **In-Process Memory (Zero Daemon)**: Прямой доступ к `vazus.db` (SQLite WAL, 0.1–2.3 мс) без внешних сетевых сервисов и портов. L0 Raw turns, L1 Atom memories, L2 FTS5 organic insights, интегрирован в `pre_invocation_hook.py` и `stop_hook.py`.
- **Skills**: DynamicSkillDispatcher 768D cosine, threshold 0.15
- **Suggestions**: ProactiveSuggestionEngine 768D relevance scoring, threshold 0.35
- **IPC**: SharedMemoryBus Windows Named Memory (zero-copy Go↔Python)
- **DB**: SQLite WAL 256MB MMAP + sqlite-vec 768D vectors
- **Code Intel**: cbm (C-based) primary; CKB deprecated (60-300s hangs)
- **Visibility**: hook outputs visible in chat via `message` (not ephemeralMessage)

## Hard Rules for Agent
- Никогда не создавать заглушки (stubs) или фасады
- Не отключать системы без явного согласования пользователя
- Не делать слепые дампы данных в контекст
- Не удалять файлы без проверки зависимостей (vulture + grep)
- **Учеба в МИРЭА (Педагогический суверенитет)**: Запрещено решать задачи/лабораторные/контрольные за пользователя и отдавать готовые решения по институту. Пользователь обучается сам. Агент помогает с учебой только по прямому запросу в роли Сократического тьютора (наводящие вопросы, разбор концепций, подсказка формул/ошибок). Иногда мягко напоминать о дедлайнах и долгах, чтобы не накапливались хвосты.
- **Автономный фокус агента**: Разрешено и поощряется делать всё, что НЕ связано с учебой в МИРЭА — системная инженерия, архитектура Vazus OS, парсеры и боты (Госзакупки, ИИ-салон), оптимизация производительности, фриланс.
- Полный бэклог → vazus_unified_recall("backlog") или C:\vazus\services\memory\BACKLOG.md

