import React, { useState, useEffect, useCallback, useRef } from 'react'
import { PaletteCommand } from '../../types'
import { useFileTreeStore } from '../../stores/fileTreeStore'
import { useEditorStore } from '../../stores/editorStore'
import { useAgentStore } from '../../stores/agentStore'

interface CommandPaletteProps {
  onOpenFolder: () => void
  onOpenFile: (filePath: string) => void
}

const SearchIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} width={16} height={16}>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.35-4.35" />
  </svg>
)

export function CommandPalette({ onOpenFolder, onOpenFile }: CommandPaletteProps): React.ReactElement {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [focusedIndex, setFocusedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const { closeAllTabs } = useEditorStore()
  const { closeFolder } = useFileTreeStore()
  const { newSession, clearMessages } = useAgentStore()

  const buildCommands = useCallback((): PaletteCommand[] => [
    {
      id: 'open-folder',
      label: 'File: Open Folder',
      shortcut: 'Ctrl+K Ctrl+O',
      category: 'File',
      action: () => { setIsOpen(false); onOpenFolder() }
    },
    {
      id: 'close-folder',
      label: 'File: Close Folder',
      category: 'File',
      action: () => { setIsOpen(false); closeFolder() }
    },
    {
      id: 'close-all-tabs',
      label: 'Editor: Close All Tabs',
      category: 'Editor',
      action: () => { setIsOpen(false); closeAllTabs() }
    },
    {
      id: 'new-agent-session',
      label: 'Agent: New Session',
      category: 'Agent',
      description: 'Start a fresh agent conversation',
      action: () => { setIsOpen(false); newSession() }
    },
    {
      id: 'clear-agent',
      label: 'Agent: Clear Messages',
      category: 'Agent',
      action: () => { setIsOpen(false); clearMessages() }
    },
    {
      id: 'toggle-theme',
      label: 'View: Toggle Color Theme',
      category: 'View',
      description: 'Dark theme only in this version',
      action: () => setIsOpen(false)
    }
  ], [onOpenFolder, closeFolder, closeAllTabs, newSession, clearMessages])

  const allCommands = buildCommands()

  const filteredCommands = query.trim()
    ? allCommands.filter((c) =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.description?.toLowerCase().includes(query.toLowerCase())
      )
    : allCommands

  // Open on Ctrl+Shift+P or Ctrl+P
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'P') {
        e.preventDefault()
        setIsOpen((v) => !v)
        setQuery('')
        setFocusedIndex(0)
      }
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 10)
    }
  }, [isOpen])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setFocusedIndex((i) => Math.min(i + 1, filteredCommands.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setFocusedIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      filteredCommands[focusedIndex]?.action()
    } else if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }, [filteredCommands, focusedIndex])

  if (!isOpen) return <></>

  return (
    <div className="command-palette-overlay" onClick={() => setIsOpen(false)}>
      <div className="command-palette" onClick={(e) => e.stopPropagation()}>
        <div className="command-palette-input-row">
          <SearchIcon />
          <input
            ref={inputRef}
            className="command-palette-input"
            placeholder="Type a command..."
            value={query}
            onChange={(e) => { setQuery(e.target.value); setFocusedIndex(0) }}
            onKeyDown={handleKeyDown}
          />
        </div>

        <div className="command-palette-results">
          {filteredCommands.length === 0 ? (
            <div className="command-palette-empty">No commands found</div>
          ) : (
            filteredCommands.map((cmd, i) => (
              <div
                key={cmd.id}
                className={`command-palette-item ${i === focusedIndex ? 'focused' : ''}`}
                onClick={cmd.action}
                onMouseEnter={() => setFocusedIndex(i)}
              >
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span className="command-palette-item-label">{cmd.label}</span>
                  {cmd.description && (
                    <span className="command-palette-item-desc">{cmd.description}</span>
                  )}
                </div>
                {cmd.shortcut && (
                  <span className="command-palette-item-shortcut">{cmd.shortcut}</span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
