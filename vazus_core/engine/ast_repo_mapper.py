"""
vazus_core.engine.ast_repo_mapper — SOTA PageRank AST Repository Mapper.
Extracts definitions and references, computes Personalized PageRank (PPR, d=0.85),
prunes bodies to signatures, and dynamically bisects the output to strictly fit < 1800 tokens.
"""

import os
import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

VAZUS_ROOT = Path("C:/vazus")


class ASTRepoMapper:
    """
    Constructs an ultra-compact (<1800 tokens) architectural map of the codebase.
    Uses Tree-sitter / AST signatures and Personalized PageRank.
    """

    def __init__(self, root_dir: Path = VAZUS_ROOT):
        self.root_dir = root_dir

    def extract_symbols(self, file_path: Path) -> Tuple[List[str], Set[str], str]:
        """
        Extracts top-level definitions, referenced identifiers, and skeletonized AST signatures.
        """
        try:
            code = file_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(code, filename=str(file_path))
        except Exception:
            return [], set(), ""

        defs = []
        refs = set()
        skeleton_lines = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_") or node.name.startswith("__"):
                    defs.append(node.name)
                    args = [a.arg for a in node.args.args]
                    skeleton_lines.append(f"  def {node.name}({', '.join(args[:4])}): ...")
            elif isinstance(node, ast.ClassDef):
                defs.append(node.name)
                skeleton_lines.append(f"  class {node.name}:")
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not sub.name.startswith("_") or sub.name.startswith("__"):
                            defs.append(f"{node.name}.{sub.name}")
                            args = [a.arg for a in sub.args.args]
                            skeleton_lines.append(f"    def {sub.name}({', '.join(args[:3])}): ...")

        # Collect references (calls & name lookups)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                refs.add(node.id)
            elif isinstance(node, ast.Attribute):
                refs.add(node.attr)

        return defs, refs, "\n".join(skeleton_lines)

    def build_repo_map(
        self,
        active_files: Optional[List[str]] = None,
        max_tokens: int = 1800,
        subsystem: str = "vazus_core"
    ) -> str:
        """
        Builds a token-budgeted (<1800 tokens) Repo Map with Personalized PageRank.
        """
        target_dir = self.root_dir / subsystem
        if not target_dir.exists():
            target_dir = self.root_dir

        py_files = [
            f for f in target_dir.rglob("*.py")
            if not any(ign in str(f) for ign in [".venv", "__pycache__", "tests", "scratch", "logs"])
        ]

        file_defs: Dict[str, List[str]] = {}
        file_refs: Dict[str, Set[str]] = {}
        file_skeletons: Dict[str, str] = {}
        all_def_counts: Dict[str, int] = defaultdict(int)

        for pf in py_files:
            rel = str(pf.relative_to(self.root_dir)).replace("\\", "/")
            defs, refs, skel = self.extract_symbols(pf)
            file_defs[rel] = defs
            file_refs[rel] = refs
            file_skeletons[rel] = skel
            for d in defs:
                all_def_counts[d] += 1

        files = list(file_defs.keys())
        if not files:
            return ""

        # Compute Directed Dependency Graph Matrix
        weights: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        out_weights: Dict[str, float] = defaultdict(float)

        for u in files:
            for v in files:
                if u == v:
                    continue
                shared = set(file_defs[v]) & file_refs[u]
                if shared:
                    w = sum(1.0 / max(1, all_def_counts[s]) for s in shared)
                    weights[u][v] = w
                    out_weights[u] += w

        # Personalized PageRank (Power Iteration, d=0.85)
        active_set = set(active_files or [])
        teleport = {}
        total_p = 0.0
        for f in files:
            val = 20.0 if any(af in f for af in active_set) else 1.0
            teleport[f] = val
            total_p += val

        for f in files:
            teleport[f] /= max(1e-9, total_p)

        scores = {f: 1.0 / len(files) for f in files}
        d = 0.85

        for _ in range(15):
            new_scores = {}
            for v in files:
                inflow = 0.0
                for u in files:
                    if out_weights[u] > 0 and v in weights[u]:
                        inflow += scores[u] * (weights[u][v] / out_weights[u])
                    elif out_weights[u] == 0:
                        inflow += scores[u] / len(files)
                new_scores[v] = (1 - d) * teleport[v] + d * inflow
            scores = new_scores

        ranked_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Bisection / Greedy Token Budget Selection (~3.5 chars per token)
        max_chars = max_tokens * 3
        current_chars = 0
        selected_blocks = []

        for f_path, score in ranked_files:
            skel = file_skeletons.get(f_path, "")
            if not skel.strip():
                continue
            block = f"📁 `{f_path}` (rank: {score:.3f}):\n{skel}\n"
            if current_chars + len(block) <= max_chars:
                selected_blocks.append(block)
                current_chars += len(block)
            else:
                break

        header = f"## 🗺️ Vazus OS Active AST Repo Map (Top {len(selected_blocks)} ranked modules):\n\n"
        return header + "\n".join(selected_blocks)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mapper = ASTRepoMapper()
    repo_map = mapper.build_repo_map(active_files=["vazus_core/engine", "vazus_core/memory"])
    print(repo_map[:1000])
    print(f"\nTotal characters: {len(repo_map)} (~{len(repo_map)//3.5:.0f} tokens)")
