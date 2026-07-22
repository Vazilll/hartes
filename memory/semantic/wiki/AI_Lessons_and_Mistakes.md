# Память об ошибках и правилах

Здесь ИИ сохраняет выводы, чтобы не повторять ошибки в будущих сессиях.

- **[2026-05-24 03:58]**: Создан центральный оркестратор C:\dnts\bin\godmode.py, объединяющий Whisper STT, Edge TTS, screen_vision (LFM), SOM (Windows UIA), hwmon (PowerShell) и LLM (локальный llama-server + внешний deepseek-v4-flash). Режимы: command, voice, screen, monitor, status, learn, recall, improve, react, interactive. Точка входа: godmode.cmd + dnts godmode из dnts.cmd. Все компоненты проверены и работают. ...
- **[2026-05-24 04:09]**: Code Intelligence System (code_intel.py) created at C:\dnts\bin\code_intel.py. Supports 4 commands: review (git pre-commit check), analyze (file/dir analysis), improve (suggest + apply fixes), learn (index code patterns). Uses opencode-go API with local llama-server fallback. Integrates with dnts-memory for pattern storage. Git pre-commit hook installed at C:\dnts\.git\hooks\pre-commit. Batch wrapper at C:\dnts\bin\code_intel.cmd.
- **[2026-05-24 04:30]**: ## Vision Pipeline Benchmark Results (2026-05-24)

**Цель:** Accelerate vision inference to <5s on CPU-only (Intel Core Ultra 5 125U, 16GB).

**Система:** llama-server.exe with LFM2.5-VL-450M-Q4_0.gguf on port 8081. screen_vision.py does screenshot → resize → base64 → OpenAI API call.

**Ключевые находки:**
1. **Resize is #1:** 640→320px reduces image tokens 285→122, giving 2.6× speedup (3.6s→1.4s). This is the single biggest win.
2. **Не форсиров...
- **[2026-05-24 04:39]**: MCP серверы из экосистемы Model Context Protocol: правильные npm имена пакетов — @modelcontextprotocol/server-sequential-thinking, @modelcontextprotocol/server-filesystem, @modelcontextprotocol/server-puppeteer (deprecated), @modelcontextprotocol/server-brave-search (требует BRAVE_API_KEY). Fetch аналог: fetch-mcp (npm-пакет). SQLite: pip install mcp-server-sqlite. Пакеты @anthropic-ai/* больше не публикуются ...
- **[2026-05-24 04:43]**: Added 4 more MCP servers to Hermes config at C:\Users\Vaz\.hermes\config.yaml:
- playwright (@playwright/mcp v0.0.75) - command: playwright-mcp, browser automation with 20+ tools
- github (@iflow-mcp/server-github v0.6.2) - command: mcp-server-github, GitHub API (requires GITHUB_TOKEN env var), 20+ tools
- time (@guanxiong/mcp-server-time v1.0.0) - command: mcp-server-time, time/date with timezone support, 2 tools
- desktop-commander (@wonderwhy-er/desktop-commander v0.2.41) - command: desktop...
- **[2026-05-25 14:19]**: AI Zoo 2026 Integration Pattern: When integrating features from other AI agents into Hermes, use a layered approach: (1) Config/skills for zero-code changes (personality, hooks), (2) Python scripts for automation (pre_compact_dump, health_check), (3) Cron jobs for periodic maintenance, (4) Skill files for agent-facing protocols. The highest-ROI patterns from 6 studied projects are: Pi Agent checkpoint/rewind (safety), Multica token budget (cost control), DeerFlow hierarchical supervision (comple...
- **[2026-05-25 14:25]**: CRITICAL LESSON: Source identity hallucination. When reading files from OTHER sessions (like analysis_results.md from Antigravity brain dir) that are written in first-person ("I cloned repos", "I launched subagents"), I MUST NOT adopt that narrative as my own. The file is a REPORT, not my action log. To prevent this: (1) always verify existence of claimed files/dirs on disk before referencing them, (2) explicitly attribute context to its source ("this file was created by Antigravity on date X"),...
- **[2026-05-27 21:18]**: OCR для русского текста: EasyOCR (pip install easyocr) — 80+ языков, включая русский, работает на CPU. PaddleOCR — точнее, но сложнее установка на Windows. Tesseract 5 — через pytesseract. Для UI-скриншотов: EasyOCR даёт лучший баланс скорость/качество.

Daimon: статус ACTIVE AWAKE, CPU 64.8°C, RAM 52%, батарея 80% зарядка. Keep-Awake DISABLED — ...
- **[2026-05-27 21:39]**: Watchdog gateway check: Telegram gateway НЕ биндит HTTP порты (9090/8080). Проверка только по process detection: tasklist | grep hermes_cli. Убрать port_check из gateway_check(). Иначе watchdog будет бесконечно перезапускать gateway.
- **[2026-07-03 12:06]**: ## Hermes Agent Reliability Improvement Pack

Для повышения success rate агента с 54.5% до 80%+ нужно применить 5 улучшений:

1. **Pre-flight Path Validation** — проверять существование пути ДО вызова read_file/write_file/patch. Устраняет FileNotFoundError (9 ошибок).
2. **Web Fallback Chain** — каскад из 3 бэкендов: default web_search/web_extract → MCP web_fetch/web_research → cu...