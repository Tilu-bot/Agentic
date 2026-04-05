import React, { useState, useCallback, useRef } from 'react'

interface ChatInputProps {
  onSend: (message: string) => void
  onAbort: () => void
  isRunning: boolean
}

const SendIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
)

const StopIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="currentColor">
    <rect x="6" y="6" width="12" height="12" rx="1" />
  </svg>
)

export function ChatInput({ onSend, onAbort, isRunning }: ChatInputProps): React.ReactElement {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const handleSend = useCallback(() => {
    const trimmed = text.trim()
    if (!trimmed || isRunning) return
    onSend(trimmed)
    setText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [text, isRunning, onSend])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value)
    // Auto-grow textarea
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [])

  return (
    <div className="chat-input-area">
      <div className="chat-input-wrapper">
        <textarea
          ref={textareaRef}
          className="chat-textarea"
          placeholder={isRunning ? 'Agent is working...' : 'Ask the agent anything... (Enter to send, Shift+Enter for newline)'}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={isRunning}
          rows={1}
        />

        {isRunning ? (
          <button
            className="chat-abort-btn"
            onClick={onAbort}
            title="Stop agent"
            aria-label="Stop agent"
          >
            <StopIcon />
          </button>
        ) : (
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={!text.trim()}
            title="Send message"
            aria-label="Send message"
          >
            <SendIcon />
          </button>
        )}
      </div>

      <div className="chat-hint">
        Enter to send · Shift+Enter for newline
      </div>
    </div>
  )
}
