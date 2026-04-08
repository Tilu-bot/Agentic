"""
Agentic – Application Entry Point
===================================
Bootstraps the desktop application with the PyQt6 UI.

  1. Adjusts sys.path so all packages resolve correctly.
  2. Launches the AgenticQtApp (PyQt6 + WebEngine).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the agentic-app directory is on the path
_APP_DIR = Path(__file__).parent.resolve()
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


def main() -> None:
    from ui.pyqt_integrated import main as qt_main
    qt_main()


if __name__ == "__main__":
    main()
