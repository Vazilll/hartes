# Project: Autonomous Absolute AI Flywheel

## Architecture
The Autonomous Absolute AI Flywheel is an asymmetric, multi-tier, 24/7 intelligent engineering and discovery system operating continuously without requiring a local machine.

### Multi-Tier Operating Topology
1. **Tier 0 (Always-On Cloud Control Plane)**: 1 GB Linux VPS (`157.228.174.15`) running a minimal systemd daemon (`vazus-flywheel-daemon.service`) with strict cgroup limits (`MemoryMax=200M`, `MemoryHigh=160M`). Operates at 70–95 MB steady-state RAM for 30s event ticks, node presence tracking, and cloud triggering.
2. **Tier 1 (Cloud Data Plane / Heavy Compute)**: Ephemeral 16 GB GitHub Actions runners (`cloud_mega_lab.yml`), Google Jules Cloud VM (`jules_client.py`), and Google Drive 30 TB Vault (`tars_vault_bridge.py`) executing heavy pytest suites, AST parsing, model fine-tuning, and cloud jobs without VPS or local PC load.
3. **Tier 1.5 (Home Edge Server Node)**: Orange Pi 4 Pro (6 GB RAM, ARM64, ~5–10W) running 24/7 native SMT Z3 formal verification on ARM64, agy CLI headless bridge, small quantized models (llama.cpp/SmolLM), and continuous background git automation.
4. **Tier 2 (Local Power Multiplier Node)**: User laptop dynamically connecting when online, registering via TTL leases (10 min TTL), offloading `agy.exe` Gemini 3.1 Pro / Claude 3.7 Sonnet quotas, and executing local REPL sandboxes without split-brain risk.

### Core Subsystems
- **Quality & Formal Verification Engine (`vazus_autonomous_harness/verification/`)**: 100-point rubric combining SMT Z3 semantic proof satisfaction (+40), empirical test integrity (+30), AST parsimony & efficiency (+15), and Academic Sovereignty (+15) with a hard admission threshold of >= 75 points.
- **Reflexion & Episodic Memory (`vazus_autonomous_harness/memory/`)**: Closed-loop error-to-insight engine storing structured `ReflexionRecord` entries in SQLite SSOT (`vazus.db` / `hartes_memory.db`) and Markdown Zettelkasten wiki (`Tars_30TB_Vault/06_reflexion_wiki`), coupled with pre-flight tri-hybrid retrieval and < 5 ms static negative constraint filtering.
- **Anti-Thrashing & Human Escalation Gate (`vazus_autonomous_harness/engine/`)**: Deadlock detector tracking cycle-consecutive failures (budget <= 3), non-positive score progression, and missing external credentials; auto-halts and generates executive diagnostic briefings in Google Drive.
- **Headless VPS Daemon & OpenColab Bridge (`vazus_autonomous_harness/daemon/`)**: Low-overhead event loop daemon, asynchronous Google Drive queue bridge (`colab_queue/inbox` and `outbox`), and dual setup scripts (`setup_vps_target1.sh` and `setup_orangepi_target2.sh`) with zero plaintext secrets.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Quality Evaluation Rubric | 100-point multi-dimensional scoring engine (SMT +40, Tests +30, Parsimony +15, Sovereignty +15, threshold >= 75) | M1 | R4 |
| F2 | SMT Z3 Equivalence Prover | Formal verification engine extracting docstring contracts, running Z3 UNSAT proofs, generating counterexample models | M1 | R4 |
| F3 | AST Bloat & Parsimony Analyzer | AST node counting, bloat ratio calculation, penalty and clean diff scoring | M1 | R4 |
| F4 | Academic Sovereignty Guard | Enforces USER.md#L37 invariants; detects and vetoes direct academic solution dumps; enforces Socratic tutoring | M1 | R4 |
| F5 | Continuous Reflexion Generator | Structured error-to-insight generator producing `ReflexionRecord` with root cause, violated invariant, and negative rules | M2 | R2 |
| F6 | Dual-Tier Episodic Memory Store | SQLite SSOT (`episodic_reflexion_records` + FTS5) and Markdown Zettelkasten wiki in `Tars_30TB_Vault/06_reflexion_wiki` | M2 | R2 |
| F7 | Pre-Flight Negative Constraint Filter | Tri-hybrid retrieval + static AST/regex/SMT hard-gate intercepting dead-ends in < 5 ms prior to execution | M2 | R2 |
| F8 | Anti-Thrashing Circuit Breaker | Active deadlock detector tracking consecutive failures (limit 3), non-positive score deltas, and structural oscillation | M3 | R3 |
| F9 | Human Escalation Diagnostic Briefing | Executive briefing generator producing structured failure matrix, SMT counterexamples, and 3 push-button forks in Drive | M3 | R3 |
| F10 | Lightweight VPS Daemon | Headless Python daemon operating <= 200 MB RAM on 1 GB VPS `157.228.174.15` with systemd cgroup limits | M4 | R5 |
| F11 | Dual Deployment Setup Targets | Modular setup scripts for Target 1 (1 GB VPS proxy/scheduler) and Target 2 (Orange Pi 4 Pro 6GB ARM64 edge node) | M4 | R5 / User Update |
| F12 | OpenColab Asynchronous Bridge | Google Drive mailbox queue (`colab_queue/inbox` and `outbox`) enabling headless GPU offloading to Colab | M4 | R5 |
| F13 | Asymmetric 4-Tier Topology Coordinator | Distributed coordination plane connecting Tier 0 (VPS), Tier 1 (GH Actions/Jules), Tier 1.5 (Orange Pi), and Tier 2 (Laptop) | M5 | R1 |
| F14 | Laptop Node Power Multiplier & Lease Manager | Dynamic registration with 10-minute TTL leases, agy CLI quota offloading, and safe git fast-forward sync avoiding split-brain | M5 | R1 |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Quality Engine & SMT Z3 Verifier | F1, F2, F3, F4 | none | DONE |
| M2 | Reflexion & Episodic Memory | F5, F6, F7 | M1 | DONE |
| M3 | Anti-Thrashing Circuit Breaker | F8, F9 | M1, M2 | DONE |
| M4 | Headless VPS Daemon & Colab Bridge | F10, F11, F12 | none | DONE |
| M5 | Asymmetric Topology & Laptop Node | F13, F14 | M1, M2, M3, M4 | DONE |
| E2E | Comprehensive E2E Test Suite | Tiers 1-4 opaque-box test suite across all features | M1-M5 contracts | DONE |
| FIN | Final Acceptance & Adversarial Hardening | Pass 100% E2E tests + Tier 5 adversarial hardening | E2E, M1-M5 | DONE |

---

## Interface Contracts

### M1: Quality Evaluation Engine (`vazus_autonomous_harness.verification.quality_engine`)
```python
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class QualityScore:
    total_score: float # 0 to 100
    correctness_smt: float # max 40
    empirical_integrity: float # max 30
    parsimony_efficiency: float # max 15
    academic_sovereignty: float # max 15
    is_admissible: bool # total_score >= 75.0 and correctness_smt == 40.0 and academic_sovereignty == 15.0
    counterexample: Optional[Dict[str, Any]] = None
    violation_reasons: list[str] = None
    ast_bloat_ratio: float = 0.0

class QualityEvaluationEngine:
    def evaluate(self, candidate_code: str, baseline_code: str, test_command: str = None) -> QualityScore:
        ...
```

### M2: Reflexion & Episodic Memory (`vazus_autonomous_harness.memory.reflexion_engine`)
```python
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class ExecutableNegativeConstraint:
    rule_id: str
    rule_type: str # 'AST_PATTERN_DENY', 'REGEX_DENY', 'SMT_PREDICATE_BLOCK'
    pattern: str
    description: str

@dataclass
class ReflexionRecord:
    record_id: str
    timestamp: float
    task_id: str
    candidate_summary: str
    root_cause: str
    violated_invariant: str
    negative_rules: List[ExecutableNegativeConstraint]
    smt_counterexample: Optional[Dict[str, Any]] = None
    fitness_score: float = 0.0

class ReflexionMemoryStore:
    def record_failure(self, record: ReflexionRecord) -> None:
        ...
    def retrieve_similar_dead_ends(self, task_description: str, limit: int = 5) -> List[ReflexionRecord]:
        ...
    def check_negative_constraints(self, candidate_code: str) -> tuple[bool, Optional[str]]:
        ... # returns (is_blocked, violation_message)
```

### M3: Anti-Thrashing Circuit Breaker (`vazus_autonomous_harness.engine.anti_thrashing`)
```python
@dataclass
class TaskAttempt:
    task_id: str
    cycle_number: int
    score: float
    code_hash: str
    error_message: Optional[str]
    missing_prerequisite: Optional[str]

class AntiThrashingCircuitBreaker:
    def record_attempt(self, attempt: TaskAttempt) -> bool:
        ... # returns True if tripped, False if execution may continue
    def is_tripped(self, task_id: str) -> bool:
        ...
    def generate_escalation_briefing(self, task_id: str) -> str:
        ... # produces diagnostic markdown report and syncs to Tars 30TB Vault
```

### M4: VPS Daemon & Colab Bridge (`vazus_autonomous_harness.daemon.vps_daemon`)
```python
class VpsDaemon:
    def __init__(self, config_path: str): ...
    def tick(self) -> Dict[str, Any]: ... # runs heartbeat, checks node presence, polls colab queue
    def dispatch_cloud_job(self, workflow_name: str, payload: dict) -> bool: ...

class ColabBridge:
    def submit_job(self, task_type: str, code: str) -> str: ... # writes to colab_queue/inbox
    def poll_result(self, job_id: str) -> Optional[dict]: ... # reads from colab_queue/outbox
```

### M5: Asymmetric Topology & Laptop Lease Manager (`vazus_autonomous_harness.topology.coordinator`)
```python
@dataclass
class NodeRegistration:
    node_id: str
    tier: str # 'Tier0_VPS', 'Tier1_Cloud', 'Tier1_5_Edge', 'Tier2_Laptop'
    capabilities: List[str] # ['SMT_Z3', 'GPU', 'NPU', 'AGY_CLI', 'REPL']
    lease_expires_at: float

class TopologyCoordinator:
    def register_node(self, node: NodeRegistration) -> bool: ...
    def heartbeat_node(self, node_id: str) -> bool: ...
    def get_best_worker_for_task(self, required_capability: str) -> Optional[NodeRegistration]: ...
    def safe_sync_git(self, repo_path: str) -> bool: ...
```

---

## Code Layout
```
C:\vazus\hartes\
├── vazus_autonomous_harness\
│   ├── verification\
│   │   ├── __init__.py
│   │   ├── quality_engine.py         # M1 (F1, F3)
│   │   ├── smt_prover.py             # M1 (F2)
│   │   └── academic_sovereignty.py   # M1 (F4)
│   ├── memory\
│   │   ├── __init__.py
│   │   ├── reflexion_engine.py       # M2 (F5)
│   │   ├── episodic_store.py         # M2 (F6)
│   │   └── preflight_filter.py       # M2 (F7)
│   ├── engine\
│   │   ├── __init__.py
│   │   ├── anti_thrashing.py         # M3 (F8)
│   │   └── escalation_gate.py        # M3 (F9)
│   ├── daemon\
│   │   ├── __init__.py
│   │   ├── vps_daemon.py             # M4 (F10)
│   │   ├── colab_bridge.py           # M4 (F12)
│   │   ├── setup_vps_target1.sh      # M4 (F11)
│   │   ├── setup_orangepi_target2.sh # M4 (F11)
│   │   └── vazus-flywheel.service    # M4 (F10, F11)
│   └── topology\
│       ├── __init__.py
│       ├── coordinator.py            # M5 (F13)
│       └── laptop_node.py            # M5 (F14)
├── tests\
│   ├── test_m1_quality_engine.py     # Unit tests M1
│   ├── test_m2_reflexion_memory.py   # Unit tests M2
│   ├── test_m3_anti_thrashing.py     # Unit tests M3
│   ├── test_m4_vps_daemon.py         # Unit tests M4
│   ├── test_m5_topology.py           # Unit tests M5
│   └── e2e\                          # E2E Test Suite (Tiers 1-4)
│       ├── test_tier1_features.py
│       ├── test_tier2_boundaries.py
│       ├── test_tier3_combinations.py
│       └── test_tier4_workloads.py
├── TEST_INFRA.md
├── TEST_READY.md
└── PROJECT.md
```
