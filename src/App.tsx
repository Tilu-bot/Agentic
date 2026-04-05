import React, { useEffect, useCallback } from 'react'
import { WorkspaceLayout } from './components/Layout/WorkspaceLayout'
import { CommandPalette } from './components/CommandPalette/CommandPalette'
import { useEditorStore } from './stores/editorStore'
import { useFileTreeStore } from './stores/fileTreeStore'
import { useAgentStore } from './stores/agentStore'
import { useSettingsStore } from './stores/settingsStore'
import { AgentUpdateEvent } from './types'

declare global {
  interface Window {
    api: import('../electron/preload').AppApi
  }
}

export default function App(): React.ReactElement {
  const { openFile } = useEditorStore()
  const { setRoot, setLoading } = useFileTreeStore()
  const { processUpdate, addUserMessage, setStatus, sessionId } = useAgentStore()
  const settings = useSettingsStore()

  // Register file system change listener
  useEffect(() => {
    const unsubscribe = window.api.fs.onDirectoryChange(() => {
      // Could trigger a tree refresh here
    })
    return unsubscribe
  }, [])

  // Register agent update listener for the current session
  useEffect(() => {
    const unsubscribe = window.api.agent.onUpdate(sessionId, (update) => {
      processUpdate(update as AgentUpdateEvent)
    })
    return unsubscribe
  }, [sessionId, processUpdate])

  const handleOpenFolder = useCallback(async () => {
    setLoading(true)
    try {
      const folderPath = await window.api.fs.openFolder()
      if (!folderPath) {
        setLoading(false)
        return
      }
      const tree = await window.api.fs.listDirectory(folderPath)
      setRoot(folderPath, tree)
      await window.api.fs.watchDirectory(folderPath)
    } catch (err) {
      console.error('Failed to open folder:', err)
      setLoading(false)
    }
  }, [setRoot, setLoading])

  const handleOpenFile = useCallback(async (filePath: string) => {
    const result = await window.api.fs.readFile(filePath)
    if (result.success && result.content !== undefined) {
      openFile(filePath, result.content)
    }
  }, [openFile])

  const handleSendMessage = useCallback(async (message: string) => {
    const { rootPath } = useFileTreeStore.getState()
    if (!rootPath) {
      alert('Please open a folder first.')
      return
    }
    addUserMessage(message)
    setStatus('running')
    await window.api.agent.run({
      message,
      sessionId,
      workspacePath: rootPath,
      settings: settings.getProviderSettings()
    })
  }, [sessionId, addUserMessage, setStatus, settings])

  return (
    <div className="app-root">
      <WorkspaceLayout
        onOpenFolder={handleOpenFolder}
        onOpenFile={handleOpenFile}
        onSendMessage={handleSendMessage}
      />
      <CommandPalette onOpenFolder={handleOpenFolder} onOpenFile={handleOpenFile} />
    </div>
  )
}
