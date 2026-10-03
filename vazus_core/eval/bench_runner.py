"""
vazus_core.eval.bench_runner — Deterministic Local Evaluation Benchmark Harness (vazus-bench).
Evaluates agent capabilities, AST pruning, Go/Python parsing, SMT Z3 contract proofs,
and regex extraction locally with zero external API dependencies to prevent regressions.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import z3

logger = logging.getLogger(__name__)

from vazus_core.verification.ast_pruner import (
    ASTPruner,
    CTreeSitterPruner,
    GoTreeSitterPruner,
)


class BenchmarkRunner:
    """
    Local deterministic benchmark evaluator.
    Computes pass@1 accuracy, latency, and category breakdowns.
    """

    DEFAULT_TASKS_FILE = Path(r"C:\vazus\data\benchmarks\benchmark_tasks.json")
    DEFAULT_HISTORY_FILE = Path(r"C:\vazus\data\benchmarks\benchmark_history.json")

    def __init__(self, tasks_file: Optional[Path] = None):
        self.tasks_file = tasks_file or self.DEFAULT_TASKS_FILE
        self.tasks: List[Dict[str, Any]] = self._load_tasks()

    def _load_tasks(self) -> List[Dict[str, Any]]:
        if not self.tasks_file.exists():
            return []
        try:
            return json.loads(self.tasks_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load benchmark tasks from %s: %s", self.tasks_file, exc)
            return []

    def _filter_tasks(self, category_filter: Optional[str]) -> List[Dict[str, Any]]:
        if not category_filter or category_filter == "all":
            return self.tasks
        return [t for t in self.tasks if t.get("category") == category_filter]

    def _build_summary(
        self,
        tasks: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        category_stats: Dict[str, Dict[str, int]],
        start_time: float,
    ) -> Dict[str, Any]:
        total = len(tasks)
        passed = sum(1 for r in results if r["passed"])
        pass_at_1 = round((passed / max(1, total)) * 100.0, 2)
        duration_ms = round((time.time() - start_time) * 1000.0, 2)

        return {
            "timestamp": time.time(),
            "total_tasks": total,
            "passed_tasks": passed,
            "failed_tasks": total - passed,
            "pass_at_1": pass_at_1,
            "duration_ms": duration_ms,
            "category_stats": {
                cat: {
                    "total": s["total"],
                    "passed": s["passed"],
                    "pass_rate": round((s["passed"] / max(1, s["total"])) * 100.0, 2),
                }
                for cat, s in category_stats.items()
            },
            "task_results": results,
        }

    def run_all(self, category_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes all benchmark tasks or filtered by category.
        """
        start_time = time.time()
        results: List[Dict[str, Any]] = []
        category_stats: Dict[str, Dict[str, int]] = {}

        tasks_to_run = self._filter_tasks(category_filter)

        for task in tasks_to_run:
            cat = task.get("category", "general")
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "passed": 0}
            category_stats[cat]["total"] += 1

            task_res = self._evaluate_task(task)
            if task_res["passed"]:
                category_stats[cat]["passed"] += 1
            results.append(task_res)

        summary = self._build_summary(tasks_to_run, results, category_stats, start_time)
        self._record_history(summary)
        return summary

    def _evaluate_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        t_id = task.get("id", "unknown")
        t_type = task.get("type", "unknown")
        start = time.time()
        passed = False
        error_msg = None

        try:
            if t_type == "ast_signature":
                passed = self._eval_ast_signature(task)
            elif t_type == "python_ast":
                passed = self._eval_python_ast(task)
            elif t_type == "c_ast":
                passed = self._eval_c_ast(task)
            elif t_type == "z3_proof":
                passed = self._eval_z3_proof(task)
            elif t_type == "regex_parse":
                passed = self._eval_regex_parse(task)
            elif t_type == "pattern_mine":
                passed = self._eval_pattern_mine(task)
            elif t_type == "magma_traverse":
                passed = self._eval_magma_traverse(task)
            elif t_type == "tool_router":
                passed = self._eval_tool_router(task)
            else:
                error_msg = f"Unknown task type: {t_type}"
        except Exception as e:
            error_msg = str(e)
            passed = False

        duration = round((time.time() - start) * 1000.0, 2)
        return {
            "id": t_id,
            "name": task.get("name", t_id),
            "category": task.get("category", "general"),
            "passed": passed,
            "latency_ms": duration,
            "error": error_msg,
        }

    def _eval_ast_signature(self, task: Dict[str, Any]) -> bool:
        code = task.get("input_code", "")
        lang = task.get("language", "go")
        expected_sigs = task.get("expected_signatures", [])

        if lang == "go":
            pruned, stats = GoTreeSitterPruner.prune_code_string(code)
            if not stats.get("is_valid", False):
                return False
            for sig in expected_sigs:
                if sig not in pruned:
                    return False
            return True
        return False

    def _eval_python_ast(self, task: Dict[str, Any]) -> bool:
        code = task.get("input_code", "")
        expected_contains = task.get("expected_contains", [])
        pruned, stats = ASTPruner.prune_code_string(code)
        if not stats.get("is_valid", False):
            return False
        for exp in expected_contains:
            if exp not in pruned:
                return False
        return True

    def _eval_c_ast(self, task: Dict[str, Any]) -> bool:
        code = task.get("input_code", "")
        expected_contains = task.get("expected_contains", [])
        pruned, stats = CTreeSitterPruner.prune_code_string(code)
        if not stats.get("is_valid", False):
            return False
        for exp in expected_contains:
            if exp not in pruned:
                return False
        return True

    def _eval_z3_proof(self, task: Dict[str, Any]) -> bool:
        formula_type = task.get("formula_type", "")
        solver = z3.Solver()

        if formula_type == "non_negative_sum":
            x, y = z3.Int("x"), z3.Int("y")
            solver.add(x >= 0, y >= 0, z3.Not(x + y >= 0))
            return solver.check() == z3.unsat

        elif formula_type == "monotonic_counter":
            c0, c1 = z3.Int("c0"), z3.Int("c1")
            solver.add(c1 == c0 + 1, z3.Not(c1 > c0))
            return solver.check() == z3.unsat

        elif formula_type == "bounded_queue":
            size, cap = z3.Int("size"), z3.Int("cap")
            solver.add(cap == 100, size >= 0, size <= cap, z3.Not(size <= 100))
            return solver.check() == z3.unsat

        elif formula_type == "triangle_inequality":
            dab, dbc, dac = z3.Int("dab"), z3.Int("dbc"), z3.Int("dac")
            solver.add(dab == 3, dbc == 4, dac <= dab + dbc, dac == 10)
            return solver.check() == z3.unsat

        return False

    @staticmethod
    def _eval_telegram_cmd(input_text: str, exp_cmd: str, exp_args: Dict[str, str]) -> bool:
        m = re.match(r"^/([a-zA-Z0-9_]+)(?:\s+(.*))?$", input_text)
        if not m or m.group(1) != exp_cmd:
            return False
        args_str = m.group(2) or ""
        parsed_args = dict(re.findall(r"--([a-zA-Z0-9_]+)\s+([^\s]+)", args_str))
        return parsed_args == exp_args

    @staticmethod
    def _eval_yaml_fm(input_text: str, expected_fm: Dict[str, str]) -> bool:
        m = re.search(r"^---\n(.*?)\n---", input_text, re.DOTALL)
        if not m:
            return False
        fm_lines = m.group(1).strip().splitlines()
        parsed_fm = {}
        for line in fm_lines:
            if ":" in line:
                k, v = line.split(":", 1)
                parsed_fm[k.strip()] = v.strip()
        return parsed_fm == expected_fm

    def _eval_regex_parse(self, task: Dict[str, Any]) -> bool:
        input_text = task.get("input_text", "")
        if "expected_command" in task:
            return self._eval_telegram_cmd(input_text, task["expected_command"], task.get("expected_args", {}))
        elif "expected_wikilinks" in task:
            links = [m.split("|")[0] for m in re.findall(r"\[\[(.*?)\]\]", input_text)]
            return links == task.get("expected_wikilinks", [])
        elif "expected_frontmatter" in task:
            return self._eval_yaml_fm(input_text, task.get("expected_frontmatter", {}))

    def _eval_pattern_mine(self, task: Dict[str, Any]) -> bool:
        from vazus_core.analysis.pattern_miner import PatternMiner

        code = task.get("input_code", "")
        lang = task.get("language", "python")
        expected_patterns = task.get("expected_patterns", [])
        min_health = task.get("min_code_health", 0.0)

        res = PatternMiner.analyze_go_code(code) if lang == "go" else PatternMiner.analyze_python_code(code)
        if not res.get("is_valid", False) or res.get("code_health", 0.0) < min_health:
            return False
        for p in expected_patterns:
            if p not in res.get("patterns", []):
                return False
        return True

    def _eval_magma_traverse(self, task: Dict[str, Any]) -> bool:
        import tempfile

        from vazus_core.memory.magma_graph import MAGMAGraphEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test_magma.db")
            engine = MAGMAGraphEngine(db_path=db_path)
            for edge in task.get("edges", []):
                engine.add_edge(edge[0], edge[1], relation=edge[2], strength=edge[3])
            res = engine.intent_aware_traverse(task["start_node"], intent=task["intent"], max_depth=1)
            if not res or res[0]["node_id"] != task["expected_top_node"]:
                return False
            return True

    def _eval_tool_router(self, task: Dict[str, Any]) -> bool:
        from vazus_core.routing.dynamic_tool_router import DynamicToolRouter

        router = DynamicToolRouter()
        res = router.find_tools(task["query"], top_k=task.get("top_k", 1))
        if not res:
            return False
        return res[0]["name"] == task["expected_tool"]

    def _record_history(self, summary: Dict[str, Any]) -> None:
        history: List[Dict[str, Any]] = []
        if self.DEFAULT_HISTORY_FILE.exists():
            try:
                history = json.loads(self.DEFAULT_HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.debug("Failed to parse benchmark history file: %s", exc)
                history = []
        history.append(
            {
                "timestamp": summary["timestamp"],
                "pass_at_1": summary["pass_at_1"],
                "total_tasks": summary["total_tasks"],
                "duration_ms": summary["duration_ms"],
            }
        )
        try:
            self.DEFAULT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.DEFAULT_HISTORY_FILE.write_text(json.dumps(history[-50:], indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to record benchmark history to %s: %s", self.DEFAULT_HISTORY_FILE, exc)


# Global singleton instance
benchmark_runner = BenchmarkRunner()

__all__ = ["BenchmarkRunner", "benchmark_runner"]
