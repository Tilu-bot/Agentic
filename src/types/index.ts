// ── File System ──────────────────────────────────────────────────────────────

export interface FileEntry {
  name: string
  path: string
  isDirectory: boolean
  children?: FileEntry[]
  size?: number
  modifiedAt?: number
}

// ── Editor ───────────────────────────────────────────────────────────────────

export interface EditorTab {
  id: string
  path: string
  content: string
  savedContent: string
  language: string
  isDirty: boolean
  isLoading: boolean
}

// ── Agent ────────────────────────────────────────────────────────────────────

export type AgentMessageRole = 'user' | 'assistant' | 'system'

export interface ToolUseEvent {
  id: string
  toolName: string
  input: Record<string, unknown>
  output?: string
  error?: string
  status: 'running' | 'success' | 'error'
  durationMs?: number
}

export interface DiffProposal {
  id: string
  filePath: string
  originalContent: string
  proposedContent: string
  description: string
  status: 'pending' | 'accepted' | 'rejected'
}

export interface AgentMessage {
  id: string
  role: AgentMessageRole
  content: string
  timestamp: number
  toolUses?: ToolUseEvent[]
  diffProposals?: DiffProposal[]
  isStreaming?: boolean
}

export type AgentStatus = 'idle' | 'running' | 'planning' | 'error'

// ── Agent Update Events (main → renderer) ────────────────────────────────────

export type AgentUpdateEvent =
  | { type: 'stream_start'; messageId: string }
  | { type: 'stream_chunk'; messageId: string; chunk: string }
  | { type: 'stream_end'; messageId: string }
  | { type: 'tool_start'; toolUse: ToolUseEvent }
  | { type: 'tool_end'; toolUseId: string; output: string; error?: string; durationMs: number }
  | { type: 'diff_proposal'; proposal: DiffProposal }
  | { type: 'plan_proposed'; plan: string; steps: string[] }
  | { type: 'agent_done' }
  | { type: 'agent_error'; error: string }

// ── LLM Settings ─────────────────────────────────────────────────────────────

export type LLMProvider = 'anthropic' | 'openai' | 'ollama' | 'gemini'

export interface ProviderSettings {
  provider: LLMProvider
  model: string
  apiKey: string
  ollamaUrl: string
  maxTokens: number
  temperature: number
}

export const DEFAULT_MODELS: Record<LLMProvider, string[]> = {
  anthropic: ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-haiku-4-5', 'claude-3-5-sonnet-20241022'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o3-mini'],
  ollama: ['llama3.2', 'codellama', 'deepseek-coder', 'qwen2.5-coder', 'mistral'],
  gemini: ['gemini-2.5-pro', 'gemini-2.0-flash', 'gemini-1.5-pro']
}

// ── Checkpoints ───────────────────────────────────────────────────────────────

export interface Checkpoint {
  id: string
  timestamp: number
  description: string
  files: Record<string, string>
}

// ── Command Palette ───────────────────────────────────────────────────────────

export interface PaletteCommand {
  id: string
  label: string
  description?: string
  shortcut?: string
  icon?: string
  action: () => void
  category?: string
}

// ── App Panels ────────────────────────────────────────────────────────────────

export type SidebarPanel = 'files' | 'search' | 'agent' | 'settings'

export interface AppLayout {
  sidebarWidth: number
  agentPanelWidth: number
  terminalHeight: number
  showTerminal: boolean
  showAgentPanel: boolean
  activeSidebarPanel: SidebarPanel
}
