import React, { useCallback, useEffect, useRef } from 'react'
import Editor from '@monaco-editor/react'
import type * as Monaco from 'monaco-editor'
import { useEditorStore } from '../../stores/editorStore'
import { useSettingsStore } from '../../stores/settingsStore'

const SaveIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z" />
    <polyline points="17 21 17 13 7 13 7 21" />
    <polyline points="7 3 7 8 15 8" />
  </svg>
)

export function EditorPanel(): React.ReactElement {
  const { tabs, activeTabId, updateTabContent, markTabSaved, getActiveTab } = useEditorStore()
  const { fontSize, fontFamily, wordWrap, minimap } = useSettingsStore()
  const editorRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null)
  const activeTab = getActiveTab()

  // Save file on Ctrl+S / Cmd+S
  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent): Promise<void> => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        const tab = useEditorStore.getState().getActiveTab()
        if (!tab) return
        const result = await window.api.fs.writeFile(tab.path, tab.content)
        if (result.success) {
          useEditorStore.getState().markTabSaved(tab.id)
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const handleEditorMount = useCallback((editor: Monaco.editor.IStandaloneCodeEditor) => {
    editorRef.current = editor
  }, [])

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (!activeTabId || value === undefined) return
    updateTabContent(activeTabId, value)
  }, [activeTabId, updateTabContent])

  const handleSave = useCallback(async () => {
    if (!activeTab) return
    const result = await window.api.fs.writeFile(activeTab.path, activeTab.content)
    if (result.success) {
      markTabSaved(activeTab.id)
    }
  }, [activeTab, markTabSaved])

  if (!activeTab) {
    return <WelcomeScreen />
  }

  const segments = activeTab.path.split('/')
  const breadcrumb = segments.slice(-3)

  return (
    <div className="editor-panel">
      <div className="editor-breadcrumb">
        {breadcrumb.map((seg, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="sep">›</span>}
            <span style={i === breadcrumb.length - 1 ? { color: 'var(--text-primary)' } : {}}>
              {seg}
            </span>
          </React.Fragment>
        ))}
        <div style={{ flex: 1 }} />
        {activeTab.isDirty && (
          <button
            className="icon-btn"
            onClick={handleSave}
            title="Save file (Ctrl+S)"
            style={{ marginRight: 4 }}
          >
            <SaveIcon />
          </button>
        )}
      </div>

      <div className="monaco-container">
        <Editor
          key={activeTab.id}
          value={activeTab.content}
          language={activeTab.language}
          theme="vs-dark"
          options={{
            fontSize,
            fontFamily,
            fontLigatures: true,
            wordWrap: wordWrap ? 'on' : 'off',
            minimap: { enabled: minimap },
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
            insertSpaces: true,
            renderWhitespace: 'boundary',
            smoothScrolling: true,
            cursorSmoothCaretAnimation: 'on',
            bracketPairColorization: { enabled: true },
            renderLineHighlight: 'line',
            padding: { top: 8, bottom: 8 }
          }}
          onMount={handleEditorMount}
          onChange={handleEditorChange}
        />
      </div>
    </div>
  )
}

function WelcomeScreen(): React.ReactElement {
  return (
    <div className="welcome-screen">
      <div>
        <h1>Nexus Agent</h1>
        <p style={{ marginTop: 8, color: 'var(--text-muted)' }}>
          AI-powered coding assistant
        </p>
      </div>

      <p>Open a folder and start chatting with the agent to write, edit, and debug code.</p>

      <div className="welcome-shortcuts">
        <span className="welcome-shortcut-key">Ctrl+Shift+P</span>
        <span>Command Palette</span>
        <span className="welcome-shortcut-key">Ctrl+K Ctrl+O</span>
        <span>Open Folder</span>
        <span className="welcome-shortcut-key">Ctrl+S</span>
        <span>Save File</span>
        <span className="welcome-shortcut-key">Ctrl+`</span>
        <span>Toggle Terminal</span>
      </div>
    </div>
  )
}
