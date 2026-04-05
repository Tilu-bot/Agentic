import { app, BrowserWindow, shell, nativeTheme, dialog } from 'electron'
import { join } from 'path'
import { is } from '@electron-toolkit/utils'
import { registerFileSystemHandlers } from './ipc/filesystem'
import { registerTerminalHandlers } from './ipc/terminal'
import { registerAgentHandlers } from './ipc/agent'

nativeTheme.themeSource = 'dark'

let mainWindow: BrowserWindow | null = null

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    show: false,
    autoHideMenuBar: false,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#1e1e1e',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow!.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

function registerGlobalHandlers(): void {
  registerFileSystemHandlers()
  registerTerminalHandlers()
  registerAgentHandlers()
}

app.whenReady().then(() => {
  createWindow()
  registerGlobalHandlers()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

export function getMainWindow(): BrowserWindow | null {
  return mainWindow
}

export function showOpenFolderDialog(): Promise<string | null> {
  return dialog
    .showOpenDialog({
      properties: ['openDirectory'],
      title: 'Open Folder'
    })
    .then((result) => {
      if (result.canceled || result.filePaths.length === 0) return null
      return result.filePaths[0]
    })
}

export function showSaveFileDialog(defaultPath?: string): Promise<string | null> {
  return dialog
    .showSaveDialog({
      defaultPath,
      title: 'Save File'
    })
    .then((result) => {
      if (result.canceled || !result.filePath) return null
      return result.filePath
    })
}
