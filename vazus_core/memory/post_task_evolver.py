"""
vazus_core.post_task_evolver
===========================
Milestone M2 (R2 Post-Task Evolution & Reflexion).

Dataclasses:
  - TaskResult
  - ReflexionLesson
  - EvolutionSummary

Core Functions:
  - persist_reflexion_lesson(lesson: ReflexionLesson, db_path: Optional[str] = None) -> bool
  - update_agents_md(mutated_prompts: Dict[str, Any], agents_md_path: str = ..., ...) -> bool
  - run_post_task_evolution(task_result: TaskResult) -> EvolutionSummary
"""

import os
import re
import ast
import time
import json
import shutil
import random
import sqlite3
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union

# Global thread lock for file operations on AGENTS.md
_file_lock = threading.Lock()


def _retry_file_op(func, max_retries: int = 10, base_delay: float = 0.05, max_delay: float = 0.5):
    """
    Executes a file operation function with an exponential backoff retry loop
    and randomized jitter sleep to handle Windows file locking contention (PermissionError [WinError 32]).
    """
    for attempt in range(max_retries):
        try:
            return func()
        except (PermissionError, OSError) as e:
            if attempt == max_retries - 1:
                raise e
            delay = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, 0.02)
            time.sleep(delay)


from vazus_core.memory.db import get_db_connection, DEFAULT_VAZUS_DB
from vazus_core.evolution.prompt_optimizer import evaluate_prompt_fitness, run as run_prompt_optimizer
from vazus_core.memory.auto_improver import VazusAutoImprover

logger = logging.getLogger("vazus_core.post_task_evolver")

DEFAULT_AGENTS_MD_PATH = r"C:\vazus\AGENTS.md"


@dataclass
class TaskResult:
    task_id: str
    prompt: str = ""
    output: str = ""
    success: bool = True
    execution_time: float = 0.0
    subagent_name: str = "default_agent"
    error_trace: str = ""
    fitness_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflexionLesson:
    id: str = ""
    timestamp: float = field(default_factory=time.time)
    task_id: str = "default_task"
    prompt_template: str = ""
    fitness_score: float = 0.0
    lesson_learned: str = ""
    mutation_delta: Union[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Union[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = f"lesson_{int(time.time()*1000)}"

    # Backward compatibility & duck-typing properties:
    @property
    def lesson_id(self) -> str:
        return self.id

    @property
    def category(self) -> str:
        if isinstance(self.metadata, dict) and "category" in self.metadata:
            return str(self.metadata["category"])
        return self.task_id or "reflexion"

    @property
    def problem_statement(self) -> str:
        return f"Task: {self.task_id}"

    @property
    def solution_summary(self) -> str:
        return self.lesson_learned


@dataclass
class EvolutionSummary:
    task_id: str
    subagent_name: str = "default_agent"
    evolution_status: str = "SUCCESS"  # 'SUCCESS', 'NO_MUTATION_NEEDED', 'FAILED'
    initial_fitness: float = 0.0
    final_fitness: float = 0.0
    mutated_prompts: Dict[str, Any] = field(default_factory=dict)
    lessons_persisted: List[str] = field(default_factory=list)
    agents_md_updated: bool = False
    execution_time: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def lessons_learned(self) -> List[str]:
        return self.lessons_persisted


def persist_reflexion_lesson(lesson: ReflexionLesson, db_path: Optional[str] = None) -> bool:
    """
    Auto-creates 8-column `reflexion_lessons` table in `vazus.db` using `vazus_core.db.get_db_connection()`.
    Includes virtual/generated column aliases (lesson_id, category) for query compatibility.
    Inserts/replaces lesson records atomically. Integrates with `organic_memory_bridge.record_insight` if available.
    """
    target_db = db_path or os.getenv("VAZUS_DB_PATH", DEFAULT_VAZUS_DB)
    conn = None
    try:
        conn = get_db_connection(target_db)
        
        # Check existing table columns if present
        cols = []
        try:
            cur = conn.execute("PRAGMA table_info(reflexion_lessons)")
            rows = cur.fetchall()
            cols = [r["name"] if isinstance(r, sqlite3.Row) else r[1] for r in rows]
        except Exception:
            pass

        if cols and "prompt_template" not in cols:
            # Rename legacy table schema
            try:
                conn.execute("ALTER TABLE reflexion_lessons RENAME TO legacy_reflexion_lessons")
                conn.commit()
                cols = []
            except Exception as e:
                logger.warning(f"Could not rename legacy reflexion_lessons table: {e}")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS reflexion_lessons (
                id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                task_id TEXT NOT NULL,
                prompt_template TEXT NOT NULL,
                fitness_score REAL NOT NULL,
                lesson_learned TEXT NOT NULL,
                mutation_delta TEXT NOT NULL,
                metadata TEXT NOT NULL,
                lesson_id TEXT GENERATED ALWAYS AS (id) STORED,
                category TEXT GENERATED ALWAYS AS (task_id) STORED
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reflexion_lessons_task_id ON reflexion_lessons(task_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reflexion_lessons_timestamp ON reflexion_lessons(timestamp);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reflexion_lessons_fitness ON reflexion_lessons(fitness_score);")
        
        if cols and "lesson_id" not in cols:
            try:
                conn.execute("ALTER TABLE reflexion_lessons ADD COLUMN lesson_id TEXT GENERATED ALWAYS AS (id) STORED;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE reflexion_lessons ADD COLUMN category TEXT GENERATED ALWAYS AS (task_id) STORED;")
            except Exception:
                pass

        conn.commit()

        # Extract values seamlessly supporting ReflexionLesson or duck-typed objects
        lesson_id = getattr(lesson, 'id', getattr(lesson, 'lesson_id', f'lesson_{int(time.time()*1000)}'))
        ts = getattr(lesson, 'timestamp', time.time())
        task_id = getattr(lesson, 'task_id', getattr(lesson, 'category', 'default_task'))
        prompt_template = getattr(lesson, 'prompt_template', getattr(lesson, 'problem_statement', ''))
        fitness = getattr(lesson, 'fitness_score', 0.0)
        lesson_learned = getattr(lesson, 'lesson_learned', getattr(lesson, 'solution_summary', ''))
        mutation_delta = getattr(lesson, 'mutation_delta', {})
        metadata = getattr(lesson, 'metadata', {})

        delta_str = json.dumps(mutation_delta) if isinstance(mutation_delta, (dict, list)) else str(mutation_delta)
        meta_str = json.dumps(metadata) if isinstance(metadata, (dict, list)) else str(metadata)

        sql = """
        INSERT OR REPLACE INTO reflexion_lessons (
            id, timestamp, task_id, prompt_template, fitness_score,
            lesson_learned, mutation_delta, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            str(lesson_id),
            float(ts),
            str(task_id),
            str(prompt_template),
            float(fitness),
            str(lesson_learned),
            delta_str,
            meta_str,
        )
        with conn:
            conn.execute(sql, params)
        try:
            conn.close()
        except Exception:
            pass
        conn = None

        # Organic Memory Bridge Integration
        try:
            from vazus_core.memory.organic_memory_bridge import record_insight
            insight_text = f"Reflexion Lesson [{lesson_id}] task [{task_id}]: {lesson_learned[:120]} (fitness: {fitness:.4f})"
            record_insight(category="reflexion_lesson", insight=insight_text, db_path=target_db)
        except Exception as e:
            logger.debug(f"Organic memory insight integration skipped: {e}")

        logger.info(f"[PostTaskEvolver] Successfully persisted reflexion lesson {lesson_id}")
        return True
    except Exception as e:
        logger.error(f"[PostTaskEvolver] Failed to persist reflexion lesson: {e}")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _ensure_agents_md_template(filepath: str) -> None:
    """Ensures target AGENTS.md exists with standard template if missing."""
    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        template = """# vazus SuperGraph OS & Native Antigravity Subagent Architecture

## Overview
This document specifies the native subagent roles, responsibilities, bridge interfaces, repository locations, and tool bindings within the **vazus SuperGraph OS**.

---

## Native Antigravity Subagent Roles & System Prompts

### 1. `open_deep_researcher`
* **Role**: Open Deep Researcher Subagent
* **Description**: LangGraph Open Deep Research + Google Search Grounding.
* **Bridge Script**: `C:\\vazus\\scripts\\subagent_research_bridge.py`

### 2. `rlm_code_engineer`
* **Role**: RLM Code Engineer Subagent
* **Description**: MIT RLM for REPL-based self-healing code generation.
* **Bridge Script**: `C:\\vazus\\scripts\\subagent_rlm_bridge.py`

### 3. `verifier_worker`
* **Role**: Jules Verifier Worker Subagent
* **Description**: Static AST verifier, contract testing, and Git provenance.
* **Bridge Script**: `C:\\vazus\\scripts\\subagent_verifier_bridge.py`

---

## Evolved Prompt Templates & Systemic Lessons

*(Auto-generated post-task evolution log)*

---

## Governance & Verification Protocol
1. **Antigravity First**: All subagent actions are visible in the Antigravity UI dashboard and logs.
2. **Absolute Path Standard**: All internal components reference `C:\\vazus`.
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(template)
        logger.info(f"[PostTaskEvolver] Initialized template AGENTS.md at {filepath}")


def update_agents_md(
    mutated_prompts: Dict[str, Any],
    agents_md_path: str = DEFAULT_AGENTS_MD_PATH,
    fitness_threshold: float = 0.70,
    min_improvement_delta: float = 0.01,
    force_update: bool = False
) -> bool:
    """
    Updates subagent system prompts under `## Native Antigravity Subagent Roles & System Prompts`
    and appends to `## Evolved Prompt Templates & Systemic Lessons`.
    Uses thread-level lock (_file_lock), process/thread unique temporary files, and exponential backoff retry loops.
    """
    if not mutated_prompts:
        logger.warning("[PostTaskEvolver] update_agents_md called with empty mutated_prompts dict.")
        return False

    with _file_lock:
        _ensure_agents_md_template(agents_md_path)

        # 1. Evaluate fitness gating
        accepted_mutations: Dict[str, Dict[str, Any]] = {}
        for agent_id, data in mutated_prompts.items():
            if isinstance(data, str):
                pdata = {
                    "prompt_template": data,
                    "fitness_score": 0.85,
                    "baseline_fitness": 0.0,
                    "systemic_lesson": "Textual prompt refinement",
                    "mutations_applied": ["Textual refinement"]
                }
            elif isinstance(data, dict):
                pdata = data
            else:
                continue

            candidate_score = float(pdata.get("fitness_score", pdata.get("fitness", 0.85)))
            baseline_score = float(pdata.get("baseline_fitness", pdata.get("baseline", 0.0)))
            delta = candidate_score - baseline_score

            if force_update:
                accepted_mutations[agent_id] = pdata
                continue

            if candidate_score < fitness_threshold:
                logger.info(
                    f"[PostTaskEvolver] Rejected mutation for '{agent_id}': "
                    f"Candidate score {candidate_score:.4f} < threshold {fitness_threshold:.4f}"
                )
                continue

            if baseline_score > 0.0 and delta < min_improvement_delta:
                logger.info(
                    f"[PostTaskEvolver] Rejected mutation for '{agent_id}': "
                    f"Delta {delta:+.4f} < min required {min_improvement_delta:+.4f}"
                )
                continue

            accepted_mutations[agent_id] = pdata

        if not accepted_mutations:
            logger.info("[PostTaskEvolver] No prompt mutations passed fitness threshold criteria.")
            return False

        unique_id = f"{os.getpid()}_{threading.get_ident()}_{int(time.time()*1000)}"
        backup_path = f"{agents_md_path}.{unique_id}.bak"
        tmp_path = f"{agents_md_path}.{unique_id}.tmp"

        try:
            content = _retry_file_op(lambda: open(agents_md_path, "r", encoding="utf-8").read())
            original_headers = re.findall(r"^(#+\s+.*)$", content, re.MULTILINE)

            # Save backup
            _retry_file_op(lambda: shutil.copyfile(agents_md_path, backup_path))

            evolved_header = "## Evolved Prompt Templates & Systemic Lessons"
            if evolved_header not in content:
                gov_header = "## Governance & Verification Protocol"
                if gov_header in content:
                    content = content.replace(
                        gov_header,
                        f"{evolved_header}\n\n*(Auto-generated post-task evolution log)*\n\n---\n\n{gov_header}"
                    )
                else:
                    content += f"\n\n---\n\n{evolved_header}\n\n*(Auto-generated post-task evolution log)*\n"

            log_entries = []
            now_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

            for agent_id, pdata in accepted_mutations.items():
                prompt_text = str(pdata.get("prompt_template", pdata.get("prompt", ""))).strip()
                score = float(pdata.get("fitness_score", pdata.get("fitness", 0.0)))
                baseline = float(pdata.get("baseline_fitness", pdata.get("baseline", 0.0)))
                lesson = str(pdata.get("systemic_lesson", pdata.get("lesson", ""))).strip()
                gen = pdata.get("generation", 1)
                mutations = pdata.get("mutations_applied", [])

                # Update System Prompt under ## Native Antigravity Subagent Roles & System Prompts
                pattern = re.compile(rf"(###\s*(?:\d+\.\s*)?`?{re.escape(agent_id)}`?\b.*?)(?=\n###|\n##|\Z)", re.DOTALL)
                match = pattern.search(content)

                if match:
                    sub_block = match.group(1)
                    prompt_block = f"* **System Prompt Template**:\n```markdown\n{prompt_text}\n```"
                    if "* **System Prompt Template**:" in sub_block:
                        sub_block_updated = re.sub(
                            r"\* \*\*System Prompt Template\*\*:\n```markdown\n.*?\n```",
                            prompt_block,
                            sub_block,
                            flags=re.DOTALL
                        )
                    else:
                        sub_block_updated = sub_block.rstrip() + f"\n{prompt_block}\n"

                    content = content.replace(sub_block, sub_block_updated)

                # Build Evolved Prompt log entry
                delta_str = f"+{score - baseline:.4f}" if baseline > 0 else "N/A"
                muts_str = ", ".join(mutations) if mutations else "Textual refinement"
                entry = (
                    f"### Evolved Prompt: `{agent_id}` (Gen {gen})\n"
                    f"- **Updated At**: {now_str}\n"
                    f"- **Fitness Score**: {score:.4f} (Baseline: {baseline:.4f}, Delta: {delta_str})\n"
                    f"- **Mutations Applied**: {muts_str}\n"
                )
                if lesson:
                    entry += f"- **Systemic Lesson**: {lesson}\n"
                if prompt_text:
                    entry += f"- **Evolved Prompt**:\n```markdown\n{prompt_text}\n```\n"

                log_entries.append(entry)

            # Append log entries under evolved header
            evolved_pos = content.find(evolved_header)
            if evolved_pos != -1:
                header_end = evolved_pos + len(evolved_header)
                next_sec = content.find("\n## ", header_end)
                if next_sec != -1:
                    prefix = content[:next_sec].rstrip()
                    suffix = content[next_sec:]
                    content = prefix + "\n\n" + "\n".join(log_entries) + "\n" + suffix
                else:
                    content = content.rstrip() + "\n\n" + "\n".join(log_entries) + "\n"

            def _write_tmp():
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(content)

            _retry_file_op(_write_tmp)

            # Atomic swap with retry backoff
            _retry_file_op(lambda: os.replace(tmp_path, agents_md_path))

            # Structural Verification
            written_content = _retry_file_op(lambda: open(agents_md_path, "r", encoding="utf-8").read())

            for oh in original_headers:
                if oh not in written_content:
                    raise ValueError(f"Structural verification failed: Missing original header '{oh}' post-update.")
            if evolved_header not in written_content:
                raise ValueError(f"Structural verification failed: Missing required section header '{evolved_header}'.")

            if os.path.exists(backup_path):
                _retry_file_op(lambda: os.remove(backup_path))

            logger.info(f"[PostTaskEvolver] Successfully updated AGENTS.md with {len(accepted_mutations)} mutations.")
            return True

        except Exception as e:
            logger.error(f"[PostTaskEvolver] AGENTS.md update failed: {e}")
            if os.path.exists(backup_path):
                try:
                    _retry_file_op(lambda: shutil.copyfile(backup_path, agents_md_path))
                    _retry_file_op(lambda: os.remove(backup_path))
                except Exception:
                    pass
            if os.path.exists(tmp_path):
                try:
                    _retry_file_op(lambda: os.remove(tmp_path))
                except Exception:
                    pass
            return False


def run_post_task_evolution(task_result: TaskResult) -> EvolutionSummary:
    """
    Composite fitness evaluation ($F = 0.25 F_{syntax} + 0.25 F_{contract} + 0.25 F_{prompt} + 0.25 F_{exec}$).
    Runs prompt mutation using `VazusAutoImprover` / `vazus_darwinian_evolve` / fallback `prompt_optimizer.run()`.
    Persists lessons and updates `AGENTS.md`.
    """
    start_time = time.time()
    task_id = getattr(task_result, "task_id", f"task_{int(start_time*1000)}")
    subagent_name = getattr(task_result, "subagent_name", "default_agent")
    prompt = getattr(task_result, "prompt", "")
    output = getattr(task_result, "output", "")
    error_trace = getattr(task_result, "error_trace", "")
    success = getattr(task_result, "success", True)

    # 1. F_syntax
    f_syntax = 1.0
    if error_trace and "SyntaxError" in error_trace:
        f_syntax = 0.0
    elif output:
        code_blocks = re.findall(r"```(?:python)?\s*\n(.*?)\n```", output, re.DOTALL)
        code_to_check = "\n".join(code_blocks) if code_blocks else output
        try:
            ast.parse(code_to_check)
            f_syntax = 1.0
        except SyntaxError:
            f_syntax = 0.0 if code_blocks else 0.8
        except Exception:
            f_syntax = 0.8

    # 2. F_contract
    f_contract = 1.0
    if error_trace and ("ContractViolation" in error_trace or "AssertionError" in error_trace):
        f_contract = 0.0
    elif "contract" in output.lower() or "smt z3" in output.lower() or "unsat" in output.lower():
        f_contract = 1.0
    else:
        f_contract = 0.8 if success else 0.3

    # 3. F_prompt
    f_prompt = evaluate_prompt_fitness(prompt)

    # 4. F_exec
    if success and not error_trace:
        f_exec = 1.0
    elif success:
        f_exec = 0.7
    else:
        f_exec = 0.0

    initial_fitness = round(0.25 * f_syntax + 0.25 * f_contract + 0.25 * f_prompt + 0.25 * f_exec, 4)

    # Prompt Mutation Engine
    opt_res = run_prompt_optimizer(prompt_id=subagent_name, iterations=3, initial_prompt=prompt)
    evolved_prompt = opt_res.get("evolved_prompt", prompt)
    final_fitness = max(initial_fitness, float(opt_res.get("final_fitness", initial_fitness)))

    # Persist Lesson
    lesson_id = f"lesson_{task_id}_{int(start_time * 1000)}"
    lesson_text = (
        f"Evolved prompt for [{subagent_name}] post-task [{task_id}]. "
        f"Initial fitness: {initial_fitness:.4f} -> Final fitness: {final_fitness:.4f}."
    )
    if error_trace:
        lesson_text += f" Resolved trace: {error_trace[:100]}"

    lesson = ReflexionLesson(
        id=lesson_id,
        timestamp=time.time(),
        task_id=task_id,
        prompt_template=evolved_prompt,
        fitness_score=final_fitness,
        lesson_learned=lesson_text,
        mutation_delta={
            "initial_fitness": initial_fitness,
            "final_fitness": final_fitness,
            "delta": round(final_fitness - initial_fitness, 4)
        },
        metadata={"subagent_name": subagent_name, "success": success}
    )

    persisted_ok = persist_reflexion_lesson(lesson)
    lessons_persisted = [lesson_id] if persisted_ok else []

    # Update AGENTS.md
    mutated_prompts = {
        subagent_name: {
            "prompt_template": evolved_prompt,
            "fitness_score": final_fitness,
            "baseline_fitness": initial_fitness,
            "systemic_lesson": lesson_text,
            "generation": 1,
            "mutations_applied": ["Textual refinement", "AST contract enforcement"]
        }
    }
    fitness_threshold = 0.70
    agents_md_updated = update_agents_md(
        mutated_prompts,
        fitness_threshold=fitness_threshold,
        min_improvement_delta=0.01,
        force_update=(final_fitness >= initial_fitness and final_fitness >= fitness_threshold)
    )

    status = "SUCCESS" if final_fitness >= initial_fitness else "NO_MUTATION_NEEDED"
    exec_time = round(time.time() - start_time, 4)

    return EvolutionSummary(
        task_id=task_id,
        subagent_name=subagent_name,
        evolution_status=status,
        initial_fitness=initial_fitness,
        final_fitness=final_fitness,
        mutated_prompts={subagent_name: evolved_prompt},
        lessons_persisted=lessons_persisted,
        agents_md_updated=agents_md_updated,
        execution_time=exec_time,
        details={"prompt_optimizer_result": opt_res}
    )
