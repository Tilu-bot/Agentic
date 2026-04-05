import { contextBridge, ipcRenderer } from 'electron'

// The API exposed to the renderer process
// All communication goes through IPC — renderer never has direct Node access

const api = {
  // ── File System ────────────────────────────────────────────────────────────
  fs: {
    openFolder: (): Promise<string | null> =>
      ipcRenderer.invoke('fs:openFolder'),

    listDirectory: (dirPath: string) =>
      ipcRenderer.invoke('fs:listDirectory', dirPath),

    readFile: (filePath: string) =>
      ipcRenderer.invoke('fs:readFile', filePath),

    writeFile: (filePath: string, content: string) =>
      ipcRenderer.invoke('fs:writeFile', filePath, content),

    deleteFile: (filePath: string) =>
      ipcRenderer.invoke('fs:deleteFile', filePath),

    createFile: (filePath: string) =>
      ipcRenderer.invoke('fs:createFile', filePath),

    createDirectory: (dirPath: string) =>
      ipcRenderer.invoke('fs:createDirectory', dirPath),

    rename: (oldPath: string, newPath: string) =>
      ipcRenderer.invoke('fs:rename', oldPath, newPath),

    exists: (filePath: string) =>
      ipcRenderer.invoke('fs:exists', filePath),

    stat: (filePath: string) =>
      ipcRenderer.invoke('fs:stat', filePath),

    searchFiles: (
      rootPath: string,
      query: string,
      options: { regex?: boolean; caseSensitive?: boolean; includePattern?: string }
    ) => ipcRenderer.invoke('fs:searchFiles', rootPath, query, options),

    watchDirectory: (dirPath: string) =>
      ipcRenderer.invoke('fs:watchDirectory', dirPath),

    unwatchDirectory: (dirPath: string) =>
      ipcRenderer.invoke('fs:unwatchDirectory', dirPath),

    onDirectoryChange: (callback: (event: { path: string; eventType: string; filename: string | null }) => void) => {
      const handler = (_: Electron.IpcRendererEvent, data: { path: string; eventType: string; filename: string | null }) => callback(data)
      ipcRenderer.on('fs:change', handler)
      return () => ipcRenderer.removeListener('fs:change', handler)
    }
  },

  // ── Terminal ───────────────────────────────────────────────────────────────
  terminal: {
    create: (sessionId: string, cwd?: string) =>
      ipcRenderer.invoke('terminal:create', sessionId, cwd),

    write: (sessionId: string, data: string) =>
      ipcRenderer.invoke('terminal:write', sessionId, data),

    resize: (sessionId: string, cols: number, rows: number) =>
      ipcRenderer.invoke('terminal:resize', sessionId, cols, rows),

    destroy: (sessionId: string) =>
      ipcRenderer.invoke('terminal:destroy', sessionId),

    changeDir: (sessionId: string, dirPath: string) =>
      ipcRenderer.invoke('terminal:changeDir', sessionId, dirPath),

    onData: (sessionId: string, callback: (data: string) => void) => {
      const handler = (_: Electron.IpcRendererEvent, data: string) => callback(data)
      ipcRenderer.on(`terminal:data:${sessionId}`, handler)
      return () => ipcRenderer.removeListener(`terminal:data:${sessionId}`, handler)
    },

    onExit: (sessionId: string, callback: (code: number) => void) => {
      const handler = (_: Electron.IpcRendererEvent, code: number) => callback(code)
      ipcRenderer.on(`terminal:exit:${sessionId}`, handler)
      return () => ipcRenderer.removeListener(`terminal:exit:${sessionId}`, handler)
    }
  },

  // ── Agent ──────────────────────────────────────────────────────────────────
  agent: {
    run: (payload: {
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
    }) => ipcRenderer.invoke('agent:run', payload),

    abort: (sessionId: string) =>
      ipcRenderer.invoke('agent:abort', sessionId),

    applyDiff: (filePath: string, newContent: string) =>
      ipcRenderer.invoke('agent:applyDiff', filePath, newContent),

    getHistory: (sessionId: string) =>
      ipcRenderer.invoke('agent:getHistory', sessionId),

    clearHistory: (sessionId: string) =>
      ipcRenderer.invoke('agent:clearHistory', sessionId),

    onUpdate: (sessionId: string, callback: (update: unknown) => void) => {
      const handler = (_: Electron.IpcRendererEvent, update: unknown) => callback(update)
      ipcRenderer.on(`agent:update:${sessionId}`, handler)
      return () => ipcRenderer.removeListener(`agent:update:${sessionId}`, handler)
    }
  }
}

contextBridge.exposeInMainWorld('api', api)

export type AppApi = typeof api
