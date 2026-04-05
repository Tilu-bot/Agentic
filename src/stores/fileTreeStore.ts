import { create } from 'zustand'
import { FileEntry } from '../types'

interface FileTreeStore {
  rootPath: string | null
  tree: FileEntry[]
  expandedPaths: Set<string>
  selectedPath: string | null
  isLoading: boolean

  setRoot: (rootPath: string, tree: FileEntry[]) => void
  setTree: (tree: FileEntry[]) => void
  toggleExpanded: (path: string) => void
  setExpanded: (path: string, expanded: boolean) => void
  setSelected: (path: string | null) => void
  setLoading: (loading: boolean) => void
  closeFolder: () => void
}

export const useFileTreeStore = create<FileTreeStore>((set) => ({
  rootPath: null,
  tree: [],
  expandedPaths: new Set(),
  selectedPath: null,
  isLoading: false,

  setRoot: (rootPath, tree) =>
    set({
      rootPath,
      tree,
      expandedPaths: new Set([rootPath]),
      selectedPath: null,
      isLoading: false
    }),

  setTree: (tree) => set({ tree }),

  toggleExpanded: (path) =>
    set((s) => {
      const next = new Set(s.expandedPaths)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return { expandedPaths: next }
    }),

  setExpanded: (path, expanded) =>
    set((s) => {
      const next = new Set(s.expandedPaths)
      if (expanded) next.add(path)
      else next.delete(path)
      return { expandedPaths: next }
    }),

  setSelected: (path) => set({ selectedPath: path }),

  setLoading: (loading) => set({ isLoading: loading }),

  closeFolder: () =>
    set({
      rootPath: null,
      tree: [],
      expandedPaths: new Set(),
      selectedPath: null,
      isLoading: false
    })
}))
