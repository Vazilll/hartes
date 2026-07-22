# DNTS — Autonomous AI System

> DNTS v3.0 — Go MCP сервер, 44 инструмента, без Python

## Статус

✅ **MCP Server работает** — 44 инструмента в одном Go бинарнике
✅ **Ollama + llama.cpp интегрированы**
✅ **Mythos Reasoning + RAG FTS5 + Graph Memory**

## Быстрый старт

```bash
cd gomcp
dnts-brain.exe
```

## Структура проекта

```
dnts/
├── gomcp/              # Go MCP сервер (dnts-brain.exe)
│   ├── cmd/            # entrypoint
│   ├── internal/       # tools, middleware, server
│   ├── go.mod
│   └── main.go
├── bin/                # llama.cpp и другие бинарники
├── build/              # скрипты сборки
├── config/             # конфигурации
├── docs/               # документация
├── memory/             # память (graph, RAG, Obsidian)
├── models/             # GGUF модели
├── skills/             # skill definitions
├── opencode.json       # MCP конфиг для opencode
└── .mcp.json           # MCP конфиг для Claude Code
```

## Требования

- Go 1.22+
- Ollama (локально, для LLM)
- LM Studio (опционально)

## Ссылки

- [MCP Spec](https://spec.modelcontextprotocol.io)
- [Ollama](https://ollama.ai)
