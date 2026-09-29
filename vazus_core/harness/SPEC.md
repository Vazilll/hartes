# Domain Specification: `harness` (Harness Domain Subsystem)

> **Subsystem**: `vazus_core/harness`  
> **Path**: `vazus_core/harness`  
> **Last Auto-Synchronized**: 2026-09-30 02:04:48  

## 1. Core Mission & Domain Scope (Responsibilities & Boundaries)
### 1.1 Primary Mission
The `harness` component operates as a self-contained modular domain within Vazus SuperGraph OS. It provides deterministic interfaces, handles domain logic, and enforces fail-closed error handling.

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Deterministic execution of `harness` public APIs and AST-verified symbols.
  - Thread-safe SQLite WAL queries and state mutations with exponential backoff.
  - Fast-fail validation and zero-trust parameter verification.
- **PROHIBITED**:
  - Unbounded memory consumption or persistent handle leaks.
  - Blocking event loops or unhandled exceptions escaping domain boundary.
  - Modifying external state outside workspace jail boundaries.

## 2. Public Typed Interface Contracts (Public Interface Contracts)
### 2.1 Primary Classes & Signatures
```python
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from pathlib import Path

class ReflexActionType:
    pass

class ReflexSignal:
    pass

class ReflexVerdict:
    pass

class ReflexCircuitController:
    def tool_indexer(self) -> JSpaceToolIndexer: ...
    def register_custom_reflex(self, name: str, handler: Callable[[ReflexSignal], str]) -> None: ...
    def evaluate_signal(self, signal: ReflexSignal) -> ReflexVerdict: ...

class TrajectoryStep:
    pass

class Trajectory:
    pass

class MicroRule:
    pass

class TrajectoryOptimizer:
    def generate_rule_id(category: str, pattern: str, target_role: str) -> str: ...
    def diagnose_trajectory(self, trajectory: Trajectory) -> Optional[MicroRule]: ...
    def evaluate_and_promote(self, rule: MicroRule) -> bool: ...
    def get_active_micro_rules(self, role: Optional[str]=None) -> List[MicroRule]: ...
    def rollback_rule(self, rule_id: str) -> bool: ...
    def is_payload_compliant(self, payload: str, role: str) -> Tuple[bool, str]: ...

```

### 2.2 Exported Classes
- **`ReflexActionType`** (`reflex_circuit.py`): No description
- **`ReflexSignal`** (`reflex_circuit.py`): No description
- **`ReflexVerdict`** (`reflex_circuit.py`): No description
- **`ReflexCircuitController`** (`reflex_circuit.py`): Tier-0 Neuromorphic Reflex Controller.
  - *Methods*: `tool_indexer, register_custom_reflex, evaluate_signal`
- **`TrajectoryStep`** (`trajectory_optimizer.py`): No description
- **`Trajectory`** (`trajectory_optimizer.py`): No description
- **`MicroRule`** (`trajectory_optimizer.py`): No description
- **`TrajectoryOptimizer`** (`trajectory_optimizer.py`): Outer-Loop Harness Optimizer.
  - *Methods*: `generate_rule_id, diagnose_trajectory, evaluate_and_promote, get_active_micro_rules, rollback_rule, ... (+1)`

### 2.4 Invariant Guarantees & Safety Policies (Invariants & Safety Guarantees)
- Invariant 1: All operations enforce strict Zero-Trust input validation.
- Invariant 2: Database mutations utilize WAL mode and rollback on exception.
- Invariant 3: Public APIs maintain typed interfaces with sub-50ms latency guarantees.

## 3. Progressive Skill Level (Level 1..5 Capability Maturity) & Upgrade Criteria
- **Level 1 (Basic Operations)**: Foundational symbol definitions and synchronous executions.  
  *Upgrade criteria*: Add structured error handling and unit test coverage.
- **Level 2 (Resilient Handling)**: Fail-closed error boundaries and bounded memory usage.  
  *Upgrade criteria*: Integrate typed contracts and WAL storage.
- **Level 3 (Integrated Subsystem)**: Full integration with lifecycle hooks and SuperGraph OS telemetry.  
  *Upgrade criteria*: Add formal SMT Z3 contract verification.
- **Level 4 (Autonomous Closed-Loop)**: Self-healing error correction and Reflexion memory integration.  
  *Upgrade criteria*: Support distributed or NPU-accelerated execution.
- **Level 5 (Self-Sustaining Governor)**: Closed-loop autonomous adaptation, zero manual intervention, and verified invariant stability.

## 4. Known Bottlenecks & Failure Modes (Optimization Backlog)
- [ ] Concurrency contention during high-frequency SQLite WAL writes under peak load.
- [ ] Serialization latency on deep AST traversal across large files.
- [ ] Memory footprint under heavy micro-batching operations.

## 5. Extension Points & Integration
- Integrates with `vazus_core` through standard Python imports and canonical facade APIs.
- Auto-indexed by `AutoIndexRunner` and monitored by `hooks.json` lifecycle hooks.
