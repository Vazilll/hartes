# 🚀 Развертывание Vazus SuperGraph OS на Linux через Docker

Руководство по переносу и запуску **Vazus SuperGraph OS** на любой Linux-дистрибутив (Ubuntu, Debian, Fedora, Arch Linux) с помощью Docker и Docker Compose.

---

## 📋 Предварительные требования

1. **Docker Engine & Docker Compose v2**:
   ```bash
   # Проверка наличия
   docker --version
   docker compose version
   ```
   *(Если Docker не установлен, используйте официальный скрипт: `curl -fsSL https://get.docker.com | sh`)*

2. **Ollama (Опционально, для локальных нейросетей на хосте)**:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull gemma2:9b
   ```

---

## ⚡ Быстрый старт (Запуск в 1 команду)

1. **Клонируйте репозиторий или перенесите папку проекта на Linux**:
   ```bash
   cd ~/vazus # или /opt/vazus
   ```

2. **Создайте файл окружения (при необходимости)**:
   ```bash
   cp .env.example .env
   # Укажите свои API ключи в .env при необходимости (Gemini, DeepSeek и др.)
   ```

3. **Запустите контейнер**:
   ```bash
   docker compose up -d --build
   ```

4. **Проверьте запуск и здоровье системы**:
   ```bash
   # Проверка статуса здоровья (REST API)
   curl http://localhost:8000/api/health
   # Ответ: {"status": "ok", "service": "vazus-supergraph-os", ...}

   # Просмотр логов
   docker compose logs -f vazus-os
   ```

5. **Откройте веб-дашборд**:
   Перейдите в браузере по адресу:
   👉 **http://localhost:8000** (или **http://localhost:8501**)

---

## 🏗️ Архитектура контейнера

| Компонент | Назначение | Конфигурация |
|---|---|---|
| **Базовый образ** | `python:3.12-slim-bookworm` | Минималистичный, безопасный Debian Bookworm |
| **Пользователь** | `vazus` (UID 1000 / GID 1000) | Non-root права, совпадающие с дефолтным пользователем Linux |
| **Порт 8000** | Веб-дашборд и REST API | Доступен снаружи: `http://localhost:8000` |
| **Порт 8501** | Альтернативный HTTP-порт | Доступен снаружи: `http://localhost:8501` |
| **Точки монтирования (Volumes)** | Сохранение состояния | `./services/memory` (SSOT / vazus.db)<br>`./data` (кэш, логи, модели) |
| **Связь с Ollama хоста** | `host.docker.internal:host-gateway` | Контейнер прозрачно видит локальный `ollama` на порту 11434 |
| **Graceful Shutdown** | `SIGTERM` / `SIGINT` | Автоматический `PRAGMA wal_checkpoint(TRUNCATE)` перед выходом |

---

## 💾 Управление данными (Persistent Volumes)

Все критические данные сохраняются на хосте и не теряются при пересборке или удалении контейнера:
- **`./services/memory/vazus.db`**: Каноническая SQLite база данных (SSOT).
- **`./services/memory/*.md`**: Семантическая память, профили, заметки (`USER.md`, `STUDY.md`, `FINANCE.md`, `HEALTH.md`).
- **`./data/logs/`**: Логи телеметрии и трассировки.
- **`./data/cache/`**: Временные кэши эмбеддингов и AST.

> [!NOTE]
> Если файл `vazus.db` отсутствует при первом старте, контейнер автоматически инициализирует все схемы через встроенный `init_db_schemas()`.

---

## 🤖 Подключение локальных LLM (Ollama на хосте)

Контейнер уже настроен для работы с Ollama, запущенным на вашем Linux-хосте:
- Переменная `OLLAMA_HOST=http://host.docker.internal:11434` проброшена в контейнер.
- Директива `extra_hosts: ["host.docker.internal:host-gateway"]` в `docker-compose.yml` маршрутизирует запросы на шлюз хостовой ОС.

Чтобы Ollama слушал все интерфейсы (а не только localhost):
```bash
# В конфигурации systemd для Ollama (/etc/systemd/system/ollama.service.d/override.conf):
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"

# После этого перезапустите сервис:
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

---

## 🛠️ Полезные команды для управления

- **Остановить контейнер**:
  ```bash
  docker compose down
  ```
- **Перезапустить**:
  ```bash
  docker compose restart vazus-os
  ```
- **Пересобрать образ без кэша**:
  ```bash
  docker compose build --no-cache
  docker compose up -d
  ```
- **Зайти внутрь работающего контейнера (Bash)**:
  ```bash
  docker compose exec vazus-os bash
  ```
- **Запустить верификационные тесты внутри контейнера**:
  ```bash
  docker compose exec vazus-os pytest tests/unit/test_substrate_guard.py tests/unit/test_dashboard_cognitive_tab.py
  ```
- **Запустить с дополнительными сервисами (SearXNG + Qdrant)**:
  ```bash
  docker compose --profile full up -d
  ```

---

## 🛡️ Безопасность и целостность данных

1. **Non-Root**: Все процессы внутри контейнера работают от имени пользователя `vazus` (UID 1000).
2. **SQLite WAL Safe**: При отправке сигнала остановки (`docker compose stop` или `SIGTERM`) контейнер выполняет `PRAGMA wal_checkpoint(TRUNCATE)` перед выходом, гарантируя 100% целостность транзакций `vazus.db`.
3. **Fail-Closed Substrate Guard**: Движок формальной верификации Z3 SMT проверяет инварианты при инициализации контейнера.
