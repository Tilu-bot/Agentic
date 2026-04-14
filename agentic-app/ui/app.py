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
import threading
import time
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
from ui.theme import FONTS, M, Palette, palette
from utils.config import cfg
from utils.logger import build_logger

log = build_logger("agentic.app")


class AgenticApp(tk.Tk):
    """
    Root window of the Agentic desktop application.
    Layout:
            ┌──────────┬──────────────────────────────────┐
            │ Sidebar  │          Main panel              │
            │ (nav)    │    (chat / memory / settings)    │
            └──────────┴──────────────────────────────────┘
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
        self._tools_count: int = 0
        self._load_stage: str = ""
        self._load_model_short: str = "model"
        self._load_started_at: float = 0.0
        self._load_tick_job: str | None = None
        self._load_long_hint_shown: bool = False
        self._load_last_stage_announcement: str = ""
        self._load_last_download_pct: int = -1
        self._load_download_pct: int = -1

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

        # Root grid: sidebar | main
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, minsize=M.sidebar_w, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # ── Sidebar ──────────────────────────────────────────────────
        self._sidebar = tk.Frame(self, bg=pal.bg_deep, width=M.sidebar_w)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)

        # Branding section
        brand = tk.Frame(self._sidebar, bg=pal.bg_deep)
        brand.pack(fill="x", padx=M.padding_lg, pady=M.padding_lg)
        
        AgLabel(
            brand, pal, text="Agentic",
            bold=True, size=FONTS.size_xl,
            bg=pal.bg_deep,
        ).pack(pady=(0, M.padding_xs))
        
        AgLabel(
            brand, pal,
            text="AI Agent Workspace",
            muted=True, size=FONTS.size_xs,
            bg=pal.bg_deep,
        ).pack()
        
        div = tk.Frame(self._sidebar, bg=pal.border_dim, height=1)
        div.pack(fill="x", pady=(M.padding_lg, M.padding_md))

        # Navigation items
        nav_definitions = [
            ("chat",     "💬", "Chat", "chat"),
            ("memory",   "🧠", "Memory", "memory"),
            ("settings", "⚙", "Settings", "settings"),
        ]
        for nav_id, icon, label, icon_name in nav_definitions:
            item = NavItem(
                self._sidebar, pal,
                label=label,
                icon=icon,
                icon_name=icon_name,
                on_click=lambda nid=nav_id: self._show_view(nid),
            )
            item.pack(fill="x", padx=M.padding_sm, pady=(0, M.padding_xs))
            self._nav_items.append(item)
            # Store reference by nav_id
            item._nav_id = nav_id  # type: ignore[attr-defined]

        # Version info at bottom
        div2 = tk.Frame(self._sidebar, bg=pal.border_dim, height=1)
        div2.pack(fill="x", side="bottom", pady=(M.padding_lg, M.padding_sm))
        AgLabel(
            self._sidebar, pal,
            text="Agentic v1.0",
            muted=True, size=FONTS.size_xs,
            bg=pal.bg_deep,
        ).pack(side="bottom", pady=M.padding_sm, padx=M.padding_md)

        # ── Main panel container ──────────────────────────────────────
        self._main_frame = AgFrame(self, pal)
        self._main_frame.grid(row=0, column=1, sticky="nsew")
        self._main_frame.grid_rowconfigure(0, weight=1)
        self._main_frame.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Bootstrap: database, session, skills, cortex
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
        from skills.web_reader  import register_all as reg_web
        from skills.code_runner import register_all as reg_code
        from skills.memory_ops  import register_all as reg_mem
        from skills.doc_reader  import register_all as reg_docs

        reg_fs()
        reg_web()
        reg_code()
        reg_mem(self._session_mgr.memory)
        reg_docs()

        from core.skill_registry import skill_registry
        self._tools_count = len(skill_registry.all_specs())

        # Build and wire Cortex
        self._cortex = Cortex(
            memory=self._session_mgr.memory,
            registry=skill_registry,
            on_token=self._on_token_from_cortex,
        )
        self._cortex.start()

        # Subscribe to deliberation end (to signal streaming complete)
        lattice.on(SigKind.DELIBERATION_START, self._on_deliberation_start)
        lattice.on(SigKind.DELIBERATION_END,   self._on_deliberation_end)
        lattice.on(SigKind.REACT_ITERATION,    self._on_react_iteration)
        lattice.on(SigKind.MODEL_ERROR,        self._on_model_error)
        lattice.on(SigKind.MODEL_LOADING,      self._on_model_loading)

        # Build views
        self._build_views()
        self._show_view("chat")
        self._chat_view.set_runtime_info(cfg.get("model_id", "unknown"), self._tools_count)

        log.info("Agentic bootstrap complete")
        self._chat_view.append_system(
            "Welcome to Agentic! Powered by the Reactive Cortex Architecture.\n"
            "Type a message to start. The model runs locally via HuggingFace transformers.\n"
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
            on_stop=self._on_user_stop,
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

    def _on_user_stop(self) -> None:
        if self._cortex:
            self._cortex.cancel_current()

    def _on_token_from_cortex(self, token: str) -> None:
        """Called from the Cortex background thread; route to chat queue."""
        if hasattr(self, "_chat_view"):
            self._chat_view.push_token(token)

    def _on_deliberation_start(self, sig: Any) -> None:
        """Update status bar as soon as deliberation begins."""
        self._run_on_ui(self._on_deliberation_start_ui)

    def _on_deliberation_start_ui(self) -> None:
        if hasattr(self, "_chat_view"):
            self._chat_view.set_status("Working...", busy=True)

    def _on_deliberation_end(self, sig: Any) -> None:
        if hasattr(self, "_chat_view"):
            self._chat_view.finish_streaming()

    def _on_react_iteration(self, sig: Any) -> None:
        """Inform the user that the model is running tools and re-reasoning."""
        self._run_on_ui(self._on_react_iteration_ui, sig)

    def _on_react_iteration_ui(self, sig: Any) -> None:
        iteration = sig.payload.get("iteration", "?")
        skills_run = sig.payload.get("skills_run", [])
        skill_names = ", ".join(skills_run) or "none"
        if hasattr(self, "_chat_view"):
            self._chat_view.set_status(
                f"Reasoning… (iteration {iteration}, tools: {skill_names})", busy=True
            )

    def _on_model_error(self, sig: Any) -> None:
        error = sig.payload.get("error", "Unknown error")
        if hasattr(self, "_chat_view"):
            self._chat_view.push_token(f"\n[Model error: {error}]")
            self._chat_view.finish_streaming()

    def _on_model_loading(self, sig: Any) -> None:
        """Update the status bar with model loading progress."""
        self._run_on_ui(self._on_model_loading_ui, sig)

    def _on_model_loading_ui(self, sig: Any) -> None:
        stage    = sig.payload.get("stage", "")
        model_id = sig.payload.get("model_id", "model")
        # Show only the short name (last component of the HF repo path).
        short = model_id.split("/")[-1] if "/" in model_id else model_id
        self._load_stage = stage
        self._load_model_short = short
        if stage == "start":
            self._load_started_at = time.monotonic()
            self._load_long_hint_shown = False
            self._load_last_download_pct = -1
            self._load_download_pct = -1
            self._start_loading_heartbeat()
            if hasattr(self, "_chat_view"):
                self._chat_view.set_status(f"Loading {short}…", busy=True)
                self._announce_loading_stage("Initializing model")
        elif stage == "download_start":
            if hasattr(self, "_chat_view"):
                self._chat_view.set_status(f"Downloading model files: {short}…", busy=True)
                self._announce_loading_stage("Downloading model files")
        elif stage == "download":
            pct = int(sig.payload.get("progress_pct", 0))
            self._load_download_pct = pct
            file_name = sig.payload.get("file", "")
            if hasattr(self, "_chat_view"):
                if file_name:
                    self._chat_view.set_status(
                        f"Downloading {short}: {pct}% ({file_name})",
                        busy=True,
                    )
                else:
                    self._chat_view.set_status(f"Downloading {short}: {pct}%", busy=True)
                # Emit concise logs at meaningful percentage milestones.
                if pct in (10, 25, 50, 75, 90, 100) and pct != self._load_last_download_pct:
                    self._chat_view.append_info(f"Download progress: {pct}%")
                    self._load_last_download_pct = pct
        elif stage == "download_done":
            self._load_download_pct = 100
            if hasattr(self, "_chat_view"):
                self._chat_view.set_status(f"Download complete: {short}", busy=True)
                self._announce_loading_stage("Download complete, loading tokenizer")
        elif stage == "download_retry":
            attempt = int(sig.payload.get("attempt", 1))
            max_attempts = int(sig.payload.get("max_attempts", 1))
            retry_in_s = int(sig.payload.get("retry_in_s", 1))
            if hasattr(self, "_chat_view"):
                self._chat_view.set_status(
                    f"Network unstable, retrying download ({attempt}/{max_attempts})…",
                    busy=True,
                )
                self._chat_view.append_info(
                    f"Download retry {attempt}/{max_attempts} in {retry_in_s}s"
                )
        elif stage == "download_cached":
            self._load_download_pct = 100
            if hasattr(self, "_chat_view"):
                self._chat_view.append_info(
                    "Using local cached model files (network unavailable)."
                )
        elif stage == "device_warning":
            message = str(sig.payload.get("message", "Device fallback to CPU"))
            if hasattr(self, "_chat_view"):
                self._chat_view.append_info(message)
                self._chat_view.set_status("Using CPU fallback", busy=True)
        elif stage == "device_selected":
            selected = str(sig.payload.get("selected_device", "cpu"))
            torch_version = str(sig.payload.get("torch_version", "unknown"))
            if hasattr(self, "_chat_view"):
                self._chat_view.append_info(
                    f"Execution device: {selected} (torch {torch_version})"
                )
        elif stage == "tokenizer":
            if hasattr(self, "_chat_view"):
                self._chat_view.set_status(f"Loading tokenizer: {short}…", busy=True)
                self._announce_loading_stage("Tokenizer ready, preparing weights")
        elif stage == "weights":
            if hasattr(self, "_chat_view"):
                self._chat_view.set_status(f"Loading weights: {short}…", busy=True)
                self._announce_loading_stage("Loading model weights")
        elif stage == "done":
            self._stop_loading_heartbeat()
            if hasattr(self, "_chat_view"):
                self._chat_view.set_status("Model ready", busy=False)
                self._chat_view.append_info(f"✓ Model loaded: {model_id}")
                self._chat_view.set_runtime_info(model_id, self._tools_count)
        elif stage == "error":
            self._stop_loading_heartbeat()
            error = sig.payload.get("error", "unknown error")
            log.error("Model load failed: %s – %s", model_id, error)
            if hasattr(self, "_chat_view"):
                self._chat_view.set_status(f"Model load failed: {error[:60]}", busy=False)

    def _run_on_ui(self, fn: Any, *args: Any) -> None:
        """Run a callback in the Tk main thread to avoid thread-affinity errors."""
        try:
            if threading.current_thread() is threading.main_thread():
                fn(*args)
            else:
                self.after(0, lambda: fn(*args))
        except (RuntimeError, tk.TclError):
            # Ignore late signals during shutdown.
            return

    def _start_loading_heartbeat(self) -> None:
        """Show elapsed model-loading progress every second."""
        if self._load_tick_job is not None:
            self.after_cancel(self._load_tick_job)
            self._load_tick_job = None

        def _tick() -> None:
            # Stop once model load enters a terminal state.
            if self._load_stage in ("done", "error", ""):
                self._load_tick_job = None
                return

            elapsed_s = int(max(0.0, time.monotonic() - self._load_started_at))
            stage_label = {
                "start": "Initializing",
                "download_start": "Downloading model files",
                "download": "Downloading",
                "tokenizer": "Loading tokenizer",
                "weights": "Loading weights",
            }.get(self._load_stage, "Loading model")

            if hasattr(self, "_chat_view"):
                if self._load_stage in ("download_start", "download") and self._load_download_pct >= 0:
                    status = (
                        f"{stage_label}: {self._load_model_short}… "
                        f"{self._load_download_pct}% · {elapsed_s}s"
                    )
                else:
                    status = f"{stage_label}: {self._load_model_short}… {elapsed_s}s"
                self._chat_view.set_status(
                    status,
                    busy=True,
                )
                # First model download can take minutes; show a one-time hint.
                if elapsed_s >= 15 and not self._load_long_hint_shown:
                    self._chat_view.append_info(
                        "Model download in progress… first launch can take a few minutes "
                        "depending on internet speed and model size."
                    )
                    self._load_long_hint_shown = True

            self._load_tick_job = self.after(1000, _tick)

        self._load_tick_job = self.after(1000, _tick)

    def _stop_loading_heartbeat(self) -> None:
        if self._load_tick_job is not None:
            self.after_cancel(self._load_tick_job)
            self._load_tick_job = None

    def _announce_loading_stage(self, message: str) -> None:
        """Append one-time stage logs in chat to make progress visible."""
        if not hasattr(self, "_chat_view"):
            return
        if message == self._load_last_stage_announcement:
            return
        self._chat_view.append_info(message)
        self._load_last_stage_announcement = message

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
