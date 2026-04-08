"""
Agentic - Memory View (PyQt6)
================================
Browse the three Memory Lattice layers:
  • Fluid   — in-session message turns
  • Bedrock — persisted facts (long-term)
  • Crystal — episodic summaries

Read-only panel; writes happen via the model or Memory Ops skills.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class MemoryViewQt(QWidget):
    """Memory lattice browser panel."""

    def __init__(
        self,
        parent: QWidget | None = None,
        get_memory: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_memory = get_memory or (lambda: None)
        self._active_tab = "bedrock"
        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────
        top_bar = QWidget(self)
        top_bar.setStyleSheet("background:#1a1d27; border-bottom:1px solid #252840;")
        top_bar.setFixedHeight(64)
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(24, 0, 20, 0)

        title_wrap = QWidget(top_bar)
        title_wrap.setStyleSheet("background:transparent;")
        tw_l = QVBoxLayout(title_wrap)
        tw_l.setContentsMargins(0, 0, 0, 0)
        tw_l.setSpacing(1)
        lbl = QLabel("Memory Lattice", title_wrap)
        lbl.setObjectName("SectionTitle")
        lbl.setStyleSheet("font-size:18px; font-weight:700; color:#e2e8f0; background:transparent;")
        sub = QLabel("Fluid session · Bedrock facts · Crystal episodes.", title_wrap)
        sub.setObjectName("SectionSubtitle")
        tw_l.addWidget(lbl)
        tw_l.addWidget(sub)

        refresh_btn = QPushButton("⟳  Refresh", top_bar)
        refresh_btn.setObjectName("GhostButton")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setFixedHeight(34)
        refresh_btn.clicked.connect(self._refresh)

        tb_layout.addWidget(title_wrap, stretch=1)
        tb_layout.addWidget(refresh_btn)
        root.addWidget(top_bar)

        # ── Tab strip ────────────────────────────────────────────────
        tab_bar = QWidget(self)
        tab_bar.setStyleSheet("background:#1a1d27; border-bottom:1px solid #252840;")
        tab_bar.setFixedHeight(44)
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(20, 0, 20, 0)
        tab_layout.setSpacing(0)

        self._tab_buttons: dict[str, QPushButton] = {}
        for key, label in (
            ("fluid",   "Session  (Fluid)"),
            ("bedrock", "Long-Term Facts  (Bedrock)"),
            ("crystal", "Episode Log  (Crystal)"),
        ):
            btn = QPushButton(label, tab_bar)
            btn.setCheckable(True)
            btn.setChecked(key == self._active_tab)
            btn.setStyleSheet(self._tab_style(key == self._active_tab))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(44)
            btn.clicked.connect(lambda _, k=key: self._switch_tab(k))
            tab_layout.addWidget(btn)
            self._tab_buttons[key] = btn

        tab_layout.addStretch()
        root.addWidget(tab_bar)

        # ── Content area ──────────────────────────────────────────────
        content = QWidget(self)
        content.setStyleSheet("background:#0f1117;")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(24, 20, 24, 20)
        c_layout.setSpacing(12)

        # Stats row
        self._stats_lbl = QLabel("", content)
        self._stats_lbl.setObjectName("FormLabel")

        # Table
        self._table = QTableWidget(content)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        c_layout.addWidget(self._stats_lbl)
        c_layout.addWidget(self._table, stretch=1)
        root.addWidget(content, stretch=1)

    # ------------------------------------------------------------------
    # Tab logic
    # ------------------------------------------------------------------

    def _tab_style(self, active: bool) -> str:
        if active:
            return (
                "QPushButton { background:transparent; color:#818cf8; "
                "border:none; border-bottom:2px solid #6366f1; "
                "padding:0 16px; font-size:13px; font-weight:600; }"
            )
        return (
            "QPushButton { background:transparent; color:#64748b; "
            "border:none; border-bottom:2px solid transparent; "
            "padding:0 16px; font-size:13px; }"
            "QPushButton:hover { color:#e2e8f0; }"
        )

    def _switch_tab(self, key: str) -> None:
        self._active_tab = key
        for k, btn in self._tab_buttons.items():
            btn.setStyleSheet(self._tab_style(k == key))
        self._refresh()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        mem = self._get_memory()
        if mem is None:
            self._populate_empty("No active session.")
            return

        if self._active_tab == "fluid":
            self._load_fluid(mem)
        elif self._active_tab == "bedrock":
            self._load_bedrock(mem)
        else:
            self._load_crystal(mem)

    def _populate_empty(self, msg: str) -> None:
        self._table.clear()
        self._table.setColumnCount(1)
        self._table.setRowCount(1)
        self._table.setHorizontalHeaderLabels(["Status"])
        item = QTableWidgetItem(msg)
        item.setForeground(Qt.GlobalColor.gray)
        self._table.setItem(0, 0, item)
        self._stats_lbl.setText("")

    def _load_fluid(self, mem: Any) -> None:
        entries = mem.fluid_read()
        self._stats_lbl.setText(f"{len(entries)} message(s) in this session")
        self._table.clear()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Time", "Role", "Content"])
        self._table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            ts_str = time.strftime("%H:%M:%S", time.localtime(e.ts))
            self._set_item(row, 0, ts_str,  color="#64748b", width=70)
            self._set_item(row, 1, e.role.upper(), color="#818cf8", width=90)
            preview = e.text.replace("\n", " ")[:200]
            self._set_item(row, 2, preview)
            self._table.setRowHeight(row, 36)

        self._table.setColumnWidth(0, 80)
        self._table.setColumnWidth(1, 100)

    def _load_bedrock(self, mem: Any) -> None:
        facts = mem.bedrock_query(limit=100)
        self._stats_lbl.setText(f"{len(facts)} fact(s) stored")
        self._table.clear()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Category", "Confidence", "Fact"])
        self._table.setRowCount(len(facts))
        for row, f in enumerate(facts):
            self._set_item(row, 0, f.category,        color="#f59e0b", width=120)
            self._set_item(row, 1, f"{f.confidence:.2f}", color="#64748b", width=80)
            self._set_item(row, 2, f.text)
            self._table.setRowHeight(row, 36)

        self._table.setColumnWidth(0, 130)
        self._table.setColumnWidth(1, 90)

    def _load_crystal(self, mem: Any) -> None:
        records = mem.crystal_query(limit=50)
        records_sorted = sorted(records, key=lambda r: r.ts)
        self._stats_lbl.setText(f"{len(records_sorted)} episode(s) recorded")
        self._table.clear()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Date/Time", "Tags", "Summary"])
        self._table.setRowCount(len(records_sorted))
        for row, r in enumerate(records_sorted):
            ts_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.ts))
            tags   = ", ".join(r.tags) if r.tags else "—"
            self._set_item(row, 0, ts_str,      color="#64748b", width=140)
            self._set_item(row, 1, tags,         color="#818cf8", width=140)
            self._set_item(row, 2, r.summary)
            self._table.setRowHeight(row, 36)

        self._table.setColumnWidth(0, 150)
        self._table.setColumnWidth(1, 150)

    def _set_item(
        self,
        row: int,
        col: int,
        text: str,
        color: str | None = None,
        width: int | None = None,
    ) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        if color:
            from PyQt6.QtGui import QColor
            item.setForeground(QColor(color))
        self._table.setItem(row, col, item)
        if width:
            self._table.setColumnWidth(col, width)
