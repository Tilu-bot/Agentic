#!/usr/bin/env python3
"""Agentic Desktop App Launcher (PyQt integrated frontend)."""

import sys
import os
from pathlib import Path

def launch_pyqt6():
    """Launch the standard PyQt6 frontend with full backend integration."""
    try:
        from ui.pyqt_integrated import main
        print("\nLaunching Agentic (PyQt integrated frontend)...")
        main()
    except ImportError as e:
        print(f"Error: {e}")
        print("Install dependencies: pip install -r requirements.txt")
        sys.exit(1)

def main():
    # Optional argument is accepted for backward compatibility, but ignored.
    _ = sys.argv[1:] if len(sys.argv) > 1 else []
    launch_pyqt6()

if __name__ == "__main__":
    main()
