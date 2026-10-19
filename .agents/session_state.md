# Active Session State (Delta Sigma)
- [INVARIANT]: vazus.db strictly read-only for broad deletes; 810 transactions and 2552+ insights must remain preserved.
- [INVARIANT]: Meteor Lake target: Intel Core Ultra 5 125U (2P+8E+2LPE). No -mavx512. AVX2/x86-64-v3 only.
- [INVARIANT]: Background tasks scheduled on LP E-cores via scx_lavd.
- [INVARIANT]: Strict security guard: Never request, echo, or write sudo passwords in chat, scripts, or commit logs.
- [INVARIANT]: Cross-project boundary: Vazus is strictly for personal memory, university studies, finances, and knowledge graph (no hypervisors or custom SSM training).
- [DECISION]: Ponytail standard: minimal diff, Python standard library first, zero boilerplate, YAGNI.
