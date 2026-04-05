import { LLMMessage } from '../llm/BaseProvider'

const MAX_MESSAGES = 40
const MAX_TOTAL_CHARS = 200_000

export class ContextManager {
  private messages: LLMMessage[] = []
  private systemPrompt = ''

  setSystemPrompt(prompt: string): void {
    this.systemPrompt = prompt
  }

  addMessage(msg: LLMMessage): void {
    this.messages.push(msg)
    this.trim()
  }

  getMessages(): LLMMessage[] {
    const systemMsg: LLMMessage = { role: 'system', content: this.systemPrompt }
    return [systemMsg, ...this.messages]
  }

  clear(): void {
    this.messages = []
  }

  private trim(): void {
    // Remove oldest non-system messages if we exceed limits
    while (this.messages.length > MAX_MESSAGES) {
      this.messages.splice(0, 1)
    }

    // Also trim by character count
    let totalChars = this.systemPrompt.length
    for (const msg of this.messages) {
      totalChars += typeof msg.content === 'string'
        ? msg.content.length
        : JSON.stringify(msg.content).length
    }

    while (totalChars > MAX_TOTAL_CHARS && this.messages.length > 2) {
      const removed = this.messages.splice(0, 1)[0]
      totalChars -= typeof removed.content === 'string'
        ? removed.content.length
        : JSON.stringify(removed.content).length
    }
  }
}
