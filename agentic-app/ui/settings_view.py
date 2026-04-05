"""
Agentic - Settings View
========================
Configuration panel: Ollama URL, model selection, theme, memory limits.
All changes are saved immediately via the Config singleton.
"""
from __future__ import annotations

import asyncio
import threading
import tkinter as tk
from typing import Any, Callable

from ui.components import AgButton, AgEntry, AgFrame, AgLabel
from ui.theme import FONTS, M, Palette
from utils.config import cfg


class SettingsView(tk.Frame):
    def __init__(
        self,
        master: Any,
        pal: Palette,
        on_theme_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(master, bg=pal.bg_base)
        self._pal = pal
        self._on_theme_change = on_theme_change
        self._build_ui()

    def _build_ui(self) -> None:
        pal = self._pal
        pad = M.padding_md

        AgLabel(
            self, pal, text="Settings", bold=True, size=FONTS.size_h2
        ).pack(anchor="w", padx=pad, pady=(pad, M.padding_sm))

        div = tk.Frame(self, bg=pal.border, height=1)
        div.pack(fill="x", pady=(0, pad))

        # --- Model section ---
        self._section("Model & API", pal)

        self._row_label("Ollama Base URL", pal)
        self._url_var = tk.StringVar(value=cfg.get("ollama_base_url"))
        url_entry = AgEntry(self, pal, textvariable=self._url_var)
        url_entry.pack(fill="x", padx=pad, pady=(0, M.padding_sm))

        self._row_label("Gemma Model Name", pal)
        self._model_var = tk.StringVar(value=cfg.get("gemma_model"))
        model_entry = AgEntry(self, pal, textvariable=self._model_var)
        model_entry.pack(fill="x", padx=pad, pady=(0, M.padding_sm))

        AgButton(
            self, pal, text="Test Connection",
            command=self._test_connection, kind="ghost",
        ).pack(anchor="w", padx=pad, pady=(0, pad))

        self._conn_status = AgLabel(
            self, pal, text="", muted=True, size=FONTS.size_sm
        )
        self._conn_status.pack(anchor="w", padx=pad)

        # --- Memory section ---
        self._section("Memory", pal)

        self._row_label("Working Memory Limit (turns)", pal)
        self._wm_var = tk.IntVar(value=cfg.get("working_memory_limit", 20))
        wm_scale = tk.Scale(
            self,
            from_=10, to=100, orient="horizontal",
            variable=self._wm_var,
            bg=pal.bg_base, fg=pal.fg_primary,
            troughcolor=pal.bg_raised, highlightthickness=0,
            sliderrelief="flat",
        )
        wm_scale.pack(fill="x", padx=pad, pady=(0, pad))

        # --- Parallel tasks ---
        self._section("Execution", pal)

        self._row_label("Max Parallel Tasks", pal)
        self._pt_var = tk.IntVar(value=cfg.get("max_parallel_tasks", 4))
        pt_scale = tk.Scale(
            self,
            from_=1, to=12, orient="horizontal",
            variable=self._pt_var,
            bg=pal.bg_base, fg=pal.fg_primary,
            troughcolor=pal.bg_raised, highlightthickness=0,
            sliderrelief="flat",
        )
        pt_scale.pack(fill="x", padx=pad, pady=(0, pad))

        # --- Theme ---
        self._section("Appearance", pal)
        self._theme_var = tk.StringVar(value=cfg.get("theme", "dark"))
        theme_frame = AgFrame(self, pal)
        theme_frame.pack(fill="x", padx=pad, pady=(0, pad))
        for label, val in (("Dark", "dark"), ("Light", "light")):
            tk.Radiobutton(
                theme_frame,
                text=label, value=val,
                variable=self._theme_var,
                bg=pal.bg_base, fg=pal.fg_primary,
                activebackground=pal.bg_hover,
                activeforeground=pal.accent,
                selectcolor=pal.bg_raised,
                command=self._apply_theme,
            ).pack(side="left", padx=(0, M.padding_md))

        # Save button
        AgButton(
            self, pal, text="Save Settings",
            command=self._save, kind="primary",
        ).pack(anchor="w", padx=pad, pady=pad)

        self._save_status = AgLabel(self, pal, text="", muted=True, size=FONTS.size_sm)
        self._save_status.pack(anchor="w", padx=pad)

    def _section(self, title: str, pal: Palette) -> None:
        AgLabel(
            self, pal, text=title, bold=True, size=FONTS.size_md
        ).pack(anchor="w", padx=M.padding_md, pady=(M.padding_sm, M.padding_xs))

    def _row_label(self, text: str, pal: Palette) -> None:
        AgLabel(self, pal, text=text, muted=True, size=FONTS.size_sm).pack(
            anchor="w", padx=M.padding_md, pady=(0, 2)
        )

    def _save(self) -> None:
        cfg.update(
            {
                "ollama_base_url": self._url_var.get().strip(),
                "gemma_model": self._model_var.get().strip(),
                "working_memory_limit": self._wm_var.get(),
                "max_parallel_tasks": self._pt_var.get(),
                "theme": self._theme_var.get(),
            }
        )
        self._save_status.config(text="✓ Saved.", fg=self._pal.ok)
        self.after(2000, lambda: self._save_status.config(text=""))

    def _apply_theme(self) -> None:
        if self._on_theme_change:
            self._on_theme_change(self._theme_var.get())

    def _test_connection(self) -> None:
        self._conn_status.config(text="Testing…", fg=self._pal.warn)

        url   = self._url_var.get().strip()
        model = self._model_var.get().strip()

        def _check() -> None:
            try:
                import httpx
                with httpx.Client(timeout=4.0) as c:
                    resp = c.get(f"{url}/api/tags")
                    if resp.status_code == 200:
                        models = [m["name"] for m in resp.json().get("models", [])]
                        found  = model in models
                        msg    = (
                            f"✓ Connected. Model '{model}' {'found' if found else 'NOT found'}."
                        )
                        colour = self._pal.ok if found else self._pal.warn
                    else:
                        msg    = f"✗ HTTP {resp.status_code}"
                        colour = self._pal.danger
            except Exception as exc:
                msg    = f"✗ {exc}"
                colour = self._pal.danger
            self.after(0, lambda: self._conn_status.config(text=msg, fg=colour))

        threading.Thread(target=_check, daemon=True).start()
