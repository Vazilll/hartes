"""
vazus_autonomous_harness.daemon.colab_bridge -- OpenColab Asynchronous Queue Bridge.

Provides a zero-deadlock, asynchronous mailbox queue between headless orchestrators
(Tier 0 VPS / Tier 1.5 Edge) and Google Colab GPU runtimes via Google Drive:
`Tars_30TB_Vault/colab_queue/` with:
- /inbox/   : Pending jobs submitted by VPS/Edge
- /active/  : In-flight jobs claimed by Colab worker
- /outbox/  : Completed execution results and artifacts
- keepalive.json : Continuous worker heartbeat monitoring
"""

import os
import json
import time
import uuid
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger("vazus.daemon.colab_bridge")

DEFAULT_DRIVE_QUEUE = Path(r"G:\My Drive\Tars_30TB_Vault\colab_queue")
FALLBACK_QUEUE = Path(__file__).resolve().parent.parent.parent / "artifacts" / "vault" / "colab_queue"


@dataclass
class ColabJobManifest:
    job_id: str
    task_type: str
    code: str
    created_at: float
    iso_time: str
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, TIMED_OUT
    timeout_sec: int = 1800
    metadata: Dict[str, Any] = field(default_factory=dict)
    claimed_at: Optional[float] = None
    worker_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColabJobManifest":
        return cls(
            job_id=data.get("job_id", ""),
            task_type=data.get("task_type", "GENERAL"),
            code=data.get("code", ""),
            created_at=data.get("created_at", time.time()),
            iso_time=data.get("iso_time", ""),
            status=data.get("status", "PENDING"),
            timeout_sec=data.get("timeout_sec", 1800),
            metadata=data.get("metadata", {}),
            claimed_at=data.get("claimed_at"),
            worker_id=data.get("worker_id"),
        )


@dataclass
class ColabJobResult:
    job_id: str
    status: str  # SUCCESS, ERROR, TIMEOUT
    completed_at: float
    iso_time: str
    result_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColabJobResult":
        return cls(
            job_id=data.get("job_id", ""),
            status=data.get("status", "SUCCESS"),
            completed_at=data.get("completed_at", time.time()),
            iso_time=data.get("iso_time", ""),
            result_data=data.get("result_data", {}),
            error=data.get("error"),
            execution_time_sec=data.get("execution_time_sec", 0.0),
        )


class ColabBridge:
    """
    OpenColab Asynchronous Queue Bridge.
    Enables headless dispatch and retrieval of GPU compute tasks via Google Drive mailbox.
    """

    def __init__(self, queue_root: Optional[Union[str, Path]] = None):
        if queue_root:
            self.root = Path(queue_root)
        elif DEFAULT_DRIVE_QUEUE.exists():
            self.root = DEFAULT_DRIVE_QUEUE
        else:
            self.root = FALLBACK_QUEUE

        self.inbox_dir = self.root / "inbox"
        self.active_dir = self.root / "active"
        self.outbox_dir = self.root / "outbox"
        self.keepalive_file = self.root / "keepalive.json"

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.active_dir.mkdir(parents=True, exist_ok=True)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)

    def submit_job(
        self,
        task_type: str,
        code: str,
        metadata: Optional[Dict[str, Any]] = None,
        timeout_sec: int = 1800,
    ) -> str:
        """
        Submits a job manifest to colab_queue/inbox/.
        Conforms strictly to PROJECT.md interface contract:
            submit_job(self, task_type: str, code: str) -> str
        """
        now = time.time()
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        job_id = f"colab_job_{int(now)}_{uuid.uuid4().hex[:8]}"

        manifest = ColabJobManifest(
            job_id=job_id,
            task_type=task_type,
            code=code,
            created_at=now,
            iso_time=iso,
            status="PENDING",
            timeout_sec=timeout_sec,
            metadata=metadata or {},
        )

        inbox_file = self.inbox_dir / f"task_{job_id}.json"
        temp_file = self.inbox_dir / f".tmp_{job_id}.json"

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
        temp_file.replace(inbox_file)

        logger.info(f"[ColabBridge] Submitted job {job_id} ({task_type}) to {inbox_file}")
        return job_id

    def poll_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Polls colab_queue/outbox/ for completed results.
        Conforms strictly to PROJECT.md interface contract:
            poll_result(self, job_id: str) -> Optional[dict]
        """
        possible_files = [
            self.outbox_dir / f"result_{job_id}.json",
            self.outbox_dir / f"{job_id}.json",
            self.outbox_dir / f"task_{job_id}.json",
        ]

        for result_file in possible_files:
            if result_file.exists():
                try:
                    with open(result_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"[ColabBridge] Reading {result_file} failed: {e}")
                    return None
        return None

    def claim_job(
        self,
        job_id: Optional[str] = None,
        worker_id: str = "colab_gpu_worker",
    ) -> Optional[ColabJobManifest]:
        """
        Colab worker helper: Atomically claims a job from inbox and moves it to active.
        If job_id is None, claims the earliest pending job.
        """
        self._ensure_directories()

        if job_id:
            target_file = self.inbox_dir / f"task_{job_id}.json"
            if not target_file.exists():
                target_file = self.inbox_dir / f"{job_id}.json"
            if not target_file.exists():
                return None
            candidate_files = [target_file]
        else:
            candidate_files = sorted(
                self.inbox_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
            )

        for inbox_path in candidate_files:
            if inbox_path.name.startswith(".tmp") or inbox_path.name.startswith(".lock"):
                continue
            active_path = self.active_dir / inbox_path.name
            lock_path = self.active_dir / f".lock_{inbox_path.name}"

            # Exclusive atomic lock to prevent multi-worker claiming races on Windows/POSIX
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, worker_id.encode("utf-8"))
                os.close(fd)
            except (FileExistsError, PermissionError, OSError):
                # Another worker is actively claiming this job or locked it
                continue

            try:
                # Atomic rename moves file from inbox to active
                inbox_path.replace(active_path)
                with open(active_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                manifest = ColabJobManifest.from_dict(data)
                manifest.status = "RUNNING"
                manifest.claimed_at = time.time()
                manifest.worker_id = worker_id

                with open(active_path, "w", encoding="utf-8") as f:
                    json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)

                logger.info(f"[ColabBridge] Worker {worker_id} claimed job {manifest.job_id}")
                return manifest
            except (OSError, json.JSONDecodeError) as e:
                logger.debug(f"[ColabBridge] Failed to claim {inbox_path}: {e}")
                continue
            finally:
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass

        return None

    def complete_job(
        self,
        job_id: str,
        status: str = "SUCCESS",
        result_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time_sec: float = 0.0,
    ) -> ColabJobResult:
        """
        Colab worker helper: Completes an active job, writes outbox result, and cleans active.
        """
        now = time.time()
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

        result = ColabJobResult(
            job_id=job_id,
            status=status,
            completed_at=now,
            iso_time=iso,
            result_data=result_data or {},
            error=error,
            execution_time_sec=execution_time_sec,
        )

        outbox_file = self.outbox_dir / f"result_{job_id}.json"
        temp_file = self.outbox_dir / f".tmp_result_{job_id}.json"

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        temp_file.replace(outbox_file)

        # Clean active or inbox markers if they still exist
        for d in (self.active_dir, self.inbox_dir):
            for candidate in (d / f"task_{job_id}.json", d / f"{job_id}.json"):
                if candidate.exists():
                    try:
                        candidate.unlink()
                    except OSError:
                        pass

        logger.info(f"[ColabBridge] Completed job {job_id} with status {status}")
        return result

    def update_keepalive(
        self,
        worker_id: str = "colab_gpu_worker",
        gpu_info: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Colab worker heartbeat helper: Updates keepalive.json with current timestamp.
        """
        now = time.time()
        payload = {
            "worker_id": worker_id,
            "timestamp": now,
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "status": "ALIVE",
            "gpu_info": gpu_info or {},
        }
        temp_file = self.root / ".tmp_keepalive.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.keepalive_file)
        return now

    def get_keepalive_status(self, timeout_seconds: float = 120.0) -> Dict[str, Any]:
        """
        Inspects worker liveness from keepalive.json.
        """
        if not self.keepalive_file.exists():
            return {
                "alive": False,
                "reason": "keepalive_file_missing",
                "last_beat": 0.0,
                "age_seconds": -1.0,
                "worker_id": None,
            }

        try:
            with open(self.keepalive_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_beat = data.get("timestamp", 0.0)
            age = time.time() - last_beat
            is_alive = 0.0 <= age <= timeout_seconds
            return {
                "alive": is_alive,
                "reason": "OK" if is_alive else f"heartbeat_expired_{age:.1f}s",
                "last_beat": last_beat,
                "age_seconds": round(age, 2),
                "worker_id": data.get("worker_id"),
                "status": data.get("status", "UNKNOWN"),
                "gpu_info": data.get("gpu_info", {}),
            }
        except (json.JSONDecodeError, OSError) as e:
            return {
                "alive": False,
                "reason": f"error_reading_keepalive: {e}",
                "last_beat": 0.0,
                "age_seconds": -1.0,
                "worker_id": None,
            }

    def list_pending_jobs(self) -> List[str]:
        """Lists job IDs currently waiting in inbox."""
        if not self.inbox_dir.exists():
            return []
        jobs = []
        for p in self.inbox_dir.glob("*.json"):
            if not p.name.startswith(".tmp"):
                stem = p.stem.replace("task_", "")
                jobs.append(stem)
        return sorted(jobs)

    def list_active_jobs(self) -> List[str]:
        """Lists job IDs currently active."""
        if not self.active_dir.exists():
            return []
        jobs = []
        for p in self.active_dir.glob("*.json"):
            if not p.name.startswith(".tmp"):
                stem = p.stem.replace("task_", "")
                jobs.append(stem)
        return sorted(jobs)

    def list_completed_jobs(self) -> List[str]:
        """Lists job IDs completed in outbox."""
        if not self.outbox_dir.exists():
            return []
        jobs = []
        for p in self.outbox_dir.glob("*.json"):
            if not p.name.startswith(".tmp"):
                stem = p.stem.replace("result_", "").replace("task_", "")
                jobs.append(stem)
        return sorted(jobs)
