import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { LLMProvider, ProviderSettings } from '../types'

interface SettingsStore {
  provider: LLMProvider
  model: string
  apiKey: string
  ollamaUrl: string
  maxTokens: number
  temperature: number
  planModeEnabled: boolean
  autoApplyDiffs: boolean
  fontSize: number
  fontFamily: string
  wordWrap: boolean
  minimap: boolean

  setProvider: (provider: LLMProvider) => void
  setModel: (model: string) => void
  setApiKey: (key: string) => void
  setOllamaUrl: (url: string) => void
  setMaxTokens: (n: number) => void
  setTemperature: (t: number) => void
  setPlanModeEnabled: (v: boolean) => void
  setAutoApplyDiffs: (v: boolean) => void
  setFontSize: (n: number) => void
  setFontFamily: (f: string) => void
  setWordWrap: (v: boolean) => void
  setMinimap: (v: boolean) => void
  getProviderSettings: () => ProviderSettings
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set, get) => ({
      provider: 'anthropic',
      model: 'claude-opus-4-5',
      apiKey: '',
      ollamaUrl: 'http://localhost:11434',
      maxTokens: 8192,
      temperature: 0.3,
      planModeEnabled: true,
      autoApplyDiffs: false,
      fontSize: 14,
      fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
      wordWrap: false,
      minimap: true,

      setProvider: (provider) => set({ provider }),
      setModel: (model) => set({ model }),
      setApiKey: (apiKey) => set({ apiKey }),
      setOllamaUrl: (ollamaUrl) => set({ ollamaUrl }),
      setMaxTokens: (maxTokens) => set({ maxTokens }),
      setTemperature: (temperature) => set({ temperature }),
      setPlanModeEnabled: (planModeEnabled) => set({ planModeEnabled }),
      setAutoApplyDiffs: (autoApplyDiffs) => set({ autoApplyDiffs }),
      setFontSize: (fontSize) => set({ fontSize }),
      setFontFamily: (fontFamily) => set({ fontFamily }),
      setWordWrap: (wordWrap) => set({ wordWrap }),
      setMinimap: (minimap) => set({ minimap }),

      getProviderSettings: () => {
        const s = get()
        return {
          provider: s.provider,
          model: s.model,
          apiKey: s.apiKey,
          ollamaUrl: s.ollamaUrl,
          maxTokens: s.maxTokens,
          temperature: s.temperature
        }
      }
    }),
    {
      name: 'nexus-agent-settings',
      // Never persist the API key to localStorage for security
      partialize: (state) => ({
        provider: state.provider,
        model: state.model,
        ollamaUrl: state.ollamaUrl,
        maxTokens: state.maxTokens,
        temperature: state.temperature,
        planModeEnabled: state.planModeEnabled,
        autoApplyDiffs: state.autoApplyDiffs,
        fontSize: state.fontSize,
        fontFamily: state.fontFamily,
        wordWrap: state.wordWrap,
        minimap: state.minimap
      })
    }
  )
)
