import sys
import os
from pathlib import Path

ROOT_DIR = Path("C:/vazus")
for p in [str(ROOT_DIR), str(ROOT_DIR / "labs" / "raytsystem" / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from raytsystem.webapp import create_app
    from raytsystem.webapp.snapshot import SnapshotProvider
    
    print("Testing SnapshotProvider...")
    provider = SnapshotProvider(ROOT_DIR / "labs" / "raytsystem")
    snap = provider.get()
    print("Graph loaded!")
    print("Graph snapshot_id:", getattr(snap.graph, "graph_snapshot_id", None))
    print("Serializing graph model_dump...")
    dumped = snap.graph.model_dump(mode="json")
    print("Model dump succeeded! Dump keys:", list(dumped.keys()))
except Exception as e:
    import traceback
    print("EXCEPTIONAL ERROR:")
    traceback.print_exc()
