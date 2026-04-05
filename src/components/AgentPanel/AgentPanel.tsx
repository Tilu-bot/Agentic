import React, { useRef, useEffect, useCallback, useState } from 'react'
import { useAgentStore } from '../../stores/agentStore'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { DiffViewer } from '../DiffViewer/DiffViewer'

interface AgentPanelProps {
  width: number
  onSendMessage: (message: string) => void
  onClose: () => void
}

const CloseIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M18 6L6 18M6 6l12 12" />
  </svg>
)

const TrashIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6l-1 14H6L5 6" />
    <path d="M9 6V4h6v2" />
  </svg>
)

const NewIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M12 5v14M5 12h14" />
  </svg>
)

export function AgentPanel({ width, onSendMessage, onClose }: AgentPanelProps): React.ReactElement {
  const { messages, status, pendingDiffs, currentPlan, planSteps, clearMessages, newSession, acceptDiff, rejectDiff } = useAgentStore()
  const scrollRef = useRef<HTMLDivElement | null>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleAcceptDiff = useCallback(async (diffId: string, filePath: string, newContent: string) => {
    await window.api.agent.applyDiff(filePath, newContent)
    acceptDiff(diffId)
  }, [acceptDiff])

  const handleRejectDiff = useCallback((diffId: string) => {
    rejectDiff(diffId)
  }, [rejectDiff])

  const handleAbort = useCallback(async () => {
    const { sessionId } = useAgentStore.getState()
    await window.api.agent.abort(sessionId)
    useAgentStore.getState().setStatus('idle')
  }, [])

  const statusDotClass = `agent-status-dot ${status !== 'idle' ? status : ''}`

  return (
    <div className="agent-panel" style={{ width }}>
      {/* Header */}
      <div className="agent-panel-header">
        <div className={statusDotClass} title={status} />
        <span className="agent-panel-title">Agent</span>
        <button
          className="icon-btn"
          onClick={newSession}
          title="New session"
        >
          <NewIcon />
        </button>
        <button
          className="icon-btn"
          onClick={clearMessages}
          title="Clear conversation"
        >
          <TrashIcon />
        </button>
        <button className="icon-btn" onClick={onClose} title="Close agent panel">
          <CloseIcon />
        </button>
      </div>

      {/* Plan display */}
      {currentPlan && planSteps.length > 0 && (
        <div className="plan-display">
          <div className="plan-title">📋 Plan</div>
          <ol className="plan-steps">
            {planSteps.map((step, i) => (
              <li key={i} className="plan-step">
                <span className="plan-step-num">{i + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Messages */}
      <div className="message-list" ref={scrollRef}>
        {messages.length === 0 ? (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            gap: 8,
            color: 'var(--text-muted)',
            textAlign: 'center',
            padding: 24,
            fontSize: 12
          }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1} width={40} height={40} style={{ opacity: 0.3 }}>
              <path d="M12 2a4 4 0 014 4v1h1a2 2 0 012 2v2a2 2 0 01-2 2h-1v1a4 4 0 01-8 0v-1H7a2 2 0 01-2-2V9a2 2 0 012-2h1V6a4 4 0 014-4z" />
            </svg>
            <span>Start a conversation with the agent</span>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id}>
              <MessageBubble message={msg} />
              {msg.diffProposals?.map((diff) => (
                <DiffViewer
                  key={diff.id}
                  proposal={diff}
                  onAccept={() => handleAcceptDiff(diff.id, diff.filePath, diff.proposedContent)}
                  onReject={() => handleRejectDiff(diff.id)}
                />
              ))}
            </div>
          ))
        )}
      </div>

      {/* Chat Input */}
      <ChatInput
        onSend={onSendMessage}
        onAbort={handleAbort}
        isRunning={status === 'running' || status === 'planning'}
      />
    </div>
  )
}
