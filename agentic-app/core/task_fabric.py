"""
Agentic - Task Fabric
=====================
Parallel task execution mesh based on the Reactive Cortex Architecture.

Key concepts:
  TaskFiber  – a lightweight unit of work with lifecycle management.
  TaskFabric – the mesh that manages fibers: scheduling, concurrency,
               dependency tracking, and cancellation.

Design decisions:
  • Tasks are NOT simple coroutines; they carry rich metadata and can be
    observed, paused, or cancelled by the user or other tasks.
  • Dependency edges allow independent fibers to run in parallel while
    enforcing order where required.
  • The fabric emits signals on every lifecycle transition so the UI can
    reflect real-time status without polling.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine

from core.signal_lattice import SigKind, Signal, lattice
from utils.logger import build_logger

log = build_logger("agentic.task_fabric")


# ---------------------------------------------------------------------------
# Fiber status
# ---------------------------------------------------------------------------

class FiberStatus(Enum):
    PENDING   = auto()
    RUNNING   = auto()
    PAUSED    = auto()
    DONE      = auto()
    FAILED    = auto()
    CANCELLED = auto()

    def is_terminal(self) -> bool:
        return self in (
            FiberStatus.DONE, FiberStatus.FAILED, FiberStatus.CANCELLED
        )


# ---------------------------------------------------------------------------
# TaskFiber
# ---------------------------------------------------------------------------

FiberFn = Callable[["TaskFiber"], Coroutine[Any, Any, Any]]


@dataclass
class TaskFiber:
    """
    A unit of work in the Task Fabric.

    Attributes:
        fiber_id: Unique identifier.
        label:    Human-readable description.
        fn:       Async callable that receives this fiber and returns a result.
        deps:     Set of fiber_ids that must complete before this fiber starts.
        priority: Lower = higher priority (0 = urgent).
        tags:     Arbitrary labels for filtering.
    """
    label: str
    fn: FiberFn
    deps: frozenset[str] = field(default_factory=frozenset)
    priority: int = 5
    tags: list[str] = field(default_factory=list)
    # Optional wall-clock timeout (seconds).  When > 0, the fiber is
    # automatically cancelled if it has not completed within this duration.
    # 0 means no timeout (unlimited).  The default 0 is safe because the
    # SkillRegistry already enforces skill_timeout_s via asyncio.wait_for.
    timeout_s: float = 0.0

    fiber_id: str       = field(default_factory=lambda: uuid.uuid4().hex[:10])
    status: FiberStatus = field(default=FiberStatus.PENDING, init=False)
    result: Any         = field(default=None, init=False)
    error: str          = field(default="", init=False)
    created_at: float   = field(default_factory=time.monotonic, init=False)
    started_at: float   = field(default=0.0, init=False)
    ended_at: float     = field(default=0.0, init=False)
    progress: float     = field(default=0.0, init=False)   # 0.0 – 1.0
    _cancel_evt: asyncio.Event = field(
        default_factory=asyncio.Event, init=False, repr=False
    )

    def request_cancel(self) -> None:
        self._cancel_evt.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_evt.is_set()

    @property
    def elapsed(self) -> float:
        if self.started_at == 0.0:
            return 0.0
        end = self.ended_at if self.ended_at > 0.0 else time.monotonic()
        return end - self.started_at

    def set_progress(self, value: float) -> None:
        self.progress = max(0.0, min(1.0, value))
        lattice.emit_kind(
            SigKind.TASK_PROGRESS,
            {"fiber_id": self.fiber_id, "progress": self.progress, "label": self.label},
            source="task_fabric",
        )


# ---------------------------------------------------------------------------
# Task Fabric
# ---------------------------------------------------------------------------

class TaskFabric:
    """
    The execution mesh that manages TaskFibers.

    The fabric maintains a dependency graph; independent fibers execute
    in parallel up to max_concurrent. When a fiber completes, the fabric
    automatically promotes waiting fibers whose dependencies are satisfied.
    """

    def __init__(self, max_concurrent: int = 4) -> None:
        self._max_concurrent = max_concurrent
        self._fibers: dict[str, TaskFiber] = {}
        self._lock = asyncio.Lock()
        self._running: set[str] = set()
        self._scheduler_task: asyncio.Task | None = None  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Fiber management
    # ------------------------------------------------------------------

    def add_fiber(self, fiber: TaskFiber) -> str:
        """Register a fiber. Returns its fiber_id."""
        self._fibers[fiber.fiber_id] = fiber
        lattice.emit_kind(
            SigKind.TASK_SPAWNED,
            {
                "fiber_id": fiber.fiber_id,
                "label": fiber.label,
                "priority": fiber.priority,
                "tags": fiber.tags,
            },
            source="task_fabric",
        )
        log.debug("Fiber added: %s [%s]", fiber.fiber_id, fiber.label)
        return fiber.fiber_id

    def cancel_fiber(self, fiber_id: str) -> bool:
        fiber = self._fibers.get(fiber_id)
        if fiber and not fiber.status.is_terminal():
            fiber.request_cancel()
            return True
        return False

    def get_fiber(self, fiber_id: str) -> TaskFiber | None:
        return self._fibers.get(fiber_id)

    def all_fibers(self) -> list[TaskFiber]:
        return list(self._fibers.values())

    def active_fibers(self) -> list[TaskFiber]:
        return [f for f in self._fibers.values() if not f.status.is_terminal()]

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    async def run_until_empty(self) -> None:
        """
        Drive the fabric until all fibers reach terminal states.
        Call this from within the asyncio event loop.
        """
        while True:
            promoted = await self._promote_ready()
            if not promoted and not self._running:
                pending = [
                    f for f in self._fibers.values()
                    if f.status == FiberStatus.PENDING
                ]
                if not pending:
                    break
            await asyncio.sleep(0.05)

    async def _promote_ready(self) -> bool:
        """
        Check for fibers whose deps are satisfied and concurrency slot is free.
        Returns True if any fiber was promoted to RUNNING.
        """
        promoted = False
        async with self._lock:
            slots_free = self._max_concurrent - len(self._running)
            if slots_free <= 0:
                return False

            candidates = [
                f for f in self._fibers.values()
                if f.status == FiberStatus.PENDING
                and self._deps_satisfied(f)
            ]
            # sort by priority ascending (lower = higher priority)
            candidates.sort(key=lambda f: (f.priority, f.created_at))

            for fiber in candidates[:slots_free]:
                fiber.status = FiberStatus.RUNNING
                fiber.started_at = time.monotonic()
                self._running.add(fiber.fiber_id)
                asyncio.create_task(self._run_fiber(fiber))
                promoted = True

        return promoted

    def _deps_satisfied(self, fiber: TaskFiber) -> bool:
        for dep_id in fiber.deps:
            dep = self._fibers.get(dep_id)
            if dep is None or dep.status != FiberStatus.DONE:
                return False
        return True

    async def _run_fiber(self, fiber: TaskFiber) -> None:
        log.info("Fiber START: %s [%s]", fiber.fiber_id, fiber.label)
        try:
            if fiber.is_cancelled:
                fiber.status = FiberStatus.CANCELLED
                return
            coro = fiber.fn(fiber)
            if fiber.timeout_s > 0:
                result = await asyncio.wait_for(coro, timeout=fiber.timeout_s)
            else:
                result = await coro
            if fiber.is_cancelled:
                fiber.status = FiberStatus.CANCELLED
                lattice.emit_kind(
                    SigKind.TASK_CANCELLED,
                    {"fiber_id": fiber.fiber_id, "label": fiber.label},
                    source="task_fabric",
                )
            else:
                fiber.result = result
                fiber.status = FiberStatus.DONE
                fiber.progress = 1.0
                lattice.emit_kind(
                    SigKind.TASK_COMPLETED,
                    {
                        "fiber_id": fiber.fiber_id,
                        "label": fiber.label,
                        "result": result,
                    },
                    source="task_fabric",
                )
                log.info("Fiber DONE: %s [%.2fs]", fiber.fiber_id, fiber.elapsed)
        except asyncio.CancelledError:
            fiber.status = FiberStatus.CANCELLED
            lattice.emit_kind(
                SigKind.TASK_CANCELLED,
                {"fiber_id": fiber.fiber_id, "label": fiber.label},
                source="task_fabric",
            )
        except asyncio.TimeoutError:
            # Raised by asyncio.wait_for when timeout_s is exceeded.
            timeout_msg = f"Timed out after {fiber.timeout_s}s"
            fiber.error  = timeout_msg
            fiber.status = FiberStatus.FAILED
            lattice.emit_kind(
                SigKind.TASK_FAILED,
                {
                    "fiber_id": fiber.fiber_id,
                    "label": fiber.label,
                    "error": timeout_msg,
                },
                source="task_fabric",
            )
            log.warning("Fiber TIMEOUT %s [%s]: %s", fiber.fiber_id, fiber.label, timeout_msg)
        except Exception as exc:
            fiber.error = str(exc)
            fiber.status = FiberStatus.FAILED
            lattice.emit_kind(
                SigKind.TASK_FAILED,
                {
                    "fiber_id": fiber.fiber_id,
                    "label": fiber.label,
                    "error": str(exc),
                },
                source="task_fabric",
            )
            log.exception("Fiber FAILED %s: %s", fiber.fiber_id, exc)
        finally:
            fiber.ended_at = time.monotonic()
            async with self._lock:
                self._running.discard(fiber.fiber_id)
