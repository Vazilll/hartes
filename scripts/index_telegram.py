#!/usr/bin/env python3
"""
scripts/index_telegram.py
CLI helper to run Telegram SuperGraph Indexer (Milestone 2).
"""

import sys
import os
import argparse
import json

# Ensure C:\vazus is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vazus_core.telegram_indexer import index_telegram_messages


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description="Telegram Discussion Threads SuperGraph Indexer (Milestone 2)")
    parser.add_argument(
        "--messages-dir",
        default="C:/vazus/knowledge/telegram_messages",
        help="Path to Telegram messages directory containing .jsonl and .md export files"
    )
    parser.add_argument(
        "--db-path",
        default="C:/vazus/services/memory/vazus.db",
        help="Path to target SuperGraph SQLite database file"
    )

    args = parser.parse_args()

    print(f"Starting Telegram Indexing:")
    print(f"  Messages directory: {args.messages_dir}")
    print(f"  Target database:    {args.db_path}")

    try:
        summary = index_telegram_messages(messages_dir=args.messages_dir, db_path=args.db_path)
        print("\nIndexing completed successfully!")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    except Exception as e:
        sys.stderr.write(f"\n[ERROR] Telegram Indexing failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
