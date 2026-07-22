# Graph Report - gomcp  (2026-07-04)

## Corpus Check
- 85 files · ~72,448 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 971 nodes · 2169 edges · 44 communities (41 shown, 3 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 321 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7b2a2524`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_router_test.go|router_test.go]]
- [[_COMMUNITY_main.go|main.go]]
- [[_COMMUNITY_p2p_bridge.go|p2p_bridge.go]]
- [[_COMMUNITY_DB|DB]]
- [[_COMMUNITY_http.go|http.go]]
- [[_COMMUNITY_affect.go|affect.go]]
- [[_COMMUNITY_unified_graph.go|unified_graph.go]]
- [[_COMMUNITY_GetStateMachine|GetStateMachine]]
- [[_COMMUNITY_hermes.go|hermes.go]]
- [[_COMMUNITY_taskqueue_test.go|taskqueue_test.go]]
- [[_COMMUNITY_CallModel|CallModel]]
- [[_COMMUNITY_eventstore.go|eventstore.go]]
- [[_COMMUNITY_mythosReason|mythosReason]]
- [[_COMMUNITY_epistemic.go|epistemic.go]]
- [[_COMMUNITY_cache.go|cache.go]]
- [[_COMMUNITY_executeBash|executeBash]]
- [[_COMMUNITY_unified.go|unified.go]]
- [[_COMMUNITY_model_eval.go|model_eval.go]]
- [[_COMMUNITY_Store|Store]]
- [[_COMMUNITY_search.go|search.go]]
- [[_COMMUNITY_files.go|files.go]]
- [[_COMMUNITY_chaos.go|chaos.go]]
- [[_COMMUNITY_sessions.go|sessions.go]]
- [[_COMMUNITY_auto_journal.go|auto_journal.go]]
- [[_COMMUNITY_micro_models.go|micro_models.go]]
- [[_COMMUNITY_indexSingleFile|indexSingleFile]]
- [[_COMMUNITY_self.go|self.go]]
- [[_COMMUNITY_skills.go|skills.go]]
- [[_COMMUNITY_resources.go|resources.go]]
- [[_COMMUNITY_http_test.go|http_test.go]]
- [[_COMMUNITY_power.go|power.go]]
- [[_COMMUNITY_analyzeTool|analyzeTool]]
- [[_COMMUNITY_sessionSearch|sessionSearch]]
- [[_COMMUNITY_backupTool|backupTool]]
- [[_COMMUNITY_circuitBreaker|circuitBreaker]]
- [[_COMMUNITY_syclInferenceServerHandler|syclInferenceServerHandler]]
- [[_COMMUNITY_trajectoryCompress|trajectoryCompress]]
- [[_COMMUNITY_webFetch|webFetch]]
- [[_COMMUNITY_memoryAutoSummarize|memoryAutoSummarize]]
- [[_COMMUNITY_userModelGet|userModelGet]]
- [[_COMMUNITY_TestDeprecatedHelpers|TestDeprecatedHelpers]]
- [[_COMMUNITY_MEMORY|MEMORY.md]]
- [[_COMMUNITY_dntsgomcp|dnts/gomcp]]

## God Nodes (most connected - your core abstractions)
1. `DB` - 34 edges
2. `CallModel()` - 27 edges
3. `kgDB()` - 27 edges
4. `GetStateMachine()` - 20 edges
5. `classifyKeyword()` - 19 edges
6. `mythosReason()` - 15 edges
7. `vecNorm()` - 13 edges
8. `AskHandler()` - 13 edges
9. `IsToolAllowed()` - 13 edges
10. `Emit()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `CloseDB()`  [INFERRED]
  cmd/dnts-agent/main.go → tools/db.go
- `main()` --calls--> `RunCronCheckDue()`  [INFERRED]
  cmd/dnts-agent/main.go → tools/hermes.go
- `main()` --calls--> `CloseDB()`  [INFERRED]
  cmd/dnts-core/main.go → tools/db.go
- `main()` --calls--> `CloseDB()`  [INFERRED]
  cmd/dnts-memory/main.go → tools/db.go
- `main()` --calls--> `CloseDB()`  [INFERRED]
  cmd/dnts-reason/main.go → tools/db.go

## Import Cycles
- None detected.

## Communities (44 total, 3 thin omitted)

### Community 0 - "router_test.go"
Cohesion: 0.05
Nodes (90): CacheSemanticSearch(), cacheData, cacheTool, findBestToolsTFIDF(), initToolIndex(), loadTFIDFCache(), saveTFIDFCache(), tokenize() (+82 more)

### Community 1 - "main.go"
Cohesion: 0.07
Nodes (43): main(), main(), main(), main(), corsMiddleware(), MCPServer, RawMessage, Request (+35 more)

### Community 2 - "p2p_bridge.go"
Cohesion: 0.07
Nodes (45): Conn, GetActiveAgent(), SetActiveAgent(), CheckApproval(), CliApprovalCheckHandler(), CliApprovalListHandler(), CliApprovalResolveHandler(), CliApprovalSubmitHandler() (+37 more)

### Community 3 - "DB"
Cohesion: 0.09
Nodes (39): Row, Stmt, DB, CloseDB(), DecryptText(), EncryptText(), getEncryptionKey(), Context (+31 more)

### Community 4 - "http.go"
Cohesion: 0.06
Nodes (46): Client, ChatMessage, deepseekResponse, deepseekUsage, callDeepSeek(), callOllamaEmbed(), callOllamaGenerate(), fetchURL() (+38 more)

### Community 5 - "affect.go"
Cohesion: 0.08
Nodes (36): AffectiveModulation(), affectReflect(), affectStatus(), affectUpdate(), GetAffectSummary(), GetModelForAffect(), CallToolRequest, CallToolResult (+28 more)

### Community 6 - "unified_graph.go"
Cohesion: 0.16
Nodes (42): AutoCycleResponse, getDBPath(), getFloatArg(), getIntArg(), CallToolRequest, ScoredNode, CallToolRequest, CallToolResult (+34 more)

### Community 7 - "GetStateMachine"
Cohesion: 0.11
Nodes (39): Phase, CallToolRequest, CallToolResult, Context, handlePhaseControl(), phaseHelp(), phaseHistory(), phaseSet() (+31 more)

### Community 8 - "hermes.go"
Cohesion: 0.10
Nodes (37): appendCronLog(), cronAdd(), cronCheckDue(), cronDelete(), cronList(), cronNextRun(), cronToggle(), getRolePrompt() (+29 more)

### Community 9 - "taskqueue_test.go"
Cohesion: 0.13
Nodes (33): Event, eventBus, Emit(), RWMutex, Subscribe(), Unsubscribe(), EventType, Task (+25 more)

### Community 10 - "CallModel"
Cohesion: 0.14
Nodes (31): CurateSessionMemory(), CallToolRequest, CallToolResult, Context, SyncWorkspaceMemory(), userModelCurate(), workspaceSync(), ModelRequest (+23 more)

### Community 11 - "eventstore.go"
Cohesion: 0.18
Nodes (24): agMessage, agentBroadcast(), agentCall(), agentPoll(), agentRegister(), CallToolRequest, CallToolResult, Context (+16 more)

### Community 12 - "mythosReason"
Cohesion: 0.16
Nodes (25): classifyComplexity(), compressReasoning(), extractConfidence(), CallToolRequest, CallToolResult, Context, loopPhase(), mythosClassify() (+17 more)

### Community 13 - "epistemic.go"
Cohesion: 0.21
Nodes (24): Belief, Doubt, curiosityReport(), doubt(), epistemicDoubt(), epistemicExplore(), epistemicKnow(), epistemicReport() (+16 more)

### Community 14 - "cache.go"
Cohesion: 0.17
Nodes (22): cachedEntryCount(), cacheDispatch(), CacheGet(), CacheInvalidate(), CacheSet(), CacheStats(), classifyQuery(), CallToolRequest (+14 more)

### Community 15 - "executeBash"
Cohesion: 0.13
Nodes (16): adaptiveBucket, adaptiveLimiter, bucket, executeBash(), CallToolRequest, CallToolResult, Context, runPython() (+8 more)

### Community 16 - "unified.go"
Cohesion: 0.34
Nodes (16): main(), delegateToAgent(), executeCommand(), getCognitiveDashboard(), getResultText(), CallToolRequest, CallToolResult, Context (+8 more)

### Community 17 - "model_eval.go"
Cohesion: 0.22
Nodes (13): EvalEntry, ftoa(), GetEvalReport(), Mutex, InitEval(), itoa(), LogCommandVerdict(), LogExtractValidation() (+5 more)

### Community 18 - "Store"
Cohesion: 0.18
Nodes (10): Store, StoreConfig, Context, Duration, Result, Rows, NewStore(), Context (+2 more)

### Community 19 - "search.go"
Cohesion: 0.25
Nodes (16): fetchPageAsMarkdown(), CallToolRequest, CallToolResult, Context, htmlToMarkdown(), removeTagBlock(), replaceTag(), searchDDG() (+8 more)

### Community 20 - "files.go"
Cohesion: 0.31
Nodes (14): cacheEntry, cacheGet(), cacheSet(), getFileInfo(), globFiles(), CallToolRequest, CallToolResult, Context (+6 more)

### Community 21 - "chaos.go"
Cohesion: 0.35
Nodes (14): callModel(), chaosConfigs(), chaosCycle(), chaosExport(), chaosRun(), chaosSubAgent(), detectEmergence(), epistemicReset() (+6 more)

### Community 22 - "sessions.go"
Cohesion: 0.33
Nodes (13): Once, Session, CallToolRequest, CallToolResult, Context, Turn, initSessionDB(), sessionAddTurn() (+5 more)

### Community 23 - "auto_journal.go"
Cohesion: 0.25
Nodes (13): appendToJournal(), AutoJournalEntry(), autoJournalHandler(), getRecentCompletedTasks(), getRecentSessions(), getSessionTurns(), CallToolRequest, CallToolResult (+5 more)

### Community 24 - "micro_models.go"
Cohesion: 0.23
Nodes (9): ErrorAction, errorPattern, MemoryDedup, ClassifyError(), GetRetryDelay(), RWMutex, jaccardSimilarity(), trigrams() (+1 more)

### Community 25 - "indexSingleFile"
Cohesion: 0.27
Nodes (11): main(), FileInfo, IndexingStats, CallToolRequest, CallToolResult, Context, indexSingleFile(), projectIndexTool() (+3 more)

### Community 26 - "self.go"
Cohesion: 0.40
Nodes (12): improvement, CallToolRequest, CallToolResult, Context, init(), loadSelfState(), saveSelfState(), selfApply() (+4 more)

### Community 27 - "skills.go"
Cohesion: 0.38
Nodes (11): skill, CallToolRequest, CallToolResult, Context, listSkills(), loadSkill(), skillCreate(), skillDelete() (+3 more)

### Community 28 - "resources.go"
Cohesion: 0.39
Nodes (11): ReadResourceRequest, ResourceContents, Context, MCPServer, handleBenchmark(), handleCurrentTime(), handleEvolution(), handleFileResource() (+3 more)

### Community 29 - "http_test.go"
Cohesion: 0.30
Nodes (11): T, TestChatMessageJSONRoundtrip(), TestDeepseekCostConstants(), TestDeepSeekResponse(), TestDeepSeekUsageJSON(), TestDeepSeekUsageZeroCache(), TestLocalCostPerToken(), TestOllamaRequestJSON() (+3 more)

### Community 30 - "power.go"
Cohesion: 0.35
Nodes (9): CallToolRequest, CallToolResult, Context, SetKeepAwake(), SetProcessAffinity(), SetProcessPriority(), systemKeepAwake(), systemSetAffinity() (+1 more)

### Community 31 - "analyzeTool"
Cohesion: 0.68
Nodes (7): analyzeProjectHealth(), analyzeTool(), detectTechDebt(), CallToolRequest, CallToolResult, Context, suggestImprovements()

### Community 32 - "sessionSearch"
Cohesion: 0.54
Nodes (7): CallToolRequest, CallToolResult, Context, sessionFork(), sessionSearch(), sessionSummarize(), summarizeStr()

### Community 33 - "backupTool"
Cohesion: 0.67
Nodes (6): backupData(), backupList(), backupTool(), CallToolRequest, CallToolResult, Context

### Community 34 - "circuitBreaker"
Cohesion: 0.33
Nodes (5): Duration, Mutex, Time, breakerState, circuitBreaker

### Community 35 - "syclInferenceServerHandler"
Cohesion: 0.38
Nodes (6): CallToolRequest, CallToolResult, Context, prepareSYCLEnvironment(), syclInferenceServerHandler(), SYCLConfig

### Community 36 - "trajectoryCompress"
Cohesion: 0.33
Nodes (6): CallToolRequest, CallToolResult, Context, turn, summarizeText(), trajectoryCompress()

### Community 37 - "webFetch"
Cohesion: 0.40
Nodes (5): CallToolRequest, CallToolResult, Context, stripTags(), webFetch()

### Community 38 - "memoryAutoSummarize"
Cohesion: 0.53
Nodes (5): CallToolRequest, CallToolResult, Context, memoryAutoSummarize(), memoryNudge()

### Community 39 - "userModelGet"
Cohesion: 0.53
Nodes (5): CallToolRequest, CallToolResult, Context, userModelGet(), userModelUpdate()

## Knowledge Gaps
- **25 isolated node(s):** `dnts/gomcp`, `agMessage`, `MEMORYSTATUSEX`, `SYSTEM_POWER_STATUS`, `toolIndex` (+20 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CallModel()` connect `CallModel` to `router_test.go`, `DB`, `http.go`, `affect.go`, `hermes.go`, `taskqueue_test.go`, `mythosReason`, `cache.go`, `chaos.go`, `auto_journal.go`?**
  _High betweenness centrality (0.251) - this node is a cross-community bridge._
- **Why does `ollamaGenerate()` connect `http.go` to `router_test.go`, `p2p_bridge.go`, `unified_graph.go`, `hermes.go`, `CallModel`, `epistemic.go`?**
  _High betweenness centrality (0.186) - this node is a cross-community bridge._
- **Why does `handlePhoneClient()` connect `p2p_bridge.go` to `http.go`, `affect.go`, `unified_graph.go`?**
  _High betweenness centrality (0.139) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `CallModel()` (e.g. with `AutoJournalEntry()` and `callModel()`) actually correct?**
  _`CallModel()` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `kgDB()` (e.g. with `handlePhoneClient()` and `HandlePhoneMemorySync()`) actually correct?**
  _`kgDB()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `dnts/gomcp`, `agMessage`, `MEMORYSTATUSEX` to the rest of the system?**
  _25 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `router_test.go` be split into smaller, more focused modules?**
  _Cohesion score 0.05170441546556852 - nodes in this community are weakly interconnected._