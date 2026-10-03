# Domain Specification: `sandbox` (Sandbox Domain Subsystem)

> **Subsystem**: `vazus_core/sandbox`  
> **Path**: `vazus_core/sandbox`  
> **Last Auto-Synchronized**: 2026-10-02 17:14:43  

## 1. Core Mission & Domain Scope (Responsibilities & Boundaries)
### 1.1 Primary Mission
The `sandbox` component operates as a self-contained modular domain within Vazus SuperGraph OS. It provides deterministic interfaces, handles domain logic, and enforces fail-closed error handling.

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Deterministic execution of `sandbox` public APIs and AST-verified symbols.
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

class StepSnapshot:
    pass

class StepExecutionResult:
    pass

class TimeTravelSandbox:
    def track_file(self, file_path: Union[str, Path]) -> None: ...
    def create_checkpoint(self, step_name: str, variable_state: Optional[Dict[str, Any]]=None) -> StepSnapshot: ...
    def execute_code(self, code_str: str, step_name: str='eval_step', variable_state: Optional[Dict[str, Any]]=None, track_files: Optional[List[Union[str, Path]]]=None, rollback_on_failure: bool=False, counterexample: Optional[Dict[str, Any]]=None) -> StepExecutionResult: ...
    def rollback(self, target_step_id: Optional[int]=None) -> bool: ...
    def inject_counterexample(self, prompt: str, counterexample: Dict[str, Any], failing_step_id: int) -> str: ...
    def execute_wasm(self, wasm_bytes_or_path: Union[bytes, str, Path], entry_point: str='_start', args: Optional[List[str]]=None, env: Optional[Dict[str, str]]=None, step_name: str='wasm_step', rollback_on_failure: bool=False) -> StepExecutionResult: ...
    def cleanup(self) -> None: ...

class IO_COUNTERS:
    pass

class JOBOBJECT_BASIC_LIMIT_INFORMATION:
    pass

class JOBOBJECT_EXTENDED_LIMIT_INFORMATION:
    pass

class Win32JobSandbox:
    def assign_process(self, pid_or_handle: int) -> bool: ...
    def terminate(self, exit_code: int=1) -> bool: ...
    def close(self): ...

class WSBSandboxConfig:
    pass

class WSBSandboxResult:
    def check_returncode(self) -> None: ...

class WSBSandboxController:
    def find_wsb_executable(cls) -> Path: ...
    def is_available(cls) -> bool: ...
    def is_sandbox_running(cls) -> bool: ...
    def list_sandboxes(cls) -> List[Dict[str, Any]]: ...
    def generate_wsb_config(self) -> str: ...
    def write_wsb_file(self) -> Path: ...
    def get_pip_offline_flags(cls, cache_dir: str='C:\\pip_cache') -> List[str]: ...
    def wrap_pip_command(cls, cmd: str, cache_dir: str='C:\\pip_cache') -> str: ...
    # ... (+18 additional methods)

def generate_wsb_config(session_id: Optional[str]=None, host_scratch_dir: Optional[Union[str, Path]]=None, host_pip_cache: Optional[Union[str, Path]]=None, host_vazus_root: Optional[Union[str, Path]]=None) -> str: ...
def run_command_sandboxed(command: str, timeout: int=30, working_dir: Optional[str]=None, scratch_dir: Optional[Union[str, Path]]=None, run_as: str='System') -> WSBSandboxResult: ...
def main(): ...

```

### 2.2 Exported Classes
- **`StepSnapshot`** (`time_travel_sandbox.py`): Immutable Copy-on-Write snapshot of sandbox state before or after a step.
- **`StepExecutionResult`** (`time_travel_sandbox.py`): Execution outcome of a sandboxed step.
- **`TimeTravelSandbox`** (`time_travel_sandbox.py`): Deterministic Time-Travel Micro-Sandbox with CoW snapshots and instant rollback.
  - *Methods*: `track_file, create_checkpoint, execute_code, rollback, inject_counterexample, ... (+2)`
- **`IO_COUNTERS`** (`win32_job_guard.py`): No description
- **`JOBOBJECT_BASIC_LIMIT_INFORMATION`** (`win32_job_guard.py`): No description
- **`JOBOBJECT_EXTENDED_LIMIT_INFORMATION`** (`win32_job_guard.py`): No description
- **`Win32JobSandbox`** (`win32_job_guard.py`): Win32 Job Objects wrapper guaranteeing process isolation and resource limits.
  - *Methods*: `assign_process, terminate, close`
- **`WSBSandboxConfig`** (`wsb_sandbox_controller.py`): Configuration parameters for Windows Sandbox session.
- **`WSBSandboxResult`** (`wsb_sandbox_controller.py`): Execution result container mimicking subprocess.CompletedProcess.
  - *Methods*: `check_returncode`
- **`WSBSandboxController`** (`wsb_sandbox_controller.py`): Programmatic controller for Windows Sandbox environments using wsb.exe CLI.
  - *Methods*: `find_wsb_executable, is_available, is_sandbox_running, list_sandboxes, generate_wsb_config, ... (+21)`

### 2.3 Exported Functions
- **`generate_wsb_config()`** (`wsb_sandbox_controller.py`): Module-level function satisfying PROJECT.md interface contract:
- **`run_command_sandboxed()`** (`wsb_sandbox_controller.py`): Module-level function satisfying PROJECT.md interface contract:
- **`main()`** (`wsb_sandbox_controller.py`): Command-line interface for wsb_sandbox_controller.

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
