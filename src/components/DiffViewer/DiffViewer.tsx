import React, { useState } from 'react'
import { DiffProposal } from '../../types'
import * as diff from 'diff'

interface DiffViewerProps {
  proposal: DiffProposal
  onAccept: () => void
  onReject: () => void
}

interface DiffLine {
  type: 'added' | 'removed' | 'context'
  content: string
  lineNum?: number
}

function computeDiffLines(original: string, proposed: string): DiffLine[] {
  const changes = diff.diffLines(original, proposed)
  const result: DiffLine[] = []
  let lineNum = 1

  for (const change of changes) {
    const lines = change.value.split('\n')
    if (lines[lines.length - 1] === '') lines.pop()

    for (const line of lines) {
      if (change.added) {
        result.push({ type: 'added', content: line })
      } else if (change.removed) {
        result.push({ type: 'removed', content: line, lineNum })
        lineNum++
      } else {
        result.push({ type: 'context', content: line, lineNum })
        lineNum++
      }
    }
  }

  return result
}

export function DiffViewer({ proposal, onAccept, onReject }: DiffViewerProps): React.ReactElement {
  const [collapsed, setCollapsed] = useState(false)
  const filename = proposal.filePath.split('/').pop() ?? proposal.filePath

  const isPending = proposal.status === 'pending'
  const isAccepted = proposal.status === 'accepted'
  const isRejected = proposal.status === 'rejected'

  const diffLines = computeDiffLines(proposal.originalContent, proposal.proposedContent)

  // Show only up to 5 context lines around changes to keep it compact
  const maxContextLines = 3
  const visibleLines: Array<DiffLine & { showEllipsis?: boolean }> = []
  let consecutiveContext = 0
  let skippedContext = 0

  for (let i = 0; i < diffLines.length; i++) {
    const line = diffLines[i]
    if (line.type === 'context') {
      consecutiveContext++
      if (consecutiveContext > maxContextLines) {
        skippedContext++
        continue
      }
    } else {
      if (skippedContext > 0) {
        visibleLines.push({ type: 'context', content: `... ${skippedContext} lines hidden ...`, showEllipsis: true })
        skippedContext = 0
      }
      consecutiveContext = 0
    }
    visibleLines.push(line)
  }

  const addedCount = diffLines.filter((l) => l.type === 'added').length
  const removedCount = diffLines.filter((l) => l.type === 'removed').length

  return (
    <div className="diff-viewer" style={{ margin: '4px 0', opacity: isRejected ? 0.5 : 1 }}>
      <div className="diff-viewer-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, overflow: 'hidden' }}>
          <button
            onClick={() => setCollapsed((v) => !v)}
            style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: 0 }}
          >
            {collapsed ? '▶' : '▼'}
          </button>
          <span className="diff-viewer-path" title={proposal.filePath}>{filename}</span>
          <span style={{ fontSize: 10, color: '#4caf50' }}>+{addedCount}</span>
          <span style={{ fontSize: 10, color: 'var(--text-error)' }}>-{removedCount}</span>
          {proposal.description && (
            <span style={{ fontSize: 10, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {proposal.description}
            </span>
          )}
        </div>

        {isPending && (
          <div className="diff-viewer-actions">
            <button className="btn-accept" onClick={onAccept}>✓ Accept</button>
            <button className="btn-reject" onClick={onReject}>✕ Reject</button>
          </div>
        )}

        {isAccepted && (
          <span style={{ fontSize: 10, color: '#4caf50', fontWeight: 600 }}>✓ Accepted</span>
        )}
        {isRejected && (
          <span style={{ fontSize: 10, color: 'var(--text-error)', fontWeight: 600 }}>✕ Rejected</span>
        )}
      </div>

      {!collapsed && (
        <div className="diff-content">
          {visibleLines.map((line, i) => (
            <div key={i} className={`diff-line ${line.type}`}>
              <span className="diff-line-num">
                {line.showEllipsis ? '...' : line.lineNum ?? ''}
              </span>
              <span className="diff-line-content">{line.content}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
