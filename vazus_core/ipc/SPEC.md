# Domain Specification: `ipc` (Ipc Domain Subsystem)

> **Subsystem**: `vazus_core/ipc`  
> **Path**: `vazus_core/ipc`  
> **Last Auto-Synchronized**: 2026-10-02 16:22:51  

## 1. Core Mission & Domain Scope (Responsibilities & Boundaries)
### 1.1 Primary Mission
The `ipc` component operates as a self-contained modular domain within Vazus SuperGraph OS. It provides deterministic interfaces, handles domain logic, and enforces fail-closed error handling.

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Deterministic execution of `ipc` public APIs and AST-verified symbols.
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

class ActorMessage:
    def create(cls, sender: str, recipient: str, msg_type: str, payload: Dict[str, Any], correlation_id: str='') -> 'ActorMessage': ...
    def to_dict(self) -> Dict[str, Any]: ...
    def from_dict(cls, d: Dict[str, Any]) -> 'ActorMessage': ...
    def to_bytes(self) -> bytes: ...
    def from_bytes(cls, b: bytes) -> 'ActorMessage': ...

class BaseActor:
    async def receive(self, message: ActorMessage) -> Optional[ActorMessage]: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...

class ActorBus:
    def register_actor(self, actor: BaseActor) -> None: ...
    def unregister_actor(self, actor_id: str) -> None: ...
    async def send(self, message: ActorMessage) -> bool: ...
    async def broadcast(self, sender: str, msg_type: str, payload: Dict[str, Any]) -> int: ...

class DAGStage:
    pass

class DynamicDAGPipeline:
    def add_stage(self, stage_id: str, dependencies: Optional[List[str]]=None, worker_actors: Optional[List[str]]=None, map_task_fn: Optional[Callable[[Dict[str, Any], str], Dict[str, Any]]]=None, reduce_fn: Optional[Callable[[List[Dict[str, Any]]], Dict[str, Any]]]=None) -> None: ...
    async def execute(self, initial_payload: Dict[str, Any]) -> Dict[str, Any]: ...

class WindowsNamedMutex:
    def acquire(self, timeout_ms: int=5000) -> bool: ...
    def release(self) -> None: ...
    def close(self) -> None: ...

class SharedMemoryRingBuffer:
    def write_payload(self, data: bytes) -> Optional[int]: ...
    def read_payload(self) -> Optional[Tuple[bytes, int]]: ...
    def read_slot(self, seq: int) -> Optional[Tuple[bytes, int]]: ...
    def read_new_messages(self, last_seq: int) -> List[Tuple[int, bytes, int]]: ...
    def stats(self) -> dict: ...
    def close(self): ...

class SymbolPoolBridge:
    def intern(self, symbol: str) -> int: ...
    def resolve(self, symbol_id: int) -> Optional[str]: ...
    def hash_symbol(self, symbol: str) -> int: ...
    def resolve_hash(self, hash_val: int) -> Optional[str]: ...
    def batch_intern(self, symbols: List[str]) -> List[int]: ...
    def size(self) -> int: ...
    def clear(self) -> None: ...

def fnv1a_64(text: str) -> int: ...

```

### 2.2 Exported Classes
- **`ActorMessage`** (`actor_bus.py`): Immutable, strongly typed message passed across the Actor Bus.
  - *Methods*: `create, to_dict, from_dict, to_bytes, from_bytes`
- **`BaseActor`** (`actor_bus.py`): Subagent Actor with private, isolated state and a typed asynchronous mailbox.
  - *Methods*: `receive, start, stop`
- **`ActorBus`** (`actor_bus.py`): Central Actor Message Bus coordinating agent dispatch and routing.
  - *Methods*: `register_actor, unregister_actor, send, broadcast`
- **`DAGStage`** (`actor_bus.py`): A stage in the dynamic DAG pipeline.
- **`DynamicDAGPipeline`** (`actor_bus.py`): Dynamic Directed Acyclic Graph (DAG) Pipeline Orchestrator with Map-Reduce.
  - *Methods*: `add_stage, execute`
- **`WindowsNamedMutex`** (`shared_memory_ring.py`): Lightweight cross-process named mutex wrapper using Win32 API.
  - *Methods*: `acquire, release, close`
- **`SharedMemoryRingBuffer`** (`shared_memory_ring.py`): True multi-slot cyclic FIFO ring buffer with named shared memory on Windows/POSIX.
  - *Methods*: `write_payload, read_payload, read_slot, read_new_messages, stats, ... (+1)`
- **`SymbolPoolBridge`** (`symbol_pool_bridge.py`): Bidirectional symbol interning pool connecting to services/gomcp Go backend
  - *Methods*: `intern, resolve, hash_symbol, resolve_hash, batch_intern, ... (+2)`

### 2.3 Exported Functions
- **`fnv1a_64()`** (`symbol_pool_bridge.py`): No description

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
