# Vazus Quality & Lifecycle Invariants

## 1. Dead Code Prevention (Gate-5 Vulture Invariant)
- Любые неиспользуемые аргументы в сигнатурах функций, коллбэках сигналов (`SIGINT`), интерфейсах хуков и адаптерах ОБЯЗАНЫ иметь префикс нижнего подчеркивания:
  - `*_args`, `**_kwargs` вместо `*args`, `**kwargs`
  - `_sig`, `_frame` вместо `sig`, `frame`
- Это исключает ложноположительные блокировки pre-commit хука при проверке `python -m vulture --min-confidence 90`.

## 2. Context Watchdog & Lifecycle Compression
- Агент обязан учитывать пороги сторожа сессий (`ContextWatchdog`):
  - **400 шагов / 250k токенов**: статус `WARNING` — обязательная семантическая дистилляция через `handoff_generator`.
  - **800 шагов / 450k токенов**: статус `CRITICAL_COMPRESS` — принудительный хендофф и сброс сессионного контекста.

## 3. Git Worktree Isolation Standard (`-w` mode)
- Все спекулятивные мутации, рефакторинг и авто-генерация кода субагентами выполняются в изолированных Git worktrees через `AntigravityWorktreeSandbox` (`C:\vazus\scratch\worktrees`).
- Ветви `sandbox/*` верифицируются через 8 уровней `precommit_gate.py` перед слиянием в `vazus-dev`.
