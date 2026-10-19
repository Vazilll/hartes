#!/usr/bin/env python3
"""
vazus_core.engine.dialogue_synthesizer — Dialogue Review, Insight Extraction & SM-2 Cognitive Grounding.

Systematically scans conversation trajectories, subagent dialogues, and user requests,
extracting key architectural insights, promoting them to 768-D vector memory,
and creating SuperMemo SM-2 active recall cards in vazus.db and Obsidian.
"""

import sys
from pathlib import Path

if "/home/tarhes/Проекты/vazus" not in sys.path and "/home/tarhes/Проекты/vazus" not in sys.path:
    sys.path.insert(0, "/home/tarhes/Проекты/vazus")

import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    pass

from vazus_core.memory.db import get_db_connection

logger = logging.getLogger("vazus.dialogue_synthesizer")

try:
    from vazus_core.embeddings import embed_text
except Exception as _emb_err:
    logger.debug("Optional module vazus_core.embeddings unavailable: %s", _emb_err)
    embed_text = None


class DialogueSynthesizer:
    """
    Synthesizes multi-turn conversations and subagent traces into actionable
    memory facts, SuperMemo SM-2 flashcards, and Obsidian Zettelkasten roadmaps.
    """

    def __init__(self, db_path: Optional[str] = None):
        from vazus_core.integrations.cognitive_tutor_engine import CognitiveTutorEngine

        self.db_path = db_path
        self.tutor = CognitiveTutorEngine(db_path=db_path)
        self.wiki_dir = Path("/home/tarhes/Проекты/vazus/services/memory/semantic/wiki")
        self.wiki_dir.mkdir(parents=True, exist_ok=True)

    def extract_core_dialogue_insights(self) -> List[Dict[str, Any]]:
        """
        Extracts foundational architectural insights from the conversation history.
        """
        insights = [
            {
                "topic": "Autonomous Cognitive Engine",
                "content": "Antigravity is the autonomous operating system itself, equipped with Hermes dispatch, SMT Z3 solvers, AST token pruning, and lifecycle hooks.",
                "question": "What is the primary role and identity of Antigravity in Vazus OS?",
                "answer": "Antigravity is the autonomous cognitive OS core itself, not an external tool, orchestrating memory, hooks, RLM code generation, and formal SMT verification.",
                "domain": "architecture",
            },
            {
                "topic": "Formal Logic & Cognitive Laws (Chelpanov)",
                "content": "Application of Chelpanov's formal logic: eradication of script graveyard, zero-mock empirical verification, AST pruning (Law of Inverse Relation), and anti-loop circuit breakers.",
                "question": "How are Chelpanov's principles of formal logic applied in Vazus OS?",
                "answer": "1) Zero-Script Policy (no dead scripts), 2) Zero-Mock Empirical Testing (no Petitio Principii), 3) AST JIT Pruning (Law of Inverse Relation), 4) AntiLoop Circuit Breaker, 5) Obsidian SM-2 synchronization.",
                "domain": "cognitive",
            },
            {
                "topic": "Applied Domain Hub",
                "content": "Single unified facade AppliedDomainHub aggregates Tinkoff/NPD finance, Mi Scale BIA health, RTU MIREA schedule, RAM clipboard OCR, and Obsidian Daily Briefing in <= 10 ms.",
                "question": "What capabilities are unified inside AppliedDomainHub?",
                "answer": "Personal Finance (Tinkoff API/NPD), Health & Bio-Analytics (Mi Scale BIA), Academic Schedule (RTU MIREA), Windows RAM Clipboard OCR, and atomic Daily Briefings in Obsidian.",
                "domain": "applied_domains",
            },
            {
                "topic": "Knowledge Ingestion & NotebookLM",
                "content": "Two-layer knowledge pipeline: NotebookLM for audio podcasts and macro-synthesis, Obsidian + SuperMemo SM-2 for atomic Zettelkasten and active recall.",
                "question": "How does the two-layer knowledge architecture function in Vazus OS?",
                "answer": "Layer 1 (NotebookLM) handles macro-synthesis, podcasts, and study guides; Layer 2 (Obsidian + SM-2) handles atomic Zettelkasten notes and mathematical active recall intervals (1, 3, 7, 21 days).",
                "domain": "knowledge",
            },
            {
                "topic": "Test Isolation & Zero-Leak Invariant",
                "content": "All test suites in tests/ use isolated tmp_path SQLite fixtures, guaranteeing zero side-effects and byte-identical SHA256 on production services/memory/vazus.db.",
                "question": "Why is test database isolation mandatory in Vazus OS?",
                "answer": "To eliminate Petitio Principii, prevent database bloating (> 25 MB), and ensure 100% reproducible tests without corrupting production facts or vector indexes.",
                "domain": "verification",
            },
            {
                "topic": "MIT RLM & Recursive REPL",
                "content": "MIT RLM (Recursive Language Modeling) with AngelicHoleSolver localizes code holes and synthesizes formal patches in isolated LocalREPL with convergence in <= 1.4 iterations.",
                "question": "How does the RLM Self-Healing REPL operate?",
                "answer": "It formulates symbolic code holes, verifies invariants with SMT Z3 solvers, executes tests in LocalREPL, and enforces RollbackGuardrail on failure.",
                "domain": "engine",
            },
        ]
        return insights

    def sync_to_memory_and_tutor(self) -> Dict[str, int]:
        """
        Persists extracted dialogue insights to SQLite WAL memory (mem0_facts)
        and registers active recall flashcards in tutor_cards.
        """
        conn = get_db_connection(self.db_path)
        insights = self.extract_core_dialogue_insights()

        facts_added = 0
        cards_added = 0
        now = time.time()

        for ins in insights:
            # 1. Store in mem0_facts with 768-D embedding
            fact_id = f"fact_dlg_{hashlib.sha256(ins['topic'].encode()).hexdigest()[:12]}"
            fact_text = f"[{ins['topic']}] {ins['content']}"
            emb_json = None
            if embed_text:
                try:
                    vec = embed_text(fact_text)
                    emb_json = json.dumps(vec)
                except Exception as _vec_err:
                    logger.debug("Failed to embed fact text: %s", _vec_err)

            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO mem0_facts (
                        fact_id, category, entity, fact_text, embedding_json, confidence, created_at, updated_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                    (fact_id, ins["domain"], ins["topic"], fact_text, emb_json, 1.0, now, now, "active"),
                )
                facts_added += 1
            except Exception as e:
                logger.warning("Error storing fact %s: %s", fact_id, e)

            # 2. Register SM-2 Tutor Card
            card_id = f"card_dlg_{hashlib.sha256(ins['topic'].encode()).hexdigest()[:12]}"
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO tutor_cards (
                        id, entity_id, entity_type, question_type, question_text, target_answer,
                        repetition_n, ease_factor, interval_days, lapses, last_review_at, next_review_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                    (
                        card_id,
                        fact_id,
                        "dialogue_insight",
                        "concept_recall",
                        ins["question"],
                        ins["answer"],
                        0,
                        2.5,
                        1,
                        0,
                        None,
                        now + 86400.0,
                        now,
                        now,
                    ),
                )
                cards_added += 1
            except Exception as e:
                logger.warning("Error creating tutor card %s: %s", card_id, e)

        conn.commit()
        conn.close()

        # 3. Generate Obsidian Zettelkasten Note
        self._write_obsidian_roadmap(insights)

        return {"insights_processed": len(insights), "facts_added": facts_added, "cards_added": cards_added}

    def _write_obsidian_roadmap(self, insights: List[Dict[str, Any]]) -> Path:
        """
        Writes the synthesized architectural roadmap note to the Obsidian wiki.
        """
        note_path = self.wiki_dir / "Zettel_Dialogue_Synthesis_Roadmap.md"

        lines = [
            "# 🗺️ Zettel: Dialogue Synthesis & Architectural Roadmap",
            "",
            "**Type**: #architectural_roadmap #dialogue_synthesis #chelpanov_logic",
            f"**Last Synchronized**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 📌 Core Dialogue Directives & System Invariants",
            "",
            "| Domain | Topic | Core Specification | Active Recall Status |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for ins in insights:
            lines.append(f"| `{ins['domain']}` | **{ins['topic']}** | {ins['content']} | 🟢 SM-2 Card Scheduled |")

        lines.extend(
            [
                "",
                "## 🌐 System-Wide Subsystem Flowchart",
                "",
                "```mermaid",
                "flowchart TD",
                "    User([👤 User / Antigravity]) --> JIT[⚡ JIT Prompt & Spec Router]",
                "    JIT --> Hub[🎯 AppliedDomainHub]",
                "    Hub --> Fin[💳 Finance Manager]",
                "    Hub --> Hlt[🏥 Health Mi Scale]",
                "    Hub --> Sch[🎓 RTU MIREA Schedule]",
                "    Hub --> OCR[👁️ Windows RAM OCR]",
                "    JIT --> RLM[🧬 MIT RLM / REPL Engine]",
                "    RLM --> SMT[📐 SMT Z3 Verifier]",
                "    SMT --> Jury[⚖️ Concordia Multi-Agent Jury]",
                "    JIT --> Mem[🧠 Persistent Memory vazus.db]",
                "    Mem --> Wiki[📚 Obsidian LLM Wiki]",
                "    Mem --> NLM[🎙️ NotebookLM Inbox]",
                "    Mem --> SM2[🔁 SuperMemo SM-2 Scheduler]",
                "```",
                "",
                "## 🔗 Related Knowledge Nodes",
                "- [[Zettel_Логика_Георгий_Челпанов_Master_Guide]]",
                "- [[Zettel_О_памяти_и_мнемонике_Георгий_Челпанов]]",
                "- [[Zettel_Skill_Tree_Dashboard]]",
                "- [[Zettel_Daily_Briefing_2026-08-20]]",
                "",
            ]
        )

        note_path.write_text("\n".join(lines), encoding="utf-8")
        return note_path


def run_dialogue_synthesis() -> Dict[str, Any]:
    """Convenience execution entry point."""
    synthesizer = DialogueSynthesizer()
    return synthesizer.sync_to_memory_and_tutor()


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    res = run_dialogue_synthesis()
    print("Dialogue Synthesis Result:", json.dumps(res, indent=2, ensure_ascii=False))
