"""
Agentic - Main Application Window
===================================
Orchestrates the full UI:
  • Sidebar navigation (Chat, Tasks, Memory, Settings)
  • Dynamic centre panel that swaps between views
  • Right task panel (always visible, collapsible)
  • Wires Signal Lattice → UI callbacks
  • Bootstraps the Cortex with all skills registered

Window title: Agentic
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from typing import Any

from core.cortex import Cortex
from core.signal_lattice import SigKind, lattice
from state.session import SessionManager
from state.store import Store
from ui.chat_view import ChatView
from ui.components import AgFrame, AgLabel, NavItem
from ui.memory_view import MemoryView
from ui.settings_view import SettingsView
from ui.task_panel import TaskPanel
from ui.theme import FONTS, M, Palette, palette
from utils.config import cfg
from utils.logger import build_logger

log = build_logger("agentic.app")


class AgenticApp(tk.Tk):
    """
    Root window of the Agentic desktop application.
    Layout:
      ┌──────────┬──────────────────────┬─────────────┐
      │ Sidebar  │   Main panel         │  Task panel │
      │ (nav)    │   (chat/memory/etc)  │  (fibers)   │
      └──────────┴──────────────────────┴─────────────┘
    """

    def __init__(self) -> None:
        super().__init__()
        self._pal: Palette = palette(cfg.get("theme", "dark"))
        self._nav_items: list[NavItem] = []
        self._active_nav: str = "chat"
        self._views: dict[str, tk.Frame] = {}
        self._cortex: Cortex | None = None
        self._session_mgr: SessionManager | None = None
        self._store: Store | None = None

        self._configure_window()
        self._build_layout()
        self._bootstrap()

    # ------------------------------------------------------------------
    # Window configuration
    # ------------------------------------------------------------------

    def _configure_window(self) -> None:
        pal = self._pal
        self.title("Agentic")
        self.geometry("1280x800")
        self.minsize(900, 600)
        self.configure(bg=pal.bg_deep)

        # Application icon (graceful fallback if not found)
        icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            try:
                icon = tk.PhotoImage(file=str(icon_path))
                self.iconphoto(True, icon)
            except Exception:
                pass

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        pal = self._pal

        # Root grid: sidebar | main | task panel
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, minsize=M.sidebar_w, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, minsize=260, weight=0)

        # ── Sidebar ──────────────────────────────────────────────────
        self._sidebar = tk.Frame(self, bg=pal.bg_deep)
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        # Branding
        brand = tk.Frame(self._sidebar, bg=pal.bg_deep, pady=M.padding_lg)
        brand.pack(fill="x")
        AgLabel(
            brand, pal, text="⬡ Agentic",
            bold=True, size=FONTS.size_xl,
            bg=pal.bg_deep,
        ).pack(padx=M.padding_md)
        AgLabel(
            brand, pal,
            text="Reactive Cortex · Gemma",
            muted=True, size=FONTS.size_xs,
            bg=pal.bg_deep,
        ).pack()
        div = tk.Frame(self._sidebar, bg=pal.border, height=1)
        div.pack(fill="x", pady=(M.padding_sm, M.padding_md))

        # Navigation items
        nav_definitions = [
            ("chat",     "💬", "Chat"),
            ("memory",   "🧠", "Memory"),
            ("settings", "⚙", "Settings"),
        ]
        for nav_id, icon, label in nav_definitions:
            item = NavItem(
                self._sidebar, pal,
                label=label, icon=icon,
                on_click=lambda nid=nav_id: self._show_view(nid),
            )
            item.pack(fill="x", padx=M.padding_xs)
            self._nav_items.append(item)
            # Store reference by nav_id
            item._nav_id = nav_id  # type: ignore[attr-defined]

        # Session list (bottom of sidebar)
        div2 = tk.Frame(self._sidebar, bg=pal.border, height=1)
        div2.pack(fill="x", side="bottom", pady=M.padding_sm)
        AgLabel(
            self._sidebar, pal,
            text="v1.0  •  Gemma · HuggingFace",
            muted=True, size=FONTS.size_xs,
            bg=pal.bg_deep,
        ).pack(side="bottom", pady=M.padding_xs)

        # ── Main panel container ──────────────────────────────────────
        self._main_frame = AgFrame(self, pal)
        self._main_frame.grid(row=0, column=1, sticky="nsew")
        self._main_frame.grid_rowconfigure(0, weight=1)
        self._main_frame.grid_columnconfigure(0, weight=1)

        # ── Task panel ───────────────────────────────────────────────
        task_frame = tk.Frame(self, bg=pal.bg_base, bd=0)
        task_frame.grid(row=0, column=2, sticky="nsew")
        div_v = tk.Frame(task_frame, bg=pal.border, width=1)
        div_v.pack(fill="y", side="left")
        self._task_panel = TaskPanel(task_frame, pal)
        self._task_panel.pack(fill="both", expand=True, side="left")

    # ------------------------------------------------------------------
    # Bootstrap: database, session, skills, cortex
    # ------------------------------------------------------------------

    def _bootstrap(self) -> None:
        data_dir = cfg.data_dir
        db_path  = data_dir / "agentic.db"

        self._store       = Store(db_path)
        self._session_mgr = SessionManager(self._store)
        self._session_mgr.new_session()

        # Register skills
        from skills.filesystem import register_all as reg_fs
        from skills.web_reader  import register_all as reg_web
        from skills.code_runner import register_all as reg_code
        from skills.memory_ops  import register_all as reg_mem

        reg_fs()
        reg_web()
        reg_code()
        reg_mem(self._session_mgr.memory)

        from core.skill_registry import skill_registry

        # Build and wire Cortex
        self._cortex = Cortex(
            memory=self._session_mgr.memory,
            registry=skill_registry,
            on_token=self._on_token_from_cortex,
        )
        self._cortex.start()

        # Subscribe to deliberation end (to signal streaming complete)
        lattice.on(SigKind.DELIBERATION_END, self._on_deliberation_end)
        lattice.on(SigKind.MODEL_ERROR,       self._on_model_error)

        # Build views
        self._build_views()
        self._show_view("chat")

        log.info("Agentic bootstrap complete")
        self._chat_view.append_system(
            "Welcome to Agentic! Powered by the Reactive Cortex Architecture.\n"
            "Type a message to start. Gemma runs locally via HuggingFace transformers.\n"
            "  → The model is downloaded automatically on first use.\n"
            "  → Go to Settings to choose a model and device."
        )

    # ------------------------------------------------------------------
    # View management
    # ------------------------------------------------------------------

    def _build_views(self) -> None:
        assert self._session_mgr is not None

        # Chat view
        self._chat_view = ChatView(
            self._main_frame, self._pal,
            on_submit=self._on_user_submit,
            on_new_session=self._new_session,
        )
        self._views["chat"] = self._chat_view

        # Memory view
        mem_view = MemoryView(
            self._main_frame, self._pal,
            get_memory=lambda: (
                self._session_mgr.memory if self._session_mgr else None
            ),
        )
        self._views["memory"] = mem_view

        # Settings view
        settings_view = SettingsView(
            self._main_frame, self._pal,
            on_theme_change=self._on_theme_change,
        )
        self._views["settings"] = settings_view

        for v in self._views.values():
            v.grid(row=0, column=0, sticky="nsew")

    def _show_view(self, nav_id: str) -> None:
        self._active_nav = nav_id
        view = self._views.get(nav_id)
        if view:
            view.tkraise()

        for item in self._nav_items:
            item.set_active(getattr(item, "_nav_id", "") == nav_id)

    # ------------------------------------------------------------------
    # Cortex ↔ UI bridge
    # ------------------------------------------------------------------

    def _on_user_submit(self, text: str) -> None:
        if self._cortex:
            self._cortex.submit_input(text)

    def _on_token_from_cortex(self, token: str) -> None:
        """Called from the Cortex background thread; route to chat queue."""
        if hasattr(self, "_chat_view"):
            self._chat_view.push_token(token)

    def _on_deliberation_end(self, sig: Any) -> None:
        if hasattr(self, "_chat_view"):
            self._chat_view.finish_streaming()

    def _on_model_error(self, sig: Any) -> None:
        error = sig.payload.get("error", "Unknown error")
        if hasattr(self, "_chat_view"):
            self._chat_view.push_token(f"\n[Model error: {error}]")
            self._chat_view.finish_streaming()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _new_session(self) -> None:
        assert self._session_mgr is not None and self._cortex is not None
        sid = self._session_mgr.new_session()
        # Rebuild cortex with fresh memory
        from core.skill_registry import skill_registry
        from skills.memory_ops import set_memory_ref
        set_memory_ref(self._session_mgr.memory)
        self._cortex.update_memory(self._session_mgr.memory)
        self._chat_view.clear()
        self._chat_view.append_system("New session started.")
        log.info("New session started: %s", sid)

    # ------------------------------------------------------------------
    # Theme switching
    # ------------------------------------------------------------------

    def _on_theme_change(self, theme_name: str) -> None:
        cfg.set("theme", theme_name)
        self._chat_view.append_info(
            "Theme changed to '{}'. Restart the app to fully apply the new theme.".format(
                theme_name
            )
        )

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        log.info("Closing Agentic…")
        if self._cortex:
            self._cortex.stop()
        if self._store:
            self._store.close()
        self.destroy()
        sys.exit(0)
