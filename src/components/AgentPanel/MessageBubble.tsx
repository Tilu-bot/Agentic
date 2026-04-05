import React, { useState } from 'react'
import { AgentMessage } from '../../types'
import { ToolUseCard } from './ToolUseCard'

interface MessageBubbleProps {
  message: AgentMessage
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function MessageBubble({ message }: MessageBubbleProps): React.ReactElement {
  const isUser = message.role === 'user'

  return (
    <div className="message-bubble">
      <div className="message-bubble-header">
        <span className={`message-role-badge ${message.role}`}>
          {isUser ? 'You' : 'Agent'}
        </span>
        <span>{formatTime(message.timestamp)}</span>
      </div>

      <div className={`message-body ${isUser ? 'user' : ''}`}>
        {message.content}
        {message.isStreaming && <span className="message-cursor" />}
      </div>

      {message.toolUses && message.toolUses.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {message.toolUses.map((tu) => (
            <ToolUseCard key={tu.id} toolUse={tu} />
          ))}
        </div>
      )}
    </div>
  )
}
