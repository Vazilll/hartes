#!/usr/bin/env python3
"""
build_leann_index.py — Create or update a LEANN passages index.
Called by leann_index() in leann-mcp.py:
    python build_leann_index.py --name <name> --docs <json_file>

The JSON file should contain a list of document strings.
Creates:
  leann-indexes/<name>.leann.passages.jsonl
"""
import argparse
import json
import sys
from pathlib import Path

LEANN_DIR = Path("C:/vazus/pyenv/leann-indexes")
LEANN_DIR.mkdir(parents=True, exist_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="Index name")
    ap.add_argument("--docs", required=True, help="JSON file with list of document strings")
    ap.add_argument("--append", action="store_true", help="Append to existing index")
    args = ap.parse_args()

    import re

    # Sanitize index name to prevent path traversal
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', args.name).strip('_')
    if not safe_name:
        safe_name = "default_index"

    # Load documents
    docs_path = Path(args.docs).resolve()
    if not docs_path.exists():
        print(f"ERROR: docs file not found: {docs_path}", file=sys.stderr)
        sys.exit(1)

    with open(docs_path, encoding="utf-8") as f:
        docs = json.load(f)

    if not isinstance(docs, list):
        print("ERROR: docs must be a JSON array of strings", file=sys.stderr)
        sys.exit(1)

    docs = [str(d) for d in docs if d]

    # Write passages JSONL (strictly confined to LEANN_DIR)
    out_path = (LEANN_DIR / f"{safe_name}.leann.passages.jsonl").resolve()
    if not out_path.is_relative_to(LEANN_DIR):
        print("ERROR: Path traversal detected in output path", file=sys.stderr)
        sys.exit(1)

    mode = "a" if args.append else "w"
    written = 0
    with open(out_path, mode, encoding="utf-8") as f:
        for text in docs:
            f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
            written += 1

    print(f"added={written}", flush=True)
    print(f"path={out_path}", flush=True)
    print(f"total={sum(1 for _ in open(out_path, encoding='utf-8'))}", flush=True)


if __name__ == "__main__":
    main()
