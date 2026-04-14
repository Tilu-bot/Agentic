# Agentic

A local AI assistant desktop application that runs open-source LLMs entirely in-process — no API keys, no cloud, no server required.

## Features

- **Fully local inference** — models run on your machine via HuggingFace `transformers`
- **Multi-model support** — Gemma, Llama, Mistral, Phi, and Qwen model families
- **Parallel task execution** — skills run concurrently as TaskFibers
- **Built-in skills** — filesystem, code runner, web fetch, memory operations
- **Persistent memory** — conversation history saved across sessions
- **Cross-platform** — Windows, macOS, and Linux via PyQt6

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
User input
    │
    ▼
Signal Lattice (event bus)
    │
    ▼
Cortex (async reasoning loop, background thread)
    ├── TaskOrchestrator — classifies requests and selects routing strategy
    ├── MemoryLattice  — retrieves conversation context
    ├── PromptWeaver   — builds system prompt with skill manifest
    ├── ModelNexus     — streams tokens from the local HF model
    └── TaskFabric     — dispatches @@SKILL:...@@ markers as parallel TaskFibers
            │
            ▼
        SkillRegistry  — filesystem · code runner · web fetch · memory ops
```

Results are injected back into the stream and the completed exchange is persisted to memory.

## Project Structure

```
agentic-app/
├── main.py              # Entry point
├── core/
│   ├── cortex.py        # Central reasoning loop
│   ├── memory_lattice.py
│   ├── signal_lattice.py
│   ├── skill_registry.py
│   ├── task_fabric.py
│   └── task_orchestrator.py
├── model/
│   ├── gemma_nexus.py   # ModelNexus — HuggingFace inference + streaming
│   └── prompt_weaver.py
├── skills/
│   ├── base.py
│   ├── filesystem.py
│   ├── code_runner.py
│   ├── web_reader.py
│   ├── memory_ops.py
│   └── doc_reader.py
├── ui/
│   ├── pyqt_integrated.py  # Frontend bootstrap + backend wiring
│   ├── chat_view_qt.py
│   ├── task_panel_qt.py
│   ├── settings_view_qt.py
│   └── memory_view_qt.py
├── state/
│   ├── session.py
│   └── store.py
└── utils/
    ├── config.py
    └── logger.py
```

## Building a Distributable

### Recommended for non-technical users

Publish prebuilt binaries in GitHub Releases so users can download and run without
installing Python or dependencies.

### Maintainer packaging workflow

1. Build on the target OS (Windows for `.exe`, macOS for `.app`, Linux for ELF).
2. Use PyInstaller to package the app from `agentic-app/`.
3. Upload produced artifacts to a tagged GitHub Release.

This repository intentionally keeps source and runtime code clean; installer helper
scripts are not required for end-user installation.

