import { ipcMain, BrowserWindow } from 'electron'
import * as pty from 'node-pty'
import * as os from 'os'

interface TerminalSession {
  pty: pty.IPty
  id: string
}

const sessions = new Map<string, TerminalSession>()

export function registerTerminalHandlers(): void {
  ipcMain.handle('terminal:create', async (_event, sessionId: string, cwd?: string) => {
    if (sessions.has(sessionId)) {
      return { success: true, sessionId }
    }

    const shell =
      process.platform === 'win32'
        ? 'powershell.exe'
        : process.env['SHELL'] || (process.platform === 'darwin' ? '/bin/zsh' : '/bin/bash')

    const env: Record<string, string> = {}
    for (const [k, v] of Object.entries(process.env)) {
      if (v !== undefined) env[k] = v
    }
    env['TERM'] = 'xterm-256color'
    env['COLORTERM'] = 'truecolor'

    const ptyProcess = pty.spawn(shell, [], {
      name: 'xterm-256color',
      cols: 120,
      rows: 30,
      cwd: cwd || os.homedir(),
      env
    })

    const session: TerminalSession = { pty: ptyProcess, id: sessionId }
    sessions.set(sessionId, session)

    ptyProcess.onData((data) => {
      const sender = BrowserWindow.getAllWindows()[0]?.webContents
      if (sender && !sender.isDestroyed()) {
        sender.send(`terminal:data:${sessionId}`, data)
      }
    })

    ptyProcess.onExit(({ exitCode }) => {
      sessions.delete(sessionId)
      const sender = BrowserWindow.getAllWindows()[0]?.webContents
      if (sender && !sender.isDestroyed()) {
        sender.send(`terminal:exit:${sessionId}`, exitCode)
      }
    })

    return { success: true, sessionId }
  })

  ipcMain.handle('terminal:write', async (_event, sessionId: string, data: string) => {
    const session = sessions.get(sessionId)
    if (!session) return { success: false, error: 'Session not found' }
    session.pty.write(data)
    return { success: true }
  })

  ipcMain.handle('terminal:resize', async (_event, sessionId: string, cols: number, rows: number) => {
    const session = sessions.get(sessionId)
    if (!session) return { success: false, error: 'Session not found' }
    session.pty.resize(cols, rows)
    return { success: true }
  })

  ipcMain.handle('terminal:destroy', async (_event, sessionId: string) => {
    const session = sessions.get(sessionId)
    if (session) {
      session.pty.kill()
      sessions.delete(sessionId)
    }
    return { success: true }
  })

  ipcMain.handle('terminal:changeDir', async (_event, sessionId: string, dirPath: string) => {
    const session = sessions.get(sessionId)
    if (!session) return { success: false, error: 'Session not found' }
    const escaped = dirPath.replace(/'/g, "'\\''")
    session.pty.write(`cd '${escaped}'\r`)
    return { success: true }
  })
}
