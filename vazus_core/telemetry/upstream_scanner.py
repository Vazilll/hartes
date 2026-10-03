"""
vazus_core.telemetry.upstream_scanner
Layer 2 Component: Upstream Dependency Modernization & API Scanner.

Scans installed package metadata, AST signatures in site-packages, and local code references
to discover outdated API patterns, deprecated calls, and optimization opportunities.
"""

import importlib.metadata
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class UpstreamScanner:
    """
    Scans the codebase for external package usage and matches against
    known modernization patterns and optimization recipes.
    """

    KNOWN_MODERNIZATIONS = [
        {
            "id": "pydantic_v1_to_v2",
            "package": "pydantic",
            "deprecated_pattern": ".dict()",
            "modern_pattern": ".model_dump()",
            "description": "Migrate Pydantic v1 .dict() to v2 .model_dump() for 3-5x faster serialization.",
        },
        {
            "id": "numpy_simsimd_cosine",
            "package": "numpy",
            "deprecated_pattern": "np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))",
            "modern_pattern": "simsimd.cosine(a, b)",
            "description": "Replace NumPy manual cosine similarity with AVX-512 accelerated simsimd.cosine.",
        },
        {
            "id": "python312_type_alias",
            "package": "typing",
            "deprecated_pattern": "TypeAlias =",
            "modern_pattern": "type X =",
            "description": "Use native Python 3.12+ 'type' statement instead of typing.TypeAlias.",
        },
        {
            "id": "builtin_generic_types",
            "package": "typing",
            "deprecated_pattern": "from typing import List, Dict, Tuple, Set",
            "modern_pattern": "Use built-in list, dict, tuple, set",
            "description": "Replace typing.List/Dict with built-in generic collections (PEP 585).",
        },
    ]

    def __init__(self, workspace_root: str = r"C:\vazus"):
        self.workspace_root = Path(workspace_root).resolve()

    def get_installed_packages(self) -> dict[str, str]:
        """Returns a mapping of installed package names to versions."""
        packages = {}
        for dist in importlib.metadata.distributions():
            try:
                packages[dist.metadata["Name"].lower()] = dist.version
            except Exception as exc:
                logger.debug("Distribution metadata read skipped for %s: %s", dist, exc)
        return packages

    def scan_modernization_opportunities(self) -> list[dict[str, Any]]:
        """
        Scans workspace Python files to detect applicable modernization opportunities.
        """
        opportunities = []
        installed = self.get_installed_packages()

        for py_file in self.workspace_root.rglob("*.py"):
            # Skip virtual environments and caches
            if any(part in py_file.parts for part in (".venv", "__pycache__", ".pytest_cache", ".git")):
                continue

            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                rel_path = str(py_file.relative_to(self.workspace_root)).replace("\\", "/")

                for mod in self.KNOWN_MODERNIZATIONS:
                    pkg = mod["package"]
                    dep_pattern = mod["deprecated_pattern"]

                    # If the pattern is found in the source file
                    if dep_pattern in content:
                        opportunities.append(
                            {
                                "id": mod["id"],
                                "file": rel_path,
                                "package": pkg,
                                "installed_version": installed.get(pkg, "unknown"),
                                "deprecated_pattern": dep_pattern,
                                "modern_replacement": mod["modern_pattern"],
                                "description": mod["description"],
                                "tier": "Tier 1 (ast-grep/GritQL)",
                            }
                        )
            except Exception as exc:
                logger.debug("Modernization scan failed for %s: %s", py_file, exc)

        return opportunities
