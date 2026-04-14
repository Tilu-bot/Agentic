# Agentic

A local AI assistant desktop application that runs open-source LLMs entirely in-process — no API keys, no cloud, no server required.

## Features

- **Fully local inference** — models run on your machine via HuggingFace `transformers`
- **Multi-model support** — Gemma, Llama, Mistral, Phi, and Qwen model families
- **ReAct + Reflexion loop** — up to 6 reasoning–action iterations with auto-synthesis on exhaustion
- **Autopilot routing** — classifies task intent, picks a model ladder, and applies a response quality gate
- **Parallel task execution** — skills run concurrently as TaskFibers with dependency tracking
- **Three-tier memory** — Fluid (RAM) → Crystal (episodic SQLite) → Bedrock (BM25-ranked semantic facts)
- **9 built-in skills** — filesystem, code runner, web fetch, memory ops, PDF/Excel/Word/PowerPoint reading
- **Native tool-calling** — Llama 3.1+, Qwen 2.5, Phi-4, and Mistral-Nemo use the model's own format
- **Persistent sessions** — SQLite-backed history that survives restarts
- **Cross-platform desktop app** — Windows, macOS, and Linux via PyQt6

## Supported Models

| Family | Example models |
|--------|---------------|
| Gemma | `google/gemma-3-1b-it`, `gemma-3-4b-it`, `gemma-3-12b-it` |
| Llama | `meta-llama/Llama-3.2-1B-Instruct`, `Llama-3.1-8B-Instruct` |
| Mistral | `mistralai/Mistral-7B-Instruct-v0.3` |
| Phi | `microsoft/Phi-4-mini-instruct`, `Phi-3.5-mini-instruct` |
| Qwen | `Qwen/Qwen2.5-1.5B-Instruct`, `Qwen2.5-7B-Instruct` |

Device is auto-selected: CUDA → MPS (Apple Silicon) → CPU.

## Installation

**Requirements:** Python 3.11+

```bash
cd agentic-app
pip install -r requirements.txt
```

### Optional: 4-bit quantization (GPU only)

```bash
pip install bitsandbytes>=0.43.0
```

## Usage

```bash
python main.py
```

## Architecture

Agentic uses a **Reactive Cortex Architecture (RCA)**:

```
User Input
    │
    ▼
Signal Lattice (event bus)
    │
    ▼
TaskOrchestrator — classifies intent, routes model ladder, quality gate
    │
    ▼
Cortex (ReAct loop, up to 6 iterations + Reflexion synthesis)
    ├── MemoryLattice  — Fluid / Crystal / Bedrock (BM25-ranked)
    ├── PromptWeaver   — builds system prompt; parses 4 skill-call formats
    ├── ModelNexus     — streams tokens from the local HF model
    └── TaskFabric     — dispatches skill calls as parallel TaskFibers
            │
            ▼
        SkillRegistry  — filesystem · code runner · web fetch · memory ops · document reader
```

Results are injected back into the reasoning loop, and the completed exchange is persisted to the Memory Lattice.

## Project Structure

```
agentic-app/
├── main.py                   # Entry point (launches PyQt6 UI)
├── requirements.txt          # All Python dependencies
├── core/
│   ├── cortex.py             # ReAct loop + Reflexion synthesis
│   ├── memory_lattice.py     # Fluid / Crystal / Bedrock + BM25 ranking
│   ├── signal_lattice.py     # Typed reactive event bus
│   ├── skill_registry.py     # Skill catalogue with per-skill timeouts
│   ├── task_fabric.py        # Parallel TaskFiber execution
│   └── task_orchestrator.py  # Autopilot routing + quality gate
├── model/
│   ├── gemma_nexus.py        # ModelNexus — multi-family HF inference + streaming
│   └── prompt_weaver.py      # Prompt assembly + skill-call parser
├── skills/
│   ├── base.py               # Abstract SkillBase
│   ├── filesystem.py         # read_file · write_file · list_directory
│   ├── code_runner.py        # run_python (AST sandbox + subprocess)
│   ├── web_reader.py         # fetch_web (SSRF-protected)
│   ├── memory_ops.py         # save_fact · recall_facts · recall_history
│   └── doc_reader.py         # read_pdf · read_excel · read_word · read_pptx
├── ui/                       # PyQt6 frontend
│   ├── pyqt_integrated.py    # Bootstrap + backend wiring
│   ├── main_window.py        # Main shell and navigation
│   ├── chat_view_qt.py       # Streaming chat panel
│   ├── task_panel_qt.py      # Live TaskFiber monitor
│   ├── settings_view_qt.py   # Configuration panel
│   ├── memory_view_qt.py     # Memory browser (all three tiers)
│   └── qt_bridge.py          # Thread-safe signal-to-Qt bridge
├── state/
│   ├── session.py            # Session lifecycle manager
│   └── store.py              # SQLite store
├── tests/                    # Test suite
└── utils/
    ├── config.py             # Thread-safe JSON config
    └── logger.py             # Rotating file + console logger
```

## Building a Distributable

### Windows — Single Installer `.exe` (recommended)

Produces `installer/Agentic-Setup.exe` — a wizard-based installer that handles
installation directory, Start Menu entry, Desktop shortcut, and an uninstaller,
just like any standard Windows application.

**Prerequisites:**
1. Python 3.11+ on PATH
2. [Inno Setup 6](https://jrsoftware.org/isdl.php) (free, installs to default path)

**Build:**
```bat
cd agentic-app
build_installer.bat
```

The script automatically:
1. Installs Python dependencies
2. Generates `assets/icon.ico`
3. Bundles the app with PyInstaller → `dist/Agentic/`
4. Compiles the Inno Setup script → `installer/Agentic-Setup.exe`

Distribute **`installer/Agentic-Setup.exe`** to users. Double-clicking it
starts the installation wizard.

### Portable Bundle (all platforms)

Produces `dist/Agentic/` — a folder containing `Agentic.exe` and its
dependencies. No installation required; copy the folder anywhere and run
`Agentic.exe`.

```bash
cd agentic-app
pyinstaller agentic.spec
```

### macOS `.app` Bundle

Running the same `pyinstaller agentic.spec` command on macOS additionally
produces `dist/Agentic.app` which can be dragged to `/Applications`.

