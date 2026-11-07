# 🧠 Hartes OS: 6-Tier AI Cognitive Layer Architecture & Inter-Layer Synergy
> **Hartes (Harness + TARS) — Deep Epistemic Design & Layer Decomposition**  
> *Resolving the Unknown Information Paradox | SMT Z3 Neuro-Symbolic Barrier | Recursive Mutual Enhancement*

---

## 🏛️ The 6-Tier Layered Cognitive Model

```
+-----------------------------------------------------------------------------------+
|               LAYER 5: AUTONOMOUS SCAFFOLDING & META-EVOLUTION (DGM/Self-Harness) |
|      • Scaffolding-as-Code in Git    • Evolutionary Program Search                |
|      • Weakness Mining & Auto-Fix     • Offloaded to Google Jules & Cloud Run      |
+-----------------------------------------------------------------------------------+
                                         ▲
                                         │ (Mutual Optimization & Flywheel)
                                         ▼
+-----------------------------------------------------------------------------------+
|               LAYER 4: DIALECTICAL REASONING & BYZANTINE CONSENSUS (Concordia)     |
|      • 4-Agent Jury (Plan/Code/Verify/Review) • Chelpanov Formal Logic Invariants  |
|      • Anti-Hallucination Veto Gate  • High-Level Goal Arbitration                |
+-----------------------------------------------------------------------------------+
                                         ▲
                                         │ (Falsifiable Hypotheses & Claims)
                                         ▼
+-----------------------------------------------------------------------------------+
|               LAYER 3: EPISTEMIC SEARCH & META-RETRIEVAL (Active Inference)        |
|      • Expected Information Gain (EIG) Entropy Collapse                            |
|      • Orthogonal Triangulation (Sandbox + Z3 SMT + Literature Consensus)         |
|      • Thompson Sampling Multi-Armed Bandit over Search Modalities                 |
+-----------------------------------------------------------------------------------+
                                         ▲
                                         │ (Retrieved Facts & Grounding Context)
                                         ▼
+-----------------------------------------------------------------------------------+
|               LAYER 2: PROCEDURAL SKILL BANK & DYNAMIC ROLLOUTS (SkillRL / SAGE)   |
|      • Dual-Granularity SkillBank (Strategic Guidance vs. Executable Primitives)  |
|      • Sequential Rollout Auto-Compilation • Skill-Integrated Reinforcement Weight|
+-----------------------------------------------------------------------------------+
                                         ▲
                                         │ (Tool Invocations & AST Actions)
                                         ▼
+-----------------------------------------------------------------------------------+
|               LAYER 1: CODE TOPOLOGY & STRUCTURAL GRAPH (SCIP / Tree-Sitter)       |
|      • Semantic Code Graph & Call-Graph Tracing • Blast Radius Impact Analysis     |
|      • Context Reducer (O(1) Token Compression via Signature Pruning)             |
+-----------------------------------------------------------------------------------+
                                         ▲
                                         │ (Pre-Flight Safety Verifications)
                                         ▼
+-----------------------------------------------------------------------------------+
|               LAYER 0: NEURO-SYMBOLIC SMT Z3 SUBSTRATE GUARD (Hard Barrier)       |
|      • Sub-Millisecond (< 0.05 ms) Formal Verification (UNSAT = Mathematical Proof)|
|      • Strict Path Jail Invariance    • ReDoS-Immune Destructive Command Blocking |
|      • Dual-Layer Anti-Vacuous Proof Filter (Z3 Proof + Pytest Sandbox)           |
+-----------------------------------------------------------------------------------+
```

---

## 🔍 Layer Breakdown & Functional Interplay

### Layer 0: Neuro-Symbolic SMT Z3 Substrate Guard (Hard Safety Barrier)
* **Purpose**: Absolute fail-closed determinism. Never permits an LLM hallucination to destroy filesystem boundaries, corrupt memory, or execute unauthorized privilege escalations.
* **Mechanism**: Models parameters, paths, and command signatures as symbolic SMT-LIB2 formulas evaluated by Microsoft Research's Z3 solver in under **0.05 ms**.
* **Anti-Vacuous Verification Filter**: Prevents models from generating trivial specifications (e.g. `ensures true`) by requiring both mathematical proof AND functional test passage.

### Layer 1: Code Topology & Structural Graph (SCIP / Tree-Sitter)
* **Purpose**: Maintains deterministic topological awareness of the entire repository.
* **Mechanism**: Employs SCIP code indexing and AST pruning. Extracts function signatures, class interfaces, and docstrings while pruning away implementation bodies, achieving $O(1)$ token budget compression without losing call-graph visibility.

### Layer 2: Procedural Skill Bank & Dynamic Rollouts (SkillRL & SAGE)
* **Purpose**: Accumulates and optimizes operational competence over time.
* **Mechanism**:
  - *Dual-Granularity*: Separates high-level strategic reasoning from low-level executable code.
  - *SAGE Sequential Rollouts*: When an agent successfully solves an algorithmic obstacle, the verified sequence is compiled into a standalone skill function.
  - *SkillRL Dynamic Weights*: Reusable skills that assist downstream tasks receive positive reward reinforcement ($w \leftarrow 1.05 \cdot w$); failing skills are demoted ($w \leftarrow 0.90 \cdot w$) or queued for Darwinian mutation.

### Layer 3: Epistemic Search & Meta-Retrieval (Unknown Information Discovery)
* **Purpose**: Solves Meno's Paradox—identifying the optimal search strategy and the truth without prior knowledge of the answer.
* **Mechanism**:
  1. *Expected Information Gain (EIG)*: Prioritizes search modalities that cause the steepest entropy collapse across candidate hypotheses:
     $$\text{EIG}(Q, S) = H(\Theta) - \mathbb{E}[H(\Theta \mid \text{result})]$$
  2. *Orthogonal Triangulation*: Cross-validates claims across three non-overlapping epistemological axes:
     - Vector A (Empirical): Code execution in isolated sandbox.
     - Vector B (Formal): SMT Z3 mathematical proof of boundaries.
     - Vector C (Literature): Corroboration across independent peer-reviewed literature.
  3. *Thompson Sampling Multi-Armed Bandit*: Dynamically balances exploration and exploitation across search modalities (SCIP Code Graph, 768D Vector Memory, NotebookLM RAG, Web Research).

### Layer 4: Dialectical Reasoning & Multi-Agent Consensus (Concordia Jury)
* **Purpose**: Eliminates single-model reasoning blind spots through structured adversarial debate.
* **Mechanism**: A 4-agent jury (Planner, Coder, Verifier, Reviewer) evaluates major architectural changes. Invariants are anchored in classical formal logic (Laws of Identity, Contradiction, Excluded Middle, and Sufficient Reason). A Byzantine voting protocol prevents ungrounded consensus drift.

### Layer 5: Autonomous Scaffolding & Meta-Harness Evolution (DGM / Self-Harness)
* **Purpose**: Ensures the agent architecture continuously improves itself without human intervention.
* **Mechanism**:
  - Treats the harness (system prompts, tool configurations, memory reducers, and verifiers) as version-controlled code files in Git.
  - Background workers on **Google Jules (Ultra)** and **Cloud Run Worker Pools** continuously cluster execution failure traces into weakness taxonomies, formulate bounded code patches, validate them against held-out regression test splits, and commit verified enhancements.

---

## 🔄 The Mutual Enhancement Flywheel (How Layers Improve Each Other)

1. **Layer 3 enhances Layer 1 & 2**: The epistemic meta-search engine finds optimal external algorithms and tools, adding them as Level 2 skills.
2. **Layer 0 protects Layer 5**: SMT Z3 hard gates ensure that when Layer 5 mutates harness code, it cannot disable security barriers or violate path jail invariants.
3. **Layer 4 audits Layer 3**: The dialectical jury cross-examines search results to prevent confirmation bias.
4. **Layer 5 refines Layer 1, 2, 3, and 4**: The meta-harness evolver optimizes prompt templates, context reducers, and bandit hyperparameters based on real-world task pass rates.
