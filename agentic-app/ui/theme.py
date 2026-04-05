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
    bg_deep   = "#0d0f14",
    bg_base   = "#13161e",
    bg_raised = "#1c2030",
    bg_hover  = "#242840",
    bg_input  = "#1a1e2e",

    fg_primary = "#e8eaf6",
    fg_muted   = "#9fa8c0",
    fg_dim     = "#5a6080",

    accent       = "#6c8ef5",
    accent_hover = "#8ca8ff",
    accent_dim   = "#3a4e8a",

    ok     = "#4caf80",
    warn   = "#ffb347",
    danger = "#ef5350",
    info   = "#5bc8f5",

    border     = "#2c3248",
    border_dim = "#1c2030",

    scroll_bg    = "#1c2030",
    scroll_thumb = "#3a4e8a",
)

LIGHT = Palette(
    bg_deep   = "#f0f2f8",
    bg_base   = "#ffffff",
    bg_raised = "#f7f9ff",
    bg_hover  = "#e8ecff",
    bg_input  = "#ffffff",

    fg_primary = "#1a1e2e",
    fg_muted   = "#4a5070",
    fg_dim     = "#9fa8c0",

    accent       = "#4060d0",
    accent_hover = "#5070e0",
    accent_dim   = "#c0ccff",

    ok     = "#2e7d52",
    warn   = "#b86800",
    danger = "#c62828",
    info   = "#0078b8",

    border     = "#ccd0e0",
    border_dim = "#e0e4f0",

    scroll_bg    = "#e8ecff",
    scroll_thumb = "#8090c0",
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
    family_code = "Consolas",
    size_xs = 9,
    size_sm = 10,
    size_md = 12,
    size_lg = 14,
    size_xl = 16,
    size_h1 = 22,
    size_h2 = 17,
)


@dataclass(frozen=True)
class Metrics:
    padding_xs: int = 4
    padding_sm: int = 8
    padding_md: int = 14
    padding_lg: int = 20
    corner:     int = 8
    corner_sm:  int = 4
    border_w:   int = 1
    icon_sm:    int = 16
    icon_md:    int = 24
    sidebar_w:  int = 220


M = Metrics()


def palette(name: str = "dark") -> Palette:
    return LIGHT if name == "light" else DARK
