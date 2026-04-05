"""
Agentic - Signal Lattice
========================
The reactive backbone of the Reactive Cortex Architecture (RCA).

Unlike a simple pub-sub bus, the Signal Lattice supports:
- Typed signals with structured payloads
- Signal transforms: signals can be mapped/filtered into new signals
- Lattice junctions: merge multiple signal streams into one
- Async-first delivery with thread-safe synchronous fallback

Design philosophy:
  Signals are first-class values. Every state change in Agentic
  is expressed as a typed signal flowing through the lattice.
  Components never call each other directly – they emit signals
  and react to signals, keeping coupling minimal.
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine

from utils.logger import build_logger

log = build_logger("agentic.signal_lattice")


# ---------------------------------------------------------------------------
# Signal type registry
# ---------------------------------------------------------------------------

class SigKind(Enum):
    # Lifecycle
    APP_READY          = auto()
    APP_CLOSING        = auto()
    # User interaction
    USER_INPUT         = auto()
    # Cortex lifecycle
    DELIBERATION_START = auto()
    DELIBERATION_END   = auto()
    REACT_ITERATION    = auto()   # emitted after each ReAct tool-use round-trip
    # Model interaction
    MODEL_STREAM_TOKEN = auto()
    MODEL_STREAM_DONE  = auto()
    MODEL_ERROR        = auto()
    # Task management
    TASK_SPAWNED       = auto()
    TASK_PROGRESS      = auto()
    TASK_COMPLETED     = auto()
    TASK_FAILED        = auto()
    TASK_CANCELLED     = auto()
    # Skill execution
    SKILL_INVOKED      = auto()
    SKILL_RESULT       = auto()
    SKILL_ERROR        = auto()
    # Memory
    MEMORY_WRITE       = auto()
    MEMORY_CRYSTALLIZE = auto()
    # Settings
    CONFIG_CHANGED     = auto()
    # Generic
    NOTIFICATION       = auto()
    ERROR              = auto()


# ---------------------------------------------------------------------------
# Signal dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Signal:
    kind: SigKind
    payload: Any
    source: str = "unknown"
    sig_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    ts: float = field(default_factory=time.monotonic)

    def derive(self, kind: SigKind, payload: Any, source: str = "") -> "Signal":
        """Create a related signal carrying a transformed payload."""
        return Signal(kind=kind, payload=payload, source=source or self.source)


# ---------------------------------------------------------------------------
# Handler types
# ---------------------------------------------------------------------------

SyncHandler  = Callable[[Signal], None]
AsyncHandler = Callable[[Signal], Coroutine[Any, Any, None]]
AnyHandler   = SyncHandler | AsyncHandler


# ---------------------------------------------------------------------------
# Junction: merges multiple SigKinds into a single subscription
# ---------------------------------------------------------------------------

@dataclass
class Junction:
    kinds: frozenset[SigKind]
    handler: AnyHandler
    label: str = ""


# ---------------------------------------------------------------------------
# Signal Lattice
# ---------------------------------------------------------------------------

class SignalLattice:
    """
    Central reactive event mesh for Agentic.

    Signals flow from producers to consumers through the lattice.
    Each lattice runs with an optional asyncio event loop for async delivery.
    When no loop is available, sync handlers are called in-band.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # kind → list of handlers
        self._sync_table: dict[SigKind, list[SyncHandler]] = defaultdict(list)
        self._async_table: dict[SigKind, list[AsyncHandler]] = defaultdict(list)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._junctions: list[Junction] = []

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Attach an asyncio loop so async handlers can be scheduled."""
        self._loop = loop

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def on(self, kind: SigKind, handler: AnyHandler) -> "SignalLattice":
        """Subscribe handler to a specific signal kind. Returns self for chaining."""
        with self._lock:
            if asyncio.iscoroutinefunction(handler):
                self._async_table[kind].append(handler)  # type: ignore[arg-type]
            else:
                self._sync_table[kind].append(handler)  # type: ignore[arg-type]
        return self

    def junction(self, *kinds: SigKind, handler: AnyHandler, label: str = "") -> None:
        """Subscribe one handler to multiple signal kinds at once."""
        j = Junction(frozenset(kinds), handler, label)
        with self._lock:
            self._junctions.append(j)
        for k in kinds:
            self.on(k, handler)

    def off(self, kind: SigKind, handler: AnyHandler) -> None:
        """Unsubscribe a handler from a specific signal kind."""
        with self._lock:
            tbl = (
                self._async_table
                if asyncio.iscoroutinefunction(handler)
                else self._sync_table
            )
            try:
                tbl[kind].remove(handler)  # type: ignore[arg-type]
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    def emit(self, sig: Signal) -> None:
        """
        Emit a signal to all registered handlers.
        Sync handlers are called immediately.
        Async handlers are scheduled on the attached loop if available,
        otherwise they are skipped with a warning.
        """
        with self._lock:
            sync_handlers  = list(self._sync_table.get(sig.kind, []))
            async_handlers = list(self._async_table.get(sig.kind, []))

        for h in sync_handlers:
            try:
                h(sig)
            except Exception as exc:
                log.exception("Sync handler %s raised: %s", h, exc)

        if async_handlers:
            if self._loop and self._loop.is_running():
                for ah in async_handlers:
                    asyncio.run_coroutine_threadsafe(ah(sig), self._loop)
            else:
                log.debug(
                    "No running loop – async handlers skipped for %s", sig.kind
                )

    def emit_kind(
        self, kind: SigKind, payload: Any, source: str = "lattice"
    ) -> Signal:
        """Convenience: create and emit a signal, returning it."""
        sig = Signal(kind=kind, payload=payload, source=source)
        self.emit(sig)
        return sig

    # ------------------------------------------------------------------
    # Async emission (call from within a running loop)
    # ------------------------------------------------------------------

    async def aemit(self, sig: Signal) -> None:
        """Emit with awaitable async handler dispatch."""
        with self._lock:
            sync_handlers  = list(self._sync_table.get(sig.kind, []))
            async_handlers = list(self._async_table.get(sig.kind, []))

        for h in sync_handlers:
            try:
                h(sig)
            except Exception as exc:
                log.exception("Sync handler %s raised: %s", h, exc)

        if async_handlers:
            coros = [ah(sig) for ah in async_handlers]
            results = await asyncio.gather(*coros, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    log.exception("Async handler raised: %s", r)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

lattice = SignalLattice()
