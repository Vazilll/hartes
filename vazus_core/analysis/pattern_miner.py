"""
vazus_core.analysis.pattern_miner — Structural Pattern Miner & Code Health Engine.
Extracts architectural design patterns (Worker Pool, Ring Buffer, Mutex State, RAII)
and calculates objective Code Health metrics (0.0 - 10.0) based on Tree-Sitter & Python AST.
"""

import ast
from pathlib import Path
from typing import Any, Dict, List


class PatternMiner:
    """
    Analyzes polyglot source code to discover design patterns,
    anti-patterns, and calculate an objective Code Health Score.
    """

    @classmethod
    def _is_visitor_node(cls, node: ast.AST) -> bool:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("visit_"):
            return True
        if isinstance(node, ast.ClassDef):
            return any(isinstance(base, ast.Name) and "Visitor" in base.id for base in node.bases)
        return False

    @classmethod
    def _detect_python_patterns(cls, tree: ast.AST) -> List[str]:
        """Detects design patterns in a parsed Python AST."""
        patterns = []
        has_enter = any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "__enter__" for n in ast.walk(tree)
        )
        has_exit = any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "__exit__" for n in ast.walk(tree)
        )
        has_visitor = any(cls._is_visitor_node(n) for n in ast.walk(tree))
        has_async_yield = any(
            isinstance(n, ast.AsyncFunctionDef) and any(isinstance(c, (ast.Yield, ast.YieldFrom)) for c in ast.walk(n))
            for n in ast.walk(tree)
        )

        if has_enter and has_exit:
            patterns.append("ContextManager (RAII)")
        if has_async_yield:
            patterns.append("AsyncGenerator Stream")
        if has_visitor:
            patterns.append("Visitor Pattern")

        return patterns

    @classmethod
    def _calc_cyclomatic_complexity(cls, node: ast.AST) -> int:
        """Calculates CC for a single function AST node."""
        cc = 1
        for child in ast.walk(node):
            if isinstance(
                child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith)
            ):
                cc += 1
            elif isinstance(child, ast.BoolOp):
                cc += len(child.values) - 1
        return cc

    @classmethod
    def _calc_max_nesting(cls, node: ast.AST, lines: List[str]) -> int:
        """Calculates maximum indentation nesting for a function node."""
        max_nesting = 0
        start = node.lineno
        end = min(len(lines) + 1, (node.end_lineno or node.lineno) + 1)
        for lno in range(start, end):
            line = lines[lno - 1]
            indent = len(line) - len(line.lstrip())
            nesting_level = indent // 4
            if nesting_level > max_nesting:
                max_nesting = nesting_level
        return max_nesting

    @classmethod
    def _analyze_function_metrics(cls, node: ast.AST, lines: List[str]) -> Dict[str, Any]:
        """Calculates complexity, nesting, lines, and smells for a single function."""
        fn_name = getattr(node, "name", "anonymous")
        param_count = len(node.args.args) if hasattr(node, "args") else 0
        fn_lines = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1

        cc = cls._calc_cyclomatic_complexity(node)
        max_nesting = cls._calc_max_nesting(node, lines)

        fn_smells = []
        if cc > 10:
            fn_smells.append(f"High Cyclomatic Complexity (CC={cc})")
        if max_nesting > 3:
            fn_smells.append(f"Deep Nesting (depth={max_nesting})")
        if param_count > 4:
            fn_smells.append(f"Long Parameter List ({param_count} params)")
        if fn_lines > 50:
            fn_smells.append(f"God Function ({fn_lines} lines)")

        return {
            "name": fn_name,
            "cc": cc,
            "lines": fn_lines,
            "params": param_count,
            "max_nesting": max_nesting,
            "smells": fn_smells,
        }

    @classmethod
    def _calculate_code_health(cls, function_metrics: List[Dict[str, Any]]) -> float:
        """Computes Code Health score (0.0 to 10.0) from function metrics."""
        code_health = 10.0
        for m in function_metrics:
            if m["cc"] > 10:
                code_health -= 1.5
            if m["max_nesting"] > 3:
                code_health -= 1.0
            if m["params"] > 4:
                code_health -= 0.5
            if m["lines"] > 50:
                code_health -= 1.0
        return max(0.0, min(10.0, round(code_health, 2)))

    @classmethod
    def analyze_python_code(cls, source_code: str) -> Dict[str, Any]:
        """Performs AST analysis on Python source code."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return {"is_valid": False, "error": str(e), "code_health": 0.0}

        patterns_detected = cls._detect_python_patterns(tree)
        lines = source_code.splitlines()

        function_metrics = []
        smells_detected = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                m = cls._analyze_function_metrics(node, lines)
                function_metrics.append(m)
                smells_detected.extend([f"{m['name']}: {s}" for s in m["smells"]])

        code_health = cls._calculate_code_health(function_metrics)

        return {
            "is_valid": True,
            "language": "python",
            "code_health": code_health,
            "ai_ready": code_health >= 9.5,
            "patterns": patterns_detected,
            "smells": smells_detected,
            "functions": function_metrics,
            "refactoring_actions": [f"Extract Method on {m['name']}" for m in function_metrics if m["smells"]],
        }

    @classmethod
    def _detect_go_patterns(cls, source_code: str) -> List[str]:
        """Detects concurrency and state patterns in Go code."""
        patterns = []
        if "sync.Mutex" in source_code or "sync.RWMutex" in source_code:
            patterns.append("Mutex-Guarded State")
        if ("chan " in source_code or "make(chan" in source_code) and (
            "go " in source_code or "sync.WaitGroup" in source_code
        ):
            patterns.append("Concurrency Worker Pool")
        if "%" in source_code and ("head" in source_code or "tail" in source_code):
            patterns.append("Circular Ring Buffer")
        if "context.WithTimeout" in source_code or "context.WithCancel" in source_code:
            patterns.append("Context-Bound Lifetime")
        return patterns

    @classmethod
    def analyze_go_code(cls, source_code: str) -> Dict[str, Any]:
        """Performs pattern mining and heuristic health analysis on Go source code."""
        patterns = cls._detect_go_patterns(source_code)
        lines = source_code.splitlines()
        deep_nesting = any((len(line) - len(line.lstrip("\t"))) > 4 for line in lines)

        smells = ["Deep Nesting (>4 indentation levels)"] if deep_nesting else []
        code_health = 10.0
        if deep_nesting:
            code_health -= 1.0
        if len(lines) > 200 and not patterns:
            code_health -= 2.0

        code_health = max(0.0, min(10.0, round(code_health, 2)))

        return {
            "is_valid": True,
            "language": "go",
            "code_health": code_health,
            "ai_ready": code_health >= 9.5,
            "patterns": patterns,
            "smells": smells,
            "total_lines": len(lines),
            "refactoring_actions": ["Decompose large nested blocks" if deep_nesting else "Maintain current structure"],
        }

    @classmethod
    def analyze_file(cls, file_path: str | Path) -> Dict[str, Any]:
        """Dispatches analysis based on file extension."""
        path = Path(file_path)
        if not path.exists():
            return {"is_valid": False, "error": f"File not found: {path}", "code_health": 0.0}

        content = path.read_text(encoding="utf-8", errors="replace")
        ext = path.suffix.lower()

        if ext == ".py":
            return cls.analyze_python_code(content)
        if ext == ".go":
            return cls.analyze_go_code(content)
        return {"is_valid": True, "language": "unsupported", "code_health": 9.0, "patterns": []}


pattern_miner = PatternMiner()

__all__ = [
    "PatternMiner",
    "pattern_miner",
]
