"""
scripts/full_workspace_indexer.py — Re-export Alias & CLI Runner.
Redirects to unified vazus_core.memory.knowledge_engine module.
"""

import sys
from pathlib import Path

# Ensure vazus workspace is in sys.path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from vazus_core.memory.knowledge_engine import FullWorkspaceIndexer

__all__ = ["FullWorkspaceIndexer"]

if __name__ == "__main__":
    indexer = FullWorkspaceIndexer(root_dir=root)
    result = indexer.run_indexer()
    print("Full Workspace Indexing Complete:")
    print(result)
