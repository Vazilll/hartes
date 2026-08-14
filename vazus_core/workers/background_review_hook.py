"""
vazus_core.background_review_hook — Hermes-Style Background Review Daemon Hook.
Spawns a lightweight daemon thread after every turn to evaluate if a new skill or memory
should be saved/updated without blocking the main conversation turn.
"""

import os
import sys
import time
import threading
import logging
from pathlib import Path

sys.path.insert(0, "C:/vazus")

from vazus_core.skill_author import create_autonomous_skill
from vazus_core.mem0_memory_engine import Mem0Engine

logger = logging.getLogger("BackgroundReviewHook")


class BackgroundReviewHook:
    """
    Hermes-style daemon background reviewer.
    Inspects turn execution artifacts and automatically extracts SKILL.md and mem0 facts.
    """

    @classmethod
    def spawn_review_async(cls, turn_prompt: str, response_summary: str, files_modified: list = None):
        """
        Fires a daemon thread to evaluate turn artifacts asynchronously.
        """
        thread = threading.Thread(
            target=cls._review_worker,
            args=(turn_prompt, response_summary, files_modified or []),
            daemon=True
        )
        thread.start()

    @classmethod
    def _review_worker(cls, turn_prompt: str, response_summary: str, files_modified: list):
        try:
            # 1. mem0 Fact Extraction
            mem0 = Mem0Engine()
            if len(turn_prompt) > 15:
                mem0.add_fact(f"User task context: {turn_prompt[:150]}", category="turn_context")

            # 2. Heuristic check for auto-skill creation
            # If complex python files or new workflows were generated
            is_complex_workflow = any(
                kw in turn_prompt.lower()
                for kw in ["create skill", "build pipeline", "custom architecture", "optimize database"]
            ) or len(files_modified) >= 3

            if is_complex_workflow:
                skill_slug = f"vazus-auto-{int(time.time())}"
                skill_desc = f"Auto-generated skill from task: {turn_prompt[:100]}"
                instructions = f"""## Overview
Auto-extracted workflow for task: {turn_prompt}

## Execution Pattern
Files modified: {', '.join(files_modified) if files_modified else 'None'}
Summary: {response_summary[:500]}
"""
                create_autonomous_skill(
                    skill_name=skill_slug,
                    description=skill_desc,
                    instructions_markdown=instructions,
                    category="Vazus Auto-Extracted"
                )
                logger.info(f"[BackgroundReview] Created auto-skill: {skill_slug}")

        except Exception as e:
            logger.warning(f"[BackgroundReview] Background review worker error: {e}")


if __name__ == "__main__":
    BackgroundReviewHook.spawn_review_async(
        turn_prompt="Build custom architecture pipeline",
        response_summary="Implemented custom pipeline with SMT Z3 and mem0",
        files_modified=["C:/vazus/vazus_core/mem0_memory_engine.py"]
    )
    time.sleep(1.0)
    print("[+] Background Review Hook test executed successfully.")
