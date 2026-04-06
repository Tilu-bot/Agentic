"""
pytest configuration for agentic-app/tests.

Adds the agentic-app package root to sys.path and sets the AGENTIC_DATA_DIR
environment variable to a temp path so tests never touch the real config or
database.  Using conftest.py ensures this setup runs exactly once per session
and is isolated from other test suites.
"""
import os
import sys
from pathlib import Path

# Ensure agentic-app/ is on sys.path before any test module is imported.
_pkg_root = str(Path(__file__).parent.parent)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

# Redirect config and SQLite files to a throwaway temp directory.
os.environ.setdefault("AGENTIC_DATA_DIR", "/tmp/agentic_test")
