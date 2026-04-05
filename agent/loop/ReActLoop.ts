import { ProviderRegistry } from '../llm/ProviderRegistry'
import { ToolRegistry } from '../tools/ToolRegistry'
import { ContextManager } from '../context/ContextManager'
import { LLMMessage, StreamChunk } from '../llm/BaseProvider'
import { v4 as uuidv4 } from 'uuid'
import * as fs from 'fs'
import * as path from 'path'

interface DiffProposal {
  id: string
  filePath: string
  originalContent: string
  proposedContent: string
  description: string
  status: 'pending'
}

export interface RunOptions {
  userMessage: string
  sessionId: string
  workspacePath: string
  providerSettings: {
    provider: string
    model: string
    apiKey: string
    ollamaUrl: string
    maxTokens: number
    temperature: number
  }
  onUpdate: (event: unknown) => void
}

const MAX_ITERATIONS = 20

const SYSTEM_PROMPT = `You are Nexus Agent, an expert AI coding assistant embedded in a VS Code-style desktop app.

You have full access to the user's workspace through a set of tools. You can:
- Read and write files
- Run shell commands (tests, builds, installations)
- Search across the codebase
- Apply targeted edits to specific code blocks
- Fetch documentation from the web

## Guidelines

1. **Always explore before acting**: Use list_directory and read_file to understand the codebase before making changes.

2. **Make targeted edits**: Prefer apply_edit over write_file when modifying existing files — it's safer and shows the user exactly what changed.

3. **Verify your changes**: After making changes, run relevant tests or the build to ensure nothing is broken.

4. **Be transparent**: Explain what you're doing and why, before doing it.

5. **Ask before big changes**: If a task would involve large refactors or deleting files, describe your plan first and ask for confirmation.

6. **Workspace awareness**: Your tools are sandboxed to the workspace. You cannot access files outside it.

## Tool Best Practices

- Use \`list_directory\` with \`recursive: true\` to understand project structure quickly
- Use \`search_files\` to find function definitions, imports, and usages
- Use \`apply_edit\` for surgical changes (change one function, add an import, etc.)
- Use \`write_file\` only for new files or complete rewrites
- Use \`run_command\` to run \`npm test\`, \`npm run build\`, \`python -m pytest\`, etc.
- Use \`web_fetch\` for library documentation and API references

When you've completed the task, summarize what you did and any important notes for the user.`

export class ReActLoop {
  private providerRegistry = new ProviderRegistry()
  private toolRegistry = new ToolRegistry()
  private abortSignals = new Map<string, boolean>()
  private sessions = new Map<string, ContextManager>()

  abort(sessionId: string): void {
    this.abortSignals.set(sessionId, true)
  }

  isAborted(sessionId: string): boolean {
    return this.abortSignals.get(sessionId) === true
  }

  getOrCreateContext(sessionId: string): ContextManager {
    if (!this.sessions.has(sessionId)) {
      const ctx = new ContextManager()
      ctx.setSystemPrompt(SYSTEM_PROMPT)
      this.sessions.set(sessionId, ctx)
    }
    return this.sessions.get(sessionId)!
  }

  clearSession(sessionId: string): void {
    this.sessions.delete(sessionId)
    this.abortSignals.delete(sessionId)
  }

  getHistory(sessionId: string): LLMMessage[] {
    return this.sessions.get(sessionId)?.getMessages() ?? []
  }

  async run(options: RunOptions): Promise<void> {
    const { userMessage, sessionId, workspacePath, providerSettings, onUpdate } = options

    this.abortSignals.set(sessionId, false)

    const ctx = this.getOrCreateContext(sessionId)
    const provider = this.providerRegistry.get(providerSettings.provider)

    // Add user message to context
    ctx.addMessage({ role: 'user', content: userMessage })

    const config = {
      model: providerSettings.model,
      apiKey: providerSettings.apiKey,
      ollamaUrl: providerSettings.ollamaUrl,
      maxTokens: providerSettings.maxTokens,
      temperature: providerSettings.temperature
    }

    let iterations = 0

    while (iterations < MAX_ITERATIONS) {
      if (this.isAborted(sessionId)) {
        onUpdate({ type: 'agent_error', error: 'Aborted by user' })
        return
      }

      iterations++

      const messageId = uuidv4()
      onUpdate({ type: 'stream_start', messageId })

      let assistantText = ''
      const pendingToolCalls: Array<{ id: string; name: string; input: Record<string, unknown> }> = []

      try {
        const response = await provider.complete(
          ctx.getMessages(),
          this.toolRegistry.getDefinitions(),
          config,
          (chunk: StreamChunk) => {
            if (this.isAborted(sessionId)) return

            if (chunk.type === 'text' && chunk.text) {
              assistantText += chunk.text
              onUpdate({ type: 'stream_chunk', messageId, chunk: chunk.text })
            }

            if (chunk.type === 'tool_start') {
              onUpdate({ type: 'tool_start', toolUse: {
                id: chunk.toolCallId!,
                toolName: chunk.toolName!,
                input: {},
                status: 'running'
              }})
            }

            if (chunk.type === 'tool_end' && chunk.toolInput) {
              pendingToolCalls.push({
                id: chunk.toolCallId!,
                name: chunk.toolName!,
                input: chunk.toolInput
              })
            }
          }
        )

        if (this.isAborted(sessionId)) return

        onUpdate({ type: 'stream_end', messageId })

        // Add assistant message to context
        const assistantMsg: LLMMessage = {
          role: 'assistant',
          content: assistantText || response.content
        }
        ctx.addMessage(assistantMsg)

        // No tool calls — agent is done
        if (response.toolCalls.length === 0 && pendingToolCalls.length === 0) {
          onUpdate({ type: 'agent_done' })
          return
        }

        // Execute tool calls
        const toolCallsToExecute = response.toolCalls.length > 0 ? response.toolCalls : pendingToolCalls

        for (const tc of toolCallsToExecute) {
          if (this.isAborted(sessionId)) return

          const tool = this.toolRegistry.get(tc.name)
          const startTime = Date.now()

          if (!tool) {
            const errorMsg = `Unknown tool: ${tc.name}`
            onUpdate({ type: 'tool_end', toolUseId: tc.id, output: '', error: errorMsg, durationMs: 0 })
            ctx.addMessage({ role: 'tool', content: `Error: ${errorMsg}`, toolCallId: tc.id, toolName: tc.name })
            continue
          }

          onUpdate({ type: 'tool_start', toolUse: {
            id: tc.id,
            toolName: tc.name,
            input: tc.input,
            status: 'running'
          }})

          let result
          try {
            result = await tool.execute(tc.input, workspacePath)
          } catch (err) {
            result = { success: false, output: '', error: String(err) }
          }

          const durationMs = Date.now() - startTime

          onUpdate({
            type: 'tool_end',
            toolUseId: tc.id,
            output: result.output,
            error: result.error,
            durationMs
          })

          // For write_file and apply_edit, also emit a diff proposal
          if ((tc.name === 'write_file' || tc.name === 'apply_edit') && result.success) {
            await this.maybeProposeAsDiff(tc, workspacePath, onUpdate)
          }

          // Add tool result to context
          const toolResultContent = result.error
            ? `Error: ${result.error}\n${result.output}`
            : result.output

          ctx.addMessage({
            role: 'tool',
            content: toolResultContent,
            toolCallId: tc.id,
            toolName: tc.name
          })
        }

      } catch (err) {
        onUpdate({ type: 'agent_error', error: String(err) })
        return
      }
    }

    // Exceeded max iterations
    onUpdate({ type: 'agent_error', error: `Exceeded maximum iterations (${MAX_ITERATIONS})` })
  }

  private async maybeProposeAsDiff(
    tc: { name: string; input: Record<string, unknown> },
    workspacePath: string,
    onUpdate: (event: unknown) => void
  ): Promise<void> {
    // For write_file, we can show the new content as a "diff"
    if (tc.name === 'write_file') {
      const filePath = tc.input['path'] as string
      const newContent = tc.input['content'] as string
      if (!filePath || !newContent) return

      const resolvedPath = path.isAbsolute(filePath) ? filePath : path.join(workspacePath, filePath)
      let originalContent = ''
      try {
        if (fs.existsSync(resolvedPath)) {
          originalContent = fs.readFileSync(resolvedPath, 'utf-8')
        }
      } catch {
        originalContent = ''
      }

      const proposal: DiffProposal = {
        id: uuidv4(),
        filePath: resolvedPath,
        originalContent,
        proposedContent: newContent,
        description: `Written by agent`,
        status: 'pending'
      }
      onUpdate({ type: 'diff_proposal', proposal })
    }
  }
}
