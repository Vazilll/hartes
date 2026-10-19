---
id: open_deep_researcher
title: "Open Deep Researcher Subagent Specification"
date: "2026-09-04"
domain: subagent_research
tags:
  - iad
  - zettel
  - subagent
  - open_deep_researcher
  - research
status: VERIFIED
sources:
  - "subagent_research_bridge.py"
  - "vazus_core/subagents/open_deep_researcher.py"
---

# Open Deep Researcher Subagent Specification

> **Canonical Hub**: [[open_deep_researcher_Memory_Hub]]  
> **Architecture**: [[SuperGraph_OS_Architecture]]  
> **Status**: `VERIFIED`  

## 📌 Subagent Mission
The `open_deep_researcher` subagent conducts autonomous, grounded web and multi-source research using LangGraph workflows and Google Search Grounding with SearXNG fallback.

## Key Capabilities
- Multi-turn research planning (`__start__` -> `write_research_brief` -> `research_supervisor` -> `final_report_generation`).
- Autonomous query decomposition and parallel search worker dispatch.
- Citation synthesis with grounded verification against hallucination (`grounding == 1.0`).

## Linked Memory Nodes
- [[open_deep_researcher_Memory_Hub]]
- [[Research_SuperGraph_OS_Architecture]]
- [[SuperGraph_OS_Architecture]]
- [[verifier_worker]]
- [[rlm_code_engineer]]
