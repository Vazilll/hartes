#!/usr/bin/env python3
"""
vazus.scripts.update_parameter — CLI for Reactive Parameter Engine.

Usage:
  python update_parameter.py --list
  python update_parameter.py <key> <value> [--desc "Description"]
  python update_parameter.py --sync-all
  python update_parameter.py --sync-db

Example:
  python update_parameter.py student.debts_count 17
  python update_parameter.py health.weight_kg 73.8
"""

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("update_parameter")

sys.path.insert(0, "/home/tarhes/Проекты/vazus")
from vazus_core.memory.reactive_parameters import get_parameter_engine


def main():
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Update and sync reactive parameters across Vazus OS.")
    parser.add_argument("key", nargs="?", help="Parameter key, e.g. student.debts_count")
    parser.add_argument("value", nargs="?", help="New parameter value, e.g. 17")
    parser.add_argument("--desc", help="Optional parameter description")
    parser.add_argument("--list", action="store_true", help="List all active parameters")
    parser.add_argument("--sync-all", action="store_true", help="Resync all parameter slots in markdown notes")
    parser.add_argument("--sync-db", action="store_true", help="Auto-pull metrics from SQLite tables")

    args = parser.parse_args()
    engine = get_parameter_engine()

    if args.list:
        params = engine.get_all()
        print(f"\n📊 Reactive Parameters Registry ({len(params)} items):")
        print("=" * 60)
        for k, v in sorted(params.items()):
            print(f"  {k:30} = {v}")
        print("=" * 60)
        return

    if args.sync_all:
        stats = engine.sync_all()
        logger.info("Resynced all markdown notes: %s", stats)
        return

    if args.sync_db:
        updates = engine.auto_sync_from_database()
        logger.info("Pulled live updates from database: %s", updates)
        return

    if not args.key or args.value is None:
        parser.print_help()
        sys.exit(1)

    res = engine.set(args.key, args.value, args.desc)
    print(f"\n✅ Parameter '{res['key']}' updated to: {res['value']}")
    if res['files_updated']:
        print(f"📝 Reactive updates applied to {len(res['files_updated'])} note file(s):")
        for f in res['files_updated']:
            print(f"  • {f}")
    else:
        print("ℹ️ No active parameter slots found with this key in subscribed note files.")


if __name__ == "__main__":
    main()
