# Domain Specification: `hooks` (Real-Time Lifecycle Interception & Security Hooks Subsystem)

> **Subsystem**: `vazus_core/hooks`  
> **Path**: `vazus_core/hooks`  
> **Last Auto-Synchronized**: 2026-10-03 14:03:06  

## 1. Core Mission & Domain Scope (Responsibilities & Boundaries)
### 1.1 Primary Mission
The `hooks` component governs real-time lifecycle interception across all agent execution stages (session_start, pre_invocation, pre_tool, post_tool, post_invocation, stop). It enforces sub-50ms latency constraints, strict zero-trust path jail boundaries, MCP gateway tool masking, and execution signal telemetry.

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Sub-50ms pre-tool path checks, security jail enforcement, and tool output masking.
  - Dynamic skill selection, MCP gateway routing, and intent-schema overlap filtering.
  - Real-time HUD telemetry streaming and execution signal recording.
  - Non-blocking background maintenance scheduling via AutoIndexRunner.
- **PROHIBITED**:
  - Lifecycle hook latency exceeding statutory 50.0 ms threshold under normal operation.
  - Spawning unbounded background processes or detached compilation daemons.
  - Modifying tool execution state or return values outside declared hook contracts.
  - Bypassing path jail security validation on tool file mutations.

## 2. Public Typed Interface Contracts (Public Interface Contracts)
### 2.1 Primary Classes & Signatures
```python
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from pathlib import Path

class EntropyGovernor:
    def estimate_normalized_entropy(total_chars: int, baseline_chars: int=8000, max_scale_chars: int=500000) -> float: ...
    def compact_trajectory(self, trajectory: Any, force: bool=False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]: ...

class DynamicMCPGateway:
    def register_tool(self, tool_name: str, schema: Dict[str, Any], server_name: str='default'): ...
    def compute_iso_score(self, query: str, tool_name: str, query_tokens: Optional[Set[str]]=None, lower_query: Optional[str]=None) -> float: ...
    def resolve_active_tools(self, current_user_query: str) -> List[Dict[str, Any]]: ...
    def get_token_savings_metric(self) -> Dict[str, Any]: ...

class ObservationMasker:
    def mask_tool_output(cls, tool_name: str, raw_output: str, max_chars: int=800) -> str: ...

def write_hud_event(event_type: str, payload: dict) -> None: ...
def extract_last_model_response(messages: list) -> str: ...
def extract_last_user_message(messages: list) -> str: ...
def classify_insight(text: str) -> tuple: ...
def main(): ...
async def run_post_invocation_hook(session_id: str='unknown', turn_index: int=0, model_response: str='', tool_executions_count: int=0, **kwargs) -> dict: ...
def run_post_tool_hook(session_id: str='unknown', tool_name: str='', tool_args: Optional[dict]=None, raw_output: str='', **_kwargs) -> dict: ...
def main(): ...
def auto_disclose_domain_specs(prompt: str='', *args, **_kwargs) -> str: ...
def clean_user_prompt(text: str) -> str: ...
def extract_user_prompt(hook_data: dict) -> str: ...
def auto_select_skills(user_prompt: str) -> list: ...
def auto_retrieve_memory(user_prompt: str, invocation_num: int) -> str: ...
def build_skills_injection(skills: list) -> str: ...
def generate_executive_briefing() -> str: ...
def create_default_mcp_gateway() -> DynamicMCPGateway: ...
def get_default_mcp_gateway() -> DynamicMCPGateway: ...
def run_pre_invocation(trajectory: List[Dict[str, Any]], query: str) -> Dict[str, Any]: ...
def main(): ...
def handle_pre_invocation(hook_data: dict) -> dict: ...
async def run_pre_invocation_hook(session_id: str='unknown', user_prompt: str='', turn_index: int=0, messages: Optional[list]=None, **_kwargs) -> dict: ...
def get_substrate_guard() -> SubstrateGuard: ...
def run_pre_tool(tool_name: str, args: dict) -> dict: ...
def main(): ...
def pre_tool_enforce_security_jail(tool_name: str, tool_args: dict, workspace_root: str='C:/vazus', **kwargs) -> dict: ...
def check_code_intelligence_readiness() -> Dict[str, Any]: ...
def check_ckb_connectivity(port: int=9999, timeout: float=0.1, **kwargs) -> Dict[str, Any]: ...
async def warm_database_pool(db_pool: AsyncDatabasePool) -> Dict[str, Any]: ...
async def run_session_start(workspace_path: str='C:/vazus') -> Dict[str, Any]: ...
async def run_session_start_hook(session_id: str='unknown', workspace_root: str='C:/vazus', **kwargs) -> Dict[str, Any]: ...
def main(): ...
def extract_all_user_messages(messages: list) -> list: ...
def extract_all_model_responses(messages: list) -> list: ...
def build_session_summary(conversation_id: str, user_msgs: list, model_msgs: list, turn_count: int) -> str: ...
def check_pending_verification() -> tuple[bool, str]: ...
def auto_curate_session_memory(transcript: list, min_confidence: float=0.7, max_facts: int=5) -> list: ...
def main(): ...
async def run_stop_hook(session_id: str='unknown', workspace_root: str='C:/vazus', invocation_num: int=0, messages: Optional[list]=None, **_kwargs) -> dict: ...

```

### 2.2 Exported Classes
- **`EntropyGovernor`** (`entropy_governor.py`): Trajectory manager preventing attention entropy dispersion and instruction burial.
  - *Methods*: `estimate_normalized_entropy, compact_trajectory`
- **`DynamicMCPGateway`** (`mcp_gateway.py`): Dynamic Tool Disclosure Gateway implementing Intent-Schema Overlap (ISO) filtering
  - *Methods*: `register_tool, compute_iso_score, resolve_active_tools, get_token_savings_metric`
- **`ObservationMasker`** (`observation_masker.py`): Synthesizes and compacts bulky tool outputs (pytest, terminal logs, compiler dumps)
  - *Methods*: `mask_tool_output`

### 2.3 Exported Functions
- **`write_hud_event()`** (`hud_writer.py`): Appends one line to the HUD session log (JSON-Lines format).
- **`extract_last_model_response()`** (`post_invocation_hook.py`): Extract the last assistant message text from conversation messages.
- **`extract_last_user_message()`** (`post_invocation_hook.py`): Extract the last user message text.
- **`classify_insight()`** (`post_invocation_hook.py`): Classify text into an insight category. Returns (category, excerpt).
- **`main()`** (`post_invocation_hook.py`): No description
- **`run_post_invocation_hook()`** (`post_invocation_hook.py`): Async wrapper for post-invocation state recording.
- **`run_post_tool_hook()`** (`post_tool_hook.py`): Captures post-tool execution telemetry and signal metrics.
- **`main()`** (`post_tool_hook.py`): No description
- **`auto_disclose_domain_specs()`** (`pre_invocation_hook.py`): Auto-discloses relevant domain specifications based on prompt intent.
- **`clean_user_prompt()`** (`pre_invocation_hook.py`): No description
- **`extract_user_prompt()`** (`pre_invocation_hook.py`): Extract the most recent user prompt from hook data across all Antigravity formats.
- **`auto_select_skills()`** (`pre_invocation_hook.py`): Uses NousResearch HermesSkillEngine to dynamically match skills for user prompt.
- **`auto_retrieve_memory()`** (`pre_invocation_hook.py`): Passively retrieves profile, skills catalog, semantic facts, and traces.
- **`build_skills_injection()`** (`pre_invocation_hook.py`): Formats loaded skills into a readable injection block.
- **`generate_executive_briefing()`** (`pre_invocation_hook.py`): Generates a high-level JIT executive briefing HUD for Vazus OS.
- **`create_default_mcp_gateway()`** (`pre_invocation_hook.py`): Constructs and populates DynamicMCPGateway with standard Vazus OS tools.
- **`get_default_mcp_gateway()`** (`pre_invocation_hook.py`): No description
- **`run_pre_invocation()`** (`pre_invocation_hook.py`): Pre-invocation lifecycle hook execution:
- **`main()`** (`pre_invocation_hook.py`): No description
- **`handle_pre_invocation()`** (`pre_invocation_hook.py`): Synchronous processor for pre-invocation hook data with Watchdog and J-Space checks.
- **`run_pre_invocation_hook()`** (`pre_invocation_hook.py`): Async wrapper for pre-invocation hook execution and context injection.
- **`get_substrate_guard()`** (`pre_tool_hook.py`): No description
- **`run_pre_tool()`** (`pre_tool_hook.py`): Evaluator delegating directly to formal SMT Z3 SubstrateGuard.
- **`main()`** (`pre_tool_hook.py`): No description
- **`pre_tool_enforce_security_jail()`** (`pre_tool_hook.py`): Enforces strict path jail security boundaries under sub-50ms latency.
- **`check_code_intelligence_readiness()`** (`session_start_hook.py`): Checks cbm (Codebase Memory) and ast-grep readiness with zero network delay.
- **`check_ckb_connectivity()`** (`session_start_hook.py`): Compatibility alias for CKB / CBM graph connectivity.
- **`warm_database_pool()`** (`session_start_hook.py`): Warms the async connection pool and executes integrity and metrics checks in single thread dispatch.
- **`run_session_start()`** (`session_start_hook.py`): Executes full session start initialization, GC freezing, schema migration, and health verification.
- **`run_session_start_hook()`** (`session_start_hook.py`): Compatibility lifecycle wrapper for session start hook.
- **`main()`** (`session_start_hook.py`): No description
- **`extract_all_user_messages()`** (`stop_hook.py`): Extract all user messages from conversation history.
- **`extract_all_model_responses()`** (`stop_hook.py`): Extract all model response texts from conversation history.
- **`build_session_summary()`** (`stop_hook.py`): Build a compact semantic session summary.
- **`check_pending_verification()`** (`stop_hook.py`): Check if any Z3 verification, Pytest suite, or Concordia Jury vote is pending.
- **`auto_curate_session_memory()`** (`stop_hook.py`): Anthropic Memory Loop — Curation Phase.
- **`main()`** (`stop_hook.py`): No description
- **`run_stop_hook()`** (`stop_hook.py`): Async wrapper for stop hook consolidation.

### 2.4 Invariant Guarantees & Safety Policies (Invariants & Safety Guarantees)
- Invariant 1: Pre-tool security checks complete within 50.0 ms latency limit.
- Invariant 2: File operations outside workspace boundaries are strictly blocked (fail-closed).
- Invariant 3: Post-tool telemetry and HUD event streams never raise unhandled exceptions.

## 3. Progressive Skill Level (Level 1..5 Capability Maturity) & Upgrade Criteria
- **Level 1 (Basic Logging Hooks)**: Synchronous terminal print statements and basic hook wrappers.  
  *Upgrade criteria*: Add path validation and structured telemetry recording.
- **Level 2 (Path Jail & Latency Budgeting)**: Zero-trust path security enforcement and sub-50ms execution timers.  
  *Upgrade criteria*: Implement dynamic skill loading and MCP gateway tool masking.
- **Level 3 (Adaptive MCP Gateway & HUD)**: Intent-schema overlap scoring, observation masking, and live HUD event streaming.  
  *Upgrade criteria*: Add closed-loop maintenance triggering and test failure capture.
- **Level 4 (Closed-Loop Signal Interception)**: Autonomous test failure capture, reflexion routing, and progressive domain disclosure.  
  *Upgrade criteria*: Integrate predictive security anomaly detection.
- **Level 5 (Autonomous Self-Governing Membrane)**: Zero-overhead non-blocking interceptors, self-tuning latency thresholds, and formal safety guardrails.

## 4. Known Bottlenecks & Failure Modes (Optimization Backlog)
- [ ] Cold-start initialization latency during session_start database pool warming.
- [ ] File system stat overhead on large repository path scans during pre-tool verification.
- [ ] High-frequency IPC event queue saturation under rapid tool execution.

## 5. Extension Points & Integration
- Integrates with `vazus_core` through standard Python imports and canonical facade APIs.
- Auto-indexed by `AutoIndexRunner` and monitored by `hooks.json` lifecycle hooks.
