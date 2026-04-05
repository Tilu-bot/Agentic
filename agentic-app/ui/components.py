"""
Agentic - Reusable UI Components
==================================
Custom tkinter widgets that enforce the Agentic design system.
All widgets accept a Palette for consistent theming.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ui.theme import FONTS, M, Palette


# ---------------------------------------------------------------------------
# Styled Button
# ---------------------------------------------------------------------------

class AgButton(tk.Button):
    """Flat, accent-coloured button with hover effects."""

    def __init__(
        self,
        master: Any,
        pal: Palette,
        text: str = "",
        command: Callable | None = None,
        kind: str = "primary",   # "primary" | "ghost" | "danger"
        **kw: Any,
    ) -> None:
        self._pal = pal
        self._kind = kind

        bg, fg = self._colours()
        super().__init__(
            master,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=pal.accent_hover,
            activeforeground=pal.fg_primary,
            relief="flat",
            cursor="hand2",
            font=(FONTS.family_ui, FONTS.size_sm, "bold"),
            padx=M.padding_md,
            pady=M.padding_xs,
            borderwidth=0,
            **kw,
        )
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _colours(self) -> tuple[str, str]:
        pal = self._pal
        if self._kind == "primary":
            return pal.accent, pal.fg_primary
        if self._kind == "danger":
            return pal.danger, pal.fg_primary
        return pal.bg_raised, pal.fg_muted   # ghost

    def _on_enter(self, _: Any) -> None:
        self.config(bg=self._pal.accent_hover)

    def _on_leave(self, _: Any) -> None:
        bg, _ = self._colours()
        self.config(bg=bg)


# ---------------------------------------------------------------------------
# Styled Entry
# ---------------------------------------------------------------------------

class AgEntry(tk.Entry):
    """Single-line text input with Agentic styling."""

    def __init__(self, master: Any, pal: Palette, **kw: Any) -> None:
        super().__init__(
            master,
            bg=pal.bg_input,
            fg=pal.fg_primary,
            insertbackground=pal.accent,
            selectbackground=pal.accent_dim,
            selectforeground=pal.fg_primary,
            relief="flat",
            highlightthickness=1,
            highlightcolor=pal.accent,
            highlightbackground=pal.border,
            font=(FONTS.family_ui, FONTS.size_md),
            **kw,
        )


# ---------------------------------------------------------------------------
# Styled Label
# ---------------------------------------------------------------------------

class AgLabel(tk.Label):
    def __init__(
        self,
        master: Any,
        pal: Palette,
        text: str = "",
        size: int | None = None,
        bold: bool = False,
        muted: bool = False,
        **kw: Any,
    ) -> None:
        weight = "bold" if bold else "normal"
        fg = pal.fg_muted if muted else pal.fg_primary
        super().__init__(
            master,
            text=text,
            bg=kw.pop("bg", pal.bg_base),
            fg=fg,
            font=(FONTS.family_ui, size or FONTS.size_md, weight),
            **kw,
        )


# ---------------------------------------------------------------------------
# Styled Frame
# ---------------------------------------------------------------------------

class AgFrame(tk.Frame):
    def __init__(self, master: Any, pal: Palette, raised: bool = False, **kw: Any) -> None:
        bg = pal.bg_raised if raised else pal.bg_base
        super().__init__(master, bg=kw.pop("bg", bg), **kw)


# ---------------------------------------------------------------------------
# Scrollable Text Display (read-only)
# ---------------------------------------------------------------------------

class ScrolledText(tk.Frame):
    """Read-only scrollable text widget with syntax-aware colouring."""

    def __init__(self, master: Any, pal: Palette, **kw: Any) -> None:
        super().__init__(master, bg=pal.bg_base)
        self._pal = pal

        self.text = tk.Text(
            self,
            bg=pal.bg_base,
            fg=pal.fg_primary,
            insertbackground=pal.accent,
            selectbackground=pal.accent_dim,
            selectforeground=pal.fg_primary,
            relief="flat",
            wrap="word",
            cursor="arrow",
            state="disabled",
            font=(FONTS.family_ui, FONTS.size_md),
            padx=M.padding_md,
            pady=M.padding_sm,
            spacing3=4,
            **kw,
        )
        sb = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.config(yscrollcommand=sb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Tag definitions for message roles
        self.text.tag_config("user",   foreground=pal.accent, font=(FONTS.family_ui, FONTS.size_md, "bold"))
        self.text.tag_config("assistant", foreground=pal.fg_primary)
        self.text.tag_config("system", foreground=pal.fg_muted, font=(FONTS.family_ui, FONTS.size_sm, "italic"))
        self.text.tag_config("skill",  foreground=pal.ok, font=(FONTS.family_code, FONTS.size_sm))
        self.text.tag_config("error",  foreground=pal.danger)
        self.text.tag_config("info",   foreground=pal.info)
        self.text.tag_config("dim",    foreground=pal.fg_dim)

    def append(self, text: str, tag: str = "assistant") -> None:
        self.text.config(state="normal")
        self.text.insert("end", text, tag)
        self.text.see("end")
        self.text.config(state="disabled")

    def clear(self) -> None:
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")


# ---------------------------------------------------------------------------
# Sidebar Navigation Item
# ---------------------------------------------------------------------------

class NavItem(tk.Frame):
    """Clickable navigation row for the sidebar."""

    def __init__(
        self,
        master: Any,
        pal: Palette,
        label: str,
        icon: str = "•",
        on_click: Callable | None = None,
    ) -> None:
        super().__init__(master, bg=pal.bg_deep, cursor="hand2")
        self._pal = pal
        self._on_click = on_click
        self._active = False

        self._icon_lbl = tk.Label(
            self, text=icon, bg=pal.bg_deep, fg=pal.fg_muted,
            font=(FONTS.family_ui, FONTS.size_md),
            padx=M.padding_sm, pady=M.padding_sm,
        )
        self._text_lbl = tk.Label(
            self, text=label, bg=pal.bg_deep, fg=pal.fg_muted,
            font=(FONTS.family_ui, FONTS.size_sm),
            anchor="w",
        )
        self._icon_lbl.pack(side="left")
        self._text_lbl.pack(side="left", fill="x", expand=True)

        for w in (self, self._icon_lbl, self._text_lbl):
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>",    self._enter)
            w.bind("<Leave>",    self._leave)

    def _click(self, _: Any) -> None:
        if self._on_click:
            self._on_click()

    def _enter(self, _: Any) -> None:
        if not self._active:
            for w in (self, self._icon_lbl, self._text_lbl):
                w.config(bg=self._pal.bg_hover)

    def _leave(self, _: Any) -> None:
        if not self._active:
            for w in (self, self._icon_lbl, self._text_lbl):
                w.config(bg=self._pal.bg_deep)

    def set_active(self, active: bool) -> None:
        self._active = active
        bg = self._pal.accent_dim if active else self._pal.bg_deep
        fg = self._pal.accent_hover if active else self._pal.fg_muted
        for w in (self, self._icon_lbl, self._text_lbl):
            w.config(bg=bg)
        self._icon_lbl.config(fg=fg)
        self._text_lbl.config(fg=fg)


# ---------------------------------------------------------------------------
# Progress bar (custom, no ttk)
# ---------------------------------------------------------------------------

class AgProgressBar(tk.Canvas):
    """Thin horizontal progress bar."""

    def __init__(self, master: Any, pal: Palette, height: int = 4, **kw: Any) -> None:
        super().__init__(
            master, height=height, bg=pal.bg_raised,
            highlightthickness=0, **kw
        )
        self._pal = pal
        self._value = 0.0
        self.bind("<Configure>", self._redraw)

    def set_value(self, v: float) -> None:
        self._value = max(0.0, min(1.0, v))
        self._redraw()

    def _redraw(self, _: Any = None) -> None:
        self.delete("bar")
        w = self.winfo_width()
        h = self.winfo_height()
        filled = int(w * self._value)
        if filled > 0:
            self.create_rectangle(
                0, 0, filled, h,
                fill=self._pal.accent, outline="",
                tags="bar",
            )
