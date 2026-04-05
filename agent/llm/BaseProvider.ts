import { ToolDefinition } from '../tools/BaseTool'

export interface LLMMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string | LLMContentBlock[]
  toolCallId?: string
  toolName?: string
}

export interface LLMContentBlock {
  type: 'text' | 'tool_use' | 'tool_result'
  text?: string
  id?: string
  name?: string
  input?: Record<string, unknown>
  content?: string
  isError?: boolean
}

export interface LLMToolCall {
  id: string
  name: string
  input: Record<string, unknown>
}

export interface LLMResponse {
  content: string
  toolCalls: LLMToolCall[]
  inputTokens: number
  outputTokens: number
  stopReason: 'end_turn' | 'tool_use' | 'max_tokens' | 'stop_sequence'
}

export interface StreamChunk {
  type: 'text' | 'tool_start' | 'tool_input_delta' | 'tool_end' | 'done'
  text?: string
  toolCallId?: string
  toolName?: string
  toolInputDelta?: string
  toolInput?: Record<string, unknown>
  response?: LLMResponse
}

export interface ProviderConfig {
  model: string
  apiKey: string
  ollamaUrl: string
  maxTokens: number
  temperature: number
}

export abstract class BaseProvider {
  abstract get name(): string

  abstract complete(
    messages: LLMMessage[],
    tools: ToolDefinition[],
    config: ProviderConfig,
    onStream?: (chunk: StreamChunk) => void
  ): Promise<LLMResponse>
}
