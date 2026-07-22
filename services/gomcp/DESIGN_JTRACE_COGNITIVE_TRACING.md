# J-Trace: Cognitive Tracing for Go MCP (dnts-core) — Design & Plan

## P1 #1 — Multi-Agent Cognitive Trace

> **Context:** Amodei's Claude J-space (mental workspace) — когнитивный трейсинг multi-agent
> решений. Нужен JSON-лог внутренних состояний multi-agent с полной цепочкой решений,
> размышлений, вызовов инструментов и переходов фаз.

---

## 1. Текущая архитектура (что есть сейчас)

### 1.1. Общая структура

```
C:\vazus\pyenv\gomcp\
├── main.go                         # dnts-brain (основной MCP сервер, 22–93 tools)
├── cmd/
│   ├── dnts-core/main.go           # DNTS Core (8 tools, focused profile)
│   ├── dnts-agent/main.go          # Agent-to-agent MCP сервер
│   ├── dnts-memory/main.go         # Memory layer MCP сервер
│   └── dnts-reason/main.go         # Reasoning MCP сервер
├── tools/
│   ├── register.go                 # RegisterAll() / RegisterUnified() — 12-22 tools
│   ├── register_agent.go           # agent tools (делегация, task queue, cron)
│   ├── register_system.go          # system tools
│   ├── register_files.go           # file I/O tools
│   ├── register_search.go          # search tools
│   ├── register_memory.go          # memory tools
│   ├── register_kg.go              # knowledge graph tools
│   ├── register_session.go         # session tools
│   ├── register_self.go            # self tools
│   ├── register_approval.go        # CLI approval tools
│   ├── register_semantic.go        # semantic graph tools
│   ├── register_p2p.go             # P2P bridge tools
│   ├── register_daimon.go          # Daimon bridge tools
│   ├── register_skills.go          # skill management tools
│   ├── register_infra.go           # events/cache/backup tools
│   ├── register_reason.go          # reasoning tools
│   ├── profiles.go                 # RegisterCore() — focused server profiles
│   ├── middleware.go               # PhaseGuardMiddleware + LoggingMiddleware
│   ├── states.go                   # Phase state machine (plan/implement/verify/done)
│   ├── phase_control.go            # Phase control tool handler
│   ├── router.go                   # Tool registry + AskHandler + intent classification
│   ├── agent_router.go             # Agent selection + Hermes proxy
│   ├── orchestrator.go             # Auto-delegation + self-healing
│   ├── events.go                   # In-memory event bus
│   ├── eventstore.go              # SQLite event sourcing (StoredEvent)
│   ├── trajectory.go              # Session turn compression
│   ├── db.go                       # DB wrapper (CQRS, encryption, schema init)
│   └── resources.go               # MCP resource handlers
└── internal/
```

### 1.2. Уже существующие механизмы логирования

| Механизм | Что логирует | Формат | Проблема |
|----------|-------------|--------|----------|
| **LoggingMiddleware** | Имя tool + аргументы + длительность + OK/FAIL | `[AUDIT] tool(args) OK (5ms)` | Плоский, без структуры, только stderr |
| **PhaseGuardMiddleware** | Блокировки по фазе | `[PHASE_GUARD] BLOCKED: tool — reason` | Только ошибки, не logging |
| **StateMachine.history** | Переходы фаз | `PhaseTransition{from, to, tool, timestamp}` | Только смена фаз |
| **EventStore** | Все Emit() события | SQLite `events` table | payload — `map[string]string`, слабая типизация |
| **Affect Engine** | Эмоциональное состояние | `UpdateAffect(valence, arousal)` | Только affect, нет reasoning trace |
| **trajectory.go** | Компрессия turn-ов сессии | `trajectoryCompress` | Post-hoc, не real-time |

### 1.3. Архитектура multi-agent

Текущая система имеет **три уровня агентов**:

1. **Hermes / Jules / Agy** — внешние AI-агенты (3-agent pipeline)
2. **dnts-agent** — MCP сервер для agent-to-agent сообщений через SQLite `agent_messages`
3. **autoDelegateTask** (orchestrator.go) — встроенный планировщик: Planner → parallel workers → Synthesizer
4. **RLM Worker Pool** — параллельные reasoning workers

**Проблема:** Нет единого, структурированного JSON-лога, который связывал бы:
- Вызов инструмента → решение → переход фазы → внутреннее рассуждение (reasoning)
- Agent A → Agent B → ответ агента
- Планировщик → subtask → результат → синтез
- Affect → решение → результат

---

## 2. Дизайн JSON-лога J-Trace

### 2.1. Принципы

1. **Immutable — append-only.** Никаких UPDATE, только INSERT.
2. **Стандартный JSON Lines** (`.jsonl`) — каждая строка отдельный trace event.
3. **Корреляция через `trace_id`** — одна цепочка решений = один trace_id.
4. **Hierarchical spans** — parent/child отношения через `span_id` / `parent_span_id`.
5. **Привязка к реальному времени** — `timestamp` (RFC3339 наносекунды) + `phase` на момент события.
6. **Source-agnostic** — работает и для внутренних вызовов (Go), и для внешних (агенты через MCP).

### 2.2. Базовая структура события

```jsonl
{"trace_id":"7c9a...","span_id":"b3e1...","parent_span_id":"a2f4...",
 "event":"tool_call","timestamp":"2026-07-08T14:30:00.123456789Z",
 "phase":"implement","agent":"dnts-core",
 "duration_ms":1427,
 "data":{...}}
```

### 2.3. Типы событий (event types)

#### `reasoning` — внутреннее рассуждение (thinking)

```json
{
  "trace_id": "jtrace_7c9a",
  "span_id": "sp_001",
  "parent_span_id": null,
  "event": "reasoning",
  "timestamp": "2026-07-08T14:30:00.000000000Z",
  "phase": "plan",
  "agent": "dnts-brain",
  "data": {
    "model": "lfm2.5-thinking:latest",
    "provider": "ollama",
    "input_tokens": 1247,
    "output_tokens": 456,
    "reasoning_steps": [
      {"step": 1, "content": "First, I need to understand the user's request..."},
      {"step": 2, "content": "This is a file operation, so I need to check phase..."}
    ],
    "confidence": 0.85,
    "intent": "file_read"
  }
}
```

#### `tool_call` — вызов инструмента

```json
{
  "trace_id": "jtrace_7c9a",
  "span_id": "sp_002",
  "parent_span_id": "sp_001",
  "event": "tool_call",
  "timestamp": "2026-07-08T14:30:01.234000000Z",
  "phase": "implement",
  "agent": "dnts-core",
  "data": {
    "tool": "smart_search",
    "arguments": {"query": "register.go", "path": "."},
    "risk_level": 0,
    "result_summary": "Found 3 files",
    "result_tokens": 230,
    "error": null,
    "duration_ms": 1427
  }
}
```

#### `phase_transition` — смена фазы

```json
{
  "trace_id": "jtrace_7c9a",
  "span_id": "sp_003",
  "parent_span_id": "sp_001",
  "event": "phase_transition",
  "timestamp": "2026-07-08T14:30:05.000000000Z",
  "phase": "implement",
  "agent": "dnts-core",
  "data": {
    "from_phase": "plan",
    "to_phase": "implement",
    "trigger": "phase_control",
    "reason": "User requested file modification"
  }
}
```

#### `agent_delegate` — делегация агенту

```json
{
  "trace_id": "jtrace_7c9a",
  "span_id": "sp_004",
  "parent_span_id": "sp_001",
  "event": "agent_delegate",
  "timestamp": "2026-07-08T14:30:03.000000000Z",
  "phase": "plan",
  "agent": "dnts-brain",
  "data": {
    "mode": "research",
    "subtasks": [
      {"role": "analyst", "description": "Analyze register.go structure"},
      {"role": "researcher", "description": "Find all tool handlers"}
    ],
    "model_used": "deepseek-chat",
    "provider": "deepseek"
  }
}
```

#### `agent_result` — результат от агента

```json
{
  "trace_id": "jtrace_7c9a",
  "span_id": "sp_005",
  "parent_span_id": "sp_004",
  "event": "agent_result",
  "timestamp": "2026-07-08T14:30:08.000000000Z",
  "phase": "plan",
  "agent": "dnts-brain",
  "data": {
    "subtask_index": 0,
    "role": "analyst",
    "result_length": 1540,
    "result_tokens": 385,
    "success": true,
    "duration_ms": 5000
  }
}
```

#### `synthesis` — синтез результатов

```json
{
  "trace_id": "jtrace_7c9a",
  "span_id": "sp_006",
  "parent_span_id": "sp_001",
  "event": "synthesis",
  "timestamp": "2026-07-08T14:30:10.000000000Z",
  "phase": "done",
  "agent": "dnts-brain",
  "data": {
    "mode": "auto_delegate",
    "sources": ["sp_005", "sp_007"],
    "model": "deepseek-chat",
    "output_tokens": 620,
    "coherence_score": 0.92
  }
}
```

#### `affect_state` — эмоциональное состояние

```json
{
  "trace_id": "jtrace_7c9a",
  "span_id": "sp_000",
  "parent_span_id": null,
  "event": "affect_state",
  "timestamp": "2026-07-08T14:30:00.000000000Z",
  "phase": "plan",
  "agent": "dnts-brain",
  "data": {
    "valence": 0.6,
    "arousal": 0.5,
    "frustration": 0.1,
    "curiosity": 0.8,
    "urgency": 0.2,
    "summary": "STABLE ACTIVE LEARNING"
  }
}
```

#### `error` — ошибка

```json
{
  "trace_id": "jtrace_7c9a",
  "span_id": "sp_008",
  "parent_span_id": "sp_002",
  "event": "error",
  "timestamp": "2026-07-08T14:30:06.000000000Z",
  "phase": "implement",
  "agent": "dnts-core",
  "data": {
    "source": "tool_call",
    "tool": "execute_command",
    "error_type": "timeout",
    "error_message": "Command timed out after 45 seconds",
    "exit_code": -1,
    "recovery_attempted": true,
    "recovery_success": false
  }
}
```

### 2.4. Trace ID и корреляция

```
trace_id = "jtrace_" + hex(time.Now().UnixNano())[:12] + "_" + shortUUID(8)

span_id  = "sp_" + sequentialCounter

parent_span_id = span_id родительского события
               = null для корневого события (обычно affect_state или reasoning)
```

Связь trace_id через границы:
- **client → dnts-core:** через JSON-RPC request id (MCP request id = trace_id)
- **dnts-brain → agent:** через поле `trace_id` в payload agent_messages
- **orchestrator → subtask:** через parent_span_id

### 2.5. Выходные форматы

| Формат | Назначение | Путь |
|--------|-----------|------|
| **JSON Lines** (основной) | Real-time поток, log rotation | `C:\vazus\logs\jtrace\YYYY-MM-DD.jsonl` |
| **SQLite events** (зеркало) | Быстрый поиск, агрегация | `events` table в vazus.db |
| **MCP Resource** (live) | Чтение через MCP | `dnts://trace/live` (последние 100) |

---

## 3. Конкретные изменения в Go код

### 3.1. Новый файл: `tools/jtrace.go`

**Назначение:** Core-структуры для J-Trace.

```go
package tools

// TraceEventType — все типы событий трейсинга
type TraceEventType string

const (
    TraceReasoning       TraceEventType = "reasoning"
    TraceToolCall        TraceEventType = "tool_call"
    TracePhaseTransition TraceEventType = "phase_transition"
    TraceAgentDelegate   TraceEventType = "agent_delegate"
    TraceAgentResult     TraceEventType = "agent_result"
    TraceSynthesis       TraceEventType = "synthesis"
    TraceAffectState     TraceEventType = "affect_state"
    TraceError           TraceEventType = "error"
)

// ReasoningStep — один шаг рассуждения
type ReasoningStep struct {
    Step    int    `json:"step"`
    Content string `json:"content"`
}

// TraceEvent — универсальное событие трейсинга
type TraceEvent struct {
    TraceID       string          `json:"trace_id"`
    SpanID        string          `json:"span_id"`
    ParentSpanID  *string         `json:"parent_span_id,omitempty"`
    Event         TraceEventType  `json:"event"`
    Timestamp     string          `json:"timestamp"`       // RFC3339Nano
    Phase         Phase           `json:"phase"`
    Agent         string          `json:"agent"`
    DurationMs    *int64          `json:"duration_ms,omitempty"`
    Data          json.RawMessage `json:"data"`
}

// TraceStore — интерфейс для storage backend
type TraceStore interface {
    Append(evt *TraceEvent) error
    Query(traceID string, limit int) ([]*TraceEvent, error)
    Close() error
}

// JSONLTraceStore — append-only JSON Lines writer
type JSONLTraceStore struct {
    mu       sync.Mutex
    file     *os.File
    encoder  *json.Encoder
}

// SQLiteTraceStore — зеркало в events table
type SQLiteTraceStore struct {
    db *DB
}
```

**Функции:**

```go
// InitTraceStore — открывает JSONL файл на сегодня + создаёт таблицу SQLite
func InitTraceStore() error

// EmitTrace — главная точка входа: создаёт TraceEvent и пишет во все backend-ы
func EmitTrace(evt *TraceEvent)

// NewTraceID — генерирует уникальный trace_id
func NewTraceID(agent string) string
```

### 3.2. Модификация: `tools/middleware.go`

**LoggingMiddleware** расширяется до **JTraceMiddleware**:

```go
func JTraceMiddleware() server.ServerOption {
    return server.WithToolHandlerMiddleware(func(next server.ToolHandlerFunc) server.ToolHandlerFunc {
        return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
            start := time.Now()
            name := req.Params.Name

            // Создаём span для tool_call
            spanID := nextSpanID()
            traceID := extractOrCreateTraceID(ctx)

            // Reasoning step перед вызовом (опционально)
            if reasoning := getReasoningFromContext(ctx); reasoning != "" {
                EmitTrace(&TraceEvent{
                    TraceID: traceID,
                    SpanID:  nextSpanID(),
                    ParentSpanID: &spanID,
                    Event:   TraceReasoning,
                    // ...
                })
            }

            result, err := next(ctx, req)
            elapsed := time.Since(start)

            // Emit tool_call event
            EmitTrace(&TraceEvent{
                TraceID:    traceID,
                SpanID:     spanID,
                Event:      TraceToolCall,
                Timestamp:  time.Now().UTC().Format(time.RFC3339Nano),
                Phase:      GetStateMachine().Current(),
                Agent:      "dnts-core",
                DurationMs: ptr(int64(elapsed.Milliseconds())),
                Data:       buildToolCallData(name, req, result, err),
            })

            return result, err
        }
    })
}
```

### 3.3. Модификация: `tools/orchestrator.go`

Добавить EmitTrace в:

1. **autoDelegateTask** — после планирования, перед каждым subtask, после синтеза
2. **selfHealingExecute** — после выполнения, при ошибке

```go
// В autoDelegateTask:
EmitTrace(&TraceEvent{
    TraceID: traceID,
    SpanID:  spanID,
    Event:   TraceAgentDelegate,
    Data:    marshalJSON(subtasks),
})

// После каждого subtask:
EmitTrace(&TraceEvent{
    TraceID:       traceID,
    SpanID:        subSpanID,
    ParentSpanID:  &spanID,
    Event:         TraceAgentResult,
    Data:          marshalJSON(result),
})
```

### 3.4. Модификация: `tools/states.go`

В `StateMachine.Transition()` добавить EmitTrace:

```go
func (sm *StateMachine) Transition(to Phase, toolName string) error {
    // ... existing logic ...

    EmitTrace(&TraceEvent{
        TraceID:   currentTraceID,
        SpanID:    nextSpanID(),
        Event:     TracePhaseTransition,
        Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
        Phase:     to,
        Agent:     "dnts-core",
        Data:      marshalJSON(map[string]interface{}{
            "from_phase": from,
            "to_phase":   to,
            "trigger":    toolName,
        }),
    })

    return nil
}
```

### 3.5. Модификация: `tools/events.go` (affect tracking)

В `UpdateAffect()` добавить EmitTrace:

```go
func UpdateAffect(outcome string, strength float64) {
    // ... existing affect update ...

    EmitTrace(&TraceEvent{
        Event: TraceAffectState,
        Data:  marshalJSON(currentAffect),
    })
}
```

### 3.6. Новый MCP tool: `trace_query`

В `register_infra.go` или новом `register_trace.go`:

```go
s.AddTool(mcp.NewTool("trace_query",
    mcp.WithDescription("Query J-Trace cognitive trace store. Returns structured JSON events for debugging multi-agent decisions."),
    mcp.WithString("trace_id", mcp.Description("Filter by trace ID (optional)")),
    mcp.WithString("event_type", mcp.Description("Filter by event type (reasoning, tool_call, phase_transition, agent_delegate, agent_result, synthesis, error)")),
    mcp.WithNumber("limit", mcp.Description("Max events (default 50)")),
    mcp.WithString("since", mcp.Description("ISO8601 timestamp: only events after this time")),
), traceQueryHandler)
```

### 3.7. Новый MCP resource: `dnts://trace/live`

В `resources.go`:

```go
s.AddResource(mcp.NewResource(
    "dnts://trace/live",
    "Live Trace Feed",
    mcp.WithResourceDescription("Last 100 trace events in real time"),
    mcp.WithMIMEType("application/json"),
), handleTraceLive)
```

### 3.8. Активация в `cmd/dnts-core/main.go`

```go
// Инициализация
tools.InitTraceStore()

// Замена LoggingMiddleware на JTraceMiddleware
s := server.NewMCPServer("DNTS Core", "1.0.0",
    server.WithLogging(),
    tools.PhaseGuardMiddleware(),
    tools.JTraceMiddleware(),  // ← новая
)
```

---

## 4. Схема SQLite (events table extension)

Добавить в инициализацию БД (`db.go`):

```sql
CREATE TABLE IF NOT EXISTS trace_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id        TEXT NOT NULL,
    span_id         TEXT NOT NULL,
    parent_span_id  TEXT,
    event_type      TEXT NOT NULL,    -- reasoning, tool_call, phase_transition, ...
    timestamp       TEXT NOT NULL,    -- RFC3339Nano
    phase           TEXT,
    agent           TEXT DEFAULT 'dnts-core',
    duration_ms     INTEGER,
    data            TEXT,             -- JSON
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_trace_events_trace_id ON trace_events(trace_id);
CREATE INDEX idx_trace_events_event_type ON trace_events(event_type);
CREATE INDEX idx_trace_events_timestamp ON trace_events(timestamp);
```

---

## 5. План имплементации

### Фаза 1: Core (1 день)

| Шаг | Файл | Изменение |
|-----|------|-----------|
| 1 | `tools/jtrace.go` | Создать — структуры, интерфейсы, JSONL writer, SQLite writer, EmitTrace |
| 2 | `tools/middleware.go` | Добавить JTraceMiddleware; старый LoggingMiddleware оставить как fallback |
| 3 | `tools/states.go` | EmitTrace в PhaseTransition |
| 4 | `tools/db.go` | Добавить CREATE TABLE trace_events |
| 5 | `cmd/dnts-core/main.go` | InitTraceStore + JTraceMiddleware |

### Фаза 2: Multi-agent spans (1 день)

| Шаг | Файл | Изменение |
|-----|------|-----------|
| 6 | `tools/orchestrator.go` | EmitTrace в autoDelegateTask (plan, subtask start, subtask end, synthesis) |
| 7 | `tools/orchestrator.go` | EmitTrace в selfHealingExecute (error recovery) |
| 8 | `tools/events.go` | EmitTrace в UpdateAffect |
| 9 | `tools/agent_router.go` | Propagate trace_id через agent_messages |

### Фаза 3: MCP tool + resource (0.5 дня)

| Шаг | Файл | Изменение |
|-----|------|-----------|
| 10 | `tools/register_trace.go` | Создать — RegisterTraceTools (trace_query tool) |
| 11 | `tools/register.go` | Добавить RegisterTraceTools в RegisterAll / RegisterUnified |
| 12 | `tools/resources.go` | Добавить resource `dnts://trace/live` |

### Фаза 4: Log rotation + maintenance (0.5 дня)

| Шаг | Файл | Изменение |
|-----|------|-----------|
| 13 | `tools/jtrace.go` | Auto-rotate JSONL по дате, max 7 дней |
| 14 | `tools/jtrace.go` | Auto-vacuum SQLite trace_events при старте (удалить записи старше 30 дней) |

**Итого: ~3 дня.**

---

## 6. Пример полного trace (end-to-end)

```
Запрос пользователя: "найди register.go и покажи его содержимое"

trace_id: jtrace_a1b2c3d4e5f6

1. [affect_state]  valence=0.6, arousal=0.5, curiosity=0.7
2. [reasoning]     "Пользователь хочет прочитать файл. Нужно проверить фазу..."
3. [tool_call]     phase_control(action=status) → PhasePlan → OK
4. [tool_call]     smart_search(query="register.go") → Found 1 file
5. [tool_call]     read_file(path="register.go") → 12504 bytes
6. [synthesis]     "Файл найден и прочитан. Возвращаю содержимое..."
7. [affect_state]  valence=0.75, arousal=0.4 (success)

Если бы была делегация:

2b. [agent_delegate]  Planner → 2 subtasks
2c. [agent_result]    analyst: "register.go содержит RegisterAll()..."
2d. [agent_result]    researcher: "tool handlers в router.go..."
2e. [synthesis]       "Объединяю результаты..."
```

---

## 7. Метрики и мониторинг

J-Trace позволяет считать:

- **Avg reasoning depth** (среднее количество reasoning steps на trace)
- **Tool latency p50/p95/p99** (по tool name)
- **Phase transition frequency** (как часто переключаются фазы)
- **Agent delegation success rate** (сколько subtask-ов завершились успешно)
- **Recovery rate** (сколько ошибок self-healing исправил)

Эти метрики можно экспортировать через `dnts://trace/stats` resource.

---

## 8. Trade-offs и альтернативы

| Решение | Pros | Cons |
|---------|------|------|
| **JSONL + SQLite** (dual write) | Отказоустойчивость, быстрый поиск через SQL | Двойная запись, ~2x I/O |
| **Только SQLite** | Проще код, единый источник | Медленный sequential read для больших объёмов |
| **Только JSONL** | Минимальный overhead | Нет индексов, сложный поиск |
| **OTel/OpenTelemetry** | Стандарт, интеграция с Grafana | Overkill для 20MB бинарника, лишние зависимости |

**Выбор: dual-write (JSONL + SQLite).** JSONL — для streaming/rotation, SQLite — для query tool.

---

## 9. Связь с существующей архитектурой

```
J-Trace Integration Map:

middleware.go ──→ EmitTrace(tool_call) ──→ JSONL file
states.go     ──→ EmitTrace(phase_transition) ──→ SQLite events
orchestrator  ──→ EmitTrace(agent_delegate/result/synthesis)
events.go     ──→ EmitTrace(affect_state)
router.go     ──→ EmitTrace(reasoning)
                                    ↓
                           trace_query tool
                           trace/live resource
```

**Никакие существующие механизмы не ломаются.** LoggingMiddleware остаётся как fallback.
JTraceMiddleware — расширение, не замена.
