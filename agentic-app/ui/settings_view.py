"""
Agentic - Settings View
========================
Configuration panel: model selection, device, HF token, theme, memory limits.
All changes are saved immediately via the Config singleton.
"""
from __future__ import annotations

import threading
import tkinter as tk
from typing import Any, Callable

from model.gemma_nexus import KNOWN_MODELS, MODEL_FAMILIES
from ui.components import AgButton, AgEntry, AgFrame, AgLabel
from ui.theme import FONTS, M, Palette
from utils.config import cfg

_DEVICES = ["auto", "cpu", "cuda", "mps"]


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
        self._section("Model", pal)

        self._row_label("HuggingFace Model ID", pal)
        self._model_var = tk.StringVar(value=cfg.get("model_id", KNOWN_MODELS[0]))
        model_frame = AgFrame(self, pal)
        model_frame.pack(fill="x", padx=pad, pady=(0, M.padding_xs))

        model_entry = AgEntry(model_frame, pal, textvariable=self._model_var)
        model_entry.pack(side="left", fill="x", expand=True, padx=(0, M.padding_xs))

        # Quick-pick dropdown grouped by model family
        pick_btn = tk.Menubutton(
            model_frame,
            text="Quick pick…",
            bg=pal.bg_raised, fg=pal.fg_primary,
            activebackground=pal.bg_hover,
            activeforeground=pal.accent,
            highlightthickness=0, relief="flat",
            font=(FONTS.family_ui, FONTS.size_sm),
        )
        pick_menu = tk.Menu(pick_btn, tearoff=0, bg=pal.bg_raised, fg=pal.fg_primary)
        pick_btn["menu"] = pick_menu

        for family, models in MODEL_FAMILIES.items():
            pick_menu.add_command(
                label=f"── {family} ──",
                foreground=pal.fg_muted,
                state="disabled",
            )
            for mid in models:
                pick_menu.add_command(
                    label=mid,
                    command=lambda v=mid: self._model_var.set(v),
                )

        pick_btn.pack(side="right")

        self._row_label("HuggingFace Token (optional, for gated models)", pal)
        self._token_var = tk.StringVar(value=cfg.get("hf_token", ""))
        token_entry = AgEntry(self, pal, textvariable=self._token_var, show="*")
        token_entry.pack(fill="x", padx=pad, pady=(0, M.padding_sm))

        self._row_label("Device", pal)
        self._device_var = tk.StringVar(value=cfg.get("device", "auto"))
        device_frame = AgFrame(self, pal)
        device_frame.pack(fill="x", padx=pad, pady=(0, M.padding_sm))
        for dev in _DEVICES:
            tk.Radiobutton(
                device_frame,
                text=dev, value=dev,
                variable=self._device_var,
                bg=pal.bg_base, fg=pal.fg_primary,
                activebackground=pal.bg_hover,
                activeforeground=pal.accent,
                selectcolor=pal.bg_raised,
            ).pack(side="left", padx=(0, M.padding_md))

        self._q4_var = tk.BooleanVar(value=cfg.get("quantize_4bit", False))
        tk.Checkbutton(
            self,
            text="4-bit quantization (requires bitsandbytes + GPU)",
            variable=self._q4_var,
            bg=pal.bg_base, fg=pal.fg_muted,
            activebackground=pal.bg_hover,
            activeforeground=pal.accent,
            selectcolor=pal.bg_raised,
            font=(FONTS.family_ui, FONTS.size_sm),
        ).pack(anchor="w", padx=pad, pady=(0, pad))

        AgButton(
            self, pal, text="Check model availability",
            command=self._check_model, kind="ghost",
        ).pack(anchor="w", padx=pad, pady=(0, M.padding_xs))

        self._model_status = AgLabel(self, pal, text="", muted=True, size=FONTS.size_sm)
        self._model_status.pack(anchor="w", padx=pad, pady=(0, pad))

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
                "model_id": self._model_var.get().strip(),
                "hf_token": self._token_var.get().strip(),
                "device": self._device_var.get(),
                "quantize_4bit": self._q4_var.get(),
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

    def _check_model(self) -> None:
        """Check whether the model is already cached locally."""
        self._model_status.config(text="Checking…", fg=self._pal.warn)
        model_id = self._model_var.get().strip()

        def _check() -> None:
            try:
                from huggingface_hub import try_to_load_from_cache
                # Try the config file as a lightweight availability probe.
                result = try_to_load_from_cache(model_id, "config.json")
                if result is not None:
                    msg    = f"✓ '{model_id}' found in local cache."
                    colour = self._pal.ok
                else:
                    msg    = (
                        f"'{model_id}' not cached locally – "
                        "it will be downloaded on first use."
                    )
                    colour = self._pal.warn
            except Exception as exc:
                msg    = f"✗ {exc}"
                colour = self._pal.danger
            self.after(0, lambda: self._model_status.config(text=msg, fg=colour))

        threading.Thread(target=_check, daemon=True).start()
