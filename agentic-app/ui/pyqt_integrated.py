"""
Agentic - PyQt6 Integrated Entry Point
========================================
Bootstraps the complete Agentic application with the PyQt6 UI:

  1. Creates QApplication and loads the global QSS stylesheet.
  2. Creates the MainWindow shell.
  3. Initialises the database, session, skills, and Cortex (backend).
  4. Creates all view widgets and wires them into the window.
  5. Connects the QtBridge signals to view slots.
  6. Runs the Qt event loop.

The entire core/ / model/ / skills/ / state/ / utils/ layer is unchanged
from the Tkinter version — only the ui/ layer has been replaced.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# ── PyQt6 imports ────────────────────────────────────────────────────────────
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

# ── Internal imports ─────────────────────────────────────────────────────────
from ui.main_window    import MainWindow
from ui.chat_view_qt   import ChatViewQt
from ui.memory_view_qt import MemoryViewQt
from ui.settings_view_qt import SettingsViewQt
from ui.task_panel_qt  import TaskPanelQt
from ui.qt_bridge      import QtBridge

from core.cortex        import Cortex
from core.skill_registry import skill_registry
from core.signal_lattice import SigKind, lattice
from state.session      import SessionManager
from state.store        import Store
from utils.config       import cfg
from utils.logger       import build_logger

log = build_logger("agentic.pyqt_integrated")

_APP_DIR = Path(__file__).parent.parent
_QSS_PATH = Path(__file__).parent / "style.qss"


# ---------------------------------------------------------------------------
# Application class
# ---------------------------------------------------------------------------

class AgenticQtApp:
    """
    Owns all top-level objects for the lifetime of the process.
    """

    def __init__(self, qt_app: QApplication) -> None:
        self._qt_app      = qt_app
        self._window:      MainWindow | None = None
        self._cortex:      Cortex | None     = None
        self._session_mgr: SessionManager | None = None
        self._store:       Store | None       = None
        self._bridge:      QtBridge | None    = None
        self._tools_count: int                = 0

        self._setup_window()
        self._bootstrap()
        self._wire_signals()
        self._post_boot_message()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self._chat_view     = ChatViewQt()
        self._memory_view   = MemoryViewQt()
        self._settings_view = SettingsViewQt(on_theme_change=self._on_theme_change)
        self._task_panel    = TaskPanelQt()
        self._bridge        = QtBridge()

        self._window = MainWindow()
        self._window.install_views(
            self._chat_view,
            self._memory_view,
            self._settings_view,
            self._task_panel,
        )

        # Connect sidebar ↔ window switch (expose to chat view for "New Chat")
        self._chat_view.new_session_requested.connect(self._new_session)
        self._chat_view.message_submitted.connect(self._on_user_submit)
        self._chat_view.stop_requested.connect(self._on_user_stop)

        # Wire suggestion chips → chat submit
        self._chat_view._web.loadFinished.connect(self._install_suggestion_callback)

    # ------------------------------------------------------------------
    # Backend bootstrap
    # ------------------------------------------------------------------

    def _bootstrap(self) -> None:
        data_dir = cfg.data_dir
        db_path  = data_dir / "agentic.db"

        self._store       = Store(db_path)
        self._session_mgr = SessionManager(self._store)
        restored_id = self._session_mgr.load_most_recent_session()
        if restored_id is None:
            restored_id = self._session_mgr.new_session()

        # Register skills
        from skills.filesystem import register_all as reg_fs
        from skills.web_reader import register_all as reg_web
        from skills.code_runner import register_all as reg_code
        from skills.memory_ops  import register_all as reg_mem
        from skills.doc_reader  import register_all as reg_docs

        reg_fs()
        reg_web()
        reg_code()
        reg_mem(self._session_mgr.memory)
        reg_docs()

        self._tools_count = len(skill_registry.all_specs())

        # Build Cortex — on_token routed through the bridge
        self._cortex = Cortex(
            memory=self._session_mgr.memory,
            registry=skill_registry,
            on_token=self._bridge.emit_token,
        )
        self._cortex.start()

        # Wire memory view's get_memory callback
        self._memory_view._get_memory = (
            lambda: self._session_mgr.memory if self._session_mgr else None
        )

        # Replay persisted conversation turns into the chat view.
        self._chat_view.hydrate_from_fluid(self._session_mgr.memory.fluid_read())

        log.info("Agentic (Qt) bootstrap complete — %d skills registered", self._tools_count)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        b = self._bridge

        # Token streaming
        b.tokenReceived.connect(self._chat_view.push_token)
        b.streamFinished.connect(self._chat_view.finish_streaming)

        # Status
        b.statusChanged.connect(
            lambda text, busy: self._chat_view.set_status(text, busy)
        )

        # System / info messages generated by the bridge itself
        # (error path)
        b.modelError.connect(
            lambda err: (
                self._chat_view.append_info(f"[Model error] {err}"),
                self._chat_view.finish_streaming(),
            )
        )

        # Model loading
        b.modelLoading.connect(self._chat_view.handle_model_loading)

        # Task panel (subscribes to bridge signals internally)
        self._task_panel.connect_bridge(b)

        # Window close → shut down Cortex
        self._window.closeEvent = self._on_close

        # Deliberation start → mark busy
        b.deliberationStart.connect(
            lambda: self._chat_view.set_status("Working…", busy=True)
        )

    # ------------------------------------------------------------------
    # Suggestion chip callback
    # ------------------------------------------------------------------

    def _install_suggestion_callback(self) -> None:
        """
        Install a JS function that forwards chip clicks back to Python.
        We poll a JS variable (_agSuggestion) because QWebChannel isn't
        needed for this simple one-way trigger.
        """
        page = self._chat_view._web.page()
        page.runJavaScript(
            "window._suggestionCallback = function(t) { window._agSuggestion = t; };"
        )

        def _poll_suggestion() -> None:
            if not self._chat_view._streaming:
                page.runJavaScript(
                    "window._agSuggestion || null",
                    lambda val: self._handle_suggestion(val),
                )

        self._suggestion_timer = QTimer()
        self._suggestion_timer.setInterval(300)
        self._suggestion_timer.timeout.connect(_poll_suggestion)
        self._suggestion_timer.start()

    def _handle_suggestion(self, text: str | None) -> None:
        if not text:
            return
        # Clear the JS variable to avoid re-triggering
        self._chat_view._web.page().runJavaScript("window._agSuggestion = null;")
        self._chat_view.submit_suggestion(text)

    # ------------------------------------------------------------------
    # User interaction handlers
    # ------------------------------------------------------------------

    def _on_user_submit(self, text: str, attachments: list[str] | None = None) -> None:
        if self._cortex:
            self._cortex.submit_input(text, attachments)

    def _on_user_stop(self) -> None:
        if self._cortex:
            self._cortex.cancel_current()

    def _new_session(self) -> None:
        assert self._session_mgr is not None and self._cortex is not None
        sid = self._session_mgr.new_session()
        from skills.memory_ops import set_memory_ref
        set_memory_ref(self._session_mgr.memory)
        self._cortex.update_memory(self._session_mgr.memory)
        self._chat_view.clear()
        self._chat_view.append_system("New session started.")
        log.info("New session: %s", sid)

    def _on_theme_change(self, theme_name: str) -> None:
        cfg.set("theme", theme_name)
        self._chat_view.append_info(
            f"Theme changed to '{theme_name}'. "
            "Restart the app to fully apply the new theme."
        )

    # ------------------------------------------------------------------
    # Post-boot welcome message
    # ------------------------------------------------------------------

    def _post_boot_message(self) -> None:
        model_id = cfg.get("model_id", "unknown")
        restored_entries = len(self._session_mgr.memory.fluid_read()) if self._session_mgr else 0
        if restored_entries > 0:
            self._chat_view.append_info(
                f"Restored previous session: {restored_entries} message(s) loaded."
            )
            return
        self._chat_view.append_system(
            "Welcome to Agentic!\n"
            "Powered by the Reactive Cortex Architecture.\n"
            f"Model: {model_id} · Tools: {self._tools_count}\n"
            "The model is downloaded automatically on first use.\n"
            "Go to Settings (⚙) to choose a different model or device."
        )

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _on_close(self, event: object) -> None:
        log.info("Closing Agentic…")
        if hasattr(self, "_suggestion_timer"):
            self._suggestion_timer.stop()
        if self._cortex:
            self._cortex.stop()
        if self._store:
            self._store.close()
        lattice.emit_kind(SigKind.APP_CLOSING, {}, source="app")
        event.accept()  # type: ignore[attr-defined]

    def show(self) -> None:
        assert self._window is not None
        self._window.show()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the Agentic Qt application."""
    import platform

    # High-DPI support
    if platform.system() == "Windows":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    # Qt attribute must be set before creating QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Agentic")
    app.setOrganizationName("Agentic")
    app.setStyle("Fusion")

    # Load QSS stylesheet
    if _QSS_PATH.exists():
        app.setStyleSheet(_QSS_PATH.read_text(encoding="utf-8"))

    # Set default font with cross-platform fallbacks
    default_font = QFont()
    for family in ("Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue", "Arial"):
        default_font.setFamily(family)
        if default_font.exactMatch() or QFontDatabase.hasFamily(family):
            break
    default_font.setPointSize(10)
    app.setFont(default_font)

    agentic = AgenticQtApp(app)
    agentic.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
