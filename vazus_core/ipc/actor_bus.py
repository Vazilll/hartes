"""
vazus_core.ipc.actor_bus
========================
Typed Multi-Agent Actor Model Message Bus & Dynamic DAG Pipeline.
Implements:
1. Pure Actor Model with isolated state and asynchronous typed mailboxes.
2. Zero shared memory mutations between agents — immutable typed ActorMessages.
3. Dynamic DAG Pipeline Orchestration with Map-Reduce hypothesis parallelization.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("vazus_core.ipc.actor_bus")


@dataclass(frozen=True)
class ActorMessage:
    """Immutable, strongly typed message passed across the Actor Bus."""
    message_id: str
    sender: str
    recipient: str
    msg_type: str  # "TASK", "HYPOTHESIS", "VERDICT", "REDUCE", "ACK", "ERROR"
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""

    @classmethod
    def create(
        cls,
        sender: str,
        recipient: str,
        msg_type: str,
        payload: Dict[str, Any],
        correlation_id: str = "",
    ) -> "ActorMessage":
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        return cls(
            message_id=msg_id,
            sender=sender,
            recipient=recipient,
            msg_type=msg_type,
            payload=copy.deepcopy(payload),
            timestamp=time.time(),
            correlation_id=correlation_id or msg_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts message into structured dictionary."""
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "msg_type": self.msg_type,
            "payload": copy.deepcopy(self.payload),
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ActorMessage":
        """Reconstructs message from structured dictionary."""
        return cls(
            message_id=d["message_id"],
            sender=d["sender"],
            recipient=d["recipient"],
            msg_type=d["msg_type"],
            payload=copy.deepcopy(d.get("payload", {})),
            timestamp=float(d.get("timestamp", time.time())),
            correlation_id=d.get("correlation_id", ""),
        )

    def to_bytes(self) -> bytes:
        """Serializes message into UTF-8 JSON bytes (typed schema framing)."""
        import json
        return json.dumps(self.to_dict()).encode("utf-8")

    @classmethod
    def from_bytes(cls, b: bytes) -> "ActorMessage":
        """Deserializes message from typed bytes."""
        import json
        return cls.from_dict(json.loads(b.decode("utf-8")))


class BaseActor:
    """
    Subagent Actor with private, isolated state and a typed asynchronous mailbox.
    """

    def __init__(self, actor_id: str, bus: Optional["ActorBus"] = None):
        self.actor_id = actor_id
        self.bus = bus
        self.mailbox: asyncio.Queue[ActorMessage] = asyncio.Queue()
        self._private_state: Dict[str, Any] = {}
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self.processed_count: int = 0

    async def receive(self, message: ActorMessage) -> Optional[ActorMessage]:
        """User-defined message handler. Must NOT mutate external state.

        Default implementation logs and acknowledges the message. Subclasses override
        to implement custom actor processing logic.
        """
        logger.debug("BaseActor '%s' received message: %s", self.actor_id, message.message_id)
        return None

    async def start(self) -> None:
        """Starts the actor's internal mailbox processing loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stops the actor loop cleanly."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        while self._running:
            try:
                msg = await self.mailbox.get()
                self.processed_count += 1
                try:
                    response_msg = await self.receive(msg)
                    if response_msg is not None and self.bus is not None:
                        await self.bus.send(response_msg)
                except Exception as exc:
                    logger.error("Actor '%s' failed processing message %s: %s", self.actor_id, msg.message_id, exc)
                finally:
                    self.mailbox.task_done()
            except asyncio.CancelledError:
                break


class ActorBus:
    """
    Central Actor Message Bus coordinating agent dispatch and routing.
    """

    def __init__(self):
        self._actors: Dict[str, BaseActor] = {}
        self._message_history: List[ActorMessage] = []
        self._lock = asyncio.Lock()

    def register_actor(self, actor: BaseActor) -> None:
        """Registers an actor on the bus."""
        self._actors[actor.actor_id] = actor
        if actor.bus is None:
            actor.bus = self

    def unregister_actor(self, actor_id: str) -> None:
        """Removes an actor from the bus."""
        self._actors.pop(actor_id, None)

    async def send(self, message: ActorMessage) -> bool:
        """Delivers an immutable message to the recipient's mailbox."""
        recipient = self._actors.get(message.recipient)
        if not recipient:
            logger.warning("ActorBus: recipient '%s' not registered", message.recipient)
            return False

        await recipient.mailbox.put(message)
        async with self._lock:
            self._message_history.append(message)
            if len(self._message_history) > 1000:
                self._message_history.pop(0)
        return True

    async def broadcast(self, sender: str, msg_type: str, payload: Dict[str, Any]) -> int:
        """Broadcasts an immutable message to all other registered actors."""
        count = 0
        actors_snapshot = list(self._actors.items())
        for act_id, act in actors_snapshot:
            if act_id != sender:
                msg = ActorMessage.create(sender, act_id, msg_type, payload)
                await act.mailbox.put(msg)
                async with self._lock:
                    self._message_history.append(msg)
                    if len(self._message_history) > 1000:
                        self._message_history.pop(0)
                count += 1
        return count


@dataclass
class DAGStage:
    """A stage in the dynamic DAG pipeline."""
    stage_id: str
    dependencies: List[str]  # IDs of predecessor stages
    worker_actors: List[str]  # Actor IDs executing tasks in this stage (Map phase)
    map_task_fn: Callable[[Dict[str, Any], str], Dict[str, Any]]
    reduce_fn: Optional[Callable[[List[Dict[str, Any]]], Dict[str, Any]]] = None


class DynamicDAGPipeline:
    """
    Dynamic Directed Acyclic Graph (DAG) Pipeline Orchestrator with Map-Reduce.
    Executes independent subagent stages concurrently and deterministically merges hypotheses.
    """

    def __init__(self, bus: Optional[ActorBus] = None):
        self.bus = bus or ActorBus()
        self.stages: Dict[str, DAGStage] = {}

    def add_stage(
        self,
        stage_id: str,
        dependencies: Optional[List[str]] = None,
        worker_actors: Optional[List[str]] = None,
        map_task_fn: Optional[Callable[[Dict[str, Any], str], Dict[str, Any]]] = None,
        reduce_fn: Optional[Callable[[List[Dict[str, Any]]], Dict[str, Any]]] = None,
    ) -> None:
        """Registers a computational stage into the DAG."""
        self.stages[stage_id] = DAGStage(
            stage_id=stage_id,
            dependencies=dependencies or [],
            worker_actors=worker_actors or ["default_worker"],
            map_task_fn=map_task_fn or (lambda inp, worker: {"worker": worker, "result": inp}),
            reduce_fn=reduce_fn or (lambda results: {"aggregated": results, "count": len(results)}),
        )

    async def execute(self, initial_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the DAG respecting topological dependency order.
        Within each stage, performs concurrent Map execution across worker actors
        followed by deterministic Reduce aggregation.
        """
        for sid, st in self.stages.items():
            for dep in st.dependencies:
                if dep not in self.stages:
                    raise ValueError(f"Stage '{sid}' depends on non-existent stage '{dep}'")

        stage_results: Dict[str, Dict[str, Any]] = {}
        executed: Set[str] = set()

        # Simple topological loop
        while len(executed) < len(self.stages):
            runnable = [
                sid for sid, st in self.stages.items()
                if sid not in executed and all(dep in executed for dep in st.dependencies)
            ]

            if not runnable:
                raise ValueError("Cyclic dependency or unresolvable stage in DAG pipeline")

            # Run all ready stages concurrently
            stage_tasks = [self._execute_single_stage(self.stages[sid], stage_results, initial_payload) for sid in runnable]
            outputs = await asyncio.gather(*stage_tasks)

            for sid, out in zip(runnable, outputs):
                stage_results[sid] = out
                executed.add(sid)

        return stage_results

    async def _execute_single_stage(
        self,
        stage: DAGStage,
        prior_results: Dict[str, Dict[str, Any]],
        initial_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Executes the Map and Reduce phases for a single stage."""
        import inspect

        # 1. Prepare stage input from dependencies
        stage_input = copy.deepcopy(initial_payload)
        for dep in stage.dependencies:
            stage_input[f"dep_{dep}"] = prior_results.get(dep, {})

        # 2. Map phase: parallel evaluation across workers (sync or async)
        async def _run_worker(worker_id: str) -> Dict[str, Any]:
            if inspect.iscoroutinefunction(stage.map_task_fn):
                return await stage.map_task_fn(stage_input, worker_id)
            else:
                return await asyncio.to_thread(stage.map_task_fn, stage_input, worker_id)

        map_tasks = [_run_worker(w) for w in stage.worker_actors]
        worker_outputs = await asyncio.gather(*map_tasks)

        # 3. Reduce phase: aggregate worker hypotheses (sync or async)
        if stage.reduce_fn:
            if inspect.iscoroutinefunction(stage.reduce_fn):
                reduced = await stage.reduce_fn(list(worker_outputs))
            else:
                reduced = stage.reduce_fn(list(worker_outputs))
        else:
            reduced = {"outputs": list(worker_outputs)}

        return reduced
