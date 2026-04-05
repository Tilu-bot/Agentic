import React from 'react'
import { useSettingsStore } from '../../stores/settingsStore'
import { DEFAULT_MODELS, LLMProvider } from '../../types'

const PROVIDERS: { value: LLMProvider; label: string }[] = [
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'ollama', label: 'Ollama (local)' },
  { value: 'gemini', label: 'Google Gemini' }
]

export function SettingsPanel(): React.ReactElement {
  const settings = useSettingsStore()

  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>): void => {
    const provider = e.target.value as LLMProvider
    settings.setProvider(provider)
    settings.setModel(DEFAULT_MODELS[provider][0])
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="sidebar-header">
        <span>SETTINGS</span>
      </div>

      <div className="settings-panel">
        {/* LLM Provider */}
        <div className="settings-section">
          <div className="settings-section-title">LLM Provider</div>

          <div className="settings-field">
            <label className="settings-label">Provider</label>
            <select
              className="settings-select"
              value={settings.provider}
              onChange={handleProviderChange}
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>

          <div className="settings-field">
            <label className="settings-label">Model</label>
            <select
              className="settings-select"
              value={settings.model}
              onChange={(e) => settings.setModel(e.target.value)}
            >
              {DEFAULT_MODELS[settings.provider].map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          <div className="settings-field">
            <label className="settings-label">
              API Key {settings.provider === 'ollama' ? '(not required)' : ''}
            </label>
            <input
              type="password"
              className="settings-input"
              value={settings.apiKey}
              onChange={(e) => settings.setApiKey(e.target.value)}
              placeholder={
                settings.provider === 'anthropic'
                  ? 'sk-ant-...'
                  : settings.provider === 'openai'
                  ? 'sk-...'
                  : settings.provider === 'gemini'
                  ? 'AIza...'
                  : 'Not required for Ollama'
              }
              disabled={settings.provider === 'ollama'}
            />
          </div>

          {settings.provider === 'ollama' && (
            <div className="settings-field">
              <label className="settings-label">Ollama URL</label>
              <input
                type="text"
                className="settings-input"
                value={settings.ollamaUrl}
                onChange={(e) => settings.setOllamaUrl(e.target.value)}
                placeholder="http://localhost:11434"
              />
            </div>
          )}

          <div className="settings-field">
            <label className="settings-label">Max Tokens ({settings.maxTokens})</label>
            <input
              type="range"
              min={512}
              max={32768}
              step={512}
              value={settings.maxTokens}
              onChange={(e) => settings.setMaxTokens(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent)' }}
            />
          </div>

          <div className="settings-field">
            <label className="settings-label">Temperature ({settings.temperature})</label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={settings.temperature}
              onChange={(e) => settings.setTemperature(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent)' }}
            />
          </div>
        </div>

        {/* Agent behavior */}
        <div className="settings-section">
          <div className="settings-section-title">Agent Behavior</div>

          <label className="settings-checkbox-row">
            <input
              type="checkbox"
              checked={settings.planModeEnabled}
              onChange={(e) => settings.setPlanModeEnabled(e.target.checked)}
            />
            Plan before acting (show plan for approval)
          </label>

          <label className="settings-checkbox-row">
            <input
              type="checkbox"
              checked={settings.autoApplyDiffs}
              onChange={(e) => settings.setAutoApplyDiffs(e.target.checked)}
            />
            Auto-apply file changes (skip diff review)
          </label>
        </div>

        {/* Editor */}
        <div className="settings-section">
          <div className="settings-section-title">Editor</div>

          <div className="settings-field">
            <label className="settings-label">Font Size ({settings.fontSize}px)</label>
            <input
              type="range"
              min={10}
              max={24}
              step={1}
              value={settings.fontSize}
              onChange={(e) => settings.setFontSize(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent)' }}
            />
          </div>

          <label className="settings-checkbox-row">
            <input
              type="checkbox"
              checked={settings.wordWrap}
              onChange={(e) => settings.setWordWrap(e.target.checked)}
            />
            Word Wrap
          </label>

          <label className="settings-checkbox-row">
            <input
              type="checkbox"
              checked={settings.minimap}
              onChange={(e) => settings.setMinimap(e.target.checked)}
            />
            Show Minimap
          </label>
        </div>
      </div>
    </div>
  )
}
