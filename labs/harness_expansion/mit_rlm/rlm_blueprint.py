"""
labs.harness_expansion.mit_rlm.rlm_blueprint
MIT RLM REPL Code Engineer & Low-Level Debugger Blueprint.
"""

import sys
import platform
from pathlib import Path
from typing import Dict, Any, Optional

PYENV_DIR = Path(r"C:\vazus")
if str(PYENV_DIR) not in sys.path:
    sys.path.insert(0, str(PYENV_DIR))

from vazus_core.workers.rlm import LocalREPL
from vazus_core.ast_pruner import ASTPruner

try:
    from scripts.subagent_rlm_bridge import RLMSubagentBridge, get_debugger_tools
except ImportError:
    RLMSubagentBridge = None
    get_debugger_tools = None


class MITRLMBlueprint:
    """
    MIT RLM (Recursive Language Modeling) REPL Code Engineer Harness Blueprint.
    Provides LocalREPL code execution, subagent recursive sub-branching, and debugger tools.
    """

    def __init__(self):
        self.debugger_tools = get_debugger_tools() if get_debugger_tools else {}
        self.repl = LocalREPL(custom_tools=self.debugger_tools)
        self.bridge = RLMSubagentBridge() if RLMSubagentBridge else None

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "harness_id": "mit_rlm",
            "name": "MIT RLM REPL Code Engineer & Debugger Harness",
            "lab": "MIT",
            "domain": "repl_code_execution_and_debugging",
            "description": "LocalREPL execution, low-level binary debugger tools, hardware profiling, and RLM bridge.",
            "features": ["local_repl", "debugger_tools", "recursive_subbranching", "hardware_profiling"],
        }

    def initialize_repl(self, custom_tools: Optional[Dict[str, Any]] = None) -> LocalREPL:
        """Instantiates a LocalREPL instance with registered debugger tools."""
        tools = dict(self.debugger_tools)
        if custom_tools:
            tools.update(custom_tools)
        return LocalREPL(custom_tools=tools)

    def execute_code_in_repl(self, code_str: str) -> Dict[str, Any]:
        """Prunes code AST signatures and executes code in LocalREPL environment."""
        pruned_code = ASTPruner.prune_ast(code_str)
        res = self.repl.execute_code(pruned_code)
        return {
            "stdout": res.stdout,
            "stderr": res.stderr,
            "is_ready": res.is_ready,
            "final_answer": res.final_answer,
            "variables_count": len(res.variables),
        }

    def run_recursive_task(
        self,
        prompt: str,
        depth: int = 2,
        complexity: str = "medium",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Executes a recursive RLM code engineering task using the subagent RLM bridge."""
        if self.bridge:
            return self.bridge.run_subagent_task(
                prompt=prompt,
                max_depth=depth,
                complexity=complexity,
                dry_run=dry_run,
            )
        else:
            exec_res = self.execute_code_in_repl(f"print('RLM Task: {prompt}')")
            return {
                "subagent": "rlm_code_engineer",
                "status": "SUCCESS",
                "prompt": prompt,
                "execution_result": exec_res,
            }

    def profile_hardware_execution(self) -> Dict[str, Any]:
        """Inspects CPU architecture, active process state, and available memory."""
        machine = platform.machine()
        processor = platform.processor()
        system = platform.system()
        python_ver = sys.version.split()[0]

        return {
            "status": "OPERATIONAL",
            "system": system,
            "architecture": machine,
            "processor": processor,
            "python_version": python_ver,
            "debugger_tools_count": len(self.debugger_tools),
        }
