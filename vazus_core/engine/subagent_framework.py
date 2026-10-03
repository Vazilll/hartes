"""
vazus_core.subagent_framework - Declarative Subagent Lifecycle & Hook System
Eliminates script duplication across subagents by providing a unified hook-driven execution engine.
"""

import time
import logging
import inspect
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, List, Callable, Optional

from vazus_core.engine.utils import fast_json_dumps
from vazus_core.memory.db import get_db_connection

logger = logging.getLogger("SubagentFramework")

# Auto-import AGY Customizations HUD (registers compact on_start hook)
try:
    import vazus_core.integrations.agy_customizations_hud  # noqa: F401 — side-effect: registers hook
except Exception as _hud_err:
    logger.debug(f"[SubagentFramework] AGY HUD hook not registered: {_hud_err}")


@dataclass
class SubagentContext:
    """Execution context passed through subagent lifecycle hooks."""
    subagent_name: str
    task_id: str
    prompt: str
    params: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class SubagentHookRegistry:
    """Registry for global pre-execution, post-step, verification, and completion middleware hooks."""
    
    def __init__(self):
        self._on_start_hooks: List[Callable[[SubagentContext], Any]] = []
        self._on_step_hooks: List[Callable[[SubagentContext, str], Any]] = []
        self._on_verify_hooks: List[Callable[[SubagentContext], Any]] = []
        self._on_complete_hooks: List[Callable[[SubagentContext], Any]] = []
        self._on_fail_hooks: List[Callable[[SubagentContext], Any]] = []

    def register_on_start(self, hook: Callable[[SubagentContext], Any]):
        self._on_start_hooks.append(hook)

    def register_on_step(self, hook: Callable[[SubagentContext, str], Any]):
        self._on_step_hooks.append(hook)

    def register_on_verify(self, hook: Callable[[SubagentContext], Any]):
        self._on_verify_hooks.append(hook)

    def register_on_complete(self, hook: Callable[[SubagentContext], Any]):
        self._on_complete_hooks.append(hook)

    def register_on_fail(self, hook: Callable[[SubagentContext], Any]):
        self._on_fail_hooks.append(hook)

    async def trigger_on_start(self, ctx: SubagentContext):
        for hook in self._on_start_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    await hook(ctx)
                else:
                    res = hook(ctx)
                    if inspect.isawaitable(res):
                        await res
            except Exception as e:
                ctx.logs.append(f"[Hook Warning] on_start failed: {e}")

    async def trigger_on_step(self, ctx: SubagentContext, step_name: str):
        for hook in self._on_step_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    await hook(ctx, step_name)
                else:
                    res = hook(ctx, step_name)
                    if inspect.isawaitable(res):
                        await res
            except Exception as e:
                ctx.logs.append(f"[Hook Warning] on_step failed: {e}")

    async def trigger_on_verify(self, ctx: SubagentContext) -> bool:
        overall_verified = True
        for hook in self._on_verify_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    res = await hook(ctx)
                else:
                    res = hook(ctx)
                    if inspect.isawaitable(res):
                        res = await res
                if not res:
                    overall_verified = False
            except Exception as e:
                ctx.logs.append(f"[Hook Error] on_verify exception: {e}")
                overall_verified = False
        return overall_verified

    async def trigger_on_complete(self, ctx: SubagentContext):
        for hook in self._on_complete_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    await hook(ctx)
                else:
                    res = hook(ctx)
                    if inspect.isawaitable(res):
                        await res
            except Exception as e:
                ctx.logs.append(f"[Hook Warning] on_complete failed: {e}")

    async def trigger_on_fail(self, ctx: SubagentContext):
        for hook in self._on_fail_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    await hook(ctx)
                else:
                    res = hook(ctx)
                    if inspect.isawaitable(res):
                        await res
            except Exception as e:
                ctx.logs.append(f"[Hook Warning] on_fail failed: {e}")


# Global default hook registry
global_hook_registry = SubagentHookRegistry()


# Default DB logging hook for on_complete
async def default_db_logging_hook(ctx: SubagentContext):
    """Logs subagent task completion telemetry into vazus.db subagent_memory_traces table asynchronously."""
    def _sync_db_log():
        conn = get_db_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subagent_memory_traces (
                trace_id TEXT PRIMARY KEY,
                subagent_name TEXT,
                task_id TEXT,
                prompt TEXT,
                status TEXT,
                results_json TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO subagent_memory_traces (trace_id, subagent_name, task_id, prompt, status, results_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"trace_{int(time.time()*1000)}",
                ctx.subagent_name,
                ctx.task_id,
                ctx.prompt[:500],
                "SUCCESS" if ctx.success else "FAILURE",
                fast_json_dumps(ctx.results)
            )
        )
        conn.commit()
        conn.close()

    try:
        await asyncio.to_thread(_sync_db_log)
    except Exception as e:
        ctx.logs.append(f"[DB Hook Warning] Failed to log trace to DB: {e}")


global_hook_registry.register_on_complete(default_db_logging_hook)


async def _report_top_skills_on_success(ctx: SubagentContext) -> None:
    """Queries top skill statistics on task success."""
    try:
        from vazus_core.memory.auto_improver import get_auto_improver
        improver = get_auto_improver()
        top_res = improver.skill_tracker.get_top_skills(3)
        top = await top_res if inspect.isawaitable(top_res) else top_res
        if top:
            skills_str = ", ".join(f"{s['name']}={s['score']:.2f}" for s in top)
            ctx.logs.append(f"[AutoImprover] Top skills: {skills_str}")
    except Exception as exc:
        logger.debug("[AutoImprover] Top skills query failed: %s", exc)


def _build_reflexion_prompt(code: str, critique: str, lessons: list, task_desc_str: str) -> str:
    """Constructs prompt for Reflexion code repair."""
    lessons_formatted = "\n".join(f"- {lesson}" for lesson in lessons) if lessons else "- None recorded"
    return (
        "SYSTEM: You are the Vazus OS Reflexion Code Repair Engineer (powered by Gemini 3.6 Flash).\n"
        "Your objective is to fix broken Python code based on evaluation critique and past failure lessons.\n\n"
        "CONSTRAINTS:\n"
        "1. Do NOT import google.genai directly or instantiate genai.Client() with external GEMINI_API_KEY.\n"
        "2. Ensure valid Python AST syntax and satisfy all contract preconditions/postconditions.\n"
        "3. Output ONLY valid Python code inside a ```python ``` codeblock or raw Python code without narrative commentary.\n\n"
        f"CONTEXT:\n"
        f"Task Description: {task_desc_str[:500]}\n\n"
        f"Failing Code:\n```python\n{code}\n```\n\n"
        f"Evaluation Critique & Error Traceback:\n{critique}\n\n"
        f"Past Failure Lessons (Episodic Memory):\n{lessons_formatted}\n\n"
        "INSTRUCTION:\n"
        "Analyze the error root cause and past failure lessons, and generate the corrected, complete Python code snippet."
    )


def _extract_and_sanitize_repaired_code(response_text: str, original_code: str) -> str:
    """Parses, sanitizes, and verifies syntax of repaired code."""
    import re
    import ast as _ast

    match = re.search(r"```python\s*(.*?)\s*```", response_text, re.DOTALL)
    if match:
        repaired_code = match.group(1).strip()
    else:
        match_gen = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
        repaired_code = match_gen.group(1).strip() if match_gen else response_text.strip()

    sanitized = "\n".join(
        l for l in repaired_code.splitlines()
        if "import google.genai" not in l and "from google import genai" not in l
    )

    try:
        _ast.parse(sanitized)
        return sanitized
    except SyntaxError as exc:
        logger.debug("[AutoImprover] Repaired code AST invalid, reverting to original: %s", exc)
        return original_code


async def _llm_fix_fn(code: str, critique: str, lessons: list, task_description: str = "") -> str:
    """LLM-powered Reflexion code repair function querying Gemini 3.6 Flash."""
    if not code or len(code.strip()) == 0:
        return code

    prompt = _build_reflexion_prompt(code, critique, lessons, task_description)
    sys_prompt = "You are the Vazus OS Reflexion Code Repair Engineer (powered by Gemini 3.6 Flash)."

    try:
        from vazus_core.engine.llm_client import async_generate_llm
        response_text = await async_generate_llm(
            prompt=prompt,
            system_prompt=sys_prompt,
            model="gemini-3.6-flash",
        )
    except Exception as _llm_err:
        logger.warning("[AutoImprover] LLM generation error in _llm_fix_fn: %s", _llm_err)
        response_text = ""

    if not response_text:
        import ast as _ast
        try:
            _ast.parse(code)
            response_text = code
        except SyntaxError:
            lines = [l for l in code.splitlines() if l.strip()]
            response_text = "\n".join(lines[:-1]) if len(lines) > 1 else code

    return _extract_and_sanitize_repaired_code(response_text, code)


async def _execute_auto_improver_reflexion(ctx: SubagentContext, code_output: str, error_trace: str) -> None:
    """Executes VazusAutoImprover reflexion loop on failed subagent task."""
    try:
        from vazus_core.memory.auto_improver import get_auto_improver
        improver = get_auto_improver(max_iterations=2)
        improve_res = improver.improve(
            task_id=ctx.task_id,
            task_description=ctx.prompt[:200],
            initial_code=code_output,
            fix_fn=_llm_fix_fn,
            error_trace=error_trace,
            task_type=ctx.subagent_name,
        )
        session = await improve_res if inspect.isawaitable(improve_res) else improve_res
        if session.success and session.final_code != code_output:
            ctx.results["code"] = session.final_code
            ctx.results["auto_improved"] = True
            ctx.logs.append(f"[AutoImprover] Self-corrected in {session.iterations} iterations. Score: {session.final_score:.3f}")
    except Exception as exc:
        logger.warning("[AutoImprover Hook Error] %s", exc)
        ctx.logs.append(f"[AutoImprover Hook Warning] {exc}")


async def auto_improver_on_complete_hook(ctx: SubagentContext):
    """
    Automatically triggers the VazusAutoImprover reflexion loop when a subagent task fails.
    On success, just shows live stats. Visible in terminal in real-time.
    """
    if ctx.success and not ctx.error:
        await _report_top_skills_on_success(ctx)
        return

    # Record failure lesson and Mem0 fact for subagent failure
    try:
        from vazus_core.memory.auto_improver import LessonMemoryBank
        from vazus_core.memory.mem0_memory_engine import Mem0Engine

        err_msg = ctx.error or "Subagent task execution failed"
        prompt_snippet = (ctx.prompt or "")[:120]
        subagent_name = ctx.subagent_name or "subagent"

        Mem0Engine().add_fact(
            fact_text=f"[subagent_failure] {subagent_name}: {err_msg} (prompt: {prompt_snippet})",
            category="task_failure",
            entity=subagent_name
        )
        LessonMemoryBank().save_lesson(
            task_type=subagent_name,
            error_sig=f"{subagent_name}: {str(err_msg)[:60]}",
            lesson_text=f"Subagent {subagent_name} failed: {err_msg}. Task: {prompt_snippet}",
            fix_hint=f"Review parameters, tool calls, and invariants for {subagent_name}."
        )
    except Exception as mem_err:
        logger.debug("Subagent failure memory routing non-fatal: %s", mem_err)

    code_output = ctx.results.get("code", "") or ctx.results.get("output", "")
    error_trace = ctx.error or ""
    if not code_output or len(code_output) < 10:
        return

    await _execute_auto_improver_reflexion(ctx, code_output, error_trace)


global_hook_registry.register_on_complete(auto_improver_on_complete_hook)


SYSTEM_HARNESS_POLICY = """
[ANTIGRAVITY HARNESS EXECUTION POLICY]
1. Never import google.genai directly or instantiate genai.Client() with external GEMINI_API_KEY.
2. All vision/OCR tasks must use local Pix2Text/RapidOCR or agy CLI OAuth sessions.
3. All code generation must be valid Python AST and pass SMT Z3 contract checks.
"""


async def harness_security_on_start_hook(ctx: SubagentContext):
    """Injects Antigravity Harness system policy and automatically matches/loads relevant Hermes skills into context."""
    if SYSTEM_HARNESS_POLICY not in ctx.prompt:
        ctx.prompt = f"{SYSTEM_HARNESS_POLICY}\n\n{ctx.prompt}"

    from vazus_core.hermes_skill_syncer import AutomaticSkillSelector
    from vazus_core.integrations.tui_preview_renderer import render_terminal_harness_hud

    def _sync_skill_load():
        selector = AutomaticSkillSelector()
        matching_skills = selector.select_matching_skills(ctx.prompt)
        loaded_skill_names = []
        for skill in matching_skills:
            skill_name = skill["name"]
            skill_content = selector.load_skill_content(skill_name)
            if skill_content and skill_name not in ctx.prompt:
                ctx.prompt = f"--- [AUTO-LOADED SKILL: {skill_name}] ---\n{skill_content}\n--- [END SKILL] ---\n\n{ctx.prompt}"
                loaded_skill_names.append(skill_name)
        hud_box = render_terminal_harness_hud(active_skills=loaded_skill_names)
        return loaded_skill_names, hud_box

    loaded_skill_names, hud_box = await asyncio.to_thread(_sync_skill_load)
    ctx.logs.append("[Harness Hook] Injected SYSTEM_HARNESS_POLICY into context.")
    if loaded_skill_names:
        ctx.logs.append(f"[Skill Auto-Load] Dynamically sub-loaded skills: {loaded_skill_names}")
    ctx.logs.append(hud_box)


def security_api_quota_on_verify_hook(ctx: SubagentContext) -> bool:
    """Verifies that generated code or results contain no unauthorized external billing API imports."""
    output_text = ctx.results.get("output", "") or ""
    code_to_check = ctx.results.get("code", "") or output_text
    
    if "import google.genai" in code_to_check or "from google import genai" in code_to_check:
        ctx.logs.append("[Security Hook Error] Prohibited direct google.genai import detected!")
        return False
    if "genai.Client()" in code_to_check and "GEMINI_API_KEY" in code_to_check:
        ctx.logs.append("[Security Hook Error] Unauthorized external GEMINI_API_KEY client instantiation detected!")
        return False
    return True


global_hook_registry.register_on_start(harness_security_on_start_hook)
global_hook_registry.register_on_verify(security_api_quota_on_verify_hook)


@dataclass
class DeclarativeSubagentTemplate:
    """Declarative specification for a subagent role."""
    name: str
    description: str
    system_prompt: str
    allowed_tools: List[str] = field(default_factory=list)
    hermes_protocol: bool = True
    executor_fn: Optional[Callable[[SubagentContext], Any]] = None
    verifier_fn: Optional[Callable[[SubagentContext], Any]] = None


class SubagentTemplateRegistry:
    """Central registry of declarative subagent definitions."""
    
    def __init__(self):
        self._templates: Dict[str, DeclarativeSubagentTemplate] = {}
        self._register_defaults()

    def _register_defaults(self):
        defaults = [
            DeclarativeSubagentTemplate(name="code_engineer", description="RLM REPL Code Engineer", system_prompt="Engineer code using Python REPL and AST validation."),
            DeclarativeSubagentTemplate(name="open_deep_researcher", description="LangGraph Open Deep Researcher", system_prompt="Deep research with Google Search Grounding."),
            DeclarativeSubagentTemplate(name="verifier_worker", description="Jules SMT Z3 Verifier Worker", system_prompt="SMT Z3 contract verifier and Git provenance gatekeeper."),
            DeclarativeSubagentTemplate(name="research", description="General Research Agent", system_prompt="Codebase inspection and documentation research.")
        ]
        for t in defaults:
            self.register(t)

    def register(self, template: DeclarativeSubagentTemplate):
        self._templates[template.name] = template

    def get(self, name: str) -> Optional[DeclarativeSubagentTemplate]:
        return self._templates.get(name)

    def list_subagents(self) -> List[str]:
        return list(self._templates.keys())


subagent_registry = SubagentTemplateRegistry()


class DeclarativeSubagentEngine:
    """Unified engine to execute any registered declarative subagent using lifecycle hooks."""

    def __init__(
        self,
        registry: Optional[SubagentTemplateRegistry] = None,
        hooks: Optional[SubagentHookRegistry] = None
    ):
        self.registry = registry or subagent_registry
        self.hooks = hooks or global_hook_registry

    async def _execute_template_body(
        self,
        template: DeclarativeSubagentTemplate,
        ctx: SubagentContext,
        prompt: str,
    ) -> None:
        """Executes subagent body including Hermes initialization and custom executor."""
        if template.hermes_protocol:
            from vazus_core.hermes_agent_engine import HermesAgentEngine, HermesToolRegistry
            hermes_registry = HermesToolRegistry()
            hermes_engine = HermesAgentEngine(registry=hermes_registry)
            ctx.state["hermes_system_prompt"] = hermes_engine.build_system_prompt(template.system_prompt)
            ctx.logs.append("[Hermes Protocol Enabled] System prompt built with <tools> XML tags.")

        if template.executor_fn:
            if inspect.iscoroutinefunction(template.executor_fn):
                exec_results = await template.executor_fn(ctx)
            else:
                exec_results = template.executor_fn(ctx)
                if inspect.isawaitable(exec_results):
                    exec_results = await exec_results
            if exec_results:
                ctx.results.update(exec_results)
        else:
            ctx.results["output"] = f"Executed generic prompt: {prompt[:100]}..."

    async def _verify_template_execution(
        self,
        template: DeclarativeSubagentTemplate,
        ctx: SubagentContext,
    ) -> None:
        """Runs template-specific and global verification hooks."""
        is_verified = True
        if template.verifier_fn:
            if inspect.iscoroutinefunction(template.verifier_fn):
                is_verified = await template.verifier_fn(ctx)
            else:
                is_verified = template.verifier_fn(ctx)
                if inspect.isawaitable(is_verified):
                    is_verified = await is_verified

        global_verified = await self.hooks.trigger_on_verify(ctx)
        if not is_verified or not global_verified:
            ctx.success = False
            ctx.error = "Subagent output verification failed."

    async def run_subagent(
        self,
        subagent_name: str,
        prompt: str,
        task_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> SubagentContext:
        """Executes a subagent by name using standardized lifecycle hooks asynchronously with a 300s timeout guard."""
        t_start = time.time()
        ctx = SubagentContext(
            subagent_name=subagent_name,
            task_id=task_id or f"task_{int(t_start*1000)}",
            prompt=prompt,
            params=params or {},
        )

        template = self.registry.get(subagent_name)
        if not template:
            ctx.success = False
            ctx.error = f"Subagent template '{subagent_name}' not registered."
            return ctx

        try:
            async with asyncio.timeout(300):
                await self.hooks.trigger_on_start(ctx)
                await self.hooks.trigger_on_step(ctx, "execution")
                await self._execute_template_body(template, ctx, prompt)
                await self.hooks.trigger_on_step(ctx, "verification")
                await self._verify_template_execution(template, ctx)
        except TimeoutError:
            ctx.success = False
            ctx.error = "Subagent execution timed out after 300 seconds."
            ctx.logs.append("[Timeout Error] Execution exceeded 300 seconds.")
        except Exception as exc:
            ctx.success = False
            ctx.error = str(exc)
            ctx.logs.append(f"[Execution Error] {exc}")

        ctx.results["elapsed_seconds"] = round(time.time() - t_start, 4)
        if not ctx.success:
            await self.hooks.trigger_on_fail(ctx)
        await self.hooks.trigger_on_complete(ctx)
        return ctx

    def run_subagent_sync(
        self,
        subagent_name: str,
        prompt: str,
        task_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> SubagentContext:
        """Synchronous wrapper for run_subagent to support legacy sync callers."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    asyncio.run,
                    self.run_subagent(subagent_name, prompt, task_id=task_id, params=params)
                )
                return future.result()
        else:
            return asyncio.run(
                self.run_subagent(subagent_name, prompt, task_id=task_id, params=params)
            )

