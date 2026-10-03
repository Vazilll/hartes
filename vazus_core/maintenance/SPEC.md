# Domain Specification: `maintenance` (Self-Sustaining Codebase Maintenance & Indexing Subsystem)

> **Subsystem**: `vazus_core/maintenance`  
> **Path**: `vazus_core/maintenance`  
> **Last Auto-Synchronized**: 2026-10-03 15:57:09  

## 1. Core Mission & Domain Scope (Responsibilities & Boundaries)
### 1.1 Primary Mission
The `maintenance` component enforces continuous codebase hygiene, synchronizes SCIP/CKB symbol indices with strict concurrency mutex locking (.ckb/indexing.lock), auto-generates domain specifications (SPEC.md), and terminates zombie indexing processes.

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Atomic mutex acquisition (.ckb/indexing.lock) and process tree lifecycle governance.
  - AST extraction and automatic SPEC.md multi-tier synchronization.
  - Pyright configuration scoping and SCIP index stale detection.
  - Resource-bounded indexing execution with NODE_OPTIONS memory limits.
- **PROHIBITED**:
  - Running parallel concurrent SCIP/CKB indexing processes.
  - Blocking file editing hooks with detached compilation daemons.
  - Allowing orphan node.exe or ckb.exe processes to accumulate in OS memory.

## 2. Public Typed Interface Contracts (Public Interface Contracts)
### 2.1 Primary Classes & Signatures
```python
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from pathlib import Path

class SpecSynchronizer:
    def inspect_module_ast(self, py_file: Path) -> Dict[str, Any]: ...
    def generate_spec_markdown(self, component_dir: Path) -> str: ...
    def sync_component_spec(self, component_dir: Path, force: bool=False) -> bool: ...

class IndexingLockManager:
    def is_indexer_process_running(cls) -> Tuple[bool, Optional[int], str]: ...
    def is_pid_indexer(cls, pid: Any) -> bool: ...
    def acquire(cls, trigger: str='auto') -> bool: ...
    def release(cls, force: bool=False) -> None: ...

class SCIPIndexSynchronizer:
    def mark_dirty(self) -> None: ...
    def clear_dirty(self) -> None: ...
    def is_index_stale(self, max_age_seconds: float=3600.0) -> bool: ...
    def trigger_scip_reindex(self, background: bool=True, timeout: float=30.0, max_rss_mb: float=300.0) -> Dict[str, Any]: ...

class AutoIndexRunner:
    def sync_all_components(self, force: bool=False) -> List[str]: ...
    def run(self, paths: Optional[List[str]]=None, force_reindex: bool=False, trigger_indexer: bool=False) -> Dict[str, Any]: ...

def run_maintenance(paths: Optional[List[str]]=None, force_reindex: bool=False, trigger_indexer: bool=False) -> Dict[str, Any]: ...

```

### 2.2 Exported Classes
- **`SpecSynchronizer`** (`auto_index_runner.py`): Automated extractor and synchronizer for modular component specifications (SPEC.md).
  - *Methods*: `inspect_module_ast, generate_spec_markdown, sync_component_spec`
- **`IndexingLockManager`** (`auto_index_runner.py`): Concurrency Mutex & Active Process Guard.
  - *Methods*: `is_indexer_process_running, is_pid_indexer, acquire, release`
- **`SCIPIndexSynchronizer`** (`auto_index_runner.py`): Manages incremental or complete SCIP graph reindexing with strict concurrency control.
  - *Methods*: `mark_dirty, clear_dirty, is_index_stale, trigger_scip_reindex`
- **`AutoIndexRunner`** (`auto_index_runner.py`): Unified Self-Sustaining Protocol Runner.
  - *Methods*: `sync_all_components, run`

### 2.3 Exported Functions
- **`run_maintenance()`** (`auto_index_runner.py`): Convenience top-level entrypoint for hooks and tools.

### 2.4 Invariant Guarantees & Safety Policies (Invariants & Safety Guarantees)
- Invariant 1: At most 1 indexing process runs system-wide (enforced via IndexingLockManager).
- Invariant 2: Full background indexing completes within 30 seconds under 300 MB RSS.
- Invariant 3: Component SPEC.md generation preserves multi-tier structure and typed contracts.

## 3. Progressive Skill Level (Level 1..5 Capability Maturity) & Upgrade Criteria
- **Level 1 (Manual Maintenance)**: Ad-hoc command-line script execution.  
  *Upgrade criteria*: Implement automated post-tool hooks.
- **Level 2 (Hook-Driven Indexing)**: Automatic spec updates and indexing triggered on file mutations.  
  *Upgrade criteria*: Add concurrency mutex and process watchdog.
- **Level 3 (Concurrency-Guarded Indexer)**: Strict PID locking, stale eviction, and RSS memory caps.  
  *Upgrade criteria*: Implement multi-tier spec generation and feedback loops.
- **Level 4 (Self-Healing Spec Synchronizer)**: Automatic typed contract extraction, failure mode tracking, and closed loops.  
  *Upgrade criteria*: Support continuous autonomous repository refactoring.
- **Level 5 (Self-Sustaining Repository Organism)**: Fully autonomous, zero-leak codebase stewardship and self-synchronizing architecture.

## 4. Known Bottlenecks & Failure Modes (Optimization Backlog)
- [ ] Pyright index generation time on cold start repositories.
- [ ] Windows file locking semantics during rapid concurrent indexer access.

## 5. Extension Points & Integration
- Integrates with `vazus_core` through standard Python imports and canonical facade APIs.
- Auto-indexed by `AutoIndexRunner` and monitored by `hooks.json` lifecycle hooks.
