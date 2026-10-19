# AGENTS.md — Vazus Personal Digital Twin Guidelines

Welcome to **Vazus**. This repository is strictly dedicated to personal life context, user memory, university studies, finances, and knowledge graph.

---

## 🎯 Scope & Boundaries
1. **Focus on Personal Context & Memory**: The single source of truth is `services/memory/vazus.db` and `study/`.
2. **Never Implement Custom SSM Models Here**: Neural network blocks and training belong strictly in `tars`.
3. **Never Implement Low-Level OS Hypervisors Here**: RAM OverlayFS, LP E-cores schedulers, and NPU driver engines belong strictly in `harnet`.
4. **Data Protection Invariant**: Never run broad `DELETE` or `DROP` queries against `services/memory/vazus.db`. All 810 transactions and 2410 insights must be preserved.
5. **Cross-Project Context Guardrail (CRITICAL)**: If the conversation in Vazus shifts to low-level hypervisors/NPU drivers (belonging to `harnet`) or neural network training/SSM architecture (belonging to `tars`), the agent MUST immediately flag the boundary crossing to the user and prevent context dilution.

