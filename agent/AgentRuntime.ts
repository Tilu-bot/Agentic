import { ReActLoop, RunOptions } from './loop/ReActLoop'
import { LLMMessage } from './llm/BaseProvider'

export class AgentRuntime {
  private loop = new ReActLoop()

  async run(options: RunOptions): Promise<void> {
    return this.loop.run(options)
  }

  abort(sessionId: string): void {
    this.loop.abort(sessionId)
  }

  getHistory(sessionId: string): LLMMessage[] {
    return this.loop.getHistory(sessionId)
  }

  clearHistory(sessionId: string): void {
    this.loop.clearSession(sessionId)
  }
}
