"""
vazus_autonomous_harness.flywheel.tars_vault_bridge — 30 TB Google Drive Offload Engine.

Provides high-throughput routing of large model weights, sparse distributed memory (SDM)
matrices, dataset caches, flywheel telemetry, and NotebookLM grounding sources
to Google Drive Desktop (`G:\\My Drive\\Tars_30TB_Vault`) with local fallback.
"""

import os
import json
import time
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

logger = logging.getLogger("vazus.tars_vault")

DEFAULT_VAULT_ROOT = Path(r"G:\My Drive\Tars_30TB_Vault")
FALLBACK_VAULT_ROOT = Path(__file__).resolve().parent.parent.parent / "artifacts" / "vault"

VAULT_BUCKETS = {
    "checkpoints": "01_model_checkpoints",
    "sdm_memory": "02_sdm_sparse_memory",
    "datasets": "03_datasets_cache",
    "flywheel_runs": "04_flywheel_runs",
    "notebooklm": "05_notebooklm_sources",
}


@dataclass
class VaultOffloadResult:
    success: bool
    bucket: str
    target_path: Path
    bytes_written: int
    is_cloud_mounted: bool
    latency_ms: float
    error: Optional[str] = None


class TarsVaultBridge:
    """
    Manages offloading heavy compute and memory assets to 30 TB cloud storage.
    """

    def __init__(self, vault_root: Optional[Path] = None):
        if vault_root:
            self.root = vault_root
        elif DEFAULT_VAULT_ROOT.exists():
            self.root = DEFAULT_VAULT_ROOT
        else:
            self.root = FALLBACK_VAULT_ROOT

        self._ensure_buckets()

    def _ensure_buckets(self):
        for sub in VAULT_BUCKETS.values():
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def is_cloud_active(self) -> bool:
        return self.root == DEFAULT_VAULT_ROOT and DEFAULT_VAULT_ROOT.exists()

    def offload_artifact(
        self,
        bucket_key: str,
        filename: str,
        data: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VaultOffloadResult:
        """
        Writes raw binary/text payload directly into the designated vault bucket.
        """
        t0 = time.perf_counter()
        if bucket_key not in VAULT_BUCKETS:
            return VaultOffloadResult(
                success=False,
                bucket=bucket_key,
                target_path=self.root,
                bytes_written=0,
                is_cloud_mounted=self.is_cloud_active(),
                latency_ms=0.0,
                error=f"Invalid bucket key: {bucket_key}. Valid: {list(VAULT_BUCKETS.keys())}",
            )

        bucket_dir = self.root / VAULT_BUCKETS[bucket_key]
        bucket_dir.mkdir(parents=True, exist_ok=True)
        dest_file = bucket_dir / filename

        try:
            with open(dest_file, "wb") as f:
                f.write(data)

            if metadata:
                meta_file = bucket_dir / f"{filename}.meta.json"
                with open(meta_file, "w", encoding="utf-8") as mf:
                    json.dump({
                        "filename": filename,
                        "timestamp": time.time(),
                        "size_bytes": len(data),
                        "metadata": metadata,
                    }, mf, indent=2)

            elapsed_ms = (time.perf_counter() - t0) * 1000
            return VaultOffloadResult(
                success=True,
                bucket=bucket_key,
                target_path=dest_file,
                bytes_written=len(data),
                is_cloud_mounted=self.is_cloud_active(),
                latency_ms=elapsed_ms,
            )
        except Exception as e:
            return VaultOffloadResult(
                success=False,
                bucket=bucket_key,
                target_path=dest_file,
                bytes_written=0,
                is_cloud_mounted=self.is_cloud_active(),
                latency_ms=(time.perf_counter() - t0) * 1000,
                error=str(e),
            )

    def list_bucket_items(self, bucket_key: str) -> List[Dict[str, Any]]:
        if bucket_key not in VAULT_BUCKETS:
            return []
        bucket_dir = self.root / VAULT_BUCKETS[bucket_key]
        if not bucket_dir.exists():
            return []

        items = []
        for item in bucket_dir.iterdir():
            if item.is_file() and not item.name.endswith(".meta.json"):
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "size_bytes": item.stat().st_size,
                    "last_modified": item.stat().st_mtime,
                })
        return items
