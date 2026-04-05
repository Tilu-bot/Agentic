import { BaseProvider, LLMMessage, LLMResponse, LLMToolCall, ProviderConfig, StreamChunk } from './BaseProvider'
import { ToolDefinition } from '../tools/BaseTool'

interface AnthropicContentBlock {
  type: 'text' | 'tool_use'
  text?: string
  id?: string
  name?: string
  input?: Record<string, unknown>
}

interface AnthropicApiResponse {
  content: AnthropicContentBlock[]
  usage: { input_tokens: number; output_tokens: number }
  stop_reason: string
}

interface AnthropicMessage {
  role: 'user' | 'assistant'
  content: string | AnthropicContentBlock[]
}

export class AnthropicProvider extends BaseProvider {
  get name(): string {
    return 'anthropic'
  }

  async complete(
    messages: LLMMessage[],
    tools: ToolDefinition[],
    config: ProviderConfig,
    onStream?: (chunk: StreamChunk) => void
  ): Promise<LLMResponse> {
    const systemMessage = messages.find((m) => m.role === 'system')
    const nonSystemMessages = messages.filter((m) => m.role !== 'system')

    // Convert to Anthropic format
    const anthropicMessages: AnthropicMessage[] = this.convertMessages(nonSystemMessages)

    const body: Record<string, unknown> = {
      model: config.model,
      max_tokens: config.maxTokens,
      messages: anthropicMessages,
      tools: tools.map((t) => ({
        name: t.name,
        description: t.description,
        input_schema: t.parameters
      }))
    }

    if (systemMessage) {
      body['system'] = typeof systemMessage.content === 'string'
        ? systemMessage.content
        : (systemMessage.content as Array<{ text?: string }>).map((b) => b.text ?? '').join('\n')
    }

    if (onStream) {
      body['stream'] = true
      return this.streamComplete(body, config, onStream)
    }

    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': config.apiKey,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Anthropic API error ${response.status}: ${errorText}`)
    }

    const data = (await response.json()) as AnthropicApiResponse
    return this.parseResponse(data)
  }

  private async streamComplete(
    body: Record<string, unknown>,
    config: ProviderConfig,
    onStream: (chunk: StreamChunk) => void
  ): Promise<LLMResponse> {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': config.apiKey,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Anthropic API error ${response.status}: ${errorText}`)
    }

    if (!response.body) throw new Error('No response body for streaming')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    let fullText = ''
    const toolCalls: LLMToolCall[] = []
    let currentToolCall: Partial<LLMToolCall> & { inputStr?: string } | null = null
    let inputTokens = 0
    let outputTokens = 0
    let stopReason: LLMResponse['stopReason'] = 'end_turn'

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (data === '[DONE]') break

        try {
          const event = JSON.parse(data) as {
            type: string
            index?: number
            delta?: { type: string; text?: string; partial_json?: string }
            content_block?: { type: string; id?: string; name?: string }
            usage?: { input_tokens?: number; output_tokens?: number }
            message?: { usage?: { input_tokens?: number; output_tokens?: number }; stop_reason?: string }
          }

          if (event.type === 'content_block_start' && event.content_block) {
            if (event.content_block.type === 'tool_use') {
              currentToolCall = {
                id: event.content_block.id ?? `tool_${Date.now()}`,
                name: event.content_block.name ?? '',
                inputStr: ''
              }
              onStream({ type: 'tool_start', toolCallId: currentToolCall.id, toolName: currentToolCall.name })
            }
          } else if (event.type === 'content_block_delta' && event.delta) {
            if (event.delta.type === 'text_delta' && event.delta.text) {
              fullText += event.delta.text
              onStream({ type: 'text', text: event.delta.text })
            } else if (event.delta.type === 'input_json_delta' && event.delta.partial_json && currentToolCall) {
              currentToolCall.inputStr = (currentToolCall.inputStr ?? '') + event.delta.partial_json
              onStream({ type: 'tool_input_delta', toolCallId: currentToolCall.id, toolInputDelta: event.delta.partial_json })
            }
          } else if (event.type === 'content_block_stop') {
            if (currentToolCall) {
              try {
                currentToolCall.input = JSON.parse(currentToolCall.inputStr ?? '{}') as Record<string, unknown>
              } catch {
                currentToolCall.input = {}
              }
              toolCalls.push({ id: currentToolCall.id!, name: currentToolCall.name!, input: currentToolCall.input })
              onStream({ type: 'tool_end', toolCallId: currentToolCall.id, toolInput: currentToolCall.input })
              currentToolCall = null
            }
          } else if (event.type === 'message_delta' && event.usage) {
            outputTokens = event.usage.output_tokens ?? 0
            if (event['stop_reason']) stopReason = event['stop_reason'] as LLMResponse['stopReason']
          } else if (event.type === 'message_start' && event.message?.usage) {
            inputTokens = event.message.usage.input_tokens ?? 0
          }
        } catch {
          // Skip malformed SSE lines
        }
      }
    }

    onStream({ type: 'done' })

    return {
      content: fullText,
      toolCalls,
      inputTokens,
      outputTokens,
      stopReason
    }
  }

  private convertMessages(messages: LLMMessage[]): AnthropicMessage[] {
    const result: AnthropicMessage[] = []

    for (const msg of messages) {
      if (msg.role === 'user' || msg.role === 'assistant') {
        result.push({
          role: msg.role,
          content: typeof msg.content === 'string' ? msg.content : this.convertContentBlocks(msg.content as Array<{ type: string; text?: string; id?: string; name?: string; input?: Record<string, unknown> }>)
        })
      } else if (msg.role === 'tool') {
        // Tool results go into a user message
        const lastMsg = result[result.length - 1]
        const toolResultBlock = {
          type: 'tool_result' as const,
          tool_use_id: msg.toolCallId ?? '',
          content: typeof msg.content === 'string' ? msg.content : '',
          is_error: false
        }
        if (lastMsg?.role === 'user' && Array.isArray(lastMsg.content)) {
          (lastMsg.content as Array<unknown>).push(toolResultBlock)
        } else {
          result.push({ role: 'user', content: [toolResultBlock] as unknown as AnthropicContentBlock[] })
        }
      }
    }

    return result
  }

  private convertContentBlocks(blocks: Array<{ type: string; text?: string; id?: string; name?: string; input?: Record<string, unknown> }>): AnthropicContentBlock[] {
    return blocks.map((b) => {
      if (b.type === 'text') return { type: 'text' as const, text: b.text ?? '' }
      if (b.type === 'tool_use') return { type: 'tool_use' as const, id: b.id ?? '', name: b.name ?? '', input: b.input ?? {} }
      return { type: 'text' as const, text: '' }
    })
  }

  private parseResponse(data: AnthropicApiResponse): LLMResponse {
    let text = ''
    const toolCalls: LLMToolCall[] = []

    for (const block of data.content) {
      if (block.type === 'text') {
        text += block.text ?? ''
      } else if (block.type === 'tool_use') {
        toolCalls.push({
          id: block.id ?? `tool_${Date.now()}`,
          name: block.name ?? '',
          input: block.input ?? {}
        })
      }
    }

    return {
      content: text,
      toolCalls,
      inputTokens: data.usage.input_tokens,
      outputTokens: data.usage.output_tokens,
      stopReason: data.stop_reason as LLMResponse['stopReason']
    }
  }
}
