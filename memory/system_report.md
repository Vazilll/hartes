# DNTS — Полный отчёт о системе
## Сгенерирован AI-агентом 2026-05-13

---

## 1. АРХИТЕКТУРА СИСТЕМЫ

### Go MCP (dnts-brain.exe)
- Бинарник: 2.9 MB (UPX-сжат с 8.1 MB)
- Инструментов: 31 + 6 MCP Resources
- SDK: mark3labs/mcp-go v0.53.0
- Роутер: TF-IDF классификация (инстантно, 0ms, без API вызовов)
- Circuit breaker: при 3 ошибках Ollama — 10s cooldown
- HTTP pool: 100 connections, 20/host
- Кеш: read_file/glob/grep (TTL 30s)
- Rate limiter: 60 req/min
- UPX сжатие: -64% размера

### MCP Конфигурация
- 4 MCP сервера: dnts-brain, dnts-mythos, sequential-thinking, codebase-graph
- Глобальный конфиг очищен (~/.config/opencode/opencode.json)

### SYCL GPU (Intel iGPU 64EU)
- Билд: C:\dnts\llama.cpp\build_sycl (minimal flags)
- GPU: Intel Graphics, 64 EU, 5558 MB, Reorder: YES
- Jamba на SYCL: prompt 102 tok/s, generation 9 tok/s
- Запуск: setvars.bat + llama-server-sycl.exe

---

## 2. МОДЕЛИ И ПРОИЗВОДИТЕЛЬНОСТЬ

### Текущие модели в Ollama
| Модель | Размер | RAM | tok/s | Контекст | Архитектура |
|--------|--------|-----|-------|----------|-------------|
| lfm2.5:1.2b (Q4_K_M) | 697 MB | ~1.2 GB | 46 | 32K | Hybrid Conv+Attn |
| lfm2.5:q4_0 | 661 MB | ~1.1 GB | 47 | 32K | Hybrid Conv+Attn |
| lfm2.5:i1-q4_0 | 698 MB | ~1.2 GB | 45 | 32K | Hybrid Conv+Attn, imatrix |
| lfm2.5:i1-q4_k_m | 731 MB | ~1.3 GB | 49 | 32K | Hybrid Conv+Attn, imatrix |
| lfm2.5:350m | 219 MB | ~0.5 GB | 74 | 32K | Hybrid Conv+Attn |
| jamba-reasoning:3b | 1.8 GB | ~3 GB | 10 | 256K | Mamba+Transformer hybrid |
| cogito:3b | 2.09 GB | ~3.5 GB | 19.9 | 128K | Llama Transformer + Reasoning |
| nomic-embed-text | 0.26 GB | — | — | — | Embeddings |

### Бенчмарки
```
По умолчанию: threads=14 → LFM 30 tok/s, Jamba 9.6 tok/s
С threads=8:  LFM 46 tok/s (+53%), Jamba 10 tok/s
SYCL GPU:     Jamba prompt 102 tok/s, generation 9 tok/s
Cogito 3B:    19.9 tok/s (быстрее Jamba, extended thinking)
```

---

## 3. ОПТИМИЗАЦИИ

### Ollama
- OLLAMA_NUM_PARALLEL=4 (глобально)
- OLLAMA_KEEP_ALIVE=-1 (модель всегда в памяти)
- OLLAMA_FLASH_ATTENTION=1
- OLLAMA_MAX_LOADED_MODELS=1
- threads=8 (оптимально для Core Ultra 5 125U)

### LFM 2.5
- Архитектура: 16 слоёв (10 conv + 6 GQA attention)
- Conv-слои = 63% модели → быстры на CPU
- Q4_0 vs Q4_K_M: на этом CPU разницы нет (~45-47 tok/s)
- i1-Q4_K_M: лучшее качество через imatrix (49 tok/s)
- Оптимум: threads=8, Q4_K_M или i1-Q4_K_M

### Jamba 3B
- Архитектура: 28 слоёв (26 Mamba + 2 Attention)
- Проблема: Ollama не имеет Mamba-ядер
- Решение: vLLM с --mamba-ssm-cache-dtype float32 (30-40 tok/s)
- Наше SYCL SSM ядро: ssm_scan.cpp (SYCL port готов)
- Speculative decoding: ×2 для Mamba моделей (из vLLM исследований)

### Cogito 3B
- Extended thinking: "Enable deep thinking subroutine." в system prompt
- 19.9 tok/s, 2.09 GB, 128K context

---

## 4. САМО-УЛУЧШЕНИЕ

- self_health: проверка build, git status
- self_scan: поиск TODO/FIXME в коде
- self_apply_patch: патч → go build → откат при ошибке
- self_history: история изменений в evolution.json

---

## 5. НЕДОСТАЮЩЕЕ (TODO)

### P0
- Zig порт (mcp-zig, 131 KB)
- vLLM + mamba-ssm для Jamba (×3-4 ускорение)
- pramukta/llama.cpp-sycl-for-mamba (зрелая SYCL Mamba поддержка)

### P1
- Кеширование TF-IDF на диск (сделано)
- Middleware аудит (сделано)
- Circuit breaker (сделано)
- Больше поисковых движков (arXiv, PubMed, GitHub — скрипты готовы)

### P2
- Prometheus метрики
- Ротация evolution.json
- Авто-заполнение JOURNAL.md

---

## 6. КЛЮЧЕВЫЕ ФАЙЛЫ

```
C:\dnts\
├── gomcp\dnts-brain.exe           — Go MCP сервер (2.9 MB)
├── opencode.json                  — MCP конфиг для OpenCode
├── .mcp.json                      — MCP конфиг для Claude Code
├── AGENTS.md                      — инструкции для AI
├── BACKLOG.md                     — задачи
├── JOURNAL.md                     — дневник сессий
├── llama.cpp\build_sycl\bin\      — SYCL бинарники
├── bin\llama-server-sycl.exe      — SYCL llama-server (10.3 MB)
├── scripts\
│   ├── brain_service.py           — Python (legacy, ML fallback)
│   ├── mythos_reasoning.py        — Deep reasoning с RAG
│   ├── deep_research_v2.py        — Multi-search research
│   ├── search_prod.py             — arXiv+GitHub+Wikipedia+DDG
│   └── download_lfm.py            — Загрузчик моделей
├── memory\
│   ├── graph.json                 — Граф знаний
│   ├── evolution.json             — История самоулучшений
│   ├── tfidf_cache.json           — TF-IDF кеш (12.4 KB)
│   └── benchmark_baseline.json   — Бенчмарк до/после
└── config\
    └── mcp_servers.json           — Legacy MCP конфиг
```
