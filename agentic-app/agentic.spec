# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build specification for the Agentic desktop app.

Usage:
    pip install pyinstaller transformers torch accelerate httpx huggingface_hub
    cd agentic-app
    pyinstaller agentic.spec

Output: dist/Agentic/ (folder mode) or dist/Agentic.exe (Windows one-file)
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
        # HuggingFace / PyTorch
        "transformers",
        "transformers.models.gemma",
        "transformers.models.gemma2",
        "transformers.generation",
        "transformers.generation.streamers",
        "torch",
        "accelerate",
        "huggingface_hub",
        # httpx (web-fetch skill)
        "httpx",
        "httpcore",
        "anyio",
        "certifi",
        "h11",
        "idna",
        "sniffio",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy unused packages
        "matplotlib", "pandas", "scipy",
        "PIL", "cv2", "tensorflow",
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
