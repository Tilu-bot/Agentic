# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build specification for the Agentic desktop app.

Usage:
    cd agentic-app
    pyinstaller agentic.spec

Output:
  • dist/Agentic/          — folder bundle (used by build_installer.bat)
  • dist/Agentic/Agentic.exe — the main executable inside the bundle

To produce a single-file Windows installer (.exe with wizard + shortcuts):
    build_installer.bat     (Windows only, requires Inno Setup 6)

To produce a standalone portable executable (no installer wizard):
    pyinstaller agentic.spec --onefile   (slower first-launch; no shortcuts)
"""

import sys
from pathlib import Path

ROOT = Path(".").resolve()

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Include the assets folder if it exists
        ("assets", "assets"),
    ],
    hiddenimports=[
        # Ensure all sub-packages are included
        "core.cortex",
        "core.signal_lattice",
        "core.task_fabric",
        "core.memory_lattice",
        "core.skill_registry",
        "model.gemma_nexus",
        "model.prompt_weaver",
        "skills.base",
        "skills.filesystem",
        "skills.web_reader",
        "skills.code_runner",
        "skills.memory_ops",
        "skills.doc_reader",
        "ui.app",
        "ui.chat_view",
        "ui.task_panel",
        "ui.settings_view",
        "ui.memory_view",
        "ui.components",
        "ui.theme",
        "state.store",
        "state.session",
        "utils.config",
        "utils.logger",
        # stdlib modules sometimes missed
        "sqlite3",
        "asyncio",
        "threading",
        "queue",
        "json",
        "logging.handlers",
        "pathlib",
        "tkinter",
        "tkinter.ttk",
        "tkinter.scrolledtext",
        # HuggingFace / PyTorch are imported lazily in model.gemma_nexus.
        # Keep only the minimal dynamic-import surface for runtime.
        "transformers",
        "transformers.generation.streamers",
        "torch",
        "accelerate",
        "huggingface_hub",
        # httpx (web-fetch skill)
        "httpx",
        # Document reader skill (PDF, Excel, Word, PowerPoint)
        "pypdf",
        "openpyxl",
        "docx",
        "pptx",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy unused packages and optional ML backends that cause
        # PyInstaller hook explosions in globally polluted Python installs.
        "matplotlib", "pandas", "scipy",
        # PIL/Pillow: only needed by build-time assets/generate_icon_ico.py,
        # not by the running app — keep it out of the bundle.
        "PIL", "cv2",
        "tensorflow", "tensorflow_intel", "keras",
        "jax", "flax",
        "datasets", "evaluate", "pyarrow",
        "sklearn", "scikit_learn",
        "boto3", "botocore", "s3transfer",
        "sqlalchemy", "nltk", "Crypto", "pytest",
        "IPython", "notebook", "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Agentic",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # No terminal window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico" if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Agentic",
)

# macOS: create a .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Agentic.app",
        icon="assets/icon.icns",
        bundle_identifier="com.agentic.app",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
        },
    )
