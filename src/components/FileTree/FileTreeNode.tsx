import React, { useCallback, useState } from 'react'
import { FileEntry } from '../../types'
import { useFileTreeStore } from '../../stores/fileTreeStore'

interface FileTreeNodeProps {
  entry: FileEntry
  depth: number
  onOpenFile: (filePath: string) => void
  onRefresh: () => Promise<void>
}

const ArrowIcon = (): React.ReactElement => (
  <svg viewBox="0 0 12 12" fill="currentColor" width="12" height="12">
    <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth={1.5} fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

const FolderOpenIcon = (): React.ReactElement => (
  <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
    <path d="M1 3.5A1.5 1.5 0 012.5 2h3.586l1 1H14a1 1 0 011 1v1H2.5A1.5 1.5 0 001 6.5v-3z" fill="#dcb67a" />
    <path d="M1 6.5A1.5 1.5 0 012.5 5h11A1.5 1.5 0 0115 6.5v5A1.5 1.5 0 0113.5 13h-11A1.5 1.5 0 011 11.5v-5z" fill="#dcb67a" />
  </svg>
)

const FolderClosedIcon = (): React.ReactElement => (
  <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
    <path d="M1 3.5A1.5 1.5 0 012.5 2h3.586l1 1H14a1 1 0 011 1v8.5A1.5 1.5 0 0113.5 14h-11A1.5 1.5 0 011 12.5v-9z" fill="#dcb67a" />
  </svg>
)

function getFileIcon(name: string): React.ReactElement {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  const colors: Record<string, string> = {
    ts: '#3178c6', tsx: '#3178c6', js: '#f7df1e', jsx: '#61dafb',
    json: '#fbc02d', md: '#42a5f5', css: '#ef6c00', scss: '#ce3c65',
    html: '#e44d26', py: '#3572a5', go: '#00acd7', rs: '#dea584',
    sh: '#89e051', bash: '#89e051', yml: '#cb171e', yaml: '#cb171e',
    toml: '#9c4221', sql: '#e38d00', graphql: '#e10098', dockerfile: '#0db7ed',
    java: '#b07219', rb: '#cc342d', php: '#4f5d95', swift: '#f05138',
    kt: '#a97bff', dart: '#00b4ab', lua: '#000080', c: '#555555', cpp: '#f34b7d'
  }

  const color = colors[ext] ?? 'var(--text-secondary)'

  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <path d="M5 1h6l3 3v10a1 1 0 01-1 1H3a1 1 0 01-1-1V2a1 1 0 011-1z" fill={color} opacity={0.9} />
      <path d="M11 1v3h3" fill="none" stroke={color} strokeWidth={1} />
    </svg>
  )
}

export function FileTreeNode({ entry, depth, onOpenFile, onRefresh }: FileTreeNodeProps): React.ReactElement {
  const { expandedPaths, selectedPath, toggleExpanded, setSelected } = useFileTreeStore()
  const isExpanded = expandedPaths.has(entry.path)
  const isSelected = selectedPath === entry.path
  const [showContextMenu, setShowContextMenu] = useState(false)

  const handleClick = useCallback(() => {
    setSelected(entry.path)
    if (entry.isDirectory) {
      toggleExpanded(entry.path)
    } else {
      onOpenFile(entry.path)
    }
  }, [entry, setSelected, toggleExpanded, onOpenFile])

  const handleDelete = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm(`Delete "${entry.name}"?`)) return
    await window.api.fs.deleteFile(entry.path)
    await onRefresh()
  }, [entry, onRefresh])

  const indent = depth * 12 + 4

  return (
    <>
      <div
        className={`file-tree-node ${isSelected ? 'selected' : ''}`}
        onClick={handleClick}
        onContextMenu={(e) => { e.preventDefault(); setSelected(entry.path); setShowContextMenu(true) }}
        title={entry.path}
      >
        <div className="file-tree-node-indent" style={{ width: indent }} />

        {entry.isDirectory ? (
          <div className={`file-tree-node-arrow ${isExpanded ? 'expanded' : ''}`}>
            <ArrowIcon />
          </div>
        ) : (
          <div style={{ width: 16, flexShrink: 0 }} />
        )}

        <div className="file-tree-node-icon">
          {entry.isDirectory
            ? isExpanded ? <FolderOpenIcon /> : <FolderClosedIcon />
            : getFileIcon(entry.name)}
        </div>

        <span className="file-tree-node-name">{entry.name}</span>
      </div>

      {entry.isDirectory && isExpanded && entry.children && (
        <>
          {entry.children.map((child) => (
            <FileTreeNode
              key={child.path}
              entry={child}
              depth={depth + 1}
              onOpenFile={onOpenFile}
              onRefresh={onRefresh}
            />
          ))}
        </>
      )}
    </>
  )
}
