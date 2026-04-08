"""
Agentic - UI Theme
==================
All colors, fonts, and sizing constants for the Agentic desktop UI.
Supports a dark theme (default) and a light theme.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    # Backgrounds
    bg_deep:    str   # deepest background (window)
    bg_base:    str   # panel background
    bg_raised:  str   # elevated widget background
    bg_hover:   str   # hover state
    bg_input:   str   # input field background

    # Foregrounds
    fg_primary: str   # main text
    fg_muted:   str   # secondary text
    fg_dim:     str   # very dim / disabled

    # Accent
    accent:       str  # primary accent (brand color)
    accent_hover: str  # lighter accent for hover
    accent_dim:   str  # muted accent

    # Status colours
    ok:      str
    warn:    str
    danger:  str
    info:    str

    # Borders
    border:     str
    border_dim: str

    # Scrollbar
    scroll_bg:    str
    scroll_thumb: str


DARK = Palette(
    bg_deep   = "#ffffff",
    bg_base   = "#fafbfc",
    bg_raised = "#ffffff",
    bg_hover  = "#f0f4f9",
    bg_input  = "#ffffff",

    fg_primary = "#0f172a",
    fg_muted   = "#475569",
    fg_dim     = "#94a3b8",

    accent       = "#6366f1",
    accent_hover = "#818cf8",
    accent_dim   = "#e0e7ff",

    ok     = "#10b981",
    warn   = "#f59e0b",
    danger = "#ef4444",
    info   = "#3b82f6",

    border     = "#e2e8f0",
    border_dim = "#cbd5e1",

    scroll_bg    = "#f1f5f9",
    scroll_thumb = "#cbd5e1",
)

LIGHT = Palette(
    bg_deep   = "#ffffff",
    bg_base   = "#fafbfc",
    bg_raised = "#ffffff",
    bg_hover  = "#f0f4f9",
    bg_input  = "#ffffff",

    fg_primary = "#0f172a",
    fg_muted   = "#475569",
    fg_dim     = "#94a3b8",

    accent       = "#6366f1",
    accent_hover = "#818cf8",
    accent_dim   = "#e0e7ff",

    ok     = "#10b981",
    warn   = "#f59e0b",
    danger = "#ef4444",
    info   = "#3b82f6",

    border     = "#e2e8f0",
    border_dim = "#cbd5e1",

    scroll_bg    = "#f1f5f9",
    scroll_thumb = "#cbd5e1",
)


@dataclass(frozen=True)
class Typography:
    family_ui:   str   # general UI text
    family_code: str   # monospace / code blocks
    size_xs:     int
    size_sm:     int
    size_md:     int
    size_lg:     int
    size_xl:     int
    size_h1:     int
    size_h2:     int


FONTS = Typography(
    family_ui   = "Segoe UI",
    family_code = "Monaco",
    size_xs = 12,
    size_sm = 13,
    size_md = 15,
    size_lg = 17,
    size_xl = 20,
    size_h1 = 36,
    size_h2 = 28,
)


@dataclass(frozen=True)
class Metrics:
    padding_xs: int = 6
    padding_sm: int = 12
    padding_md: int = 16
    padding_lg: int = 24
    corner:     int = 12
    corner_sm:  int = 6
    border_w:   int = 1
    icon_sm:    int = 18
    icon_md:    int = 28
    sidebar_w:  int = 260


M = Metrics()


def palette(name: str = "dark") -> Palette:
    return LIGHT if name == "light" else DARK
