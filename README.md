# Nexus Agent

> AI-powered coding desktop app — VS Code style, locally run, multi-provider LLM.

Nexus Agent is a full desktop application (Electron + React + Monaco Editor) that embeds an AI agent capable of reading, writing, running, and searching your codebase — with a human-in-the-loop diff review workflow.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Monaco Editor** | Full VS Code editor with syntax highlighting, multi-tab, breadcrumbs |
| **File Explorer** | Real filesystem tree sidebar with create/delete/rename |
| **Integrated Terminal** | Real PTY terminal (xterm.js + node-pty) with your shell |
| **Agent Chat Panel** | Stream LLM responses, see tool calls in real time |
| **Diff Viewer** | Review every file change before accepting it |
| **Command Palette** | `Ctrl+Shift+P` for all commands |
| **Multi-provider LLM** | Anthropic Claude, OpenAI GPT, Google Gemini, local Ollama |
| **ReAct Agent Loop** | Observe → Think → Act loop with up to 20 iterations |
| **Search** | Full-text search across your codebase |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Electron App (UI)                       │
│  ┌──────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │  File    │  │  Monaco Editor   │  │  Agent Panel  │  │
│  │  Tree    │  │  (multi-tab)     │  │  (chat + diffs│  │
│  └──────────┘  └──────────────────┘  └───────────────┘  │
│  ┌─────────────────────────────────────────────────────┐ │
│  │         Integrated Terminal (xterm.js)              │ │
│  └─────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │ Electron IPC (contextBridge)
┌────────────────────────▼────────────────────────────────┐
│              Agent Runtime (main process)                │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  ReAct Loop: observe → think → act → observe        │ │
│  └─────────────────────────────────────────────────────┘ │
│  ┌─────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ Tool Registry│  │ LLM Providers  │  │Context Manager│ │
│  │ read_file   │  │ Anthropic      │  │               │  │
│  │ write_file  │  │ OpenAI         │  │ Sliding window│  │
│  │ run_command │  │ Ollama (local) │  │               │  │
│  │ search_files│  │ Gemini         │  │               │  │
│  │ apply_edit  │  └────────────────┘  └──────────────┘  │
│  │ web_fetch   │                                         │
│  └─────────────┘                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- **Node.js 18+**
- **npm 9+**
- An API key for your LLM provider of choice (or [Ollama](https://ollama.ai) for local/free)

### Install & Run

```bash
# Install dependencies
npm install

# Start in development mode
npm run dev

# Build for production
npm run build

# Package as installable app
npm run package
```

### Configure LLM Provider

Open the **Settings** panel (gear icon in the activity bar) and:

1. Select your provider (Anthropic, OpenAI, Ollama, Gemini)
2. Enter your API key
3. Pick a model

For **Ollama** (free, local), install it from [ollama.ai](https://ollama.ai), pull a model:
```bash
ollama pull llama3.2
```
Then select "Ollama" in settings — no API key needed.

---

## 🧰 Agent Tools

| Tool | Description |
|---|---|
| `read_file` | Read any file in the workspace |
| `write_file` | Create or overwrite a file |
| `apply_edit` | Surgical search-and-replace in a file |
| `list_directory` | Explore project structure |
| `run_command` | Run shell commands (tests, builds, installs) |
| `search_files` | Full-text/regex search across codebase |
| `web_fetch` | Fetch documentation from the internet |

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+P` | Open Command Palette |
| `Ctrl+S` | Save current file |
| `Ctrl+`` ` | Toggle terminal |
| `Enter` (in chat) | Send message to agent |
| `Shift+Enter` | New line in chat |

---

## 🔒 Security

- Renderer process runs with `contextIsolation: true` and `nodeIntegration: false`
- All filesystem and agent access goes through the Electron `contextBridge`
- `write_file` and `apply_edit` tools refuse to write outside the workspace
- `run_command` blocks obviously destructive commands (rm -rf /, etc.)
- API keys are never persisted to localStorage

---

## 📁 Project Structure

```
nexus-agent/
├── electron/
│   ├── main/         # Electron main process
│   │   ├── index.ts  # Window management
│   │   └── ipc/      # IPC handlers (fs, terminal, agent)
│   └── preload/      # Context bridge API
├── src/              # React renderer
│   ├── components/   # UI components
│   ├── stores/       # Zustand state
│   └── types/        # Shared TypeScript types
└── agent/            # Agent runtime (runs in main process)
    ├── tools/        # Tool implementations
    ├── llm/          # LLM provider adapters
    ├── loop/         # ReAct agent loop
    └── context/      # Context window management
```

---

## 📜 License

MIT — build with it, ship with it, fork it.
