"""
vazus_autonomous_harness.sync.cloud_bridge — Dual NotebookLM & 30 TB Drive Vault Cloud Bridge.

Integrates:
1. Dual Master NotebookLM Workspaces:
   - Master 1st Semester: `11f9bc29-99a1-4bab-aac3-cfbee9e4e553`
   - Master 3rd Semester: `99b01f4d-b3b1-44ee-8f54-2ab7a28d617f`
2. Google Drive 30 TB Vault Sync Mappings:
   - Primary Cloud Path: `G:\\My Drive\\Tars_30TB_Vault`
   - Local Failover Path: `artifacts/vault`
   - Structured Buckets: `01_model_checkpoints`, `02_sdm_sparse_memory`, `03_datasets_cache`,
     `04_flywheel_runs`, `05_notebooklm_sources`, `06_reflexion_wiki`.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("vazus.sync.cloud_bridge")

# Authoritative Dual NotebookLM Workspace Identifiers (Survey § 3.3)
NOTEBOOK_SEM1_ID: str = "11f9bc29-99a1-4bab-aac3-cfbee9e4e553"
NOTEBOOK_SEM3_ID: str = "99b01f4d-b3b1-44ee-8f54-2ab7a28d617f"

# 30 TB Google Drive Vault Default Paths
DEFAULT_CLOUD_VAULT_ROOT: Path = Path(r"G:\My Drive\Tars_30TB_Vault")
DEFAULT_LOCAL_VAULT_ROOT: Path = Path("artifacts/vault")

# Bucket Mappings
VAULT_BUCKET_MAPPINGS: Dict[str, str] = {
    "checkpoints": "01_model_checkpoints",
    "sdm_memory": "02_sdm_sparse_memory",
    "datasets": "03_datasets_cache",
    "flywheel_runs": "04_flywheel_runs",
    "notebooklm_sources": "05_notebooklm_sources",
    "reflexion_wiki": "06_reflexion_wiki",
    "escalations": "04_flywheel_runs/escalations",
    "jules_dispatch": "04_flywheel_runs/jules_dispatch",
}


@dataclass
class NotebookLMWorkspace:
    """Represents a grounded Google NotebookLM knowledge workspace."""
    workspace_id: str
    title: str
    semester: int
    url: str
    sources: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    description: str = ""

    def contains_keyword(self, term: str) -> bool:
        t = term.lower()
        return any(k.lower() in t for k in self.keywords)


# Authoritative Pre-configured Workspaces
SEM1_WORKSPACE = NotebookLMWorkspace(
    workspace_id=NOTEBOOK_SEM1_ID,
    title="РТУ МИРЭА: Полный свод лекций и шпаргалок 1 семестра (ИВБО-22-25)",
    semester=1,
    url=f"https://notebooklm.google.com/notebook/{NOTEBOOK_SEM1_ID}",
    sources=[
        "Full_Presentation_Lectures.pdf",
        "Posobie_dlya_inzhenerov_MIREA.docx",
        "STUDY_GUIDE_ENGLISH_IT.md",
        "STUDY_GUIDE_LINEAR_ALGEBRA.md",
        "STUDY_GUIDE_MATH_ANALYSIS.md",
        "STUDY_GUIDE_MATH_LOGIC.md",
        "academic_debt_liquidation_pack.md",
        "deepmind_google_scientific_research_dossier.md",
        "spark_exported_research.md",
    ],
    keywords=[
        "math", "calculus", "analysis", "linear algebra", "matrices", "gauss",
        "logic", "predicates", "english", "foreign language", "1 семестр",
        "семестр 1", "первый семестр", "матанализ", "линал", "матлогика",
        "инглиш", "16017", "16480", "16479", "16486", "предел", "интеграл",
    ],
    description="9 active sources: Mathematics, Linear Algebra, Mathematical Logic, English IT, and Academic Guides for Semester 1.",
)

SEM3_WORKSPACE = NotebookLMWorkspace(
    workspace_id=NOTEBOOK_SEM3_ID,
    title="РТУ МИРЭА: 3 Семестр — Практикумы, Лабораторные и ДЗ (ИВБО-22-25, Вар. 6)",
    semester=3,
    url=f"https://notebooklm.google.com/notebook/{NOTEBOOK_SEM3_ID}",
    sources=[
        "AI_Lab_01_Var_06.md",
        "SETUP_GOOGLE_DRIVE_TEAM.md",
        "Template_Report_GOST.md",
        "deepmind_google_scientific_research_dossier.md",
        "spark_exported_research.md",
        "ПнЯД_практика_1.pdf",
        "Теория_вычислительных_процессов_Практическая_1.pdf",
    ],
    keywords=[
        "dc circuit", "circuit", "kirchhoff", "toe", "электротехника",
        "дз-1", "дз", "вариант 6", "вар. 6", "var 6", "узловые потенциалы",
        "контурные токи", "баланс мощностей", "потенциальная диаграмма",
        "3 семестр", "семестр 3", "третий семестр", "пняд", "твп",
        "вычислительные процессы", "электроника", "мкт", "муп", "ток", "эдс",
    ],
    description="7 active sources: Electrical Engineering (TOE DC Circuit Var 6), Programming Practice, TVP, and Lab templates for Semester 3.",
)


@dataclass
class SyncResult:
    """Outcome of a synchronization operation."""
    success: bool
    bucket: str
    target_path: Path
    bytes_synced: int
    is_cloud_mounted: bool
    latency_ms: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class NotebookLMSyncBridge:
    """
    Manages Dual NotebookLM workspace discovery, routing, and context resolution.
    """

    def __init__(self):
        self._workspaces: Dict[str, NotebookLMWorkspace] = {
            NOTEBOOK_SEM1_ID: SEM1_WORKSPACE,
            NOTEBOOK_SEM3_ID: SEM3_WORKSPACE,
        }

    def get_workspace_by_id(self, workspace_id: str) -> Optional[NotebookLMWorkspace]:
        """Returns the workspace matching the specified UUID."""
        return self._workspaces.get(workspace_id)

    def get_workspace_for_semester(self, semester: int) -> NotebookLMWorkspace:
        """Returns workspace for Semester 1 or Semester 3."""
        if semester == 1:
            return SEM1_WORKSPACE
        elif semester == 3:
            return SEM3_WORKSPACE
        # Default fallback to Sem 3 for current active semester
        return SEM3_WORKSPACE

    def resolve_workspace(self, context_or_query: Union[str, int]) -> NotebookLMWorkspace:
        """
        Dynamically resolves the most relevant NotebookLM workspace based on context keywords
        or explicit semester number.
        """
        if isinstance(context_or_query, int):
            return self.get_workspace_for_semester(context_or_query)

        query = str(context_or_query).lower()

        # Check explicit semester markers
        if any(k in query for k in ["семестр 1", "1 семестр", "sem 1", "semester 1"]):
            return SEM1_WORKSPACE
        if any(k in query for k in ["семестр 3", "3 семестр", "sem 3", "semester 3"]):
            return SEM3_WORKSPACE

        # Match keywords
        sem1_matches = sum(1 for k in SEM1_WORKSPACE.keywords if k in query)
        sem3_matches = sum(1 for k in SEM3_WORKSPACE.keywords if k in query)

        if sem1_matches > sem3_matches:
            return SEM1_WORKSPACE
        elif sem3_matches > sem1_matches:
            return SEM3_WORKSPACE

        # Default to Sem 3 if no clear signal, or Sem 1 if general math
        if any(m in query for m in ["math", "calculus", "algebra", "логика", "матем"]):
            return SEM1_WORKSPACE
        return SEM3_WORKSPACE

    def list_workspaces(self) -> List[NotebookLMWorkspace]:
        """Returns all configured NotebookLM workspaces."""
        return list(self._workspaces.values())

    def format_grounded_citation_prompt(self, workspace: NotebookLMWorkspace, query: str) -> str:
        """Constructs a grounded query prompt referencing the designated workspace."""
        sources_list = "\n".join(f"- {s}" for s in workspace.sources)
        return (
            f"[NOTEBOOKLM GROUNDED QUERY]\n"
            f"Workspace: {workspace.title} (ID: {workspace.workspace_id})\n"
            f"URL: {workspace.url}\n"
            f"Available Sources ({len(workspace.sources)}):\n{sources_list}\n\n"
            f"Grounded Task / Query:\n{query}\n"
        )


class DriveVaultSyncMapping:
    """
    Manages structured bucket mappings and synchronization to Google Drive 30 TB Vault
    with seamless local filesystem failover.
    """

    def __init__(
        self,
        cloud_root: Optional[Union[str, Path]] = None,
        local_root: Optional[Union[str, Path]] = None,
    ):
        self.cloud_root = Path(cloud_root) if cloud_root is not None else DEFAULT_CLOUD_VAULT_ROOT
        self.local_root = Path(local_root) if local_root is not None else DEFAULT_LOCAL_VAULT_ROOT
        self._ensure_local_dirs()

    def is_cloud_mounted(self) -> bool:
        """Returns True if Google Drive Desktop 30TB Vault path is accessible."""
        try:
            return self.cloud_root.exists() and self.cloud_root.is_dir()
        except Exception:
            return False

    def get_effective_root(self) -> Path:
        """Returns the primary cloud root if mounted, else local fallback root."""
        return self.cloud_root if self.is_cloud_mounted() else self.local_root

    def get_bucket_subpath(self, bucket_key: str) -> str:
        """Translates bucket key to directory subpath."""
        if bucket_key not in VAULT_BUCKET_MAPPINGS:
            raise ValueError(
                f"Unknown bucket key '{bucket_key}'. Valid buckets: {list(VAULT_BUCKET_MAPPINGS.keys())}"
            )
        return VAULT_BUCKET_MAPPINGS[bucket_key]

    def get_bucket_path(self, bucket_key: str, prefer_cloud: bool = True) -> Path:
        """Returns resolved Path for given bucket."""
        subpath = self.get_bucket_subpath(bucket_key)
        if prefer_cloud and self.is_cloud_mounted():
            return self.cloud_root / subpath
        return self.local_root / subpath

    def _ensure_local_dirs(self) -> None:
        """Ensures all standard bucket directories exist on local filesystem."""
        for sub in VAULT_BUCKET_MAPPINGS.values():
            try:
                (self.local_root / sub).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"Could not initialize local vault directory {sub}: {e}")

    def sync_payload(
        self,
        bucket_key: str,
        filename: str,
        content: Union[str, bytes],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        """
        Synchronizes content (string or raw bytes) to vault bucket with local failover.
        """
        t0 = time.perf_counter()
        subpath = self.get_bucket_subpath(bucket_key)
        is_cloud = self.is_cloud_mounted()

        target_dir = (self.cloud_root / subpath) if is_cloud else (self.local_root / subpath)
        dest_file = target_dir / filename

        try:
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                dest_file.write_text(content, encoding="utf-8")
                bytes_written = len(content.encode("utf-8"))
            else:
                dest_file.write_bytes(content)
                bytes_written = len(content)

            # Always mirror to local fallback if cloud is active
            if is_cloud:
                try:
                    local_dir = self.local_root / subpath
                    local_file = local_dir / filename
                    local_file.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(content, str):
                        local_file.write_text(content, encoding="utf-8")
                    else:
                        local_file.write_bytes(content)
                except Exception as le:
                    logger.warning(f"Local mirror write failed: {le}")

            # Write metadata sidecar if provided
            if metadata:
                meta_file = target_dir / f"{filename}.meta.json"
                meta_data = {
                    "filename": filename,
                    "bucket": bucket_key,
                    "timestamp": time.time(),
                    "size_bytes": bytes_written,
                    "is_cloud_mounted": is_cloud,
                    "metadata": metadata,
                }
                meta_file.write_text(json.dumps(meta_data, indent=2, ensure_ascii=False), encoding="utf-8")

            elapsed_ms = (time.perf_counter() - t0) * 1000
            return SyncResult(
                success=True,
                bucket=bucket_key,
                target_path=dest_file,
                bytes_synced=bytes_written,
                is_cloud_mounted=is_cloud,
                latency_ms=elapsed_ms,
                metadata=metadata or {},
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error(f"Failed to sync payload to {dest_file}: {e}")
            return SyncResult(
                success=False,
                bucket=bucket_key,
                target_path=dest_file,
                bytes_synced=0,
                is_cloud_mounted=is_cloud,
                latency_ms=elapsed_ms,
                error=str(e),
                metadata=metadata or {},
            )

    def list_bucket_items(self, bucket_key: str) -> List[Dict[str, Any]]:
        """Lists files present in the specified bucket."""
        path = self.get_bucket_path(bucket_key)
        if not path.exists():
            return []
        items = []
        for f in path.iterdir():
            if f.is_file() and not f.name.endswith(".meta.json"):
                items.append({
                    "name": f.name,
                    "path": str(f),
                    "size_bytes": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                })
        return items


class CloudBridge:
    """
    Unified Cloud Bridge orchestrating:
    - Dual NotebookLM workspaces (`11f9bc29...` Sem 1, `99b01f4d...` Sem 3)
    - Google Drive 30 TB Vault bucket routing & replication
    """

    def __init__(
        self,
        cloud_vault_root: Optional[Union[str, Path]] = None,
        local_vault_root: Optional[Union[str, Path]] = None,
    ):
        self.notebooks = NotebookLMSyncBridge()
        self.vault = DriveVaultSyncMapping(cloud_root=cloud_vault_root, local_root=local_vault_root)

    @property
    def sem1_workspace(self) -> NotebookLMWorkspace:
        return SEM1_WORKSPACE

    @property
    def sem3_workspace(self) -> NotebookLMWorkspace:
        return SEM3_WORKSPACE

    def resolve_notebook(self, query_or_semester: Union[int, str]) -> NotebookLMWorkspace:
        """Resolves workspace based on query string or semester number."""
        return self.notebooks.resolve_workspace(query_or_semester)

    def sync_to_vault(
        self,
        bucket_key: str,
        filename: str,
        content: Union[str, bytes],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        """Offloads artifact to 30 TB Drive Vault."""
        return self.vault.sync_payload(bucket_key, filename, content, metadata=metadata)

    def sync_notebook_source(
        self,
        semester: int,
        filename: str,
        content: Union[str, bytes],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        """Syncs grounding document into designated NotebookLM sources bucket."""
        sem_folder = f"sem_{semester}"
        sub_filename = f"{sem_folder}/{filename}"
        meta = metadata or {}
        meta["semester"] = semester
        meta["target_workspace"] = (
            NOTEBOOK_SEM1_ID if semester == 1 else NOTEBOOK_SEM3_ID
        )
        return self.sync_to_vault("notebooklm_sources", sub_filename, content, metadata=meta)

    def get_sync_status(self) -> Dict[str, Any]:
        """Provides status summary of all cloud endpoints and storage buckets."""
        return {
            "cloud_vault_mounted": self.vault.is_cloud_mounted(),
            "cloud_root": str(self.vault.cloud_root),
            "effective_root": str(self.vault.get_effective_root()),
            "notebook_sem1": {
                "id": SEM1_WORKSPACE.workspace_id,
                "title": SEM1_WORKSPACE.title,
                "source_count": len(SEM1_WORKSPACE.sources),
            },
            "notebook_sem3": {
                "id": SEM3_WORKSPACE.workspace_id,
                "title": SEM3_WORKSPACE.title,
                "source_count": len(SEM3_WORKSPACE.sources),
            },
            "buckets": list(VAULT_BUCKET_MAPPINGS.keys()),
        }
