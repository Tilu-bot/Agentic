import React, { useCallback } from 'react'
import { useEditorStore } from '../../stores/editorStore'

const CloseIcon = (): React.ReactElement => (
  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M2 2l8 8M10 2l-8 8" />
  </svg>
)

export function EditorTabs(): React.ReactElement {
  const { tabs, activeTabId, setActiveTab, closeTab } = useEditorStore()

  const handleClose = useCallback((e: React.MouseEvent, tabId: string) => {
    e.stopPropagation()
    closeTab(tabId)
  }, [closeTab])

  if (tabs.length === 0) return <div style={{ height: 'var(--tab-height)', background: 'var(--bg-panel)', borderBottom: '1px solid var(--border)', flexShrink: 0 }} />

  return (
    <div className="editor-tabs" role="tablist">
      {tabs.map((tab) => {
        const filename = tab.path.split('/').pop() ?? tab.path
        return (
          <div
            key={tab.id}
            className={`editor-tab ${tab.id === activeTabId ? 'active' : ''}`}
            role="tab"
            aria-selected={tab.id === activeTabId}
            onClick={() => setActiveTab(tab.id)}
            title={tab.path}
          >
            {tab.isDirty && <span className="editor-tab-dot" title="Unsaved changes" />}
            <span className="editor-tab-name">{filename}</span>
            <button
              className="editor-tab-close"
              onClick={(e) => handleClose(e, tab.id)}
              aria-label={`Close ${filename}`}
              title={`Close ${filename}`}
            >
              <CloseIcon />
            </button>
          </div>
        )
      })}
    </div>
  )
}
