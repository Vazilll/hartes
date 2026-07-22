"""
Knowledge Graph Cleanup Script
Removes redundant code nodes from the SQLite database that are
already indexed by codebase-memory-mcp, plus general housekeeping.
"""

import shutil
import sqlite3
import os
from datetime import datetime

DB_PATH = r"C:\vazus\memory\dnts.db"
BACKUP_PATH = DB_PATH + ".bak"


def main():
    print(f"{'='*60}")
    print(f"  Knowledge Graph Cleanup")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 1. Backup
    print("[1/13] Backing up database...")
    db_size_before = os.path.getsize(DB_PATH)
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"  Backup saved to: {BACKUP_PATH}")
    print(f"  Database size before: {db_size_before / (1024*1024):.2f} MB\n")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    # 2. Count nodes before
    cur.execute("SELECT COUNT(*) FROM kg_nodes")
    nodes_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM kg_edges")
    edges_before = cur.fetchone()[0]
    print(f"[2/13] Before cleanup:")
    print(f"  kg_nodes: {nodes_before:,}")
    print(f"  kg_edges: {edges_before:,}")

    # Show domain breakdown
    cur.execute("SELECT domain, COUNT(*) FROM kg_nodes GROUP BY domain ORDER BY COUNT(*) DESC")
    print(f"\n  Node domain breakdown:")
    for domain, count in cur.fetchall():
        print(f"    {domain or 'NULL'}: {count:,}")
    print()

    # 3. Delete edges where source is a code node
    print("[3/13] Deleting edges with code source nodes...")
    cur.execute("""
        DELETE FROM kg_edges
        WHERE source_id IN (SELECT id FROM kg_nodes WHERE domain IN ('code', 'code_test'))
    """)
    del_edges_source = cur.rowcount
    print(f"  Deleted: {del_edges_source:,} edges\n")

    # 4. Delete edges where target is a code node
    print("[4/13] Deleting edges with code target nodes...")
    cur.execute("""
        DELETE FROM kg_edges
        WHERE target_id IN (SELECT id FROM kg_nodes WHERE domain IN ('code', 'code_test'))
    """)
    del_edges_target = cur.rowcount
    print(f"  Deleted: {del_edges_target:,} edges\n")

    # 5. Delete code nodes
    print("[5/13] Deleting code nodes (domain='code' or 'code_test')...")
    cur.execute("DELETE FROM kg_nodes WHERE domain IN ('code', 'code_test')")
    del_nodes = cur.rowcount
    print(f"  Deleted: {del_nodes:,} nodes\n")

    # 6. Orphaned reviews
    print("[6/13] Deleting orphaned kg_reviews...")
    try:
        cur.execute("DELETE FROM kg_reviews WHERE node_id NOT IN (SELECT id FROM kg_nodes)")
        del_reviews = cur.rowcount
        print(f"  Deleted: {del_reviews:,} reviews\n")
    except sqlite3.OperationalError as e:
        print(f"  Skipped (table may not exist): {e}\n")
        del_reviews = 0

    # 7. Resolved doubts
    print("[7/13] Deleting resolved doubts...")
    try:
        cur.execute("DELETE FROM doubts WHERE resolved = 1")
        del_resolved = cur.rowcount
        print(f"  Deleted: {del_resolved:,} resolved doubts\n")
    except sqlite3.OperationalError as e:
        print(f"  Skipped (table may not exist): {e}\n")
        del_resolved = 0

    # 8. Orphaned doubts
    print("[8/13] Deleting orphaned doubts...")
    try:
        cur.execute("DELETE FROM doubts WHERE belief_id NOT IN (SELECT id FROM beliefs)")
        del_orphan_doubts = cur.rowcount
        print(f"  Deleted: {del_orphan_doubts:,} orphaned doubts\n")
    except sqlite3.OperationalError as e:
        print(f"  Skipped (table may not exist): {e}\n")
        del_orphan_doubts = 0

    # 9. Expired cache
    print("[9/13] Deleting expired LLM cache entries...")
    try:
        cur.execute("""
            DELETE FROM llm_cache
            WHERE expires_at IS NOT NULL AND datetime(expires_at) < datetime('now')
        """)
        del_cache = cur.rowcount
        print(f"  Deleted: {del_cache:,} expired cache entries\n")
    except sqlite3.OperationalError as e:
        print(f"  Skipped (table may not exist): {e}\n")
        del_cache = 0

    conn.commit()

    # 10. VACUUM
    print("[10/13] Running VACUUM...")
    conn.execute("VACUUM")
    print("  Done.\n")

    # 11. ANALYZE
    print("[11/13] Running ANALYZE...")
    conn.execute("ANALYZE")
    print("  Done.\n")

    # 12. Count after
    cur.execute("SELECT COUNT(*) FROM kg_nodes")
    nodes_after = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM kg_edges")
    edges_after = cur.fetchone()[0]
    print(f"[12/13] After cleanup:")
    print(f"  kg_nodes: {nodes_after:,}")
    print(f"  kg_edges: {edges_after:,}")

    cur.execute("SELECT domain, COUNT(*) FROM kg_nodes GROUP BY domain ORDER BY COUNT(*) DESC")
    print(f"\n  Remaining node domains:")
    for domain, count in cur.fetchall():
        print(f"    {domain or 'NULL'}: {count:,}")
    print()

    conn.close()

    # 13. Summary
    db_size_after = os.path.getsize(DB_PATH)
    print(f"[13/13] Summary")
    print(f"{'='*60}")
    print(f"  Nodes removed:        {del_nodes:,}")
    print(f"  Edges removed:        {del_edges_source + del_edges_target:,}")
    print(f"  Reviews removed:      {del_reviews:,}")
    print(f"  Doubts removed:       {del_resolved + del_orphan_doubts:,}")
    print(f"  Cache entries removed: {del_cache:,}")
    print(f"  ---")
    print(f"  Nodes: {nodes_before:,} -> {nodes_after:,}")
    print(f"  Edges: {edges_before:,} -> {edges_after:,}")
    print(f"  DB size: {db_size_before/(1024*1024):.2f} MB -> {db_size_after/(1024*1024):.2f} MB")
    print(f"  Size reduction: {(db_size_before - db_size_after)/(1024*1024):.2f} MB ({(1 - db_size_after/db_size_before)*100:.1f}%)")
    print(f"  Backup at: {BACKUP_PATH}")
    print(f"{'='*60}")
    print("  Cleanup complete!")


if __name__ == "__main__":
    main()
