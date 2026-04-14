"""
Agentic - Main Window (PyQt6)
================================
VS Code / Sarvam-style layout:

  ┌──────────┬──────────────────────────────┬───────────────┐
  │          │                              │               │
  │ Sidebar  │    QStackedWidget            │  Task panel   │
  │ 220 px   │    (Chat / Memory /          │  240 px       │
  │ nav icons│     Settings)                │  (activity)   │
  │          │                              │               │
  └──────────┴──────────────────────────────┴───────────────┘

The sidebar contains icon+label nav buttons.  Clicking a button raises
the corresponding view in the central stack and hides the task panel
on the non-chat views (it is only relevant during chat).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

_ASSET_DIR = Path(__file__).parent.parent / "assets"

# Nav definition: (id, emoji, label)
_NAV_ITEMS = [
    ("chat",     "💬", "Chat"),
    ("memory",   "🧠", "Memory"),
    ("settings", "⚙",  "Settings"),
]


class NavButton(QPushButton):
    """Sidebar navigation button with active/inactive visual states driven by QSS."""

    def __init__(self, icon: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(f"  {icon}  {label}", parent)
        self.setObjectName("NavButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(42)
        self.setActive(False)

    def setActive(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    """
    Application shell: sidebar + central stack + task side panel.

    The actual views (ChatViewQt, MemoryViewQt, SettingsViewQt) and the
    TaskPanelQt are created externally (in pyqt_integrated.py) and
    installed via ``install_views()``.
    """

    closing = pyqtSignal()  # emitted before the window is destroyed

    def __init__(self) -> None:
        super().__init__()
        self._active_nav = "chat"
        self._nav_buttons: dict[str, NavButton] = {}
        self._configure()
        self._build_layout()

    # ------------------------------------------------------------------
    # Window configuration
    # ------------------------------------------------------------------

    def _configure(self) -> None:
        self.setWindowTitle("Agentic")
        self.resize(1320, 820)
        self.setMinimumSize(900, 620)

        icon_path = _ASSET_DIR / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────
        sidebar = QWidget(central)
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 20, 12, 16)
        sb_layout.setSpacing(4)

        # Brand
        brand_wrap = QWidget(sidebar)
        brand_wrap.setStyleSheet("background:transparent;")
        bw_l = QVBoxLayout(brand_wrap)
        bw_l.setContentsMargins(8, 0, 0, 0)
        bw_l.setSpacing(2)

        brand_lbl = QLabel("Agentic", brand_wrap)
        brand_lbl.setObjectName("SidebarBrand")
        brand_lbl.setStyleSheet(
            "color:#e2e8f0; font-size:18px; font-weight:700; "
            "background:transparent; border:none; letter-spacing:-0.3px;"
        )

        sub_lbl = QLabel("AI Agent Workspace", brand_wrap)
        sub_lbl.setObjectName("SidebarSubtitle")

        bw_l.addWidget(brand_lbl)
        bw_l.addWidget(sub_lbl)
        sb_layout.addWidget(brand_wrap)

        # Divider
        div = QFrame(sidebar)
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background:#252840; max-height:1px; border:none; margin:12px 4px;")
        div.setFixedHeight(1)
        sb_layout.addWidget(div)
        sb_layout.addSpacing(4)

        # Nav buttons
        for nav_id, icon, label in _NAV_ITEMS:
            btn = NavButton(icon, label, sidebar)
            btn.clicked.connect(lambda _, nid=nav_id: self.switch_view(nid))
            self._nav_buttons[nav_id] = btn
            sb_layout.addWidget(btn)

        sb_layout.addStretch()

        # Version footer
        div2 = QFrame(sidebar)
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet("background:#252840; max-height:1px; border:none; margin:4px;")
        div2.setFixedHeight(1)
        sb_layout.addWidget(div2)

        ver_lbl = QLabel("Agentic v1.0  ·  Local AI", sidebar)
        ver_lbl.setObjectName("SidebarVersion")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sb_layout.addWidget(ver_lbl)

        h_layout.addWidget(sidebar)

        # ── Central stack ────────────────────────────────────────────
        self._stack = QStackedWidget(central)
        self._stack.setObjectName("MainStack")
        h_layout.addWidget(self._stack, stretch=1)

        # ── Task side panel ───────────────────────────────────────────
        self._task_panel_container = QWidget(central)
        self._task_panel_container.setObjectName("TaskPanelContainer")
        self._task_panel_container.setFixedWidth(240)
        self._task_panel_container.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        tp_layout = QVBoxLayout(self._task_panel_container)
        tp_layout.setContentsMargins(0, 0, 0, 0)
        tp_layout.setSpacing(0)
        self._tp_inner_layout = tp_layout
        h_layout.addWidget(self._task_panel_container)

    # ------------------------------------------------------------------
    # View installation (called from pyqt_integrated.py)
    # ------------------------------------------------------------------

    def install_views(
        self,
        chat_view: QWidget,
        memory_view: QWidget,
        settings_view: QWidget,
        task_panel: QWidget,
    ) -> None:
        """Install the four main views into the window layout."""
        self._view_widgets: dict[str, QWidget] = {
            "chat":     chat_view,
            "memory":   memory_view,
            "settings": settings_view,
        }

        for w in (chat_view, memory_view, settings_view):
            self._stack.addWidget(w)

        # Task panel goes into the right-side container
        task_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._tp_inner_layout.addWidget(task_panel)

        # Activate default view
        self.switch_view("chat")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def switch_view(self, nav_id: str) -> None:
        self._active_nav = nav_id
        widget = self._view_widgets.get(nav_id)
        if widget:
            self._stack.setCurrentWidget(widget)

        for nid, btn in self._nav_buttons.items():
            btn.setActive(nid == nav_id)

        # Show task panel only on chat view (it shows model activity)
        self._task_panel_container.setVisible(nav_id == "chat")

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def closeEvent(self, event: Any) -> None:
        """Emit closing signal so pyqt_integrated.py can shut down Cortex."""
        self.closing.emit()
        event.accept()
