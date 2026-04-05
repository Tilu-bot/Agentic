import React, { useCallback } from 'react'
import { useFileTreeStore } from '../../stores/fileTreeStore'
import { FileTreeNode } from './FileTreeNode'

interface FileTreeProps {
  onOpenFile: (filePath: string) => void
  onOpenFolder: () => void
}

const FolderIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M3 7a2 2 0 012-2h5l2 2h7a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
  </svg>
)

const NewFileIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" />
    <path d="M14 2v6h6M12 11v6M9 14h6" />
  </svg>
)

const RefreshIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
  </svg>
)

export function FileTree({ onOpenFile, onOpenFolder }: FileTreeProps): React.ReactElement {
  const { rootPath, tree, isLoading, setRoot } = useFileTreeStore()

  const refreshTree = useCallback(async () => {
    if (!rootPath) return
    const newTree = await window.api.fs.listDirectory(rootPath)
    setRoot(rootPath, newTree)
  }, [rootPath, setRoot])

  const handleNewFile = useCallback(async () => {
    if (!rootPath) return
    const name = window.prompt('Enter file name:')
    if (!name || !name.trim()) return
    await window.api.fs.createFile(`${rootPath}/${name.trim()}`)
    await refreshTree()
  }, [rootPath, refreshTree])

  if (!rootPath) {
    return (
      <div className="file-tree-empty" style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24 }}>
        <FolderIcon />
        <span style={{ fontSize: 12, color: 'var(--text-secondary)', textAlign: 'center' }}>
          No folder open
        </span>
        <button className="btn-primary" onClick={onOpenFolder}>
          Open Folder
        </button>
      </div>
    )
  }

  const folderName = rootPath.split('/').pop() ?? rootPath

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="sidebar-header">
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {folderName.toUpperCase()}
        </span>
        <div className="sidebar-header-actions">
          <button className="icon-btn" onClick={handleNewFile} title="New File">
            <NewFileIcon />
          </button>
          <button className="icon-btn" onClick={refreshTree} title="Refresh">
            <RefreshIcon />
          </button>
        </div>
      </div>

      <div className="sidebar-content">
        {isLoading ? (
          <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 11 }}>Loading...</div>
        ) : (
          <div className="file-tree">
            {tree.map((entry) => (
              <FileTreeNode
                key={entry.path}
                entry={entry}
                depth={0}
                onOpenFile={onOpenFile}
                onRefresh={refreshTree}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
