"""
Agentic - Qt Thread Bridge
==========================
Provides a thread-safe bridge between the Signal Lattice (which fires
callbacks from background threads) and the Qt main thread.

The Cortex and its skills run in a dedicated asyncio loop thread.
Qt widgets must only be updated from the main thread.  Emitting a
pyqtSignal from any thread is safe: Qt automatically delivers it as a
QueuedConnection when the emitter and receiver are on different threads,
queuing the slot call onto the receiver's event loop.

Usage
-----
    bridge = QtBridge()
    bridge.connect_to_ui(chat_view, task_panel)

    # Pass as on_token callback to Cortex:
    cortex = Cortex(..., on_token=bridge.emit_token)
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from core.signal_lattice import SigKind, Signal, lattice
from utils.logger import build_logger

log = build_logger("agentic.qt_bridge")


class QtBridge(QObject):
    """
    Exposes Signal Lattice events as pyqtSignals.

    All signals are safe to emit from any thread; Qt ensures delivery
    on the main thread via the event queue.
    """

    # ── Token streaming ──────────────────────────────────────────────
    tokenReceived   = pyqtSignal(str)
    streamFinished  = pyqtSignal()

    # ── System / info messages ───────────────────────────────────────
    systemMessage   = pyqtSignal(str)
    infoMessage     = pyqtSignal(str)

    # ── Status bar ───────────────────────────────────────────────────
    # (text, is_busy)
    statusChanged   = pyqtSignal(str, bool)

    # ── Model loading progress ───────────────────────────────────────
    # Carries the full payload dict
    modelLoading    = pyqtSignal(object)

    # ── Deliberation ─────────────────────────────────────────────────
    deliberationStart  = pyqtSignal()
    deliberationEnd    = pyqtSignal()
    reactIteration     = pyqtSignal(object)   # payload dict
    modelError         = pyqtSignal(str)

    # ── Tasks ────────────────────────────────────────────────────────
    taskSpawned    = pyqtSignal(str, str)   # (fiber_id, label)
    taskProgress   = pyqtSignal(str, float) # (fiber_id, progress 0–1)
    taskCompleted  = pyqtSignal(str)        # fiber_id
    taskFailed     = pyqtSignal(str, str)   # (fiber_id, error)
    taskCancelled  = pyqtSignal(str)        # fiber_id

    # ── Skills ───────────────────────────────────────────────────────
    skillInvoked   = pyqtSignal(str)        # skill name
    skillResult    = pyqtSignal(str)        # skill name
    skillError     = pyqtSignal(str, str)   # (skill, error)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._subscribe()

    # ------------------------------------------------------------------
    # Direct callback — used as on_token for Cortex
    # ------------------------------------------------------------------

    def emit_token(self, token: str) -> None:
        """
        Called by Cortex from the background thread for each streaming token.
        Emitting a pyqtSignal is thread-safe; Qt queues it to the main thread.
        """
        self.tokenReceived.emit(token)

    # ------------------------------------------------------------------
    # Signal Lattice subscriptions
    # ------------------------------------------------------------------

    def _subscribe(self) -> None:
        lattice.on(SigKind.DELIBERATION_START, self._on_deliberation_start)
        lattice.on(SigKind.DELIBERATION_END,   self._on_deliberation_end)
        lattice.on(SigKind.REACT_ITERATION,    self._on_react_iteration)
        lattice.on(SigKind.MODEL_ERROR,        self._on_model_error)
        lattice.on(SigKind.MODEL_LOADING,      self._on_model_loading)
        lattice.on(SigKind.TASK_SPAWNED,       self._on_task_spawned)
        lattice.on(SigKind.TASK_PROGRESS,      self._on_task_progress)
        lattice.on(SigKind.TASK_COMPLETED,     self._on_task_completed)
        lattice.on(SigKind.TASK_FAILED,        self._on_task_failed)
        lattice.on(SigKind.TASK_CANCELLED,     self._on_task_cancelled)
        lattice.on(SigKind.SKILL_INVOKED,      self._on_skill_invoked)
        lattice.on(SigKind.SKILL_RESULT,       self._on_skill_result)
        lattice.on(SigKind.SKILL_ERROR,        self._on_skill_error)

    # ── Lattice handlers (may be called from background thread) ──────

    def _on_deliberation_start(self, sig: Signal) -> None:
        self.deliberationStart.emit()
        self.statusChanged.emit("Working…", True)

    def _on_deliberation_end(self, sig: Signal) -> None:
        self.deliberationEnd.emit()
        self.streamFinished.emit()

    def _on_react_iteration(self, sig: Signal) -> None:
        self.reactIteration.emit(sig.payload)
        iteration   = sig.payload.get("iteration", "?")
        skills_run  = sig.payload.get("skills_run", [])
        skill_names = ", ".join(skills_run) or "none"
        self.statusChanged.emit(
            f"Reasoning… (step {iteration}, tools: {skill_names})", True
        )

    def _on_model_error(self, sig: Signal) -> None:
        error = sig.payload.get("error", "Unknown error")
        self.modelError.emit(error)
        self.streamFinished.emit()

    def _on_model_loading(self, sig: Signal) -> None:
        self.modelLoading.emit(sig.payload)

    def _on_task_spawned(self, sig: Signal) -> None:
        fid   = sig.payload.get("fiber_id", "")
        label = sig.payload.get("label", "")
        self.taskSpawned.emit(fid, label)

    def _on_task_progress(self, sig: Signal) -> None:
        fid  = sig.payload.get("fiber_id", "")
        prog = float(sig.payload.get("progress", 0.0))
        self.taskProgress.emit(fid, prog)

    def _on_task_completed(self, sig: Signal) -> None:
        fid = sig.payload.get("fiber_id", "")
        self.taskCompleted.emit(fid)

    def _on_task_failed(self, sig: Signal) -> None:
        fid = sig.payload.get("fiber_id", "")
        err = str(sig.payload.get("error", ""))
        self.taskFailed.emit(fid, err)

    def _on_task_cancelled(self, sig: Signal) -> None:
        fid = sig.payload.get("fiber_id", "")
        self.taskCancelled.emit(fid)

    def _on_skill_invoked(self, sig: Signal) -> None:
        self.skillInvoked.emit(sig.payload.get("skill", "unknown"))

    def _on_skill_result(self, sig: Signal) -> None:
        self.skillResult.emit(sig.payload.get("skill", "unknown"))

    def _on_skill_error(self, sig: Signal) -> None:
        skill = sig.payload.get("skill", "unknown")
        err   = str(sig.payload.get("error", ""))
        self.skillError.emit(skill, err)
