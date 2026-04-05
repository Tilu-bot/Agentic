import { create } from 'zustand'
import { EditorTab } from '../types'
import { v4 as uuidv4 } from 'uuid'
import * as path from 'path-browserify'

function guessLanguage(filePath: string): string {
  const ext = filePath.split('.').pop()?.toLowerCase() ?? ''
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
    json: 'json', md: 'markdown', mdx: 'markdown', css: 'css', scss: 'scss',
    html: 'html', xml: 'xml', yaml: 'yaml', yml: 'yaml', toml: 'toml',
    py: 'python', rb: 'ruby', go: 'go', rs: 'rust', java: 'java',
    c: 'c', cpp: 'cpp', cs: 'csharp', php: 'php', sh: 'shell',
    bash: 'shell', zsh: 'shell', fish: 'shell', sql: 'sql', graphql: 'graphql',
    dockerfile: 'dockerfile', tf: 'hcl', hcl: 'hcl', swift: 'swift',
    kt: 'kotlin', dart: 'dart', lua: 'lua', r: 'r', vim: 'vim',
    txt: 'plaintext', log: 'plaintext', env: 'plaintext', gitignore: 'plaintext'
  }
  const basename = filePath.split('/').pop()?.toLowerCase() ?? ''
  if (basename === 'dockerfile') return 'dockerfile'
  if (basename === 'makefile') return 'makefile'
  return map[ext] ?? 'plaintext'
}

interface EditorStore {
  tabs: EditorTab[]
  activeTabId: string | null
  recentFiles: string[]

  openFile: (filePath: string, content: string) => void
  closeTab: (tabId: string) => void
  setActiveTab: (tabId: string) => void
  updateTabContent: (tabId: string, content: string) => void
  markTabSaved: (tabId: string) => void
  setTabLoading: (tabId: string, loading: boolean) => void
  getActiveTab: () => EditorTab | null
  closeAllTabs: () => void
  moveTab: (fromIndex: number, toIndex: number) => void
}

export const useEditorStore = create<EditorStore>((set, get) => ({
  tabs: [],
  activeTabId: null,
  recentFiles: [],

  openFile: (filePath, content) => {
    const existing = get().tabs.find((t) => t.path === filePath)
    if (existing) {
      set({ activeTabId: existing.id })
      return
    }
    const tab: EditorTab = {
      id: uuidv4(),
      path: filePath,
      content,
      savedContent: content,
      language: guessLanguage(filePath),
      isDirty: false,
      isLoading: false
    }
    set((s) => ({
      tabs: [...s.tabs, tab],
      activeTabId: tab.id,
      recentFiles: [filePath, ...s.recentFiles.filter((p) => p !== filePath)].slice(0, 20)
    }))
  },

  closeTab: (tabId) => {
    set((s) => {
      const idx = s.tabs.findIndex((t) => t.id === tabId)
      const newTabs = s.tabs.filter((t) => t.id !== tabId)
      let newActiveId: string | null = null
      if (s.activeTabId === tabId && newTabs.length > 0) {
        newActiveId = newTabs[Math.max(0, idx - 1)]?.id ?? newTabs[0].id
      } else if (s.activeTabId !== tabId) {
        newActiveId = s.activeTabId
      }
      return { tabs: newTabs, activeTabId: newActiveId }
    })
  },

  setActiveTab: (tabId) => set({ activeTabId: tabId }),

  updateTabContent: (tabId, content) => {
    set((s) => ({
      tabs: s.tabs.map((t) =>
        t.id === tabId ? { ...t, content, isDirty: content !== t.savedContent } : t
      )
    }))
  },

  markTabSaved: (tabId) => {
    set((s) => ({
      tabs: s.tabs.map((t) =>
        t.id === tabId ? { ...t, savedContent: t.content, isDirty: false } : t
      )
    }))
  },

  setTabLoading: (tabId, loading) => {
    set((s) => ({
      tabs: s.tabs.map((t) => (t.id === tabId ? { ...t, isLoading: loading } : t))
    }))
  },

  getActiveTab: () => {
    const { tabs, activeTabId } = get()
    return tabs.find((t) => t.id === activeTabId) ?? null
  },

  closeAllTabs: () => set({ tabs: [], activeTabId: null }),

  moveTab: (fromIndex, toIndex) => {
    set((s) => {
      const tabs = [...s.tabs]
      const [moved] = tabs.splice(fromIndex, 1)
      tabs.splice(toIndex, 0, moved)
      return { tabs }
    })
  }
}))
