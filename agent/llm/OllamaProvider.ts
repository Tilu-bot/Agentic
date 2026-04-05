import { BaseProvider, LLMMessage, LLMResponse, LLMToolCall, ProviderConfig, StreamChunk } from './BaseProvider'
import { ToolDefinition } from '../tools/BaseTool'

interface OllamaMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
  tool_calls?: Array<{ function: { name: string; arguments: Record<string, unknown> } }>
}

interface OllamaResponse {
  message: OllamaMessage
  prompt_eval_count?: number
  eval_count?: number
  done: boolean
  done_reason?: string
}

export class OllamaProvider extends BaseProvider {
  get name(): string {
    return 'ollama'
  }

  async complete(
    messages: LLMMessage[],
    tools: ToolDefinition[],
    config: ProviderConfig,
    onStream?: (chunk: StreamChunk) => void
  ): Promise<LLMResponse> {
    const baseUrl = config.ollamaUrl.replace(/\/$/, '')
    const ollamaMessages: OllamaMessage[] = this.convertMessages(messages)

    const body = {
      model: config.model,
      messages: ollamaMessages,
      stream: !!onStream,
      options: {
        temperature: config.temperature,
        num_predict: config.maxTokens
      },
      tools: tools.map((t) => ({
        type: 'function',
        function: {
          name: t.name,
          description: t.description,
          parameters: t.parameters
        }
      }))
    }

    if (onStream) {
      return this.streamComplete(`${baseUrl}/api/chat`, body, onStream)
    }

    const response = await fetch(`${baseUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, stream: false })
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Ollama API error ${response.status}: ${errorText}`)
    }

    const data = (await response.json()) as OllamaResponse
    return this.parseResponse(data)
  }

  private async streamComplete(
    url: string,
    body: object,
    onStream: (chunk: StreamChunk) => void
  ): Promise<LLMResponse> {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Ollama API error ${response.status}: ${errorText}`)
    }

    if (!response.body) throw new Error('No response body')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullText = ''
    const toolCalls: LLMToolCall[] = []

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const event = JSON.parse(line) as OllamaResponse

          if (event.message?.content) {
            fullText += event.message.content
            onStream({ type: 'text', text: event.message.content })
          }

          if (event.message?.tool_calls) {
            for (const tc of event.message.tool_calls) {
              const id = `tool_${Date.now()}_${Math.random().toString(36).slice(2)}`
              toolCalls.push({ id, name: tc.function.name, input: tc.function.arguments })
              onStream({ type: 'tool_start', toolCallId: id, toolName: tc.function.name })
              onStream({ type: 'tool_end', toolCallId: id, toolInput: tc.function.arguments })
            }
          }

          if (event.done) break
        } catch {
          // Skip malformed JSON lines
        }
      }
    }

    onStream({ type: 'done' })

    return {
      content: fullText,
      toolCalls,
      inputTokens: 0,
      outputTokens: 0,
      stopReason: toolCalls.length > 0 ? 'tool_use' : 'end_turn'
    }
  }

  private convertMessages(messages: LLMMessage[]): OllamaMessage[] {
    return messages.map((msg): OllamaMessage => ({
      role: msg.role as OllamaMessage['role'],
      content: typeof msg.content === 'string'
        ? msg.content
        : (msg.content as Array<{ type: string; text?: string }>).map((b) => b.text ?? '').join('\n')
    }))
  }

  private parseResponse(data: OllamaResponse): LLMResponse {
    const toolCalls: LLMToolCall[] = (data.message.tool_calls ?? []).map((tc) => ({
      id: `tool_${Date.now()}`,
      name: tc.function.name,
      input: tc.function.arguments
    }))

    return {
      content: data.message.content ?? '',
      toolCalls,
      inputTokens: data.prompt_eval_count ?? 0,
      outputTokens: data.eval_count ?? 0,
      stopReason: toolCalls.length > 0 ? 'tool_use' : 'end_turn'
    }
  }
}
