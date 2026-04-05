"""
Agentic – Application Entry Point
===================================
Bootstraps the desktop application:
  1. Adjusts sys.path so all packages resolve correctly.
  2. Applies DPI awareness (Windows) and scaling (macOS).
  3. Launches the AgenticApp Tk root window.
"""
from __future__ import annotations

import os
import sys
import platform
from pathlib import Path

# Ensure the agentic-app directory is on the path
_APP_DIR = Path(__file__).parent.resolve()
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


def _apply_dpi_awareness() -> None:
    """Enable high-DPI rendering where supported."""
    _os = platform.system()
    if _os == "Windows":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    elif _os == "Darwin":
        # macOS: tkinter handles Retina displays automatically
        pass


def main() -> None:
    _apply_dpi_awareness()

    import tkinter as tk
    from ui.app import AgenticApp

    app = AgenticApp()
    app.mainloop()


if __name__ == "__main__":
    main()
