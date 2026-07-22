# Rate Limiting + Audit Trail — Design & Plan

## P1 #2 — dnts-agent MCP Server

> **Context:** Dario Amodei (Anthropic CEO) — «скорость AI = главная опасность».
> dnts-agent обрабатывает agent-to-agent вызовы через MCP.
> Нужен rate limiting на количество вызовов между агентами в минуту
> и полный audit trail с timestamp.

---

## 1. Текущая архитектура (что есть сейчас)

### 1.1. Общая структура

```
C:\vazus\pyenv\gomcp\
├── main.go                         # dnts-brain (основной MCP сервер, 22–93 tools)
├── cmd/
│   └── dnts-agent/
│       └── main.go                 # dnts-agent (6 tools, фокус на агентов)
├── tools/
│   ├── middleware.go               # PhaseGuardMiddleware + LoggingMiddleware
│   ├── security.go                 # token bucket rate limiter (не подключён)
│   ├── breaker.go                  # circuit breaker для Ollama/DeepSeek/SearXNG
│   ├── events.go                   # in-memory event bus
│   ├── eventstore.go               # persistence events → SQLite
│   ├── antigravity.go              # agent_register, agent_call, agent_poll, agent_broadcast
│   ├── agent_router.go             # ProxyToHermes, GetActiveAgent
│   ├── profiles.go                 # RegisterAgent() — 6 tools для dnts-agent
│   ├── register_agent.go           # RegisterAgentTools() — расширенный набор для dnts-brain
│   ├── db.go                       # SQLite schema (C:\vazus\memory\dnts.db)
│   ├── states.go                   # Phase state machine
│   └── phase_control.go            # phase_control tool
```

### 1.2. dnts-agent (cmd/dnts-agent/main.go) — 6 tools

| Tool | Описание |
|------|----------|
| `delegate_to_agent` | Делегирование задачи суб-агенту |
| `schedule_task` | Планирование отложенной задачи |
| `task_create` | Создание задачи в очереди |
| `task_list` | Просмотр задач |
| `task_claim` | Взять задачу в работу |
| `task_done` | Завершить задачу |

**Middleware chain (порядок важен):**
1. `PhaseGuardMiddleware()` — контроль доступа по фазе
2. `LoggingMiddleware()` — лог вызовов в stdout

### 1.3. Что УЖЕ есть (но не используется или не доделано)

#### Существующий rate limiter (`security.go`)
```go
type tokenBucketRL struct {
    buckets  map[string]*bucket
    refill   int64    // 1 token/sec
    capacity int64    // 60 tokens burst
}

func checkRateLimit(key string) error { ... }
```
- ✅ Token bucket алгоритм (правильный)
- ✅ Per-key buckets с авто-очисткой (5 мин бездействия)
- ❌ **Не подключён ни к одному middleware** — функция существует, но никто её не вызывает
- ❌ Ключ — произвольная строка, нет привязки к agent_id
- ❌ Нет конфигурации (hardcoded 60/1)
- ❌ Нет различия между типами вызовов (agent_call vs task_create)

#### Существующий audit-лог (`middleware.go` — LoggingMiddleware)
- ✅ Логирует все tool calls в stdout с `[AUDIT]` префиксом
- ✅ Содержит: имя тула, аргументы (truncated), execution time, success/failure
- ❌ **Не пишет в SQLite/event store** — только stdout, теряется при рестарте
- ❌ Нет привязки к agent_id
- ❌ Нет поиска/фильтрации по истории

#### Существующий Event Store (`eventstore.go`)
- ✅ `StoreEvent()` пишет в `events` таблицу SQLite
- ✅ `GetEvents()` — выборка по типу и лимиту
- ❌ Никто не вызывает `StoreEvent()` для audit-лога tool calls
- ❌ Нет поля `tool_name`, `execution_time_ms`, `success` в схеме

### 1.4. SQLite схема (существующие relevant таблицы)

```sql
-- Events store (используется только для кастомных событий, не для audit)
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,           -- 'agent_call', 'agent_registered', etc.
    agent_id TEXT DEFAULT 'dnts-brain',
    payload TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

-- Agent messages (AntiGravity)
CREATE TABLE agent_messages (
    id TEXT PRIMARY KEY,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending/delivered/processed
    created_at TEXT DEFAULT (datetime('now'))
);
```

---

## 2. Rate Limiting — Design

### 2.1. Принцип

Каждый **agent_id** получает свой token bucket. Bucket'ы делятся по **типу вызова**:

| Тип | Rate limit | Burst | Обоснование |
|-----|-----------|-------|-------------|
| `agent_call` | 30/min | 10 | Прямые вызовы между агентами — основной канал |
| `agent_poll` | 60/min | 20 | Поллинг — должен быть щедрее, чтобы не терять сообщения |
| `agent_broadcast` | 5/min | 3 | Широковещательные — дорогие, спам-риск |
| `task_create` | 20/min | 5 | Создание задач — не чаще, чем можно обработать |
| `delegate_to_agent` | 10/min | 3 | Делегирование — дорогая операция |
| `task_claim` | 30/min | 10 | Взятие задач |
| `task_done` | 60/min | 20 | Завершение — частое |
| `schedule_task` | 5/min | 2 | Планирование — редко |
| `*` (все прочие) | 60/min | 10 | Защита от спама |

### 2.2. Алгоритм

**Token bucket** (уже есть в `security.go`, нужно расширить):

```
бакет[agent_id:tool_type]
    tokens: количество доступных токенов
    last_refill: unix timestamp последнего пополнения
    capacity: max tokens (burst)
    refill_rate: токенов в секунду
```

Отличие от текущего: нужно добавить **tool-type-aware refill rate** и agent_id как часть ключа.

### 2.3. Конфигурация (предлагаемая)

Через environment variables:

```env
DNTS_RATE_LIMIT_ENABLED=true
DNTS_RATE_LIMIT_CALL_CAPACITY=30
DNTS_RATE_LIMIT_CALL_REFILL=0.5    # 30/min = 0.5/sec
DNTS_RATE_LIMIT_POLL_CAPACITY=60
DNTS_RATE_LIMIT_POLL_REFILL=1.0    # 60/min
DNTS_RATE_LIMIT_BROADCAST_CAPACITY=5
DNTS_RATE_LIMIT_BROADCAST_REFILL=0.083  # 5/min
```

Также через существующий KV store в SQLite для runtime adjustments без рестарта.

### 2.4. RateLimitMiddleware

Новый middleware, встраивается в цепочку:

```go
func RateLimitMiddleware() server.ServerOption {
    return server.WithToolHandlerMiddleware(func(next server.ToolHandlerFunc) server.ToolHandlerFunc {
        return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
            name := req.Params.Name

            // Определяем agent_id (из аргументов или контекста)
            agentID := req.GetString("agent_id", "")
            if agentID == "" {
                agentID = "anonymous"
            }

            // Определяем тип лимита для этого тула
            limitType := getRateLimitType(name)

            // Проверяем лимит
            if err := checkAgentRateLimit(agentID, limitType); err != nil {
                log.Printf("[RATE_LIMIT] BLOCKED: %s/%s — %v", agentID, name, err)
                return mcp.NewToolResultError(fmt.Sprintf(
                    "⏳ Rate limit exceeded for %s. Please wait before retrying.", limitType)), nil
            }

            return next(ctx, req)
        }
    })
}
```

### 2.5. Интеграция с circuit breaker

При rate limit exceeded > N раз подряд для одного agent_id → открывать circuit breaker
(используя существующий `breaker.go`), чтобы не тратить ресурсы на спамера.

---

## 3. Audit Trail — Design

### 3.1. Требования

1. **Каждый вызов инструмента** пишется в БД
2. **Timestamp** — точность до миллисекунды
3. **Agent ID** — кто вызвал
4. **Tool name** — какой инструмент
5. **Arguments** — sanitized (пароли/ключи скрыты)
6. **Result** — success/failure + error message
7. **Duration** — сколько времени заняло
8. **IP/Source** — откуда пришёл вызов (если HTTP mode)
9. **Searchable** — по agent_id, tool_name, timerange

### 3.2. Новая SQLite таблица

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL DEFAULT 'anonymous',
    tool_name TEXT NOT NULL,
    arguments TEXT DEFAULT '{}',       -- sanitized JSON
    result_status TEXT NOT NULL DEFAULT 'ok',  -- ok/error/rate_limited
    result_error TEXT DEFAULT '',
    duration_ms INTEGER DEFAULT 0,
    ip_address TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_tool ON audit_log(tool_name);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_log(result_status);
```

### 3.3. AuditMiddleware

Замена/расширение существующей `LoggingMiddleware`:

```go
func AuditMiddleware() server.ServerOption {
    return server.WithToolHandlerMiddleware(func(next server.ToolHandlerFunc) server.ToolHandlerFunc {
        return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
            start := time.Now()
            name := req.Params.Name
            agentID := resolveAgentID(req)

            // Sanitize arguments
            sanitized := sanitizeArgs(name, req.GetArguments())

            result, err := next(ctx, req)
            elapsed := time.Since(start)

            // Определяем статус
            status := "ok"
            var errMsg string
            if err != nil {
                status = "error"
                errMsg = err.Error()
            } else if result != nil && result.IsError {
                status = "error"
                errMsg = result.Text // MCP error text
            }

            // Пишем в SQLite (async, не блокируем ответ)
            go storeAuditEntry(agentID, name, sanitized, status, errMsg, elapsed.Milliseconds())

            // Также stdout лог (быстрая диагностика)
            log.Printf("[AUDIT] %s/%s %s (%dms)", agentID, name, status, elapsed.Milliseconds())

            return result, err
        }
    })
}
```

### 3.4. Sanitization правил

| Tool | Что скрываем |
|------|-------------|
| `agent_call` | `content` > 200 символов → truncated |
| Любой tool с `password`/`key`/`token`/`secret` в имени поля | Полное скрытие `[REDACTED]` |
| `execute_bash`/`execute_command` | `command` → `[hidden]` |
| Все остальные поля | Truncate > 500 chars |

### 3.5. Audit query tools

Новые MCP tools для просмотра audit лога:

```go
// audit_search — поиск по audit_log
s.AddTool(mcp.NewTool("audit_search",
    mcp.WithDescription("Search audit log. Filters: agent_id, tool_name, status, timerange."),
    mcp.WithString("agent_id", ...),
    mcp.WithString("tool_name", ...),
    mcp.WithString("status", ...),       // ok/error/rate_limited
    mcp.WithString("since", ...),        // ISO datetime or relative: 1h, 24h, 7d
    mcp.WithNumber("limit", ...),
), auditSearch)

// audit_stats — статистика по audit_log
s.AddTool(mcp.NewTool("audit_stats",
    mcp.WithDescription("Audit log statistics: calls per tool, error rates, rate limit hits."),
), auditStats)
```

### 3.6. Retention

- Audit log хранится **7 дней** по умолчанию
- Configurable через `DNTS_AUDIT_RETENTION_DAYS`
- Фоновый cleanup раз в час:
  ```sql
  DELETE FROM audit_log WHERE created_at < datetime('now', '-7 days');
  ```

---

## 4. План изменений (по файлам)

### Phase 1: Базовая инфраструктура (core)

| Файл | Изменение |
|------|-----------|
| `tools/middleware.go` | Добавить `RateLimitMiddleware()` + переименовать `LoggingMiddleware` → `AuditMiddleware` (или добавить параллельно) |
| `tools/security.go` | Расширить `checkRateLimit` → `checkAgentRateLimit(agentID, limitType)`: tool-type-aware refill, configurable capacity через env/KV |
| `tools/db.go` (sqliteSchema) | Добавить `CREATE TABLE IF NOT EXISTS audit_log (...)` |
| `tools/eventstore.go` | Добавить `StoreAuditEntry()` — быстрый INSERT в audit_log |
| `cmd/dnts-agent/main.go` | Добавить `RateLimitMiddleware()` в цепочку middleware |

### Phase 2: Audit tools + utilities

| Файл | Изменение |
|------|-----------|
| `tools/audit.go` (NEW) | `auditSearch`, `auditStats` tools + `storeAuditEntry()` helper |
| `tools/profiles.go` (RegisterAgent) | Добавить регистрацию `audit_search`, `audit_stats` тулов |
| `tools/helpers.go` | Добавить `resolveAgentID(req)`, `sanitizeArgs(name, args)` |
| `tools/breaker.go` | Добавить `rateLimitBreaker` — открывается при N rate limit hits для agent_id |

### Phase 3: Cron + retention

| Файл | Изменение |
|------|-----------|
| `cmd/dnts-agent/main.go` | Добавить retention cleanup в существующий cron ticker |
| `tools/audit.go` | Добавить `auditRetentionCleanup()` |

### Phase 4: dnts-brain integration

| Файл | Изменение |
|------|-----------|
| `main.go` | Добавить те же middleware (RateLimit + Audit) в dnts-brain |
| `tools/register.go` | Зарегистрировать audit tools для full mode |
| `tools/unified.go` | Зарегистрировать audit tools для unified mode |

---

## 5. Ordering of middleware (critical)

Порядок в цепочке имеет значение:

```
1. PhaseGuardMiddleware    → проверка фазы (самая быстрая, блокирует рано)
2. RateLimitMiddleware     → проверка лимитов (дешёвая, до исполнения)
3. AuditMiddleware         → логирование вызова + результата
```

**Почему Audit последний:** он должен видеть результат выполнения (включая ошибки от PhaseGuard и RateLimit), чтобы залогировать даже заблокированные вызовы.

---

## 6. Rate limit headers в ответах

Каждый rate limited ответ должен содержать информацию для клиента:

```
⏳ Rate limit exceeded for agent_call
   Retry after: 12 seconds
   Limit: 30 calls per minute
   Remaining: 0
   Reset at: 14:32:05
```

Это реализуется через текстовый `mcp.NewToolResultError()` сообщение.

---

## 7. Metrics & monitoring

В существующий `get_cognitive_dashboard` добавить секцию:

```
## Rate Limits
- Active buckets: 12
- Blocked calls (1h): 3
- Top blocked agents: hermes (2), unknown (1)
- Audit log size: 1,234 entries (last 7d: 8,901)

## Rate Limit by Tool
- agent_call: 28/30 used (93%)
- agent_poll: 12/60 used (20%)
- agent_broadcast: 3/5 used (60%)
```

---

## 8. Security considerations

1. **Rate limit bypass**: agent_id берётся из аргументов вызова — возможна подмена.
   - Решение: в MCP контексте добавить аутентификацию агента (server session identity).
   - Interim: логгировать заявленный agent_id + IP, но доверять с осторожностью.

2. **Audit log poisoning**: если агент шлёт гигантские аргументы.
   - Решение: truncation + ограничение размера записи (arguments TEXT capped at 2000 chars).

3. **Rate limit as DoS vector**: злоумышленник вызывает дорогие тулы, чтобы исчерпать лимит легитимного агента.
   - Решение: per-agent-type pools (не делить общий bucket между агентами).

4. **Audit log storage**: SQLite может расти.
   - Решение: retention policy + WAL mode (уже включён).

---

## 9. Estimated effort

| Phase | Файлы | Строк кода | Сложность |
|-------|-------|-----------|-----------|
| 1 | 5 | ~120 | Low |
| 2 | 3 (1 new) | ~200 | Low |
| 3 | 2 | ~40 | Trivial |
| 4 | 3 | ~30 | Trivial |
| **Total** | **~13** | **~390** | **Low** |

---

## 10. Summary

**Что меняется:**
1. ✅ Существующий token bucket (`security.go`) расширяется на per-agent + per-tool-type
2. ✅ Новый `RateLimitMiddleware()` подключается в `cmd/dnts-agent/main.go`
3. ✅ Существующий stdout audit (`LoggingMiddleware`) дополняется SQLite persistence
4. ✅ Новая таблица `audit_log` + `audit_search`/`audit_stats` tools
5. ✅ Retention cleanup через существующий cron ticker
6. ✅ Интеграция rate limit stats в cognitive dashboard
7. ✅ Circuit breaker для повторных rate limit violations

**Чего НЕ делаем:**
- Не переписываем существующие middleware — только добавляем
- Не меняем API существующих tools — только новые (`audit_search`, `audit_stats`)
- Не добавляем внешних зависимостей — только стандартная библиотека + существующий SQLite

**Ключевой принцип:** Rate limit должен блокировать ДО выполнения тула.
Audit должен логгировать ПОСЛЕ (включая факт блокировки rate limit-ом).
