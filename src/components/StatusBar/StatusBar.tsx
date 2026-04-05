import React from 'react'
import { useFileTreeStore } from '../../stores/fileTreeStore'
import { useEditorStore } from '../../stores/editorStore'
import { useAgentStore } from '../../stores/agentStore'
import { useSettingsStore } from '../../stores/settingsStore'

interface StatusBarProps {
  showTerminal: boolean
  showAgentPanel: boolean
  onToggleTerminal: () => void
  onToggleAgent: () => void
}

export function StatusBar({ showTerminal, showAgentPanel, onToggleTerminal, onToggleAgent }: StatusBarProps): React.ReactElement {
  const { rootPath } = useFileTreeStore()
  const activeTab = useEditorStore((s) => s.getActiveTab())
  const { status } = useAgentStore()
  const { provider, model } = useSettingsStore()

  const folderName = rootPath ? rootPath.split('/').pop() : null
  const filename = activeTab?.path.split('/').pop() ?? null
  const language = activeTab?.language ?? null

  const agentStatusLabel: Record<typeof status, string> = {
    idle: '',
    running: '⚡ Running',
    planning: '📋 Planning',
    error: '⚠ Error'
  }

  return (
    <div className="status-bar" role="status">
      {/* Left section */}
      <div className="status-bar-section">
        {folderName && (
          <div className="status-bar-item" title={rootPath ?? ''}>
            <svg viewBox="0 0 16 16" fill="none" width={12} height={12}>
              <path d="M1 3.5A1.5 1.5 0 012.5 2h3.586l1 1H14a1 1 0 011 1v8.5A1.5 1.5 0 0113.5 14h-11A1.5 1.5 0 011 12.5v-9z" fill="currentColor" />
            </svg>
            {folderName}
          </div>
        )}
      </div>

      <div className="status-bar-spacer" />

      {/* Center / right section */}
      <div className="status-bar-section">
        {agentStatusLabel[status] && (
          <div className="status-bar-item" style={{ color: 'rgba(255,255,255,1)', fontWeight: 600 }}>
            {agentStatusLabel[status]}
          </div>
        )}

        <div className="status-bar-item" title="LLM Provider">
          {provider}/{model}
        </div>

        {language && (
          <div className="status-bar-item" title="Language">
            {language}
          </div>
        )}

        <div
          className="status-bar-item"
          onClick={onToggleTerminal}
          style={{ cursor: 'pointer', opacity: showTerminal ? 1 : 0.7 }}
          title="Toggle Terminal"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} width={12} height={12}>
            <rect x="1" y="1" width="14" height="14" rx="1" />
            <polyline points="4 5 8 8 4 11" />
            <line x1="9" y1="11" x2="13" y2="11" />
          </svg>
          Terminal
        </div>

        <div
          className="status-bar-item"
          onClick={onToggleAgent}
          style={{ cursor: 'pointer', opacity: showAgentPanel ? 1 : 0.7 }}
          title="Toggle Agent Panel"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} width={12} height={12}>
            <circle cx="8" cy="7" r="3" />
            <path d="M2 14a6 6 0 0112 0" />
          </svg>
          Agent
        </div>
      </div>
    </div>
  )
}
