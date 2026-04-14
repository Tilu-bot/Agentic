"""
Agentic - Task Panel (PyQt6)
==============================
Side panel that shows real-time status of all active TaskFibers and a
scrolling activity feed.  Subscribes to the QtBridge signals (which are
delivered safely on the main thread) rather than directly to the Signal
Lattice.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ui.qt_bridge import QtBridge


class _FiberItem(QWidget):
    """Compact widget rendered inside a QListWidget item for one fiber."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._born = time.monotonic()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 6)
        layout.setSpacing(4)

        header = QWidget(self)
        header.setStyleSheet("background:transparent;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        self._name_lbl = QLabel(label[:64], header)
        self._name_lbl.setStyleSheet(
            "color:#e2e8f0; font-size:13px; font-weight:600; background:transparent;"
        )
        self._name_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._status_lbl = QLabel("running", header)
        self._status_lbl.setStyleSheet(
            "color:#94a3b8; font-size:11px; background:transparent;"
        )

        h_layout.addWidget(self._name_lbl)
        h_layout.addWidget(self._status_lbl)

        self._bar = QProgressBar(self)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(4)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(
            "QProgressBar { background:#252840; border-radius:2px; border:none; } "
            "QProgressBar::chunk { background:#6366f1; border-radius:2px; }"
        )

        self._time_lbl = QLabel("0.0s", self)
        self._time_lbl.setStyleSheet(
            "color:#334155; font-size:11px; background:transparent;"
        )
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(header)
        layout.addWidget(self._bar)
        layout.addWidget(self._time_lbl)

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(500)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start()

    def set_progress(self, value: float) -> None:
        self._bar.setValue(int(value * 100))

    def set_status(self, text: str, colour: str = "#94a3b8") -> None:
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
            f"color:{colour}; font-size:11px; background:transparent;"
        )

    def _tick(self) -> None:
        elapsed = time.monotonic() - self._born
        self._time_lbl.setText(f"{elapsed:.1f}s")


class TaskPanelQt(QWidget):
    """
    Activity side panel.

    Call ``connect_bridge(bridge)`` after construction to wire all signals.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fiber_items: dict[str, QListWidgetItem] = {}
        self._fiber_widgets: dict[str, _FiberItem] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────
        header = QWidget(self)
        header.setObjectName("PanelHeader")
        header.setFixedHeight(48)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)
        hdr_lbl = QLabel("Activity", header)
        hdr_lbl.setStyleSheet(
            "color:#94a3b8; font-size:13px; font-weight:600; "
            "background:transparent; letter-spacing:0.5px;"
        )
        h_layout.addWidget(hdr_lbl)
        h_layout.addStretch()
        root.addWidget(header)

        # ── Active fibers list ────────────────────────────────────────
        fibers_lbl = QLabel("Active tasks", self)
        fibers_lbl.setStyleSheet(
            "color:#334155; font-size:11px; font-weight:600; "
            "background:transparent; padding:8px 16px 2px; letter-spacing:0.4px;"
        )
        root.addWidget(fibers_lbl)

        self._fiber_list = QListWidget(self)
        self._fiber_list.setStyleSheet(
            "QListWidget { background:#0f1117; border:none; outline:none; } "
            "QListWidget::item { border:none; padding:0; } "
            "QListWidget::item:selected { background:transparent; } "
        )
        self._fiber_list.setFixedHeight(200)
        self._fiber_list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        root.addWidget(self._fiber_list)

        # ── Divider ───────────────────────────────────────────────────
        div = QFrame(self)
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background:#252840; max-height:1px; border:none;")
        div.setFixedHeight(1)
        root.addWidget(div)

        # ── Activity feed ─────────────────────────────────────────────
        feed_lbl = QLabel("Event log", self)
        feed_lbl.setStyleSheet(
            "color:#334155; font-size:11px; font-weight:600; "
            "background:transparent; padding:8px 16px 2px; letter-spacing:0.4px;"
        )
        root.addWidget(feed_lbl)

        self._feed = QListWidget(self)
        self._feed.setStyleSheet(
            "QListWidget { background:#0f1117; border:none; outline:none; "
            "font-family:'Cascadia Code','Fira Code','Consolas',monospace; "
            "font-size:11px; } "
            "QListWidget::item { padding:3px 12px; border:none; color:#475569; } "
            "QListWidget::item:selected { background:transparent; color:#94a3b8; } "
        )
        self._feed.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._feed, stretch=1)

    # ------------------------------------------------------------------
    # Bridge wiring (called from pyqt_integrated.py)
    # ------------------------------------------------------------------

    def connect_bridge(self, bridge: "QtBridge") -> None:
        bridge.taskSpawned.connect(self._on_spawned)
        bridge.taskProgress.connect(self._on_progress)
        bridge.taskCompleted.connect(self._on_completed)
        bridge.taskFailed.connect(self._on_failed)
        bridge.taskCancelled.connect(self._on_cancelled)
        bridge.deliberationStart.connect(
            lambda: self._log("▶ Reasoning started")
        )
        bridge.reactIteration.connect(self._on_react_iteration)
        bridge.skillInvoked.connect(
            lambda name: self._log(f"⚙ Skill invoked: {name}")
        )
        bridge.skillResult.connect(
            lambda name: self._log(f"✓ Skill done: {name}")
        )
        bridge.skillError.connect(
            lambda name, err: self._log(f"✗ Skill error: {name} ({err[:50]})", error=True)
        )
        bridge.modelLoading.connect(self._on_model_loading)

    # ------------------------------------------------------------------
    # Signal handlers (main thread)
    # ------------------------------------------------------------------

    def _on_spawned(self, fiber_id: str, label: str) -> None:
        item = QListWidgetItem(self._fiber_list)
        widget = _FiberItem(label)
        item.setSizeHint(widget.sizeHint())
        self._fiber_list.addItem(item)
        self._fiber_list.setItemWidget(item, widget)
        self._fiber_items[fiber_id]   = item
        self._fiber_widgets[fiber_id] = widget
        self._log(f"⬡ Task spawned: {label[:50]}")

    def _on_progress(self, fiber_id: str, progress: float) -> None:
        w = self._fiber_widgets.get(fiber_id)
        if w:
            w.set_progress(progress)

    def _on_completed(self, fiber_id: str) -> None:
        w = self._fiber_widgets.get(fiber_id)
        if w:
            w.set_progress(1.0)
            w.set_status("✓ done", "#10b981")
        self._log("✓ Task completed")
        QTimer.singleShot(4000, lambda: self._remove_fiber(fiber_id))

    def _on_failed(self, fiber_id: str, error: str) -> None:
        w = self._fiber_widgets.get(fiber_id)
        if w:
            w.set_status(f"✗ {error[:40]}", "#ef4444")
        self._log(f"✗ Task failed: {error[:60]}", error=True)

    def _on_cancelled(self, fiber_id: str) -> None:
        w = self._fiber_widgets.get(fiber_id)
        if w:
            w.set_status("cancelled", "#475569")
        self._log("◌ Task cancelled")
        QTimer.singleShot(3000, lambda: self._remove_fiber(fiber_id))

    def _on_react_iteration(self, payload: dict) -> None:
        i     = payload.get("iteration", "?")
        tools = ", ".join(payload.get("skills_run", [])) or "none"
        self._log(f"↺ Step {i}: tools={tools}")

    def _on_model_loading(self, payload: dict) -> None:
        stage = str(payload.get("stage", ""))
        if stage in ("start", "download_start", "tokenizer", "weights", "done", "error"):
            self._log(f"⬡ Model: {stage}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _remove_fiber(self, fiber_id: str) -> None:
        item = self._fiber_items.pop(fiber_id, None)
        self._fiber_widgets.pop(fiber_id, None)
        if item:
            row = self._fiber_list.row(item)
            if row >= 0:
                self._fiber_list.takeItem(row)

    def _log(self, text: str, error: bool = False) -> None:
        ts = time.strftime("%H:%M:%S")
        item = QListWidgetItem(f"[{ts}]  {text}")
        if error:
            item.setForeground(QColor("#ef4444"))
        else:
            item.setForeground(QColor("#475569"))
        self._feed.addItem(item)
        # Cap feed at 300 lines
        while self._feed.count() > 300:
            self._feed.takeItem(0)
        self._feed.scrollToBottom()
