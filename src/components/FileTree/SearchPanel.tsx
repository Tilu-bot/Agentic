import React, { useState, useCallback, useRef } from 'react'
import { useFileTreeStore } from '../../stores/fileTreeStore'

interface SearchPanelProps {
  onOpenFile: (filePath: string) => void
}

interface SearchResult {
  path: string
  line: number
  column: number
  text: string
}

interface GroupedResults {
  [path: string]: SearchResult[]
}

const SearchIcon = (): React.ReactElement => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.35-4.35" />
  </svg>
)

export function SearchPanel({ onOpenFile }: SearchPanelProps): React.ReactElement {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GroupedResults>({})
  const [isSearching, setIsSearching] = useState(false)
  const [resultCount, setResultCount] = useState(0)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const { rootPath } = useFileTreeStore()

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim() || !rootPath) {
      setResults({})
      setResultCount(0)
      return
    }
    setIsSearching(true)
    try {
      const raw = await window.api.fs.searchFiles(rootPath, q, {
        caseSensitive: false,
        regex: false
      })
      const grouped: GroupedResults = {}
      for (const r of raw) {
        if (!grouped[r.path]) grouped[r.path] = []
        grouped[r.path].push(r)
      }
      setResults(grouped)
      setResultCount(raw.length)
    } catch {
      setResults({})
      setResultCount(0)
    } finally {
      setIsSearching(false)
    }
  }, [rootPath])

  const handleQueryChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value
    setQuery(q)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(q), 400)
  }, [doSearch])

  const handleOpenResult = useCallback((filePath: string) => {
    onOpenFile(filePath)
  }, [onOpenFile])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="sidebar-header">
        <span>SEARCH</span>
        {resultCount > 0 && (
          <span style={{ color: 'var(--text-muted)' }}>{resultCount} results</span>
        )}
      </div>

      <div style={{ padding: '8px' }}>
        <div className="search-input-row">
          <SearchIcon />
          <input
            className="search-input"
            type="text"
            placeholder="Search in files..."
            value={query}
            onChange={handleQueryChange}
            disabled={!rootPath}
          />
        </div>
      </div>

      {!rootPath && (
        <div style={{ padding: '16px', color: 'var(--text-muted)', fontSize: 11 }}>
          Open a folder to search
        </div>
      )}

      {isSearching && (
        <div style={{ padding: '8px 16px', color: 'var(--text-muted)', fontSize: 11 }}>
          Searching...
        </div>
      )}

      <div className="search-results sidebar-content">
        {Object.entries(results).map(([filePath, matches]) => (
          <div key={filePath}>
            <div
              className="search-result-file"
              onClick={() => handleOpenResult(filePath)}
              title={filePath}
            >
              {filePath.replace(rootPath + '/', '')}
            </div>
            {matches.map((m, i) => (
              <div
                key={i}
                className="search-result-match"
                onClick={() => handleOpenResult(m.path)}
              >
                <span className="search-result-line-num">{m.line}</span>
                <span className="search-result-text">{m.text}</span>
              </div>
            ))}
          </div>
        ))}

        {query && !isSearching && Object.keys(results).length === 0 && rootPath && (
          <div style={{ padding: '16px', color: 'var(--text-muted)', fontSize: 11 }}>
            No results found
          </div>
        )}
      </div>
    </div>
  )
}
