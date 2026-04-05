# Agentic

**Agentic** is a multi-task AI desktop application built on the original **Reactive Cortex Architecture (RCA)** – a novel agent design that uses signal-driven cognitive cycles, a three-tier memory lattice, and a parallel task fabric to orchestrate open-source language models running entirely in-process via HuggingFace `transformers`.

> ⚠️ This is original software. All architecture, code, and design were created from scratch after studying the landscape of existing agentic systems. No code was copied from any other project.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Reactive Cortex Architecture** | Signal-driven cognitive cycles – no polling loops |
| **Task Fabric** | Parallel execution of agent sub-tasks with dependency tracking |
| **Three-Tier Memory Lattice** | Fluid (working) → Crystal (episodic) → Bedrock (semantic facts) |
| **Multi-model support** | Gemma, Llama 3, Mistral, Phi, Qwen – any HF instruction model |
| **100% local inference** | Runs via HuggingFace `transformers`; no API keys, no server needed |
| **Streaming responses** | Token-by-token display with live progress |
| **Built-in Skills** | File I/O, web fetching, Python code execution, memory ops |
| **Desktop App** | Native window (tkinter), packaged with PyInstaller – no browser needed |
| **Persistent sessions** | SQLite-backed history; sessions survive restarts |

---

## 🧠 Architecture: Reactive Cortex Architecture (RCA)

Traditional agentic systems use a polling loop (perceive → think → act → repeat).
RCA replaces the loop with a **Deliberation Pulse** – a reactive cycle triggered by
typed signals flowing through the **Signal Lattice**.

```
User Input
    │
    ▼
[Signal Lattice]  ─────────────────────────────────────────────
    │                                                          │
    ▼                                                          │
[Cortex]                                                       │
  1. Assemble context from Memory Lattice                      │
  2. Weave system prompt (skills manifest + memory context)    │
  3. Stream response from Model Nexus ─────────────────────►  │
  4. Parse Intent Shards (@@SKILL:...@@ markers)               │
  5. Dispatch to Task Fabric (parallel fibers)                 │
  6. Inject skill results into response                        │
  7. Write to Memory Lattice                                   │
  8. Emit DELIBERATION_END signal ─────────────────────────►  │
    │                                                          │
    ▼                                                          ▼
[Task Fabric]                                          [UI Layer]
  • Parallel fibers with dep-graph                     • Chat panel
  • Priority scheduling                                • Task monitor
  • Signal emission on every transition                • Memory browser
                                                       • Settings
[Memory Lattice]
  • FLUID   → sliding window (RAM, 20 turns)
  • CRYSTAL → compressed episodic (SQLite)
  • BEDROCK → semantic facts (SQLite)

[Model Nexus]
  → HuggingFace transformers (runs in-process)
  → Supports Gemma, Llama, Mistral, Phi, Qwen and any HF model
  → TextIteratorStreamer for async token delivery
  → Lazy model load with in-memory caching
  → Chat template auto-detected from tokenizer (no manual formatting)
```

### Component Glossary

| Component | Role |
|-----------|------|
| **SignalLattice** | Typed reactive event mesh; decouples all components |
| **Cortex** | Central reasoning unit; drives the Deliberation Pulse |
| **TaskFabric** | Manages TaskFibers (parallel sub-tasks) |
| **MemoryLattice** | Three-tier memory: Fluid / Crystal / Bedrock |
| **SkillRegistry** | Self-describing tool/skill catalogue |
| **ModelNexus** | Direct HuggingFace transformers inference; TextIteratorStreamer for async tokens; multi-family model support |
| **PromptWeaver** | Assembles system + history prompts; role mapping adapts to active model family |

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.11+**
- No external server needed – the model runs directly in Python.

### 2. Install dependencies

```bash
cd agentic-app
pip install -r requirements.txt
```

> **GPU (recommended for larger models):** install PyTorch with CUDA support from
> [https://pytorch.org/get-started/locally](https://pytorch.org/get-started/locally).
> On CPU, use `google/gemma-3-1b-it` or `meta-llama/Llama-3.2-1B-Instruct` for acceptable speed.

---

## 🤖 Supported Models

Agentic works with **any HuggingFace instruction-tuned model** whose tokenizer ships a `chat_template`.  The model family is auto-detected and the correct role names / special tokens are applied automatically.

| Family | Example model IDs | Notes |
|--------|-------------------|-------|
| **Gemma** | `google/gemma-3-1b-it`, `gemma-3-4b-it`, `gemma-3-12b-it`, `gemma-2-9b-it` | Default; runs on CPU |
| **Llama 3** | `meta-llama/Llama-3.2-1B-Instruct`, `Llama-3.2-3B-Instruct`, `Llama-3.1-8B-Instruct` | Requires HF token (gated) |
| **Mistral** | `mistralai/Mistral-7B-Instruct-v0.3` | Good quality/speed balance |
| **Phi** | `microsoft/Phi-4-mini-instruct`, `Phi-3.5-mini-instruct` | Very compact, fast on CPU |
| **Qwen** | `Qwen/Qwen2.5-1.5B-Instruct`, `Qwen/Qwen2.5-7B-Instruct` | Strong multilingual support |

> **Custom models:** type any HuggingFace model ID directly in the Settings panel.
> The Quick-pick menu groups the models above by family for convenience.

### 3. Run the app

```bash
python main.py
```

On first launch the selected model is downloaded automatically from HuggingFace
Hub and cached in `~/.cache/huggingface/`.  Subsequent launches are instant.

---

## 📦 Build a Downloadable App

Agentic uses [PyInstaller](https://pyinstaller.org) to create a self-contained
desktop application – no Python installation required on the end-user's machine.

### Build (all platforms)

```bash
cd agentic-app
pip install pyinstaller transformers torch accelerate httpx huggingface_hub
pyinstaller agentic.spec
```

The built app will be in `dist/Agentic/`.

### Platform-specific

| Platform | Output | Launch |
|----------|--------|--------|
| **Windows** | `dist/Agentic/Agentic.exe` | Double-click |
| **macOS** | `dist/Agentic.app` | Double-click or `open dist/Agentic.app` |
| **Linux** | `dist/Agentic/Agentic` | `./dist/Agentic/Agentic` |

> **macOS tip:** `pyinstaller agentic.spec` creates a proper `.app` bundle that
> appears in Finder like any other application.

---

## 🗂 Project Structure

```
agentic-app/
├── main.py                   # Entry point
├── requirements.txt          # Dependencies
├── agentic.spec              # PyInstaller build spec
├── assets/
│   ├── icon.png              # App icon
│   └── generate_icon.py      # Icon generator (run once)
│
├── core/                     # Reactive Cortex Architecture core
│   ├── signal_lattice.py     # Typed reactive event mesh
│   ├── cortex.py             # Central reasoning unit
│   ├── task_fabric.py        # Parallel task execution
│   ├── memory_lattice.py     # Three-tier memory
│   └── skill_registry.py     # Skill/tool catalogue
│
├── model/                    # Model integration
│   ├── gemma_nexus.py        # ModelNexus: multi-family HF transformers inference (streaming)
│   └── prompt_weaver.py      # Dynamic prompt construction
│
├── skills/                   # Built-in skills
│   ├── base.py               # Abstract skill interface
│   ├── filesystem.py         # read_file, write_file, list_directory
│   ├── web_reader.py         # fetch_web
│   ├── code_runner.py        # run_python (sandboxed subprocess)
│   └── memory_ops.py         # save_fact, recall_facts, recall_history
│
├── ui/                       # Desktop GUI (tkinter)
│   ├── app.py                # Main window & layout
│   ├── chat_view.py          # Streaming chat panel
│   ├── task_panel.py         # Live task fiber monitor
│   ├── settings_view.py      # Configuration panel
│   ├── memory_view.py        # Memory browser
│   ├── components.py         # Reusable themed widgets
│   └── theme.py              # Color palettes & typography
│
├── state/                    # Persistence
│   ├── store.py              # SQLite store (sessions, crystal, bedrock)
│   └── session.py            # Session lifecycle manager
│
└── utils/                    # Utilities
    ├── config.py             # JSON config with thread-safe access
    └── logger.py             # Rotating file + console logger
```

---

## 🛠 Skill Invocation Protocol

The Cortex and Gemma communicate skill requests using a compact in-line markup:

```
@@SKILL:<skill_name> <json_args>@@
```

**Examples:**

```
@@SKILL:read_file {"path": "~/Documents/notes.txt"}@@
@@SKILL:fetch_web {"url": "https://example.com"}@@
@@SKILL:run_python {"code": "print(2 ** 10)"}@@
@@SKILL:save_fact {"category": "preference", "text": "User prefers Python"}@@
```

The PromptWeaver replaces these markers with the skill result before displaying
the response to the user.

---

## ⚙️ Configuration

Settings are stored in `~/.agentic/config.json`. You can edit them in the
**Settings** panel inside the app.

| Key | Default | Description |
|-----|---------|-------------|
| `model_id` | `google/gemma-3-1b-it` | HuggingFace model ID |
| `hf_token` | `` | HuggingFace token (for gated models) |
| `device` | `auto` | `auto` / `cpu` / `cuda` / `mps` |
| `quantize_4bit` | `false` | 4-bit quantization (GPU + bitsandbytes) |
| `working_memory_limit` | 20 | Fluid memory window (turns) |
| `max_parallel_tasks` | 4 | Concurrent TaskFibers |
| `theme` | `dark` | UI theme: `dark` or `light` |
| `streaming_enabled` | `true` | Stream tokens live |

---

## 📝 Adding Custom Skills

1. Create a new file in `skills/`.
2. Subclass `SkillBase` and implement `execute(**kwargs)`.
3. Set `name`, `description`, `parameters`, `required`, `tags`.
4. Call `YourSkill.register()` in your skill's `register_all()`.
5. Import and call `register_all()` in `ui/app.py`'s `_bootstrap()` method.

```python
from skills.base import SkillBase

class WeatherSkill(SkillBase):
    name = "get_weather"
    description = "Fetch current weather for a city."
    parameters = {"city": {"type": "string", "description": "City name"}}
    required = ["city"]
    tags = ["web", "data"]

    async def execute(self, city: str) -> str:
        # ... your implementation
        return f"Sunny in {city}"
```

---

## 🔒 Privacy & Security

- All data stays **100% local** – the model runs in-process via HuggingFace transformers.
- No telemetry, no analytics, no cloud sync, no external server.
- Code execution skill runs in a **sandboxed subprocess** with restricted builtins.
- Filesystem skill blocks access to system directories (`/etc`, `/bin`, etc.).

---

## 📄 License

MIT License. See [LICENSE](../LICENSE) for details.
