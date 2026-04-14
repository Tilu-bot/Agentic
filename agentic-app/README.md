# Agentic

**Agentic** is a fully local, multi-task AI desktop application built on the original **Reactive Cortex Architecture (RCA)** – a novel agent design that uses signal-driven cognitive cycles, a three-tier memory lattice, and a parallel task fabric to orchestrate open-source language models running entirely in-process via HuggingFace `transformers`.

No API keys. No cloud. No server. Everything runs on your own machine.

> ⚠️ This is original software. All architecture, code, and design were created from scratch. No code was copied from any other project.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Reactive Cortex Architecture** | Signal-driven cognitive cycles – no polling loops |
| **ReAct + Reflexion loop** | Up to 6 reasoning–action iterations per response; auto-synthesis when iterations are exhausted |
| **Task Fabric** | Parallel execution of agent sub-tasks with dependency tracking |
| **Three-Tier Memory Lattice** | Fluid (working) → Crystal (episodic) → Bedrock (semantic facts) |
| **BM25 memory ranking** | Relevant facts are ranked by BM25 score and injected into every prompt |
| **Multi-model support** | Gemma 3, Llama 3, Mistral, Phi-4, Qwen 2.5 – any HF instruction model |
| **Autopilot routing** | Classifies task intent, picks model ladder, escalates on failures, and applies a response quality gate |
| **Native tool-calling** | Llama 3.1+, Qwen 2.5, Phi-4, Mistral-Nemo use the model's own tool-call format |
| **100% local inference** | Runs via HuggingFace `transformers`; no API keys, no server needed |
| **Streaming responses** | Token-by-token display with live progress |
| **9 built-in skills** | File I/O, web fetching, Python execution, memory ops, PDF/Excel/Word/PowerPoint reading |
| **Desktop App** | Native window (PyQt6 integrated), packaged with PyInstaller – no browser needed |
| **Persistent sessions** | SQLite-backed history; sessions survive restarts |

---

## 🖥️ Installation Guide

### Requirements

| Requirement | Details |
|-------------|---------|
| **Operating system** | Windows 10/11 · macOS 12+ · Ubuntu 20.04+ (or any modern Linux) |
| **Python** | 3.11 or 3.12 (3.13 not yet tested) |
| **RAM** | 8 GB minimum · 16 GB recommended for 7B+ models |
| **Disk space** | ~5 GB for a 1B model · ~15 GB for a 7B model (one-time download) |
| **GPU (optional)** | NVIDIA with CUDA 12 · Apple Silicon (MPS) · AMD with ROCm |

---

### Windows

**Step 1 – Install Python 3.11 or 3.12**

Download from [https://python.org/downloads](https://python.org/downloads).
During installation check **"Add Python to PATH"**.

Verify in a Command Prompt or PowerShell window:

```powershell
python --version
# Should print: Python 3.11.x or 3.12.x
```

**Step 2 – Clone or download the repository**

```powershell
# Option A: git (recommended)
git clone https://github.com/Tilu-bot/Agentic.git
cd Agentic\agentic-app

# Option B: download ZIP from GitHub → extract → open the agentic-app folder
```

**Step 3 – Create a virtual environment (recommended)**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

**Step 4 – Install dependencies**

```powershell
pip install -r requirements.txt
```

> **NVIDIA GPU (faster inference):** replace the plain `torch` with the CUDA build.
> Go to [https://pytorch.org/get-started/locally](https://pytorch.org/get-started/locally),
> select your CUDA version, and copy the install command. Run it *before* `pip install -r requirements.txt`.
>
> Example for CUDA 12.1:
> ```powershell
> pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
> pip install -r requirements.txt
> ```

**Step 5 – Run Agentic**

```powershell
python main.py
```

---

### macOS

**Step 1 – Install Python**

Option A – Homebrew (recommended):

```bash
brew install python@3.11
```

Option B – Download the macOS installer from [https://python.org/downloads](https://python.org/downloads).

Verify:

```bash
python3 --version
```

**Step 2 – Clone the repository**

```bash
git clone https://github.com/Tilu-bot/Agentic.git
cd Agentic/agentic-app
```

**Step 3 – Create a virtual environment**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Step 4 – Install dependencies**

```bash
pip install -r requirements.txt
```

> **Apple Silicon (M1 / M2 / M3 / M4):** PyTorch supports Metal Performance Shaders (MPS) for GPU
> acceleration out of the box. No extra steps needed – set `device` to `mps` in Settings.

**Step 5 – Run Agentic**

```bash
python main.py
```

---

### Linux (Ubuntu / Debian)

**Step 1 – Install Python and system dependencies**

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip git -y
```

**Step 2 – Clone the repository**

```bash
git clone https://github.com/Tilu-bot/Agentic.git
cd Agentic/agentic-app
```

**Step 3 – Create a virtual environment**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

**Step 4 – Install dependencies**

```bash
pip install -r requirements.txt
```

> **NVIDIA GPU:** install the CUDA-enabled PyTorch wheel first (see the Windows guide above for the URL pattern), then run `pip install -r requirements.txt`.

**Step 5 – Run Agentic**

```bash
python main.py
```

---

### First Launch

1. The app window opens. A **model download** starts automatically in the background (default model: `google/gemma-3-1b-it`, ~2.5 GB).
2. A progress bar shows download status. The first launch may take a few minutes depending on your internet speed.
3. Once the model loads, the chat panel becomes active. Type a message and press **Enter** or click **Send**.
4. Model files are cached in `~/.cache/huggingface/` – subsequent launches are instant.

---

## 🤖 Supported Models

Agentic works with **any HuggingFace instruction-tuned model** that ships a `chat_template` in its tokenizer.  The model family is auto-detected – role names and special tokens are applied automatically.

| Family | Recommended model IDs | Notes |
|--------|-----------------------|-------|
| **Gemma 3** | `google/gemma-3-1b-it` · `gemma-3-4b-it` · `gemma-3-12b-it` | Default; 1B runs on CPU |
| **Gemma 2** | `google/gemma-2-9b-it` · `gemma-2-27b-it` | Older but strong |
| **Llama 3** | `meta-llama/Llama-3.2-1B-Instruct` · `3.2-3B` · `3.1-8B-Instruct` | Gated – HF token required |
| **Mistral** | `mistralai/Mistral-7B-Instruct-v0.3` · `Mistral-Nemo-Instruct-2407` | Great quality/speed ratio |
| **Phi-4** | `microsoft/Phi-4-mini-instruct` · `Phi-3.5-mini-instruct` | Very compact, CPU-friendly |
| **Qwen 2.5** | `Qwen/Qwen2.5-1.5B-Instruct` · `Qwen2.5-7B-Instruct` | Strong multilingual support |

> **Custom model:** type any HuggingFace model ID in the **Settings → Model ID** field.

### Model size vs. hardware guide

| Model size | RAM needed | Recommended device |
|------------|------------|--------------------|
| 1–3 B | 4–6 GB | CPU or any GPU |
| 4–7 B | 8–12 GB | GPU strongly recommended |
| 8–13 B | 16+ GB | GPU required |
| 27 B+ | 48+ GB | Multi-GPU or 4-bit quant |

### Gated models (Llama, some Mistral)

1. Create a free account at [https://huggingface.co](https://huggingface.co).
2. Accept the model license on the model's HuggingFace page.
3. Generate an access token at [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
4. Paste the token in **Settings → HuggingFace Token**.

---

## 🚀 Running the App

```bash
# Activate your virtual environment first (if you created one)
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows

cd agentic-app
python main.py
```

### Autopilot routing controls

Autopilot is enabled by default and uses config keys stored in your Agentic config file:

- `autopilot_enabled`
- `autopilot_fast_model_id`
- `autopilot_code_model_id`
- `autopilot_research_model_id`
- `autopilot_longrun_model_id`
- `autopilot_fallback_models` (comma-separated)
- `autopilot_quality_gate_enabled`
- `autopilot_quality_threshold` (percentage, e.g. `60`)
- `autopilot_escalation_enabled`
- `autopilot_escalate_on_error_ratio` (percentage, e.g. `50`)
- `autopilot_checkpoint_every_n`

### Evaluate routing decisions

Use the built-in evaluator with a JSONL dataset:

```bash
python eval_router.py --dataset autopilot_eval.jsonl
```

Dataset format:

```json
{"query": "fix failing pytest in parser", "expected_task_kind": "coding"}
{"query": "latest model releases this week", "expected_task_kind": "research"}
```

### UI panels

| Panel | What it shows |
|-------|---------------|
| **Chat** | Main conversation with streaming token output |
| **Tasks** | Live view of all running skill invocations (Task Fabric fibers) |
| **Memory** | Browse Fluid / Crystal / Bedrock memory tiers |
| **Settings** | Change model, device, theme, memory limits, and all other options |

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
[Cortex – ReAct loop, up to 6 iterations]                     │
  1. Assemble context from Memory Lattice (BM25-ranked)        │
  2. Weave system prompt (skills manifest + memory context)    │
  3. Stream response from Model Nexus ─────────────────────►  │
  4. Parse skill calls (4 formats supported)                   │
  5. Dispatch to Skill Registry → Task Fabric                  │
  6. Feed observations back → next iteration                   │
  7. On exhaustion → Reflexion synthesis pass                  │
  8. Write to Memory Lattice                                   │
  9. Emit DELIBERATION_END signal ─────────────────────────►  │
    │                                                          │
    ▼                                                          ▼
[Task Fabric]                                          [UI Layer]
  • Parallel fibers with dep-graph                     • Chat panel
  • Priority scheduling                                • Task monitor
  • Signal emission on every transition                • Memory browser
                                                       • Settings
[Memory Lattice]
  • FLUID   → sliding window (RAM, 20 turns by default)
  • CRYSTAL → compressed episodic (SQLite)
  • BEDROCK → semantic facts ranked by BM25 (SQLite)

[Model Nexus]
  → HuggingFace transformers (runs in-process, no server)
  → Auto-detects model family (Gemma / Llama / Mistral / Phi / Qwen)
  → TextIteratorStreamer for async token delivery
  → Native tool-calling for Llama 3.1+, Qwen 2.5, Phi-4, Mistral-Nemo
  → Lazy model load with in-memory caching
```

### Component glossary

| Component | Role |
|-----------|------|
| **SignalLattice** | Typed reactive event mesh; decouples all components |
| **Cortex** | Central reasoning unit; drives the Deliberation Pulse |
| **TaskFabric** | Manages TaskFibers (parallel sub-tasks) |
| **MemoryLattice** | Three-tier memory: Fluid / Crystal / Bedrock |
| **SkillRegistry** | Self-describing tool/skill catalogue; enforces per-skill timeouts |
| **ModelNexus** | Direct HuggingFace transformers inference; streaming; multi-family support |
| **PromptWeaver** | Assembles system + history prompts; parses 4 skill-call formats |

---

## 🛠️ Built-in Skills

All skills are registered automatically at startup.  The model can invoke any of them using the skill-call protocol.

### Filesystem

| Skill | Description | Key parameters |
|-------|-------------|----------------|
| `read_file` | Read a text file | `path`, `max_chars` (default 4000) |
| `write_file` | Write or append to a file | `path`, `content`, `append` |
| `list_directory` | List files in a directory | `path`, `recursive`, `max_items` |

### Web

| Skill | Description | Key parameters |
|-------|-------------|----------------|
| `fetch_web` | Fetch and return the text of a web page | `url`, `max_chars` (default 8000) |

> SSRF-protected: private/loopback IP ranges are blocked.

### Code

| Skill | Description | Key parameters |
|-------|-------------|----------------|
| `run_python` | Execute Python code in a sandboxed subprocess | `code`, `timeout_s` |

> Two-layer sandbox: AST import allowlist + subprocess isolation with stdout/stderr capture.

### Memory

| Skill | Description | Key parameters |
|-------|-------------|----------------|
| `save_fact` | Store a semantic fact in Bedrock memory | `category`, `text` |
| `recall_facts` | Retrieve Bedrock facts (BM25-ranked) | `query`, `limit` |
| `recall_history` | Retrieve recent Crystal (episodic) memories | `limit` |

### Documents

| Skill | Description | Key parameters | Requires |
|-------|-------------|----------------|---------|
| `read_pdf` | Extract text from a PDF file | `path`, `pages`, `max_chars` | `pypdf` |
| `read_excel` | Read an `.xlsx` workbook as Markdown tables | `path`, `sheet`, `max_rows`, `max_chars` | `openpyxl` |
| `read_word` | Extract text and tables from a `.docx` | `path`, `include_tables`, `max_chars` | `python-docx` |
| `read_pptx` | Extract slide text from a `.pptx` | `path`, `slides`, `max_chars` | `python-pptx` |

All document libraries are included in `requirements.txt` and installed automatically.

---

## 🔧 Skill Invocation Protocol

The model can request skills using any of four supported formats.  The most common is the `@@SKILL@@` inline markup:

```
@@SKILL:<skill_name> <json_args>@@
```

**Examples:**

```
@@SKILL:read_file {"path": "~/Documents/notes.txt"}@@
@@SKILL:fetch_web {"url": "https://docs.python.org/3/"}@@
@@SKILL:run_python {"code": "import math; print(math.pi)"}@@
@@SKILL:save_fact {"category": "preference", "text": "User prefers dark mode"}@@
@@SKILL:read_pdf {"path": "~/report.pdf", "pages": "1,2,3"}@@
@@SKILL:read_excel {"path": "~/data.xlsx", "sheet": "Summary"}@@
```

Models that support native tool-calling (Llama 3.1+, Qwen 2.5, Phi-4, Mistral-Nemo) use the model's own `<tool_call>` / `[TOOL_CALLS]` format instead.

---

## ⚙️ Configuration

Settings are stored in `~/.agentic/config.json`.  Edit them in the **Settings** panel or directly in the JSON file.

| Key | Default | Range / Options | Description |
|-----|---------|-----------------|-------------|
| `model_id` | `google/gemma-3-1b-it` | any HF model ID | Active model |
| `hf_token` | `""` | — | HuggingFace access token (gated models only) |
| `device` | `auto` | `auto` `cpu` `cuda` `mps` | Inference device |
| `quantize_4bit` | `false` | `true` / `false` | 4-bit quantisation (GPU + `bitsandbytes`) |
| `theme` | `dark` | `dark` / `light` | UI colour theme |
| `font_size` | `13` | 8 – 32 | Chat font size (px) |
| `streaming_enabled` | `true` | `true` / `false` | Stream tokens live |
| `working_memory_limit` | `20` | 5 – 200 | Fluid memory window (conversation turns) |
| `max_parallel_tasks` | `4` | 1 – 32 | Concurrent TaskFibers |
| `skill_timeout_s` | `30` | 5 – 300 | Per-skill timeout (seconds) |
| `skill_retry_budget` | `1` | 0 – 3 | Retry attempts on skill error |
| `react_max_iterations` | `6` | 1 – 20 | Max reasoning–action iterations per deliberation |
| `context_limit_tokens` | `4096` | 512 – 131072 | Prompt token budget (older messages trimmed at 85%) |
| `log_level` | `INFO` | `DEBUG` `INFO` `WARNING` `ERROR` | Log verbosity |

### Enabling 4-bit quantisation (GPU only)

```bash
pip install bitsandbytes
```

Then set `quantize_4bit` to `true` in Settings.  Halves VRAM usage for large models.

---

## 📝 Adding Custom Skills

1. Create a new Python file in `agentic-app/skills/`.
2. Subclass `SkillBase` and implement `async execute(**kwargs)`.
3. Set class attributes: `name`, `description`, `parameters`, `required`, `tags`.
4. Add a `register_all()` function that calls `YourSkill.register()`.
5. Import and call `register_all()` inside `_bootstrap()` in `ui/pyqt_integrated.py`.

**Example – a simple weather skill:**

```python
from skills.base import SkillBase

class WeatherSkill(SkillBase):
    name = "get_weather"
    description = "Return the current weather for a city."
    parameters = {
        "city": {"type": "string", "description": "City name, e.g. 'London'"},
    }
    required = ["city"]
    tags = ["web", "data"]

    async def execute(self, city: str) -> str:
        # Replace with a real weather API call
        return f"Weather in {city}: Sunny, 22°C"

def register_all() -> None:
    WeatherSkill.register()
```

In `ui/pyqt_integrated.py` inside `_bootstrap()`:

```python
from skills.weather import register_all as reg_weather
reg_weather()
```

---

## 📦 Building a Standalone App (no Python required)

Agentic uses [PyInstaller](https://pyinstaller.org) to create a self-contained
executable that does not require Python to be installed on the target machine.

```bash
cd agentic-app
pip install -r requirements.txt   # includes pyinstaller
pyinstaller agentic.spec
```

| Platform | Output path | How to run |
|----------|-------------|------------|
| **Windows** | `dist/Agentic/Agentic.exe` | Double-click the `.exe` |
| **macOS** | `dist/Agentic.app` | Double-click in Finder or `open dist/Agentic.app` |
| **Linux** | `dist/Agentic/Agentic` | `chmod +x dist/Agentic/Agentic && ./dist/Agentic/Agentic` |

> Build on the target OS. PyInstaller does not cross-compile.

---

## 🧪 Running Tests

```bash
cd agentic-app
pip install pytest          # if not already installed
python -m pytest tests/ -v
```

Core and integration tests covering: config validation, BM25 memory ranking, prompt assembly, skill-call parsing, and frontend/backend smoke checks.

---

## 🗂️ Project Structure

```
agentic-app/
├── main.py                   # Application entry point
├── requirements.txt          # All Python dependencies
├── agentic.spec              # PyInstaller build specification
├── assets/
│   ├── icon.png              # Application icon
│   └── generate_icon.py      # Icon generator (run once to regenerate)
│
├── core/                     # Reactive Cortex Architecture
│   ├── signal_lattice.py     # Typed reactive event mesh
│   ├── cortex.py             # Deliberation Pulse + ReAct loop + Reflexion
│   ├── task_fabric.py        # Parallel TaskFiber execution
│   ├── task_orchestrator.py  # Autopilot routing + quality gate
│   ├── memory_lattice.py     # Fluid / Crystal / Bedrock memory + BM25 ranking
│   └── skill_registry.py     # Skill catalogue; invocation with timeout enforcement
│
├── model/                    # LLM integration
│   ├── gemma_nexus.py        # ModelNexus: multi-family HF transformers + streaming
│   └── prompt_weaver.py      # Prompt assembly + 4-format skill-call parser
│
├── skills/                   # Built-in skills (9 total)
│   ├── base.py               # Abstract SkillBase
│   ├── filesystem.py         # read_file · write_file · list_directory
│   ├── web_reader.py         # fetch_web (SSRF-protected)
│   ├── code_runner.py        # run_python (AST sandbox + subprocess)
│   ├── memory_ops.py         # save_fact · recall_facts · recall_history
│   └── doc_reader.py         # read_pdf · read_excel · read_word · read_pptx
│
├── ui/                       # Frontend (PyQt6 standardized)
│   ├── pyqt_integrated.py    # Frontend bootstrap + backend wiring
│   ├── main_window.py        # Main shell and navigation
│   ├── chat_view_qt.py       # Streaming chat panel
│   ├── task_panel_qt.py      # Live TaskFiber monitor
│   ├── settings_view_qt.py   # Configuration panel
│   ├── memory_view_qt.py     # Memory browser (all three tiers)
│   └── qt_bridge.py          # Thread-safe bridge from signals to Qt UI
│
├── state/                    # Persistence layer
│   ├── store.py              # SQLite store (sessions · crystal · bedrock)
│   └── session.py            # Session lifecycle manager
│
├── tests/                    # Test suite (76 tests)
│   ├── conftest.py           # Shared fixtures and sys.path setup
│   ├── test_config.py        # Config validation tests
│   ├── test_memory_lattice.py # BM25, context assembly tests
│   ├── test_prompt_weaver.py  # Skill-call parsing tests
│   ├── test_task_orchestrator.py # Routing and quality gate tests
│   └── test_web_reader.py    # Web fetch / SSRF guard tests
│
└── utils/                    # Utilities
    ├── config.py             # Thread-safe JSON config with schema validation
    └── logger.py             # Rotating file + console logger
```

---

## 🔒 Privacy & Security

- **100% local** – the model runs in-process via HuggingFace `transformers`. No data ever leaves your machine.
- **No telemetry, no analytics, no cloud sync.**
- **Code execution** runs in a sandboxed subprocess. Layer 1: AST import allowlist rejects dangerous modules before execution. Layer 2: subprocess with captured stdout/stderr and a hard timeout.
- **Filesystem** skill rejects access to system directories (`/etc`, `/bin`, `/sys`, `/proc`, etc.) using a parent-chain walk that cannot be bypassed with `..` or symlinks.
- **Web fetching** blocks private/loopback/link-local IP ranges (SSRF protection). Hostname is resolved before connecting.
- **Skill timeouts** enforced via `asyncio.wait_for` – a misbehaving skill cannot stall the agent indefinitely.

---

## 🩺 Troubleshooting

### App window doesn't open

- **Linux:** make sure the required Qt libraries are available. On Ubuntu/Debian: `sudo apt install libgl1 libegl1`
- **macOS:** if using a Homebrew Python, ensure PyQt6 was installed in the same environment: `pip install PyQt6 PyQt6-WebEngine`

### "No module named 'transformers'" / import errors

Make sure your virtual environment is activated before running the app:

```bash
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### Model download is very slow

The model is downloaded from HuggingFace Hub to `~/.cache/huggingface/`.  Once downloaded it is cached – subsequent launches are instant.  To change the cache location set the `HF_HOME` environment variable.

### Out of memory / model fails to load

- Switch to a smaller model (e.g. `google/gemma-3-1b-it` or `Qwen/Qwen2.5-1.5B-Instruct`).
- Enable 4-bit quantisation (GPU only): `pip install bitsandbytes`, then set `quantize_4bit: true` in Settings.
- Set `device: cpu` if your GPU has less than 6 GB VRAM.

### Llama / gated model gives "401 Unauthorized"

- Accept the model license on [https://huggingface.co](https://huggingface.co).
- Paste your HuggingFace access token in **Settings → HuggingFace Token**.

### Responses are very slow on CPU

Use a 1B–3B parameter model.  On a modern laptop CPU expect ~2–10 tokens/second for a 1B model.  A GPU is recommended for 7B+ models.

### Where are my chat sessions stored?

All data (sessions, memory, config) is stored in `~/.agentic/` (Linux/macOS) or `%USERPROFILE%\.agentic\` (Windows).  The SQLite database is `~/.agentic/agentic.db`.

---

## 📄 License

MIT License. See [LICENSE](../LICENSE) for details.
