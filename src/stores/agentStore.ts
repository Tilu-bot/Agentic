import { create } from 'zustand'
import {
  AgentMessage,
  AgentStatus,
  AgentUpdateEvent,
  DiffProposal,
  ToolUseEvent
} from '../types'
import { v4 as uuidv4 } from 'uuid'

interface AgentStore {
  sessionId: string
  messages: AgentMessage[]
  status: AgentStatus
  pendingDiffs: DiffProposal[]
  planSteps: string[]
  currentPlan: string | null
  abortController: AbortController | null

  addUserMessage: (content: string) => void
  startAssistantMessage: (messageId: string) => void
  appendChunk: (messageId: string, chunk: string) => void
  finalizeMessage: (messageId: string) => void
  addToolUseToMessage: (messageId: string, toolUse: ToolUseEvent) => void
  updateToolUse: (messageId: string, toolUseId: string, output: string, error?: string, durationMs?: number) => void
  addDiffProposal: (messageId: string, proposal: DiffProposal) => void
  acceptDiff: (diffId: string) => void
  rejectDiff: (diffId: string) => void
  setStatus: (status: AgentStatus) => void
  setPlan: (plan: string, steps: string[]) => void
  clearPlan: () => void
  clearMessages: () => void
  newSession: () => void
  processUpdate: (event: AgentUpdateEvent) => void
  getLastAssistantMessageId: () => string | null
}

export const useAgentStore = create<AgentStore>((set, get) => ({
  sessionId: uuidv4(),
  messages: [],
  status: 'idle',
  pendingDiffs: [],
  planSteps: [],
  currentPlan: null,
  abortController: null,

  addUserMessage: (content) => {
    const msg: AgentMessage = {
      id: uuidv4(),
      role: 'user',
      content,
      timestamp: Date.now()
    }
    set((s) => ({ messages: [...s.messages, msg] }))
  },

  startAssistantMessage: (messageId) => {
    const msg: AgentMessage = {
      id: messageId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      toolUses: [],
      diffProposals: [],
      isStreaming: true
    }
    set((s) => ({ messages: [...s.messages, msg] }))
  },

  appendChunk: (messageId, chunk) => {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === messageId ? { ...m, content: m.content + chunk } : m
      )
    }))
  },

  finalizeMessage: (messageId) => {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === messageId ? { ...m, isStreaming: false } : m
      )
    }))
  },

  addToolUseToMessage: (messageId, toolUse) => {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === messageId
          ? { ...m, toolUses: [...(m.toolUses ?? []), toolUse] }
          : m
      )
    }))
  },

  updateToolUse: (messageId, toolUseId, output, error, durationMs) => {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === messageId
          ? {
              ...m,
              toolUses: (m.toolUses ?? []).map((tu) =>
                tu.id === toolUseId
                  ? {
                      ...tu,
                      output,
                      error,
                      durationMs,
                      status: error ? 'error' : 'success'
                    }
                  : tu
              )
            }
          : m
      )
    }))
  },

  addDiffProposal: (messageId, proposal) => {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === messageId
          ? { ...m, diffProposals: [...(m.diffProposals ?? []), proposal] }
          : m
      ),
      pendingDiffs: [...s.pendingDiffs, proposal]
    }))
  },

  acceptDiff: (diffId) => {
    set((s) => ({
      pendingDiffs: s.pendingDiffs.filter((d) => d.id !== diffId),
      messages: s.messages.map((m) => ({
        ...m,
        diffProposals: (m.diffProposals ?? []).map((d) =>
          d.id === diffId ? { ...d, status: 'accepted' } : d
        )
      }))
    }))
  },

  rejectDiff: (diffId) => {
    set((s) => ({
      pendingDiffs: s.pendingDiffs.filter((d) => d.id !== diffId),
      messages: s.messages.map((m) => ({
        ...m,
        diffProposals: (m.diffProposals ?? []).map((d) =>
          d.id === diffId ? { ...d, status: 'rejected' } : d
        )
      }))
    }))
  },

  setStatus: (status) => set({ status }),

  setPlan: (currentPlan, planSteps) => set({ currentPlan, planSteps }),

  clearPlan: () => set({ currentPlan: null, planSteps: [] }),

  clearMessages: () => set({ messages: [], pendingDiffs: [], planSteps: [], currentPlan: null }),

  newSession: () =>
    set({
      sessionId: uuidv4(),
      messages: [],
      status: 'idle',
      pendingDiffs: [],
      planSteps: [],
      currentPlan: null
    }),

  getLastAssistantMessageId: () => {
    const msgs = get().messages
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') return msgs[i].id
    }
    return null
  },

  processUpdate: (event: AgentUpdateEvent) => {
    const { startAssistantMessage, appendChunk, finalizeMessage, addToolUseToMessage, updateToolUse, addDiffProposal, setPlan, setStatus, getLastAssistantMessageId } = get()

    switch (event.type) {
      case 'stream_start':
        startAssistantMessage(event.messageId)
        setStatus('running')
        break
      case 'stream_chunk':
        appendChunk(event.messageId, event.chunk)
        break
      case 'stream_end':
        finalizeMessage(event.messageId)
        break
      case 'tool_start': {
        const msgId = getLastAssistantMessageId()
        if (msgId) addToolUseToMessage(msgId, event.toolUse)
        break
      }
      case 'tool_end': {
        const msgId = getLastAssistantMessageId()
        if (msgId)
          updateToolUse(msgId, event.toolUseId, event.output, event.error, event.durationMs)
        break
      }
      case 'diff_proposal': {
        const msgId = getLastAssistantMessageId()
        if (msgId) addDiffProposal(msgId, event.proposal)
        break
      }
      case 'plan_proposed':
        setPlan(event.plan, event.steps)
        setStatus('planning')
        break
      case 'agent_done':
        setStatus('idle')
        break
      case 'agent_error':
        setStatus('error')
        break
    }
  }
}))
