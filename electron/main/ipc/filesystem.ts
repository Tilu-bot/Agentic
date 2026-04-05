import { ipcMain, BrowserWindow } from 'electron'
import * as fs from 'fs'
import * as path from 'path'
import { showOpenFolderDialog } from '../index'

export interface FileEntry {
  name: string
  path: string
  isDirectory: boolean
  children?: FileEntry[]
  size?: number
  modifiedAt?: number
}

function buildFileTree(dirPath: string, depth = 0, maxDepth = 4): FileEntry[] {
  if (depth > maxDepth) return []
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true })
    const result: FileEntry[] = []

    for (const entry of entries) {
      // Skip hidden files and common noise directories
      if (entry.name.startsWith('.') && entry.name !== '.env') continue
      if (['node_modules', '__pycache__', '.git', 'dist', 'dist-electron', '.next', 'build', 'coverage'].includes(entry.name)) continue

      const fullPath = path.join(dirPath, entry.name)
      const isDirectory = entry.isDirectory()

      const fileEntry: FileEntry = {
        name: entry.name,
        path: fullPath,
        isDirectory
      }

      if (isDirectory) {
        fileEntry.children = buildFileTree(fullPath, depth + 1, maxDepth)
      } else {
        try {
          const stat = fs.statSync(fullPath)
          fileEntry.size = stat.size
          fileEntry.modifiedAt = stat.mtimeMs
        } catch {
          // Ignore stat errors
        }
      }

      result.push(fileEntry)
    }

    // Directories first, then files, both sorted alphabetically
    return result.sort((a, b) => {
      if (a.isDirectory !== b.isDirectory) return a.isDirectory ? -1 : 1
      return a.name.localeCompare(b.name)
    })
  } catch {
    return []
  }
}

export function registerFileSystemHandlers(): void {
  ipcMain.handle('fs:openFolder', async () => {
    return showOpenFolderDialog()
  })

  ipcMain.handle('fs:listDirectory', async (_event, dirPath: string) => {
    return buildFileTree(dirPath, 0, 4)
  })

  ipcMain.handle('fs:readFile', async (_event, filePath: string) => {
    try {
      const content = fs.readFileSync(filePath, 'utf-8')
      return { success: true, content }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle('fs:writeFile', async (_event, filePath: string, content: string) => {
    try {
      fs.mkdirSync(path.dirname(filePath), { recursive: true })
      fs.writeFileSync(filePath, content, 'utf-8')
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle('fs:deleteFile', async (_event, filePath: string) => {
    try {
      fs.rmSync(filePath, { recursive: true, force: true })
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle('fs:createFile', async (_event, filePath: string) => {
    try {
      fs.mkdirSync(path.dirname(filePath), { recursive: true })
      if (!fs.existsSync(filePath)) {
        fs.writeFileSync(filePath, '', 'utf-8')
      }
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle('fs:createDirectory', async (_event, dirPath: string) => {
    try {
      fs.mkdirSync(dirPath, { recursive: true })
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle('fs:rename', async (_event, oldPath: string, newPath: string) => {
    try {
      fs.renameSync(oldPath, newPath)
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle('fs:exists', async (_event, filePath: string) => {
    return fs.existsSync(filePath)
  })

  ipcMain.handle('fs:stat', async (_event, filePath: string) => {
    try {
      const stat = fs.statSync(filePath)
      return {
        success: true,
        isDirectory: stat.isDirectory(),
        size: stat.size,
        modifiedAt: stat.mtimeMs,
        createdAt: stat.birthtimeMs
      }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle('fs:searchFiles', async (_event, rootPath: string, query: string, options: { regex?: boolean; caseSensitive?: boolean; includePattern?: string }) => {
    const results: Array<{ path: string; line: number; column: number; text: string }> = []
    const maxResults = 200

    function searchInFile(filePath: string): void {
      if (results.length >= maxResults) return
      try {
        const content = fs.readFileSync(filePath, 'utf-8')
        const lines = content.split('\n')
        const flags = options.caseSensitive ? 'g' : 'gi'
        const pattern = options.regex
          ? new RegExp(query, flags)
          : new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), flags)

        lines.forEach((line, idx) => {
          if (results.length >= maxResults) return
          pattern.lastIndex = 0
          const match = pattern.exec(line)
          if (match) {
            results.push({
              path: filePath,
              line: idx + 1,
              column: match.index + 1,
              text: line.trim()
            })
          }
        })
      } catch {
        // Skip unreadable files
      }
    }

    function walkDir(dirPath: string, depth = 0): void {
      if (depth > 10 || results.length >= maxResults) return
      try {
        const entries = fs.readdirSync(dirPath, { withFileTypes: true })
        for (const entry of entries) {
          if (entry.name.startsWith('.')) continue
          if (['node_modules', '__pycache__', '.git', 'dist', '.next'].includes(entry.name)) continue

          const fullPath = path.join(dirPath, entry.name)
          if (entry.isDirectory()) {
            walkDir(fullPath, depth + 1)
          } else {
            if (options.includePattern) {
              const ext = path.extname(entry.name).toLowerCase()
              const patterns = options.includePattern.split(',').map((p) => p.trim().replace('*.', ''))
              if (!patterns.includes(ext.replace('.', ''))) continue
            }
            searchInFile(fullPath)
          }
        }
      } catch {
        // Skip inaccessible directories
      }
    }

    walkDir(rootPath)
    return results
  })

  // Watch a directory for changes and notify the renderer
  const watchers = new Map<string, fs.FSWatcher>()

  ipcMain.handle('fs:watchDirectory', async (event, dirPath: string) => {
    if (watchers.has(dirPath)) return { success: true }
    try {
      const watcher = fs.watch(dirPath, { recursive: true }, (eventType, filename) => {
        const sender = BrowserWindow.getAllWindows()[0]?.webContents
        if (sender && !sender.isDestroyed()) {
          sender.send('fs:change', { path: dirPath, eventType, filename })
        }
      })
      watchers.set(dirPath, watcher)
      return { success: true }
    } catch (err) {
      return { success: false, error: String(err) }
    }
  })

  ipcMain.handle('fs:unwatchDirectory', async (_event, dirPath: string) => {
    const watcher = watchers.get(dirPath)
    if (watcher) {
      watcher.close()
      watchers.delete(dirPath)
    }
    return { success: true }
  })
}
