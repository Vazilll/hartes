#!/usr/bin/env python3
"""
index_research.py v2 — Auto-index LDR worker results into memory_index.json.

Improvements over v1:
  - Scans ALL completed LDR worker results (logs/workers/ldr_*/result.json)
    instead of only a single hardcoded report file
  - Splits large reports into H2-level sections for finer-grained indexing
  - Falls back to whole-report indexing if no H2 sections found
  - Tracks indexed task_ids to avoid re-indexing
  - Compatible with experience_replay.get_few_shot_demo() retrieval format

Usage:
  python scripts/index_research.py             # index all new LDR results
  python scripts/index_research.py --force     # re-index even already-indexed
"""
import argparse
import json
import re
import time
from pathlib import Path

WORKSPACE_DIR = Path("C:/vazus/pyenv")
WORKERS_DIR = WORKSPACE_DIR / "logs" / "workers"
MEMORY_INDEX_PATH = WORKSPACE_DIR / "logs" / "memory_index.json"
INDEXED_IDS_PATH = WORKSPACE_DIR / "logs" / "_indexed_task_ids.json"

# Max characters per section stored in memory index (prevent bloat)
MAX_SECTION_CHARS = 3000


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def split_sections(report: str) -> list[dict]:
    """Split a markdown report into H2 sections. Returns list of {title, text}."""
    # Split on ## headings
    parts = re.split(r"\n##\s+", report)
    if len(parts) <= 1:
        # No H2 sections — use the whole report as one entry
        title = "Overview"
        match = re.match(r"#\s+(.+)", report.strip())
        if match:
            title = match.group(1).strip()
        return [{"title": title, "text": report[:MAX_SECTION_CHARS]}]

    sections = []
    for part in parts[1:]:  # skip text before first ##
        lines = part.strip().split("\n")
        title = lines[0].strip() if lines else "Untitled"
        text = "\n".join(lines[1:]).strip()
        if len(text) > 50:  # skip trivially short sections
            sections.append({"title": title, "text": text[:MAX_SECTION_CHARS]})
    return sections


def index_result(task_id: str, result: dict, memory_index: dict) -> int:
    """Index one LDR result. Returns count of sections indexed."""
    topic = result.get("topic", task_id)
    report = result.get("report", "")
    if not report:
        return 0

    sections = split_sections(report)
    count = 0
    for i, section in enumerate(sections):
        entry_id = f"ldr_{task_id}_{i}" if i > 0 else f"ldr_{task_id}"
        prompt = f"[Research] {topic}: {section['title']}"
        few_shot_trace = (
            f"### RESEARCH FINDING: {section['title']} ###\n\n"
            f"Topic: {topic}\n\n"
            f"{section['text']}\n\n"
            "### END FINDING ###"
        )
        memory_index[entry_id] = {
            "prompt": prompt,
            "few_shot_trace": few_shot_trace,
            "source": task_id,
            "indexed_at": time.time(),
        }
        count += 1
    return count


def main() -> None:
    p = argparse.ArgumentParser(description="Auto-index LDR worker results v2")
    p.add_argument("--force", action="store_true", help="Re-index already indexed tasks")
    args = p.parse_args()

    memory_index: dict = load_json(MEMORY_INDEX_PATH, {})
    indexed_ids: list = load_json(INDEXED_IDS_PATH, [])

    if not WORKERS_DIR.exists():
        print("[IndexResearch] No workers directory found.")
        return

    total_indexed = 0
    tasks_processed = 0

    for task_dir in sorted(WORKERS_DIR.iterdir()):
        if not task_dir.is_dir() or not task_dir.name.startswith("ldr_"):
            continue

        task_id = task_dir.name
        if not args.force and task_id in indexed_ids:
            continue  # already indexed

        status_file = task_dir / "status.txt"
        result_file = task_dir / "result.json"

        if not result_file.exists():
            continue

        status = status_file.read_text(encoding="utf-8").strip() if status_file.exists() else "unknown"
        if status != "done":
            continue  # only index completed tasks

        try:
            result = json.loads(result_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[IndexResearch] Failed to read {result_file}: {e}")
            continue

        count = index_result(task_id, result, memory_index)
        if count > 0:
            indexed_ids.append(task_id)
            total_indexed += count
            tasks_processed += 1
            topic = result.get("topic", task_id)[:60]
            print(f"[IndexResearch] Indexed {count} sections from '{topic}' ({task_id})")

    # Save updated memory index and indexed IDs
    save_json(MEMORY_INDEX_PATH, memory_index)
    save_json(INDEXED_IDS_PATH, indexed_ids)

    print(f"[IndexResearch] Done. {tasks_processed} new task(s), {total_indexed} section(s) indexed.")
    print(f"[IndexResearch] Memory index now has {len(memory_index)} entries.")


if __name__ == "__main__":
    main()
