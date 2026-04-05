import React, { useState } from 'react'
import { ToolUseEvent } from '../../types'

interface ToolUseCardProps {
  toolUse: ToolUseEvent
}

const ChevronIcon = ({ down }: { down: boolean }): React.ReactElement => (
  <svg viewBox="0 0 12 12" fill="currentColor" width="12" height="12" style={{ transform: down ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>
    <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth={1.5} fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

function StatusIcon({ status }: { status: ToolUseEvent['status'] }): React.ReactElement {
  if (status === 'running') {
    return (
      <svg className="spin" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth={2} width={14} height={14}>
        <circle cx="12" cy="12" r="10" strokeOpacity={0.25} />
        <path d="M12 2a10 10 0 0110 10" />
      </svg>
    )
  }
  if (status === 'success') {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="#4caf50" strokeWidth={2} width={14} height={14}>
        <polyline points="20 6 9 17 4 12" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="var(--text-error)" strokeWidth={2} width={14} height={14}>
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  )
}

export function ToolUseCard({ toolUse }: ToolUseCardProps): React.ReactElement {
  const [expanded, setExpanded] = useState(false)
  const hasOutput = !!toolUse.output || !!toolUse.error

  return (
    <div className="tool-use-card">
      <div className="tool-use-card-header" onClick={() => setExpanded((v) => !v)}>
        <StatusIcon status={toolUse.status} />
        <span className="tool-use-card-name">{toolUse.toolName}</span>

        {/* Key input params summary */}
        {Object.entries(toolUse.input).slice(0, 1).map(([k, v]) => (
          <span key={k} style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
            {typeof v === 'string' ? v.slice(0, 60) : JSON.stringify(v).slice(0, 60)}
          </span>
        ))}

        {toolUse.durationMs !== undefined && (
          <span style={{ fontSize: 10, color: 'var(--text-muted)', flexShrink: 0 }}>
            {toolUse.durationMs}ms
          </span>
        )}

        {hasOutput && <ChevronIcon down={expanded} />}
      </div>

      {expanded && hasOutput && (
        <div className="tool-use-card-body">
          {toolUse.error ? (
            <pre style={{ color: 'var(--text-error)' }}>{toolUse.error}</pre>
          ) : (
            <pre>{toolUse.output}</pre>
          )}
        </div>
      )}
    </div>
  )
}
