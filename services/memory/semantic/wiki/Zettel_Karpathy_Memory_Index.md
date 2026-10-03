---
id: Zettel_Karpathy_Memory_Index
title: "Karpathy Semantic & Episodic Memory Index"
date: "2026-09-04"
domain: memory_index
tags:
  - iad
  - zettel
  - karpathy_memory
  - semantic_memory
  - lessons
status: VERIFIED
sources:
  - "AI_Lessons_and_Mistakes.md"
  - "vazus_core/memory/zettelkasten_exporter.py"
  - "services/memory/vazus.db"
---

# Karpathy Semantic & Episodic Memory Index

> **Primary Knowledge Base**: [[AI_Lessons_and_Mistakes]]  
> **SuperGraph Hub**: [[Zettel_SuperGraph_Hub]]  
> **Architecture**: [[SuperGraph_OS_Architecture]]  
> **Status**: `VERIFIED`  

---

## 🧠 Karpathy Memory Architecture
Following the Karpathy Memory Wiki paradigm, all agent experiences, runtime defects, and architectural decisions are compiled into structured, human-readable, and machine-searchable markdown documents.

## Key Memory Segments
1. **Lessons & Failure Patterns**: Cataloged in [[AI_Lessons_and_Mistakes]], capturing root causes, remediation strategies, and preventive constraints.
2. **Episodic Knowledge Base**: Stored in `vazus.db` (`reflexion_lessons`, `mem0_facts`) and retrieved JIT to prevent repeating known errors.
3. **Continuous Evaluation Flywheel**: Documented in [[agent_eval_quality_flywheel]] and [[Zettel_Continuous_Agent_Self_Improvement_Flywheel]].

## Linked SuperGraph Nodes
- [[AI_Lessons_and_Mistakes]]
- [[Zettel_SuperGraph_Hub]]
- [[SuperGraph_OS_Architecture]]
- [[agent_eval_quality_flywheel]]
- [[ADR_005_CONTINUOUS_AGENT_SELF_IMPROVEMENT_FLYWHEEL]]
