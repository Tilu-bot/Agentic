#!/usr/bin/env python3
"""
Agentic Desktop App Launcher
Choose between Tkinter (legacy) and PyQt6 (recommended) UI frameworks
"""

import sys
import os
from pathlib import Path

def print_menu():
    print("\n" + "="*60)
    print("Agentic - AI Agent Workspace")
    print("="*60)
    print("\nSelect UI Framework:")
    print("  1. PyQt6 (Recommended)  - Professional native desktop app")
    print("     • Modern, smooth interface")
    print("     • Matches ChatGPT/Gemini quality")
    print("     • Instant startup, no browser overhead")
    print()
    print("  2. Tkinter (Legacy)     - Basic native GUI")
    print("     • Simple, lightweight")
    print("     • Note: Known geometry issues")
    print()
    choice = input("Enter choice (1-2) [default: 1]: ").strip() or "1"
    return choice

def launch_pyqt6():
    """Launch with PyQt6 (recommended) with full backend integration"""
    try:
        from ui.pyqt_integrated import main
        print("\n🚀 Launching Agentic with PyQt6 + Backend...")
        main()
    except ImportError as e:
        print(f"❌ Error: {e}")
        print("Install dependencies: pip install -r requirements.txt")
        sys.exit(1)

def launch_tkinter():
    """Launch with Tkinter (legacy)"""
    try:
        from ui.app import AgenticApp
        print("\n🚀 Launching Agentic with Tkinter (legacy)...")
        from ui.app import main as app_main
        # Note: This would need the existing Tkinter main()
        print("⚠️  Tkinter mode - consider upgrading to PyQt6 for better experience")
        # Placeholder for actual Tkinter launcher
        print("Tkinter launcher not configured in this version")
    except Exception as e:
        print(f"❌ Error launching Tkinter: {e}")
        sys.exit(1)

def main():
    if len(sys.argv) > 1:
        # Allow command-line argument to skip menu
        choice = sys.argv[1]
    else:
        choice = print_menu()
    
    if choice == "1":
        launch_pyqt6()
    elif choice == "2":
        launch_tkinter()
    else:
        print("❌ Invalid choice")
        sys.exit(1)

if __name__ == "__main__":
    main()
