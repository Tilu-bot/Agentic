import React, { useEffect, useRef, useCallback } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { useFileTreeStore } from '../../stores/fileTreeStore'
import '@xterm/xterm/css/xterm.css'
import { v4 as uuidv4 } from 'uuid'

interface TerminalPanelProps {
  height: number
  onClose: () => void
}

const TrashIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6l-1 14H6L5 6" />
    <path d="M10 11v6M14 11v6" />
    <path d="M9 6V4h6v2" />
  </svg>
)

const CloseIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M18 6L6 18M6 6l12 12" />
  </svg>
)

export function TerminalPanel({ height, onClose }: TerminalPanelProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const terminalRef = useRef<Terminal | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const sessionIdRef = useRef<string>(uuidv4())
  const { rootPath } = useFileTreeStore()

  const initTerminal = useCallback(async () => {
    if (!containerRef.current || terminalRef.current) return

    const term = new Terminal({
      theme: {
        background: '#0d0d0d',
        foreground: '#d4d4d4',
        cursor: '#d4d4d4',
        black: '#000000',
        red: '#cd3131',
        green: '#0dbc79',
        yellow: '#e5e510',
        blue: '#2472c8',
        magenta: '#bc3fbc',
        cyan: '#11a8cd',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: '#f14c4c',
        brightGreen: '#23d18b',
        brightYellow: '#f5f543',
        brightBlue: '#3b8eea',
        brightMagenta: '#d670d6',
        brightCyan: '#29b8db',
        brightWhite: '#e5e5e5'
      },
      fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
      fontSize: 13,
      lineHeight: 1.2,
      cursorBlink: true,
      scrollback: 10000,
      allowProposedApi: true
    })

    const fitAddon = new FitAddon()
    const webLinksAddon = new WebLinksAddon()

    term.loadAddon(fitAddon)
    term.loadAddon(webLinksAddon)
    term.open(containerRef.current)
    fitAddon.fit()

    terminalRef.current = term
    fitAddonRef.current = fitAddon

    const sessionId = sessionIdRef.current

    // Create PTY process
    await window.api.terminal.create(sessionId, rootPath ?? undefined)

    // Listen for output data
    const unsubData = window.api.terminal.onData(sessionId, (data) => {
      term.write(data)
    })

    const unsubExit = window.api.terminal.onExit(sessionId, () => {
      term.write('\r\n\x1b[33mProcess exited. Press any key to restart.\x1b[0m')
    })

    // Forward user input to PTY
    term.onData((data) => {
      window.api.terminal.write(sessionId, data)
    })

    // Handle resize
    term.onResize(({ cols, rows }) => {
      window.api.terminal.resize(sessionId, cols, rows)
    })

    return () => {
      unsubData()
      unsubExit()
      window.api.terminal.destroy(sessionId)
      term.dispose()
    }
  }, [rootPath])

  useEffect(() => {
    let cleanup: (() => void) | undefined

    initTerminal().then((c) => {
      cleanup = c
    })

    return () => {
      cleanup?.()
      terminalRef.current = null
    }
  }, [initTerminal])

  // Refit when height changes
  useEffect(() => {
    const timer = setTimeout(() => {
      fitAddonRef.current?.fit()
    }, 50)
    return () => clearTimeout(timer)
  }, [height])

  const handleClear = useCallback(() => {
    terminalRef.current?.clear()
  }, [])

  const handleCd = useCallback(async () => {
    if (!rootPath) return
    await window.api.terminal.changeDir(sessionIdRef.current, rootPath)
  }, [rootPath])

  return (
    <div className="terminal-panel" style={{ height }}>
      <div className="terminal-toolbar">
        <span className="terminal-toolbar-title">Terminal</span>
        {rootPath && (
          <button className="icon-btn" onClick={handleCd} title="Go to workspace folder">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} width={14} height={14}>
              <path d="M3 7a2 2 0 012-2h5l2 2h7a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
            </svg>
          </button>
        )}
        <div className="terminal-toolbar-spacer" />
        <button className="icon-btn" onClick={handleClear} title="Clear terminal">
          <TrashIcon />
        </button>
        <button className="icon-btn" onClick={onClose} title="Close terminal">
          <CloseIcon />
        </button>
      </div>

      <div
        ref={containerRef}
        className="terminal-xterm"
        style={{ height: height - 28, overflow: 'hidden' }}
      />
    </div>
  )
}
