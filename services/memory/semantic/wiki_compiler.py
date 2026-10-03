"""
Karpathy LLM Wiki Compiler & Graph Linter for Vazus OS.
Implements 'Compilation Over Retrieval' paradigm, Tarjan SCC cycle analysis, and bidirectional wikilink indexing.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict


class WikiCompiler:
    """
    Compiles raw markdown notes, ADRs, and memory documents into an interlinked knowledge graph
    with Tarjan SCC cycle detection and dangling link validation.
    """

    WIKILINK_PATTERN = re.compile(r'\[\[(.*?)\]\]')

    def __init__(self, wiki_root: Optional[Path] = None):
        self.wiki_root = Path(wiki_root or "C:/vazus/services/memory/semantic/wiki").resolve()
        self.wiki_root.mkdir(parents=True, exist_ok=True)
        self.pages: Dict[str, str] = {}
        self.forward_links: Dict[str, Set[str]] = defaultdict(set)
        self.backlinks: Dict[str, Set[str]] = defaultdict(set)

    def load_wiki(self):
        """Loads all Markdown pages in the wiki directory."""
        self.pages.clear()
        self.forward_links.clear()
        self.backlinks.clear()

        for md_file in self.wiki_root.glob("**/*.md"):
            page_name = md_file.stem
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            self.pages[page_name] = content

            # Extract [[wikilinks]]
            links = self.WIKILINK_PATTERN.findall(content)
            for target in links:
                target_clean = target.strip().split("|")[0] # handle [[Target|Label]]
                self.forward_links[page_name].add(target_clean)
                self.backlinks[target_clean].add(page_name)

    def find_dangling_links(self) -> List[Tuple[str, str]]:
        """Returns list of (source_page, target_missing_page) pairs."""
        dangling = []
        for src, targets in self.forward_links.items():
            for tgt in targets:
                if tgt not in self.pages:
                    dangling.append((src, tgt))
        return dangling

    def find_strongly_connected_components(self) -> List[List[str]]:
        """
        Tarjan's algorithm for finding Strongly Connected Components (cycles) in the wikilink graph.
        """
        index = 0
        indices: Dict[str, int] = {}
        lowlink: Dict[str, int] = {}
        stack: List[str] = []
        on_stack: Set[str] = set()
        sccs: List[List[str]] = []

        def strongconnect(node: str):
            nonlocal index
            indices[node] = index
            lowlink[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)

            for neighbor in self.forward_links.get(node, []):
                if neighbor not in self.pages:
                    continue
                if neighbor not in indices:
                    strongconnect(neighbor)
                    lowlink[node] = min(lowlink[node], lowlink[neighbor])
                elif neighbor in on_stack:
                    lowlink[node] = min(lowlink[node], indices[neighbor])

            if lowlink[node] == indices[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node:
                        break
                if len(scc) > 1: # Only report cycles
                    sccs.append(scc)

        for page in self.pages:
            if page not in indices:
                strongconnect(page)

        return sccs

    def compile_index(self) -> str:
        """
        Generates master index table with backlinks and connectivity metrics.
        """
        self.load_wiki()
        dangling = self.find_dangling_links()
        cycles = self.find_strongly_connected_components()

        lines = [
            "# 📚 Vazus Knowledge Graph — Master Index",
            f"\n**Total Pages**: {len(self.pages)} | **Dangling Links**: {len(dangling)} | **Cyclic SCCs**: {len(cycles)}\n",
            "| Page | Inbound Links (Backlinks) | Outbound Links |",
            "| :--- | :---: | :---: |"
        ]

        for page in sorted(self.pages.keys()):
            in_count = len(self.backlinks.get(page, set()))
            out_count = len(self.forward_links.get(page, set()))
            lines.append(f"| [[{page}]] | {in_count} | {out_count} |")

        if dangling:
            lines.append("\n## ⚠️ Dangling Links (Missing Pages)")
            for src, tgt in dangling[:20]:
                lines.append(f"- `[[{src}]]` ➔ `[[{tgt}]]` (Uncreated)")

        index_path = self.wiki_root / "index.md"
        index_content = "\n".join(lines)
        index_path.write_text(index_content, encoding="utf-8")
        return str(index_path)
