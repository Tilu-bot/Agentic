import React, { useState, useCallback, useRef } from 'react'
import { ActivityBar } from '../ActivityBar/ActivityBar'
import { FileTree } from '../FileTree/FileTree'
import { SearchPanel } from '../FileTree/SearchPanel'
import { EditorTabs } from '../Editor/EditorTabs'
import { EditorPanel } from '../Editor/EditorPanel'
import { TerminalPanel } from '../Terminal/TerminalPanel'
import { AgentPanel } from '../AgentPanel/AgentPanel'
import { StatusBar } from '../StatusBar/StatusBar'
import { SettingsPanel } from '../Settings/SettingsPanel'
import { SidebarPanel } from '../../types'

interface WorkspaceLayoutProps {
  onOpenFolder: () => void
  onOpenFile: (filePath: string) => void
  onSendMessage: (message: string) => void
}

export function WorkspaceLayout({ onOpenFolder, onOpenFile, onSendMessage }: WorkspaceLayoutProps): React.ReactElement {
  const [activeSidebar, setActiveSidebar] = useState<SidebarPanel>('files')
  const [sidebarWidth, setSidebarWidth] = useState(240)
  const [agentPanelWidth, setAgentPanelWidth] = useState(360)
  const [terminalHeight, setTerminalHeight] = useState(200)
  const [showTerminal, setShowTerminal] = useState(false)
  const [showAgentPanel, setShowAgentPanel] = useState(true)

  const isDraggingSidebar = useRef(false)
  const isDraggingAgent = useRef(false)
  const isDraggingTerminal = useRef(false)

  const handleSidebarMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingSidebar.current = true
    const startX = e.clientX
    const startWidth = sidebarWidth

    const onMove = (ev: MouseEvent): void => {
      if (!isDraggingSidebar.current) return
      const delta = ev.clientX - startX
      setSidebarWidth(Math.max(160, Math.min(600, startWidth + delta)))
    }
    const onUp = (): void => {
      isDraggingSidebar.current = false
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [sidebarWidth])

  const handleAgentMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingAgent.current = true
    const startX = e.clientX
    const startWidth = agentPanelWidth

    const onMove = (ev: MouseEvent): void => {
      if (!isDraggingAgent.current) return
      const delta = startX - ev.clientX
      setAgentPanelWidth(Math.max(280, Math.min(700, startWidth + delta)))
    }
    const onUp = (): void => {
      isDraggingAgent.current = false
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [agentPanelWidth])

  const handleTerminalMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingTerminal.current = true
    const startY = e.clientY
    const startHeight = terminalHeight

    const onMove = (ev: MouseEvent): void => {
      if (!isDraggingTerminal.current) return
      const delta = startY - ev.clientY
      setTerminalHeight(Math.max(80, Math.min(600, startHeight + delta)))
    }
    const onUp = (): void => {
      isDraggingTerminal.current = false
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [terminalHeight])

  const toggleTerminal = useCallback(() => setShowTerminal((v) => !v), [])
  const toggleAgentPanel = useCallback(() => setShowAgentPanel((v) => !v), [])

  const renderSidebarContent = (): React.ReactElement => {
    switch (activeSidebar) {
      case 'files':
        return <FileTree onOpenFile={onOpenFile} onOpenFolder={onOpenFolder} />
      case 'search':
        return <SearchPanel onOpenFile={onOpenFile} />
      case 'settings':
        return <SettingsPanel />
      default:
        return <FileTree onOpenFile={onOpenFile} onOpenFolder={onOpenFolder} />
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <div className="workspace-layout">
        <div className="workspace-main">
          {/* Activity Bar */}
          <ActivityBar
            activePanel={activeSidebar}
            onPanelChange={setActiveSidebar}
            onToggleTerminal={toggleTerminal}
            onToggleAgent={toggleAgentPanel}
          />

          {/* Sidebar */}
          <div className="sidebar" style={{ width: sidebarWidth }}>
            {renderSidebarContent()}
          </div>

          {/* Sidebar resize handle */}
          <div className="resize-handle-v" onMouseDown={handleSidebarMouseDown} />

          {/* Main editor area */}
          <div className="workspace-center">
            <EditorTabs />
            <EditorPanel />

            {/* Terminal resize handle */}
            {showTerminal && (
              <div className="resize-handle-h" onMouseDown={handleTerminalMouseDown} />
            )}

            {/* Terminal */}
            {showTerminal && (
              <TerminalPanel height={terminalHeight} onClose={toggleTerminal} />
            )}
          </div>

          {/* Agent panel resize handle */}
          {showAgentPanel && (
            <div className="resize-handle-v" onMouseDown={handleAgentMouseDown} />
          )}

          {/* Agent Panel */}
          {showAgentPanel && (
            <AgentPanel
              width={agentPanelWidth}
              onSendMessage={onSendMessage}
              onClose={toggleAgentPanel}
            />
          )}
        </div>
      </div>

      {/* Status Bar */}
      <StatusBar
        showTerminal={showTerminal}
        showAgentPanel={showAgentPanel}
        onToggleTerminal={toggleTerminal}
        onToggleAgent={toggleAgentPanel}
      />
    </div>
  )
}
