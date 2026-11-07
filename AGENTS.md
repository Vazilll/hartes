# AGENTS.md — Vazus AI Training Lab Guidelines

Welcome to **Vazus (AI Training Edition)**. All operational runtime systems, personal memory (`vazus_core`, `services/memory/vazus.db`), and hypervisor blocks have been merged into **Harnet** (`/home/tarhes/Проекты/harnet`).

---

## 🎯 Scope & Boundaries
1. **Strictly AI Training & Model Architectures (`tars/`)**:
   - Focus exclusively on `tars/training/` (Mamba-2, BitNet, LoRA, Muon, DPO, RLVR, KTO, distillation) and `tars/brain/`.
2. **All Production Runtime & Memory Belongs in Harnet**:
   - `vazus_core`, `services/memory/vazus.db`, `gemini_bridge`, `SuperpositionEngine`, and `BlockTreeEngine` live in `/home/tarhes/Проекты/harnet`.
3. **Hardware Sympathy**:
   - Target AVX2 (`x86-64-v3`) on CachyOS Meteor Lake; never compile with `-mavx512`.
