export type Activity = { kind: 'cmd' | 'edit' | 'error'; text: string; isRunning: boolean }

export type ChatEntry = { ts: number; from: string; kind: string; text: string }

export type Member = { id: string; name: string; color: string; role: string; avatar?: string }

export type AgentView = {
  member: Member
  wp: string
  summary: string
  step: string
  note: string
  workdir: string
  isRunning: boolean
  startedAt: number
  updatedAt: number
  commands: number
  edits: number
  tokens: number
  usage: { input: number; cached: number; output: number; reasoning: number }
  model: string
  effort: string
  tier: string
  totalTokens: number
  recent: Activity[]
  chat: ChatEntry[]
}

export type Phase = { id: string; label: string; done: number; total: number; isCurrent: boolean }

export type Decision = {
  id: string
  question: string
  options: { label: string; detail: string }[]
  status: string
}

/** `.crew/config.json` in the project root, with defaults filled in. */
export type CrewConfig = {
  isActive: boolean
  project: string
  lang: 'en' | 'tr'
  planDir: string
  stateDir: string
  phasePrefix: string
}

export type Snapshot = {
  phase: string
  focus: string
  lead: Member
  user: Member
  steps: { id: string; label: string }[]
  bar: string
  themeId: string
  themeTitle: string
  teamTokens: number
  phases: Phase[]
  agents: AgentView[]
  prOpen: number
  decision: Decision | null
  checkedAt: number
}

export type DiffFile = { path: string; added: number; removed: number; isNew: boolean }

export type DiffView = { files: DiffFile[]; selected: string; patch: string; error: string }

declare module 'claude-code' {
  interface PluginState {
    'agent-crew': {
      config: CrewConfig
      snapshot: Snapshot
      opened: string[]
      tick: number
      lastSteps: Record<string, string>
      hiddenDecision: string
      diffs: Record<string, DiffView>
      diffOpen: string[]
      health: { at: number; ms: number; error: string; count: number }
    }
  }
}
