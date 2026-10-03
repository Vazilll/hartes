"""
vazus_core.maintenance.auto_index_runner — Self-Sustaining Protocol: Index & Spec Auto-Synchronizer.

Ensures that upon task or invocation completion:
1. Every modified or active component block has an up-to-date formal SPEC.md.
2. The codebase SCIP/AST symbol index is updated and synchronized.
3. Invariants, contracts, and exported public APIs are formally documented.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger("vazus_core.maintenance")

VAZUS_ROOT = Path(os.getenv("VAZUS_WORKSPACE_DIR", r"C:\vazus")).resolve()
VAZUS_CORE = VAZUS_ROOT / "vazus_core"


DOMAIN_METADATA: Dict[str, Dict[str, Any]] = {
    "engine": {
        "title": "Core Reasoning & Execution Engine",
        "mission": "The `engine` component operates as the central reasoning, execution, and verification backbone of Vazus SuperGraph OS. It provides AST code topology mapping, dynamic skill dispatching, subagent lifecycle orchestration, SMT Z3 formal logic verification, Concordia multi-agent jury consensus arbitration, and self-healing compilation loops.",
        "allowed": [
            "Deterministic execution of AST-verified symbols and local REPL sandboxes.",
            "Dynamic skill matching and intent parsing via DynamicSkillDispatcher.",
            "SMT Z3 contract proof validation and Concordia jury consensus voting (>= 66%).",
            "AST signature pruning achieving token economy and repo map generation.",
        ],
        "prohibited": [
            "Unsandboxed arbitrary shell or code execution escaping workspace boundaries.",
            "Unauthorized external billing API imports and external token budget leaks.",
            "Infinite retry loops or unbounded recursion in self-healing compiler loops.",
            "Blocking main event loop with heavy CPU-bound graph analysis.",
        ],
        "invariants": [
            "Invariant 1: Formal verification guarantees UNSAT contract proofs before code promotion.",
            "Invariant 2: Dynamic skill dispatch enforces sub-50ms intent matching and sandbox bypass rules.",
            "Invariant 3: Multi-agent consensus requires at least 66% affirmative votes to commit code changes.",
        ],
        "levels": {
            1: (
                "Basic Execution Runtime",
                "Single-turn execution, baseline AST parsing, and standalone REPL execution.",
                "Add structured error handling and unit test coverage.",
            ),
            2: (
                "Resilient Subagent Pipeline",
                "Multi-step subagent execution with circuit breakers and timeout governors.",
                "Integrate typed contracts and SQLite WAL logging.",
            ),
            3: (
                "Integrated SuperGraph & SMT",
                "Full integration with AST repo mapping, SMT Z3 verification, and Concordia jury.",
                "Add autonomous self-healing compiler and memory feedback loops.",
            ),
            4: (
                "Autonomous Self-Healing Loop",
                "Closed-loop failure diagnosis, AST pruning, and Reflexion memory integration.",
                "Support distributed execution and NPU hardware acceleration.",
            ),
            5: (
                "Self-Sustaining Cognitive Governor",
                "Zero manual intervention, autonomous task routing, and verified invariant stability.",
                "",
            ),
        },
        "bottlenecks": [
            "- [ ] Subprocess latency during recursive self-healing compiler invocations under heavy load.",
            "- [ ] AST parsing overhead on deeply nested multi-thousand LOC modules.",
            "- [ ] Rate limiting on external LLM calls during dialectical synthesis.",
        ],
    },
    "memory": {
        "title": "Persistent Multi-Tiered Memory & Knowledge Graph Subsystem",
        "mission": "The `memory` component provides persistent multi-tiered memory governance, Mem0 episodic fact storage, SQLite WAL pooling, 768-D vector embeddings (UnifiedGoogleEmbedder and OpenVINO NPU), and biological sleep-time dream consolidation within Vazus SuperGraph OS.",
        "allowed": [
            "Thread-safe SQLite WAL queries, transactions, and connection pooling via AsyncDatabasePool.",
            "Bitemporal fact updates and 768-D cosine similarity indexing with SIMD/AVX-512 acceleration.",
            "Memory tier promotion from UNTRUSTED_OBSERVATION to VERIFIED_FACT.",
            "Dream consolidation, reflexion lesson storage, and Karpathy markdown wiki synchronization.",
        ],
        "prohibited": [
            "Writing unverified user preferences or mutating facts without explicit instruction.",
            "Unbounded database growth exceeding statutory 25.0 MB invariant limit.",
            "Naked SQLite connections bypassing shared connection proxy or WAL mode.",
            "Storing unindexed raw embeddings outside vector index tables.",
        ],
        "invariants": [
            "Invariant 1: All SQLite operations enforce WAL journal mode with exponential retry backoffs.",
            "Invariant 2: Database file size is strictly capped <= 25.0 MB via automated VACUUM and pruning.",
            "Invariant 3: 768-dimensional embeddings maintain L2 normalization for exact cosine indexing.",
        ],
        "levels": {
            1: (
                "Direct File Storage",
                "File-based JSON and markdown note storage with synchronous file writes.",
                "Migrate storage to SQLite with WAL mode.",
            ),
            2: (
                "Transactional SQLite WAL",
                "Shared connection pooling, thread safety, and structured fact tables.",
                "Add vector embeddings and semantic similarity search.",
            ),
            3: (
                "Multi-Tiered Vector Store",
                "768-D vector embeddings, AVX-512 SIMD search, and Mem0 episodic fact management.",
                "Implement sleep-time dream consolidation and reflexion lessons.",
            ),
            4: (
                "Dream Consolidation & Self-Healing",
                "Asynchronous consolidation of lessons, bitemporal fact reconciliation, and wiki graph linking.",
                "Support NPU on-device embedding acceleration.",
            ),
            5: (
                "Self-Sustaining Knowledge Organism",
                "Fully closed memory loops, autonomous dream compaction, zero dangling edges, and proactive context injection.",
                "",
            ),
        },
        "bottlenecks": [
            "- [ ] SQLite WAL checkpoint contention during high-frequency concurrent subagent flushes.",
            "- [ ] 768-D embedding inference latency when falling back from NPU to CPU.",
            "- [ ] Graph edge orphan accumulation in kg_edges before dream consolidator prune runs.",
        ],
    },
    "hooks": {
        "title": "Real-Time Lifecycle Interception & Security Hooks Subsystem",
        "mission": "The `hooks` component governs real-time lifecycle interception across all agent execution stages (session_start, pre_invocation, pre_tool, post_tool, post_invocation, stop). It enforces sub-50ms latency constraints, strict zero-trust path jail boundaries, MCP gateway tool masking, and execution signal telemetry.",
        "allowed": [
            "Sub-50ms pre-tool path checks, security jail enforcement, and tool output masking.",
            "Dynamic skill selection, MCP gateway routing, and intent-schema overlap filtering.",
            "Real-time HUD telemetry streaming and execution signal recording.",
            "Non-blocking background maintenance scheduling via AutoIndexRunner.",
        ],
        "prohibited": [
            "Lifecycle hook latency exceeding statutory 50.0 ms threshold under normal operation.",
            "Spawning unbounded background processes or detached compilation daemons.",
            "Modifying tool execution state or return values outside declared hook contracts.",
            "Bypassing path jail security validation on tool file mutations.",
        ],
        "invariants": [
            "Invariant 1: Pre-tool security checks complete within 50.0 ms latency limit.",
            "Invariant 2: File operations outside workspace boundaries are strictly blocked (fail-closed).",
            "Invariant 3: Post-tool telemetry and HUD event streams never raise unhandled exceptions.",
        ],
        "levels": {
            1: (
                "Basic Logging Hooks",
                "Synchronous terminal print statements and basic hook wrappers.",
                "Add path validation and structured telemetry recording.",
            ),
            2: (
                "Path Jail & Latency Budgeting",
                "Zero-trust path security enforcement and sub-50ms execution timers.",
                "Implement dynamic skill loading and MCP gateway tool masking.",
            ),
            3: (
                "Adaptive MCP Gateway & HUD",
                "Intent-schema overlap scoring, observation masking, and live HUD event streaming.",
                "Add closed-loop maintenance triggering and test failure capture.",
            ),
            4: (
                "Closed-Loop Signal Interception",
                "Autonomous test failure capture, reflexion routing, and progressive domain disclosure.",
                "Integrate predictive security anomaly detection.",
            ),
            5: (
                "Autonomous Self-Governing Membrane",
                "Zero-overhead non-blocking interceptors, self-tuning latency thresholds, and formal safety guardrails.",
                "",
            ),
        },
        "bottlenecks": [
            "- [ ] Cold-start initialization latency during session_start database pool warming.",
            "- [ ] File system stat overhead on large repository path scans during pre-tool verification.",
            "- [ ] High-frequency IPC event queue saturation under rapid tool execution.",
        ],
    },
    "verification": {
        "title": "Formal Logic & Multi-Agent Verification Subsystem",
        "mission": "The `verification` component provides formal SMT Z3 contract verification, Concordia multi-agent jury consensus arbitration (3-agent panel), adaptive complexity gating, and pre-commit safety guardrails.",
        "allowed": [
            "AST-level precondition and postcondition parsing (:requires: / @requires).",
            "SMT Z3 UNSAT proof generation and formal contract solving.",
            "Concordia multi-agent jury consensus evaluation with weighted rubrics.",
            "Adaptive complexity classification across Micro, Standard, and Architecture changes.",
        ],
        "prohibited": [
            "Promoting unverified code changes bypassing SMT Z3 or jury consensus gates.",
            "Executing unsafe arbitrary code during precondition evaluation.",
            "Hardcoding mock verification results or bypassing fail-closed verification rules.",
        ],
        "invariants": [
            "Invariant 1: All SMT Z3 contract verifications require formal UNSAT proofs before approval.",
            "Invariant 2: Concordia multi-agent jury requires minimum 66% consensus for code modifications.",
            "Invariant 3: Fail-closed fallback triggers when theorem prover encounters timeout or unknown status.",
        ],
        "levels": {
            1: ("Heuristic Linting", "Basic syntax checks and AST linting.", "Implement automated unit testing gates."),
            2: (
                "Automated Unit & TDD Gates",
                "Pytest suite execution and targeted regression testing.",
                "Add formal contract specifications.",
            ),
            3: (
                "Formal SMT Z3 Verification",
                "Mathematical contract verification using Z3 theorem prover.",
                "Implement multi-agent consensus arbitration.",
            ),
            4: (
                "Concordia Multi-Agent Jury",
                "Autonomous 3-agent jury deliberation with adaptive complexity classification.",
                "Integrate closed-loop self-healing verification.",
            ),
            5: (
                "Self-Verifying Cognitive Core",
                "Formal end-to-end correctness proofs with zero-regression guarantees.",
                "",
            ),
        },
        "bottlenecks": [
            "- [ ] Theorem prover solver timeout on complex non-linear integer arithmetic.",
            "- [ ] Multi-agent consensus deliberation latency across diverse model APIs.",
        ],
    },
    "roles": {
        "title": "Subagent Roles & Archetype Definitions",
        "mission": "The `roles` component defines declarative archetypes, capabilities, system prompts, and tool access matrices for specialized Vazus OS subagents (planner, coder, verifier, reviewer, finance, health, vision).",
        "allowed": [
            "Declarative archetype definition and Hermes skill loading configuration.",
            "Role capability mapping and token budget allocation.",
            "Dynamic persona switching and task-specific prompt customization.",
        ],
        "prohibited": [
            "Assigning privileged execution rights to unverified subagents.",
            "Exceeding subagent memory or token allocation thresholds.",
        ],
        "invariants": [
            "Invariant 1: Subagent archetypes operate strictly within their declared capability boundaries.",
            "Invariant 2: Role prompt templates preserve security jail and fail-closed instructions.",
        ],
        "levels": {
            1: ("Static Prompts", "Hardcoded role descriptions.", "Implement declarative role templates."),
            2: (
                "Declarative Templates",
                "Config-driven subagent definitions with tool bindings.",
                "Add dynamic skill selection.",
            ),
            3: (
                "Dynamic Skill Integration",
                "Context-aware Hermes skill and MCP tool disclosure.",
                "Implement multi-agent teamwork orchestration.",
            ),
            4: (
                "Autonomous Teamwork",
                "Collaborative multi-role teamwork with specialized handoffs.",
                "Integrate continuous role capability evolution.",
            ),
            5: (
                "Self-Evolving Subagent Matrix",
                "Continuous self-assessment and autonomous archetype specialization.",
                "",
            ),
        },
        "bottlenecks": [
            "- [ ] Prompt overhead during multi-role context switching.",
        ],
    },
    "workers": {
        "title": "Distributed & Background Workers Subsystem",
        "mission": "The `workers` component executes decoupled background tasks, asynchronous telemetry collection, parallel verification jobs, and long-running maintenance pipelines.",
        "allowed": [
            "Non-blocking background thread and process execution.",
            "Bounded worker thread pools with strict memory and CPU caps.",
            "Graceful worker termination and signal handling.",
        ],
        "prohibited": [
            "Spawning unmonitored orphan daemon processes or unbounded threads.",
            "Worker process memory accumulation exceeding 300 MB.",
        ],
        "invariants": [
            "Invariant 1: All worker tasks run with execution timeouts and isolated failure domains.",
            "Invariant 2: Terminated worker process trees are cleanly reaped without leaking handles.",
        ],
        "levels": {
            1: ("Synchronous Tasks", "Inline single-threaded execution.", "Add background thread pools."),
            2: (
                "Thread Pool Execution",
                "Isolated ThreadPoolExecutor for long tasks.",
                "Implement process-level isolation and resource caps.",
            ),
            3: (
                "Resource-Guarded Workers",
                "Subprocess execution with memory and CPU watchdogs.",
                "Add distributed worker queue management.",
            ),
            4: (
                "Resilient Asynchronous Grid",
                "Self-recovering worker queues with dead-letter handling.",
                "Integrate autonomous load balancing.",
            ),
            5: (
                "Autonomous Workload Governor",
                "Dynamic elastic scaling across CPU, NPU, and remote execution bridges.",
                "",
            ),
        },
        "bottlenecks": [
            "- [ ] Process creation overhead on Windows platforms.",
        ],
    },
    "maintenance": {
        "title": "Self-Sustaining Codebase Maintenance & Indexing Subsystem",
        "mission": "The `maintenance` component enforces continuous codebase hygiene, synchronizes SCIP/CKB symbol indices with strict concurrency mutex locking (.ckb/indexing.lock), auto-generates domain specifications (SPEC.md), and terminates zombie indexing processes.",
        "allowed": [
            "Atomic mutex acquisition (.ckb/indexing.lock) and process tree lifecycle governance.",
            "AST extraction and automatic SPEC.md multi-tier synchronization.",
            "Pyright configuration scoping and SCIP index stale detection.",
            "Resource-bounded indexing execution with NODE_OPTIONS memory limits.",
        ],
        "prohibited": [
            "Running parallel concurrent SCIP/CKB indexing processes.",
            "Blocking file editing hooks with detached compilation daemons.",
            "Allowing orphan node.exe or ckb.exe processes to accumulate in OS memory.",
        ],
        "invariants": [
            "Invariant 1: At most 1 indexing process runs system-wide (enforced via IndexingLockManager).",
            "Invariant 2: Full background indexing completes within 30 seconds under 300 MB RSS.",
            "Invariant 3: Component SPEC.md generation preserves multi-tier structure and typed contracts.",
        ],
        "levels": {
            1: ("Manual Maintenance", "Ad-hoc command-line script execution.", "Implement automated post-tool hooks."),
            2: (
                "Hook-Driven Indexing",
                "Automatic spec updates and indexing triggered on file mutations.",
                "Add concurrency mutex and process watchdog.",
            ),
            3: (
                "Concurrency-Guarded Indexer",
                "Strict PID locking, stale eviction, and RSS memory caps.",
                "Implement multi-tier spec generation and feedback loops.",
            ),
            4: (
                "Self-Healing Spec Synchronizer",
                "Automatic typed contract extraction, failure mode tracking, and closed loops.",
                "Support continuous autonomous repository refactoring.",
            ),
            5: (
                "Self-Sustaining Repository Organism",
                "Fully autonomous, zero-leak codebase stewardship and self-synchronizing architecture.",
                "",
            ),
        },
        "bottlenecks": [
            "- [ ] Pyright index generation time on cold start repositories.",
            "- [ ] Windows file locking semantics during rapid concurrent indexer access.",
        ],
    },
}


class SpecSynchronizer:
    """
    Automated extractor and synchronizer for modular component specifications (SPEC.md).
    Parses component Python modules via AST and generates or updates canonical SPEC.md files.
    """

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or VAZUS_CORE).resolve()

    def inspect_module_ast(self, py_file: Path) -> Dict[str, Any]:
        """Parses a Python file using AST and extracts public symbols and docstrings."""
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(py_file))
        except Exception as e:
            logger.debug("Failed to parse AST for %s: %s", py_file, e)
            return {"file": str(py_file.name), "classes": [], "functions": [], "docstring": ""}

        docstring = ast.get_docstring(tree) or ""
        classes = []
        functions = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    cls_doc = ast.get_docstring(node) or ""
                    methods = [
                        m.name
                        for m in node.body
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("_")
                    ]
                    typed_methods = []
                    for m in node.body:
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("_"):
                            prefix = "async def " if isinstance(m, ast.AsyncFunctionDef) else "def "
                            try:
                                args_str = ast.unparse(m.args)
                                ret_str = f" -> {ast.unparse(m.returns)}" if m.returns else ""
                                typed_methods.append(f"{prefix}{m.name}({args_str}){ret_str}: ...")
                            except Exception:
                                typed_methods.append(f"{prefix}{m.name}(...): ...")
                    classes.append(
                        {
                            "name": node.name,
                            "docstring": cls_doc.strip().split("\n")[0] if cls_doc else "No description",
                            "methods": methods,
                            "typed_methods": typed_methods,
                        }
                    )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    fn_doc = ast.get_docstring(node) or ""
                    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
                    try:
                        args_str = ast.unparse(node.args)
                        ret_str = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                        fn_sig = f"{prefix}{node.name}({args_str}){ret_str}: ..."
                    except Exception:
                        fn_sig = f"{prefix}{node.name}(...): ..."
                    functions.append(
                        {
                            "name": node.name,
                            "docstring": fn_doc.strip().split("\n")[0] if fn_doc else "No description",
                            "typed_signature": fn_sig,
                        }
                    )

        return {
            "file": py_file.name,
            "docstring": docstring.strip().split("\n")[0] if docstring else "",
            "classes": classes,
            "functions": functions,
        }

    def generate_spec_markdown(self, component_dir: Path) -> str:
        """Generates a canonical SPEC.md content for a given component directory."""
        component_name = component_dir.name
        try:
            rel_path = component_dir.relative_to(VAZUS_ROOT).as_posix()
        except ValueError:
            rel_path = component_name
        py_files = sorted(list(component_dir.glob("*.py")))

        modules_info = []
        all_classes = []
        all_functions = []

        for pf in py_files:
            info = self.inspect_module_ast(pf)
            modules_info.append(info)
            for c in info["classes"]:
                all_classes.append((pf.name, c))
            for f in info["functions"]:
                all_functions.append((pf.name, f))

        meta = DOMAIN_METADATA.get(component_name, {})
        title = meta.get("title", f"{component_name.capitalize()} Domain Subsystem")
        mission_desc = meta.get(
            "mission",
            f"The `{component_name}` component operates as a self-contained modular domain within Vazus SuperGraph OS. It provides deterministic interfaces, handles domain logic, and enforces fail-closed error handling.",
        )
        allowed_items = meta.get(
            "allowed",
            [
                f"Deterministic execution of `{component_name}` public APIs and AST-verified symbols.",
                "Thread-safe SQLite WAL queries and state mutations with exponential backoff.",
                "Fast-fail validation and zero-trust parameter verification.",
            ],
        )
        prohibited_items = meta.get(
            "prohibited",
            [
                "Unbounded memory consumption or persistent handle leaks.",
                "Blocking event loops or unhandled exceptions escaping domain boundary.",
                "Modifying external state outside workspace jail boundaries.",
            ],
        )
        invariants = meta.get(
            "invariants",
            [
                "Invariant 1: All operations enforce strict Zero-Trust input validation.",
                "Invariant 2: Database mutations utilize WAL mode and rollback on exception.",
                "Invariant 3: Public APIs maintain typed interfaces with sub-50ms latency guarantees.",
            ],
        )
        levels = meta.get(
            "levels",
            {
                1: (
                    "Basic Operations",
                    "Foundational symbol definitions and synchronous executions.",
                    "Add structured error handling and unit test coverage.",
                ),
                2: (
                    "Resilient Handling",
                    "Fail-closed error boundaries and bounded memory usage.",
                    "Integrate typed contracts and WAL storage.",
                ),
                3: (
                    "Integrated Subsystem",
                    "Full integration with lifecycle hooks and SuperGraph OS telemetry.",
                    "Add formal SMT Z3 contract verification.",
                ),
                4: (
                    "Autonomous Closed-Loop",
                    "Self-healing error correction and Reflexion memory integration.",
                    "Support distributed or NPU-accelerated execution.",
                ),
                5: (
                    "Self-Sustaining Governor",
                    "Closed-loop autonomous adaptation, zero manual intervention, and verified invariant stability.",
                    "",
                ),
            },
        )
        bottlenecks = meta.get(
            "bottlenecks",
            [
                "- [ ] Concurrency contention during high-frequency SQLite WAL writes under peak load.",
                "- [ ] Serialization latency on deep AST traversal across large files.",
                "- [ ] Memory footprint under heavy micro-batching operations.",
            ],
        )

        lines = [
            f"# Domain Specification: `{component_name}` ({title})",
            "",
            f"> **Subsystem**: `vazus_core/{component_name}`  ",
            f"> **Path**: `{rel_path}`  ",
            f"> **Last Auto-Synchronized**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
            "",
            "## 1. Core Mission & Domain Scope (Responsibilities & Boundaries)",
            "### 1.1 Primary Mission",
            mission_desc,
            "",
            "### 1.2 Strict Boundary Rules",
            "- **ALLOWED**:",
        ]
        for a in allowed_items:
            lines.append(f"  - {a}")
        lines.append("- **PROHIBITED**:")
        for p in prohibited_items:
            lines.append(f"  - {p}")
        lines.append("")

        lines.extend(
            [
                "## 2. Public Typed Interface Contracts (Public Interface Contracts)",
                "### 2.1 Primary Classes & Signatures",
                "```python",
                "from typing import Dict, Any, List, Optional, Union, Tuple, Set",
                "from pathlib import Path",
                "",
            ]
        )

        if all_classes or all_functions:
            for pf_name, cls in all_classes:
                lines.append(f"class {cls['name']}:")
                typed_methods = cls.get("typed_methods", [])
                if typed_methods:
                    for m_sig in typed_methods[:8]:
                        lines.append(f"    {m_sig}")
                    if len(typed_methods) > 8:
                        lines.append(f"    # ... (+{len(typed_methods) - 8} additional methods)")
                else:
                    lines.append("    pass")
                lines.append("")
            for pf_name, fn in all_functions:
                fn_sig = fn.get("typed_signature", f"def {fn['name']}(): ...")
                lines.append(fn_sig)
            if all_functions:
                lines.append("")
        else:
            lines.append("# No public exported classes or functions discovered in domain module")
            lines.append("")
        lines.extend(
            [
                "```",
                "",
            ]
        )

        if all_classes:
            lines.append("### 2.2 Exported Classes")
            for pf_name, cls in all_classes:
                methods_str = ", ".join(cls["methods"][:5])
                if len(cls["methods"]) > 5:
                    methods_str += f", ... (+{len(cls['methods']) - 5})"
                lines.append(f"- **`{cls['name']}`** (`{pf_name}`): {cls['docstring']}")
                if methods_str:
                    lines.append(f"  - *Methods*: `{methods_str}`")
            lines.append("")

        if all_functions:
            lines.append("### 2.3 Exported Functions")
            for pf_name, fn in all_functions:
                lines.append(f"- **`{fn['name']}()`** (`{pf_name}`): {fn['docstring']}")
            lines.append("")

        lines.extend(
            [
                "### 2.4 Invariant Guarantees & Safety Policies (Invariants & Safety Guarantees)",
            ]
        )
        for inv in invariants:
            lines.append(f"- {inv}")
        lines.append("")

        lines.append("## 3. Progressive Skill Level (Level 1..5 Capability Maturity) & Upgrade Criteria")
        for lvl in range(1, 6):
            title_lvl, desc_lvl, upgrade_lvl = levels.get(lvl, (f"Level {lvl}", "Standard operations.", ""))
            upgrade_str = f"  \n  *Upgrade criteria*: {upgrade_lvl}" if upgrade_lvl else ""
            lines.append(f"- **Level {lvl} ({title_lvl})**: {desc_lvl}{upgrade_str}")
        lines.append("")

        lines.append("## 4. Known Bottlenecks & Failure Modes (Optimization Backlog)")
        for b in bottlenecks:
            lines.append(b)
        lines.append("")

        lines.extend(
            [
                "## 5. Extension Points & Integration",
                "- Integrates with `vazus_core` through standard Python imports and canonical facade APIs.",
                "- Auto-indexed by `AutoIndexRunner` and monitored by `hooks.json` lifecycle hooks.",
                "",
            ]
        )

        return "\n".join(lines)

    def sync_component_spec(self, component_dir: Path, force: bool = False) -> bool:
        """Synchronizes SPEC.md for the component if missing or updated."""
        if not component_dir.is_dir():
            return False

        spec_file = component_dir / "SPEC.md"
        generated = self.generate_spec_markdown(component_dir)

        if spec_file.exists() and not force:
            try:
                current = spec_file.read_text(encoding="utf-8", errors="replace")
                # If current has MANUAL preservation section, keep it
                if "<!-- MANUAL_SPEC_BEGIN -->" in current and "<!-- MANUAL_SPEC_END -->" in current:
                    manual_part = current.split("<!-- MANUAL_SPEC_BEGIN -->")[1].split("<!-- MANUAL_SPEC_END -->")[0]
                    generated += f"\n<!-- MANUAL_SPEC_BEGIN -->\n{manual_part}\n<!-- MANUAL_SPEC_END -->\n"
            except Exception as e:
                logger.debug("Error checking existing SPEC.md: %s", e)

        spec_file.write_text(generated, encoding="utf-8")
        logger.info("Synchronized specification: %s", spec_file)
        return True


class IndexingLockManager:
    """
    Concurrency Mutex & Active Process Guard.
    Guarantees at most 1 active indexing process runs across the entire host OS.
    Stores metadata in .ckb/indexing.lock and performs psutil OS process checks with stale eviction.
    """

    LOCK_FILE = VAZUS_ROOT / ".ckb" / "indexing.lock"
    MAX_LOCK_AGE_SECONDS = 120.0  # Stale lock threshold
    _thread_lock = threading.RLock()

    @classmethod
    def is_indexer_process_running(cls) -> Tuple[bool, Optional[int], str]:
        """
        Scans active OS processes for any running instance of ckb index or scip-python.
        O(N) fast iteration via psutil. Excludes shell interpreters and long-running MCP servers ('ckb mcp').
        """
        shell_names = {"powershell.exe", "pwsh.exe", "cmd.exe", "bash.exe", "sh.exe", "zsh.exe"}
        indexer_binaries = {"node.exe", "node", "ckb.exe", "ckb", "scip-python.exe", "scip-python"}

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info["name"] or "").lower()
                if name in shell_names:
                    continue
                if name not in indexer_binaries:
                    continue

                cmdline = " ".join(proc.cmdline() or []).lower()
                if "mcp" in cmdline:
                    continue

                if "ckb" in name or "ckb" in cmdline:
                    if "index" in cmdline:
                        return True, proc.info["pid"], f"ckb index ({name})"
                if "scip-python" in cmdline and "index" in cmdline:
                    return True, proc.info["pid"], f"scip-python ({name})"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False, None, ""

    @classmethod
    def is_pid_indexer(cls, pid: Any) -> bool:
        """
        Checks if a given PID is alive and belongs to an active indexer or indexing runner process.
        Rejects dead PIDs, shell processes, and unrelated system processes (e.g. svchost.exe).
        """
        if not isinstance(pid, int) or pid <= 0:
            return False
        try:
            if not psutil.pid_exists(pid):
                return False
            proc = psutil.Process(pid)
            name = (proc.name() or "").lower()

            # Shells are never indexers
            if name in {"powershell.exe", "pwsh.exe", "cmd.exe", "bash.exe", "sh.exe", "zsh.exe"}:
                return False

            # System or unrelated processes (e.g. recycled Windows PIDs)
            if any(k in name for k in ["svchost", "explorer", "services", "system", "lsass", "csrss", "conhost"]):
                return False

            # Valid indexer binaries
            if any(k in name for k in ["node", "ckb", "scip-python"]):
                return True

            # Valid python runner processes (vazus maintenance, pytest, test harness)
            if any(k in name for k in ["python", "pytest"]):
                cmdline = " ".join(proc.cmdline() or []).lower()
                if pid == os.getpid() or any(
                    k in cmdline for k in ["vazus", "index", "scip", "pytest", "auto_index_runner"]
                ):
                    return True
                return False

            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    @classmethod
    def acquire(cls, trigger: str = "auto") -> bool:
        """
        Atomically acquires .ckb/indexing.lock if no valid indexer is running.
        Guarantees mutual exclusion across threads and processes via open-first
        atomic test-and-set (os.O_CREAT | os.O_EXCL).
        Returns True if acquired, False otherwise.
        """
        with cls._thread_lock:
            cls.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
            now = time.time()
            lock_payload = {
                "pid": os.getpid(),
                "started_at": now,
                "trigger": trigger,
                "hostname": os.getenv("COMPUTERNAME", "localhost"),
                "host": os.getenv("COMPUTERNAME", "localhost"),
            }
            payload_bytes = json.dumps(lock_payload, indent=2).encode("utf-8")

            for attempt in range(3):
                # Step 1: Open-first atomic creation via low-level OS flags
                try:
                    fd = os.open(str(cls.LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    try:
                        os.write(fd, payload_bytes)
                    finally:
                        os.close(fd)

                    # Step 2: OS process table check guard for unmanaged indexers
                    running, r_pid, r_desc = cls.is_indexer_process_running()
                    if running and r_pid != os.getpid():
                        logger.warning(
                            "Active indexing process detected in OS process table: PID %s [%s]. Skipping concurrent spawn.",
                            r_pid,
                            r_desc,
                        )
                        cls.release(force=True)
                        return False

                    return True

                except (FileExistsError, PermissionError):
                    # Step 3: File already exists — inspect existing lock file
                    valid_json = False
                    data = None

                    # Winner might be in the middle of writing bytes; back off 20ms before deciding corrupt
                    for read_attempt in range(2):
                        try:
                            if cls.LOCK_FILE.exists():
                                raw = cls.LOCK_FILE.read_text(encoding="utf-8").strip()
                                if raw:
                                    data = json.loads(raw)
                                    valid_json = True
                                    break
                        except Exception:
                            pass
                        if read_attempt == 0:
                            time.sleep(0.02)  # 20ms backoff

                    if not valid_json:
                        if not cls.LOCK_FILE.exists():
                            continue
                        logger.warning("Corrupted lock file encountered, resetting.")
                        cls.release(force=True)
                        continue

                    if isinstance(data, dict):
                        pid = data.get("pid")
                        started_at = data.get("started_at", 0.0)
                        try:
                            started_at = float(started_at)
                        except (ValueError, TypeError):
                            started_at = 0.0
                        age = now - started_at

                        if age < cls.MAX_LOCK_AGE_SECONDS and cls.is_pid_indexer(pid):
                            logger.warning(
                                "Indexing lock already held by active PID %s (age %.1fs). Skipping concurrent spawn.",
                                pid,
                                age,
                            )
                            return False

                        # Stale (> 120s), dead PID, or recycled non-indexer PID -> Evict and retry
                        logger.warning("Evicting stale/dead/recycled indexing lock (PID %s, age %.1fs)", pid, age)
                        cls.release(force=True)
                        continue
                    else:
                        logger.warning("Lock file payload is not a valid dict, resetting.")
                        cls.release(force=True)
                        continue

                except Exception as err:
                    logger.error("Failed to acquire indexing lock: %s", err)
                    return False

            return False

    @classmethod
    def release(cls, force: bool = False) -> None:
        """Releases the lock file."""
        with cls._thread_lock:
            try:
                if cls.LOCK_FILE.exists():
                    cls.LOCK_FILE.unlink(missing_ok=True)
                    logger.debug("Indexing lock released.")
            except Exception as e:
                logger.warning("Error releasing indexing lock: %s", e)


class SCIPIndexSynchronizer:
    """Manages incremental or complete SCIP graph reindexing with strict concurrency control."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or VAZUS_ROOT).resolve()
        self.scip_file = self.root_dir / "index.scip"
        self.dirty_marker = self.root_dir / ".ckb" / "index_dirty"

    def mark_dirty(self) -> None:
        """Marks the SCIP index as needing an update without spawning indexer."""
        try:
            self.dirty_marker.parent.mkdir(parents=True, exist_ok=True)
            self.dirty_marker.write_text(str(time.time()), encoding="utf-8")
        except Exception as e:
            logger.debug("Failed to write dirty marker: %s", e)

    def clear_dirty(self) -> None:
        """Clears the dirty marker upon successful reindex."""
        try:
            if self.dirty_marker.exists():
                self.dirty_marker.unlink(missing_ok=True)
        except Exception:
            pass

    def is_index_stale(self, max_age_seconds: float = 3600.0) -> bool:
        """Checks if index.scip is missing, marked dirty, or older than modified Python files."""
        if self.dirty_marker.exists():
            return True

        if not self.scip_file.exists():
            return True

        scip_mtime = self.scip_file.stat().st_mtime
        if (time.time() - scip_mtime) > max_age_seconds:
            return True

        # Check if any .py file in vazus_core is newer than index.scip
        for py_path in (self.root_dir / "vazus_core").glob("**/*.py"):
            try:
                if py_path.stat().st_mtime > scip_mtime:
                    return True
            except OSError:
                continue

        return False

    @staticmethod
    def _terminate_proc_tree(pid: int, timeout: float = 3.0) -> None:
        """Kills a process and all its children safely and synchronously waits for exit."""
        try:
            if not psutil.pid_exists(pid):
                return
            parent = psutil.Process(pid)
            procs = parent.children(recursive=True)
            procs.append(parent)
            for p in procs:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            # Synchronously wait for all processes to exit
            gone, alive = psutil.wait_procs(procs, timeout=timeout)
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    @staticmethod
    def _get_proc_tree_rss_mb(pid: int) -> float:
        """Sums Resident Set Size (RSS) across parent process and all child processes in MB."""
        try:
            if not psutil.pid_exists(pid):
                return 0.0
            parent = psutil.Process(pid)
            total_rss = parent.memory_info().rss
            for child in parent.children(recursive=True):
                try:
                    total_rss += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return total_rss / (1024.0 * 1024.0)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def trigger_scip_reindex(
        self,
        background: bool = True,
        timeout: float = 30.0,
        max_rss_mb: float = 300.0,
    ) -> Dict[str, Any]:
        """
        Triggers SCIP reindexing under strict concurrency and resource guards:
        - Exactly 1 indexer process at a time (enforced via IndexingLockManager).
        - Hard timeout of <= 30 seconds.
        - Memory watchdog killing process tree if RSS exceeds 300 MB.
        - NODE_OPTIONS="--max-old-space-size=256" enforced.
        """
        if not IndexingLockManager.acquire(trigger="scip_syncer"):
            logger.info("Indexing skipped: lock is held by another process.")
            return {"status": "SKIPPED", "reason": "LOCKED"}

        ckb_cmd = shutil.which("ckb.cmd") or shutil.which("ckb")
        if not ckb_cmd:
            for cand in [r"C:\Users\Vaz\AppData\Roaming\npm\ckb.cmd", r"C:\vazus\bin\ckb.cmd"]:
                if os.path.exists(cand):
                    ckb_cmd = cand
                    break

        if not ckb_cmd:
            IndexingLockManager.release()
            logger.warning("ckb command not found for SCIP reindexing")
            return {"status": "ERROR", "reason": "CKB_NOT_FOUND"}

        env = os.environ.copy()
        env["NODE_OPTIONS"] = "--max-old-space-size=256"
        venv_scripts = str(self.root_dir / ".venv" / "Scripts")
        if os.path.exists(venv_scripts):
            env["PATH"] = f"{venv_scripts};" + env.get("PATH", "")

        cmd = [ckb_cmd, "index", "--lang", "py"]

        def _execute_indexer():
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.root_dir),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                start_time = time.time()
                timed_out = False
                oom_killed = False
                while proc.poll() is None:
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        logger.warning("Indexing timed out after %.1fs; terminating process tree.", elapsed)
                        self._terminate_proc_tree(proc.pid)
                        timed_out = True
                        break

                    total_rss_mb = self._get_proc_tree_rss_mb(proc.pid)
                    if total_rss_mb > max_rss_mb:
                        logger.warning(
                            "Indexing exceeded memory limit (%.1f MB > %.1f MB); terminating process tree.",
                            total_rss_mb,
                            max_rss_mb,
                        )
                        self._terminate_proc_tree(proc.pid)
                        oom_killed = True
                        break

                    time.sleep(0.5)

                # Clear dirty marker ONLY if process completed cleanly with exit code 0
                if not timed_out and not oom_killed and proc.poll() == 0:
                    self.clear_dirty()
                    logger.info("SCIP indexing completed successfully; dirty marker cleared.")
                else:
                    logger.warning(
                        "SCIP indexing incomplete or failed (poll=%s, timed_out=%s, oom=%s); preserving dirty marker.",
                        proc.poll(),
                        timed_out,
                        oom_killed,
                    )
            except Exception as ex:
                logger.warning("SCIP reindexing execution error: %s", ex)
            finally:
                IndexingLockManager.release()

        if background:
            t = threading.Thread(target=_execute_indexer, daemon=True, name="SCIPIndexerSupervisor")
            t.start()
            logger.info("Spawned supervised background SCIP indexer.")
            return {"status": "SPAWNED", "background": True}
        else:
            _execute_indexer()
            return {"status": "COMPLETED", "background": False}


class AutoIndexRunner:
    """
    Unified Self-Sustaining Protocol Runner.
    Runs component spec synchronization and SCIP index updates.
    """

    CORE_COMPONENTS = [
        "memory",
        "verification",
        "roles",
        "hooks",
        "engine",
        "workers",
        "maintenance",
    ]

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or VAZUS_ROOT).resolve()
        self.spec_syncer = SpecSynchronizer(self.root_dir / "vazus_core")
        self.index_syncer = SCIPIndexSynchronizer(self.root_dir)

    def sync_all_components(self, force: bool = False) -> List[str]:
        """Synchronizes specifications for all core components."""
        synced = []
        for comp in self.CORE_COMPONENTS:
            comp_dir = self.root_dir / "vazus_core" / comp
            if comp_dir.is_dir():
                if self.spec_syncer.sync_component_spec(comp_dir, force=force):
                    synced.append(comp)
        return synced

    def run(
        self,
        paths: Optional[List[str]] = None,
        force_reindex: bool = False,
        trigger_indexer: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes maintenance pass.
        If paths are provided, synchronizes specifications for touched component blocks.
        If trigger_indexer=False, marks index as dirty without triggering SCIP reindex.
        """
        synced_components = set()

        if paths:
            for p in paths:
                resolved = Path(p).resolve()
                if "vazus_core" in resolved.parts:
                    idx = resolved.parts.index("vazus_core")
                    if len(resolved.parts) > idx + 1:
                        comp_name = resolved.parts[idx + 1]
                        comp_dir = self.root_dir / "vazus_core" / comp_name
                        if comp_dir.is_dir():
                            self.spec_syncer.sync_component_spec(comp_dir)
                            synced_components.add(comp_name)

        if not synced_components:
            synced_components = set(self.sync_all_components())

        reindex_result: Dict[str, Any] = {"status": "SKIPPED", "reason": "TRIGGER_INDEXER_FALSE"}
        if trigger_indexer:
            if force_reindex or self.index_syncer.is_index_stale():
                reindex_result = self.index_syncer.trigger_scip_reindex(background=True)
        else:
            self.index_syncer.mark_dirty()

        return {
            "status": "OK",
            "synced_components": sorted(list(synced_components)),
            "reindexed": reindex_result.get("status") in ("COMPLETED", "SPAWNED"),
            "indexer_details": reindex_result,
            "timestamp": time.time(),
        }


def run_maintenance(
    paths: Optional[List[str]] = None,
    force_reindex: bool = False,
    trigger_indexer: bool = False,
) -> Dict[str, Any]:
    """Convenience top-level entrypoint for hooks and tools."""
    runner = AutoIndexRunner()
    return runner.run(paths=paths, force_reindex=force_reindex, trigger_indexer=trigger_indexer)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vazus OS Self-Sustaining Index & Spec Synchronizer")
    parser.add_argument("--paths", nargs="*", help="Touched file paths")
    parser.add_argument("--force-reindex", action="store_true", help="Force SCIP reindexing")
    parser.add_argument("--trigger-indexer", action="store_true", default=False, help="Trigger SCIP reindexing")
    args = parser.parse_args()

    trigger = args.trigger_indexer or args.force_reindex
    res = run_maintenance(paths=args.paths, force_reindex=args.force_reindex, trigger_indexer=trigger)
    print(json.dumps(res, indent=2))
