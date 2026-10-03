"""
Recursive Language Model (RLM) Driver Engine for Vazus OS (MIT CSAIL Paradigm, arXiv:2512.24601).
Implements Context-as-State in REPL sandbox with isolated sub-agent worker delegation.
"""

import ast
import io
import logging
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union

from vazus_core.workers.repl_engine import (
    REPLSandboxASTValidator,
    _get_safe_builtins,
)

logger = logging.getLogger("vazus_core.engine.rlm_driver")


@dataclass
class RLMStepResult:
    iteration: int
    code: str
    stdout: str
    stderr: str
    execution_time: float
    is_ready: bool
    final_answer: Optional[str] = None


class RLMDriver:
    """
    Orchestrates recursive language modeling execution with sandboxed REPL,
    ephemeral worker calls, and programmatic context inspection.
    """

    REPL_SYSTEM_PROMPT = """You are a Recursive Language Model (RLM) agent with access to a Python REPL.
The full problem context is stored in the REPL environment as the variable `context`.
Do NOT attempt to guess contents without inspecting them.

You can interact with the environment by generating Python code inside ```repl ... ``` blocks.
Special variables and functions available:
- `context`: The full input data (string, list, or dict).
- `llm_query(prompt: str) -> str`: Calls an isolated sub-LLM to answer a specific question over a text slice.
- `answer['content'] = "..."`: Set your final answer here.
- `answer['ready'] = True`: Mark the task as complete.

Rules:
1. Use programmatic search (regex, slicing, chunking, keyword filtering) to locate key information.
2. Keep sub-prompts to `llm_query` concise and focused.
3. Once you have gathered sufficient evidence, set `answer['content']` and `answer['ready'] = True`.
"""

    def __init__(
        self,
        llm_engine_call: Optional[Callable[[List[Dict[str, str]]], str]] = None,
        max_iterations: int = 10,
        max_depth: int = 2,
    ):
        self.llm_call = llm_engine_call or (
            lambda _msgs: "```repl\nanswer['content'] = 'Processed'; answer['ready'] = True\n```"
        )
        self.max_iterations = max_iterations
        self.max_depth = max_depth

    def _init_sandbox_env(self, long_context: Union[str, Dict, List]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Initializes sandbox globals and locals."""
        sandbox_locals: Dict[str, Any] = {
            "context": long_context,
            "answer": {"content": "", "ready": False},
        }

        def _sub_llm_query(sub_prompt: str) -> str:
            messages = [
                {"role": "system", "content": "You are a precise worker model analyzing a focused context snippet."},
                {"role": "user", "content": sub_prompt},
            ]
            return self.llm_call(messages)

        safe_builtins = _get_safe_builtins()
        sandbox_globals: Dict[str, Any] = {
            "__builtins__": safe_builtins,
            "llm_query": _sub_llm_query,
            "re": re,
            "len": len,
            "print": print,
            "min": min,
            "max": max,
            "range": range,
            "isinstance": isinstance,
            "str": str,
            "int": int,
            "list": list,
            "dict": dict,
        }
        return sandbox_globals, sandbox_locals

    def run(self, prompt: str, long_context: Union[str, Dict, List]) -> Dict[str, Any]:
        """Executes the RLM rollout loop."""
        sandbox_globals, sandbox_locals = self._init_sandbox_env(long_context)
        history: List[Dict[str, str]] = [
            {"role": "system", "content": self.REPL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Task: {prompt}\n(The full data is loaded in `context` of length {len(long_context)}).",
            },
        ]
        trajectory: List[RLMStepResult] = []
        final_answer = None
        validator = REPLSandboxASTValidator()

        for step in range(1, self.max_iterations + 1):
            response = self.llm_call(history)
            history.append({"role": "assistant", "content": response})

            code_blocks = re.findall(r"```(?:repl|python)?\s*\n(.*?)```", response, re.DOTALL)
            if not code_blocks:
                if sandbox_locals["answer"]["ready"]:
                    final_answer = sandbox_locals["answer"]["content"]
                    break
                history.append(
                    {
                        "role": "user",
                        "content": "No code block detected. Use ```repl to interact or set answer['ready']=True.",
                    }
                )
                continue

            code_to_exec = "\n\n".join(code_blocks)
            stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
            old_stdout, old_stderr = sys.stdout, sys.stderr
            start_t = time.perf_counter()
            try:
                # 1. AST Security Validation against forbidden modules and gadget chains
                parsed_tree = ast.parse(code_to_exec)
                validator.validate(parsed_tree)

                # 2. Execution within confined safe sandbox
                sys.stdout, sys.stderr = stdout_buf, stderr_buf
                exec(code_to_exec, sandbox_globals, sandbox_locals)
            except Exception as e:
                logger.warning("REPL execution error at step %d: %s", step, e)
                stderr_buf.write(f"\n{type(e).__name__}: {e}")
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr

            exec_time = time.perf_counter() - start_t
            out_str, err_str = stdout_buf.getvalue(), stderr_buf.getvalue()
            is_ready = bool(sandbox_locals["answer"].get("ready", False))
            ans_content = sandbox_locals["answer"].get("content", "")

            step_res = RLMStepResult(
                iteration=step,
                code=code_to_exec,
                stdout=out_str,
                stderr=err_str,
                execution_time=exec_time,
                is_ready=is_ready,
                final_answer=ans_content if is_ready else None,
            )
            trajectory.append(step_res)
            history.append(
                {"role": "user", "content": f"[REPL Output Step {step}]\nSTDOUT:\n{out_str}\nSTDERR:\n{err_str}"}
            )

            if is_ready:
                final_answer = ans_content
                break

        return {
            "status": "SUCCESS" if final_answer is not None else "MAX_ITERATIONS_REACHED",
            "final_answer": final_answer,
            "iterations": len(trajectory),
            "trajectory": trajectory,
        }
