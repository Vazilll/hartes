import os
import sys
import sqlite3
import json
import time
from pathlib import Path

PROJECT_ROOT = Path("C:/vazus")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vazus_core.zettelkasten_exporter import export_all_zettelkasten_notes, DEFAULT_DB_PATH
from vazus_core.kgb_analytical_extractor import ThesisNode, ProtocolNode
from vazus_core.supergraph_linker import SuperGraphLinker, DEFAULT_DB_PATH as LINKER_DEFAULT_DB

print(f"zettelkasten_exporter DEFAULT_DB_PATH: {DEFAULT_DB_PATH}")
print(f"supergraph_linker DEFAULT_DB_PATH:      {LINKER_DEFAULT_DB}")

output_wiki_dir = r"C:\vazus\services\memory\semantic\wiki"

t_node = ThesisNode(
    id="thesis_review_test_100",
    name="Тестовый тезис 100 для проверки базы",
    statement="Тестирование рассинхронизации путей vazus.db между exporter и linker.",
    confidence=0.95,
    domain="test_domain",
    ach_status="ACCEPTED"
)

extraction = {"nodes": [t_node.to_dict()], "edges": []}

# Make sure no lock
time.sleep(1.0)

paths = export_all_zettelkasten_notes(extraction, output_dir=output_wiki_dir, auto_reindex=True)
print(f"Exported note: {paths[0]}")

t_stem = Path(paths[0]).stem
t_wiki_id = f"wiki:{t_stem}"

conn1 = sqlite3.connect("C:/vazus/vazus.db")
row1 = conn1.execute("SELECT id FROM kg_nodes WHERE id = ?", (t_wiki_id,)).fetchone()
conn1.close()

conn2 = sqlite3.connect("C:/vazus/services/memory/vazus.db")
row2 = conn2.execute("SELECT id FROM kg_nodes WHERE id = ?", (t_wiki_id,)).fetchone()
conn2.close()

print(f"In C:/vazus/vazus.db: {row1 is not None}")
print(f"In C:/vazus/services/memory/vazus.db: {row2 is not None}")

# Default vector search (without passing db_path)
linker = SuperGraphLinker()
res_default = linker.search_unified_vector_space("рассинхронизации", top_k=5)
found_default = any(r["id"] == t_wiki_id for r in res_default)
print(f"Found in default search_unified_vector_space (services/memory/vazus.db): {found_default}")

# Vector search specifying C:/vazus/vazus.db
res_root = linker.search_unified_vector_space("рассинхронизации", db_path=Path("C:/vazus/vazus.db"), top_k=5)
found_root = any(r["id"] == t_wiki_id for r in res_root)
print(f"Found in search_unified_vector_space with C:/vazus/vazus.db: {found_root}")
