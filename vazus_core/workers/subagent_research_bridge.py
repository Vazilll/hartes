"""
vazus_core.workers.subagent_research_bridge — Open Deep Research Subagent Bridge.
Decomposes complex research queries, manages factual synthesis, and persists findings
into Mem0 768D memory and Obsidian Zettelkasten Knowledge Base.
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

VAZUS_ROOT = Path("C:/vazus")
if str(VAZUS_ROOT) not in sys.path:
    sys.path.insert(0, str(VAZUS_ROOT))

from vazus_core.memory.mem0_memory_engine import Mem0Engine
from vazus_core.memory.zettelkasten_exporter import ZettelkastenExporter


class OpenDeepResearchBridge:
    """
    Bridge for autonomous Deep Research subagents.
    Provides structured query decomposition, fact extraction, and memory persistence.
    """

    def __init__(self, root_dir: Path = VAZUS_ROOT):
        self.root_dir = root_dir
        self.mem0 = Mem0Engine()
        self.wiki_exporter = ZettelkastenExporter()

    def decompose_query(self, complex_goal: str) -> List[str]:
        """
        Decomposes a broad research goal into 3-5 concrete search directions.
        """
        # Baseline deterministic decomposition
        subqueries = [
            f"{complex_goal} architecture overview and SOTA implementations",
            f"{complex_goal} algorithms, formulas, and math specs",
            f"{complex_goal} benchmarks, known pitfalls, and edge cases"
        ]
        return subqueries

    def persist_research_report(
        self,
        title: str,
        summary: str,
        findings: List[str],
        sources: Optional[List[str]] = None,
        category: str = "deep_research"
    ) -> Dict[str, Any]:
        """
        Persists a complete research report to both Mem0 (768D) and Obsidian Zettelkasten Markdown.
        """
        # 1. Store main summary in Mem0
        fact_res = self.mem0.add_fact(
            fact_text=f"[{category}] {title}: {summary[:300]}",
            category=category,
            entity="research_agent"
        )

        # 2. Store individual high-value findings
        for f in findings[:5]:
            self.mem0.add_fact(
                fact_text=f"[{category}_finding] {f[:250]}",
                category=category,
                entity="research_finding"
            )

        # 3. Export full Obsidian Zettelkasten Markdown note
        sources_str = "\n".join(f"- {s}" for s in (sources or []))
        findings_str = "\n".join(f"- {f}" for f in findings)
        full_content = f"""## 📌 Summary
{summary}

## 🔍 Key Findings
{findings_str if findings_str else "- No specific findings."}

## 🌐 Sources & References
{sources_str if sources_str else "- Grounded via Antigravity Search"}
"""
        note_path = self.wiki_exporter.export_insight_note(
            title=f"Research_{title}",
            category=category,
            content_text=full_content
        )

        return {
            "status": "PERSISTED",
            "fact_id": fact_res.get("fact_id"),
            "note_path": str(note_path),
            "findings_count": len(findings)
        }

    def search_previous_research(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves previously saved research facts using Hybrid RRF (Dense + Lexical).
        """
        return self.mem0.search_facts(query, top_k=top_k)


if __name__ == "__main__":
    bridge = OpenDeepResearchBridge()
    subs = bridge.decompose_query("AST Code Topology")
    print(f"[+] Decomposed: {subs}")
    saved = bridge.persist_research_report(
        title="AST_Code_Topology_Test",
        summary="Tree-sitter PageRank repo map compression",
        findings=["PPR achieves <1800 token budget", "Docstrings compressed to 1 line"]
    )
    print(f"[+] Report Saved: {saved}")
