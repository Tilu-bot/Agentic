import { BaseProvider, LLMMessage, LLMResponse, LLMToolCall, ProviderConfig, StreamChunk } from './BaseProvider'
import { ToolDefinition } from '../tools/BaseTool'

interface OpenAIMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string | null
  tool_call_id?: string
  tool_calls?: Array<{ id: string; type: 'function'; function: { name: string; arguments: string } }>
}

interface OpenAIResponse {
  choices: Array<{
    message: {
      content: string | null
      tool_calls?: Array<{ id: string; type: 'function'; function: { name: string; arguments: string } }>
    }
    finish_reason: string
  }>
  usage: { prompt_tokens: number; completion_tokens: number }
}

export class OpenAIProvider extends BaseProvider {
  get name(): string {
    return 'openai'
  }

  async complete(
    messages: LLMMessage[],
    tools: ToolDefinition[],
    config: ProviderConfig,
    onStream?: (chunk: StreamChunk) => void
  ): Promise<LLMResponse> {
    const openAIMessages = this.convertMessages(messages)

    const body: Record<string, unknown> = {
      model: config.model,
      max_tokens: config.maxTokens,
      temperature: config.temperature,
      messages: openAIMessages,
      tools: tools.map((t) => ({
        type: 'function',
        function: {
          name: t.name,
          description: t.description,
          parameters: t.parameters
        }
      })),
      tool_choice: 'auto'
    }

    if (onStream) {
      body['stream'] = true
      return this.streamComplete(body, config, onStream)
    }

    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.apiKey}`
      },
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`OpenAI API error ${response.status}: ${errorText}`)
    }

    const data = (await response.json()) as OpenAIResponse
    return this.parseResponse(data)
  }

  private async streamComplete(
    body: Record<string, unknown>,
    config: ProviderConfig,
    onStream: (chunk: StreamChunk) => void
  ): Promise<LLMResponse> {
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.apiKey}`
      },
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`OpenAI API error ${response.status}: ${errorText}`)
    }

    if (!response.body) throw new Error('No response body for streaming')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullText = ''
    const toolCalls: LLMToolCall[] = []
    const toolCallBuilders: Map<number, { id: string; name: string; argsStr: string }> = new Map()

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
            choices: Array<{
              delta: {
                content?: string
                tool_calls?: Array<{ index: number; id?: string; function?: { name?: string; arguments?: string } }>
              }
              finish_reason?: string
            }>
          }

          const delta = event.choices[0]?.delta
          if (!delta) continue

          if (delta.content) {
            fullText += delta.content
            onStream({ type: 'text', text: delta.content })
          }

          if (delta.tool_calls) {
            for (const tc of delta.tool_calls) {
              if (!toolCallBuilders.has(tc.index)) {
                const builder = { id: tc.id ?? `tool_${tc.index}`, name: tc.function?.name ?? '', argsStr: '' }
                toolCallBuilders.set(tc.index, builder)
                onStream({ type: 'tool_start', toolCallId: builder.id, toolName: builder.name })
              }
              const builder = toolCallBuilders.get(tc.index)!
              if (tc.function?.arguments) {
                builder.argsStr += tc.function.arguments
                onStream({ type: 'tool_input_delta', toolCallId: builder.id, toolInputDelta: tc.function.arguments })
              }
            }
          }
        } catch {
          // Skip malformed chunks
        }
      }
    }

    // Finalize tool calls
    for (const [, builder] of toolCallBuilders) {
      let parsedInput: Record<string, unknown> = {}
      try {
        parsedInput = JSON.parse(builder.argsStr) as Record<string, unknown>
      } catch {
        parsedInput = {}
      }
      toolCalls.push({ id: builder.id, name: builder.name, input: parsedInput })
      onStream({ type: 'tool_end', toolCallId: builder.id, toolInput: parsedInput })
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

  private convertMessages(messages: LLMMessage[]): OpenAIMessage[] {
    return messages.map((msg): OpenAIMessage => {
      if (msg.role === 'tool') {
        return {
          role: 'tool',
          content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content),
          tool_call_id: msg.toolCallId ?? ''
        }
      }
      const content = typeof msg.content === 'string'
        ? msg.content
        : (msg.content as Array<{ type: string; text?: string }>).map((b) => b.text ?? '').join('\n')
      return { role: msg.role as 'system' | 'user' | 'assistant', content }
    })
  }

  private parseResponse(data: OpenAIResponse): LLMResponse {
    const choice = data.choices[0]
    const text = choice.message.content ?? ''
    const toolCalls: LLMToolCall[] = (choice.message.tool_calls ?? []).map((tc) => ({
      id: tc.id,
      name: tc.function.name,
      input: (() => {
        try { return JSON.parse(tc.function.arguments) as Record<string, unknown> }
        catch { return {} }
      })()
    }))

    return {
      content: text,
      toolCalls,
      inputTokens: data.usage.prompt_tokens,
      outputTokens: data.usage.completion_tokens,
      stopReason: choice.finish_reason === 'tool_calls' ? 'tool_use' : 'end_turn'
    }
  }
}
