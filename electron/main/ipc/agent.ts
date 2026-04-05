import { ipcMain, BrowserWindow } from 'electron'
import { AgentRuntime } from '../../../agent/AgentRuntime'

let agentRuntime: AgentRuntime | null = null

function getOrCreateRuntime(): AgentRuntime {
  if (!agentRuntime) {
    agentRuntime = new AgentRuntime()
  }
  return agentRuntime
}

export function registerAgentHandlers(): void {
  ipcMain.handle('agent:run', async (event, payload: {
    message: string
    sessionId: string
    workspacePath: string
    settings: {
      provider: string
      model: string
      apiKey: string
      ollamaUrl: string
      maxTokens: number
      temperature: number
    }
  }) => {
    const runtime = getOrCreateRuntime()

    const sendUpdate = (update: unknown): void => {
      const sender = BrowserWindow.getAllWindows()[0]?.webContents
      if (sender && !sender.isDestroyed()) {
        sender.send(`agent:update:${payload.sessionId}`, update)
      }
    }

    try {
      await runtime.run({
        userMessage: payload.message,
        sessionId: payload.sessionId,
        workspacePath: payload.workspacePath,
        providerSettings: payload.settings,
        onUpdate: sendUpdate
      })
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle('agent:abort', async (_event, sessionId: string) => {
    const runtime = getOrCreateRuntime()
    runtime.abort(sessionId)
    return { success: true }
  })

  ipcMain.handle('agent:applyDiff', async (_event, filePath: string, newContent: string) => {
    try {
      const fs = await import('fs')
      fs.mkdirSync(require('path').dirname(filePath), { recursive: true })
      fs.writeFileSync(filePath, newContent, 'utf-8')
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle('agent:getHistory', async (_event, sessionId: string) => {
    const runtime = getOrCreateRuntime()
    return runtime.getHistory(sessionId)
  })

  ipcMain.handle('agent:clearHistory', async (_event, sessionId: string) => {
    const runtime = getOrCreateRuntime()
    runtime.clearHistory(sessionId)
    return { success: true }
  })
}
