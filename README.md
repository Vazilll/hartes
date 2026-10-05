# 🌌 Vazus SuperGraph OS (v5.0)

> **Autonomous Cognitive Architecture, Formal SMT Verification Substrate & SuperGraph Knowledge Operating System**

---

## ⚡ Быстрый старт (Docker / Linux)

Для развертывания на Linux в **1 команду**:

```bash
docker compose up -d --build
```

- **Веб-дашборд**: [http://localhost:8000](http://localhost:8000) (или [http://localhost:8501](http://localhost:8501))
- **Healthcheck**: `curl http://localhost:8000/api/health`
- **Инструкция по миграции на Linux**: читайте подробное руководство в [DEPLOY_LINUX.md](file:///C:/vazus/DEPLOY_LINUX.md).

---

## 🏗️ Архитектурные уровни памяти и вычислений

1. **Layer A (Кодовая топология и AST)**:
   - Call-graph, AST-определения и анализ зависимостей через `vazus_core.engine.graphify_engine` и `vazus_core.ast_pruner`.
2. **Layer B (Семантическая память / Markdown Wiki)**:
   - Авторитетный источник памяти (SSOT) в `services/memory/` (`USER.md`, `STUDY.md`, `FINANCE.md`, `HEALTH.md`).
3. **Layer C (Структурированные данные и векторный поиск)**:
   - Реляционные таблицы и векторные индексы в `services/memory/vazus.db` (транзакции, долги, расписание, взвешивания).
4. **Formal Verification Substrate (Z3 SMT)**:
   - Математическое доказательство инвариантов безопасности и валидация действий через `vazus_core.verification.substrate_guard`.

---

## 🚀 Локальный запуск (Разработка)

```bash
# Активация виртуального окружения
source .venv/bin/activate  # на Linux
# или .\.venv\Scripts\Activate.ps1  # на Windows

# Запуск тестов
pytest tests/unit/test_substrate_guard.py tests/unit/test_dashboard_cognitive_tab.py

# Запуск веб-дашборда
python vazus_core/integrations/dashboard_server.py --port 8000
```
