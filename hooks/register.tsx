import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import { banner, quotaDials, stepTrack } from './art'

import type { Activity, AgentView, ChatEntry, CrewConfig, Decision, DiffFile, DiffView, Member, Phase, Snapshot, UsageView, UsageWindow } from '../types'

// agent-crew: Claude Code as tech lead of a named team of coding agents.
// UI: a crew board, one pane per agent, a decision band above the prompt, toasts on step changes and a
// status-line summary. Everything is read from the project the session runs in:
//   .crew/config.json            { project, lang, planDir, stateDir, phasePrefix } (absent → quiet)
//   <planDir>/team.json          roster, steps, phases, themes        <planDir>/wp/<wp>.md  "- Summary:"
//   <stateDir>/board.json        phase, focus, per-WP {agent, step, note}
//   <stateDir>/chat/<wp>.jsonl   conversation (lead / agent / user)
//   <stateDir>/decision.json     a question the lead asks the user
//   <stateDir>/runs/<wp>/<ts>/   agent runs (status, workdir, model, events.jsonl)

const PLUGIN = 'agent-crew'
const BOARD_PANE = 'crew-board'
const DEFAULTS: CrewConfig = {
  isActive: false, project: '', lang: 'en', planDir: '.crew/plan', stateDir: '.crew/state', phasePrefix: 'D',
}
const LEAD: Member = { id: 'claude', name: 'Claude', color: '#d97757', role: 'Tech lead' }
const USER: Member = { id: 'user', name: 'You', color: '#60a5fa', role: 'Product owner' }
const EMPTY: Snapshot = {
  phase: '', focus: '', lead: LEAD, user: USER, steps: [], bar: 'blocks', themeId: '', themeTitle: '', teamTokens: 0,
  phases: [], agents: [], prOpen: 0, decision: null, checkedAt: 0,
}

const config = atom({ plugin: 'agent-crew', key: 'config' } as const, DEFAULTS)
const snapshot = atom({ plugin: 'agent-crew', key: 'snapshot' } as const, EMPTY)
const opened = atom({ plugin: 'agent-crew', key: 'opened' } as const, [])
const tick = atom({ plugin: 'agent-crew', key: 'tick' } as const, 0)
const lastSteps = atom({ plugin: 'agent-crew', key: 'lastSteps' } as const, {})
const hiddenDecision = atom({ plugin: 'agent-crew', key: 'hiddenDecision' } as const, '')
const diffs = atom({ plugin: 'agent-crew', key: 'diffs' } as const, {})
const diffOpen = atom({ plugin: 'agent-crew', key: 'diffOpen' } as const, [])
const health = atom({ plugin: 'agent-crew', key: 'health' } as const, { at: 0, ms: 0, error: '', count: 0 })

const ACTIVE_STEPS = new Set(['assigned', 'working', 'reported', 'reviewing', 'changes_requested', 'approved', 'pr_open', 'failed'])
const SPINNER = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
const agentPane = (id: string) => `crew-agent-${id}`
const commandName = (m: Member) =>
  m.name.toLocaleLowerCase('tr').replace(/ı/g, 'i').replace(/ğ/g, 'g').replace(/ü/g, 'u').replace(/ş/g, 's')
    .replace(/ö/g, 'o').replace(/ç/g, 'c').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

// ── strings ───────────────────────────────────────────────────────────────────────────────

const STRINGS = {
  en: {
    board: 'crew', noPhase: 'No phase set', roadmap: 'Roadmap', decisionWaiting: '⚑ Decision waiting: ',
    teamTotal: 'team total', tokens: 'tokens', prOpen: 'PR open', idle: 'Idle', open: 'Open', noTask: 'No task right now.',
    failedRetry: '  ✗ Failed — the lead will retry', model: 'model?', thinking: 'reasoning', input: 'input', cache: 'cache',
    output: 'output', thisTask: 'this task', commands: 'commands', fileChanges: 'file changes', lastActivity: 'last activity',
    ago: 'ago', live: 'Live', conversation: 'Conversation', showDiff: 'Show diff', hideDiff: 'Hide diff', askStatus: 'Ask status',
    stop: 'Stop', changedFiles: 'Changed files', reload: 'Reload', loading: 'Loading…', noChanges: 'No changes.', isNew: 'new',
    noteLabel: (n: string) => `Note for ${n} (goes to the lead first)`, notePlaceholder: 'e.g. also cover the edge case for empty tables',
    send: 'Send', noteSent: (n: string) => `Your note went to the lead → ${n}`, requestSent: 'Request sent to the lead',
    notFound: 'Agent not found.', staleBoard: 'Board could not refresh: ', updated: (a: string) => `updated ${a} ago`,
    updating: 'updating…', refresh: (n: number) => `refresh #${n}`, decisionTitle: '⚑ The lead needs your decision  ',
    later: 'Later', wildDecision: 'A wild DECISION appeared!', waiting: 'waiting…', whatWill: (n: string) => `What will ${n} do?`,
    run: 'RUN', chose: (l: string) => `${l} chosen — it's super effective! ⚡`, noteMsg: 'Crew note', requestMsg: 'Crew request',
    noteHint: (n: string) => `(Sent from the panel. Review it as the lead; if it fits, relay it to ${n} with tell.sh.)`,
    statusQ: 'Summarize the status of this work package and the next step.', stopQ: 'Stop this agent and write why on the board.',
    decisionMsg: 'Decision', boardOpened: 'Crew board opened.', paneOpened: (n: string) => `${n} pane opened.`,
    notConfigured: 'No crew in this project. Ask Claude to run the crew-init skill.', failedStep: 'failed', running: 'running',
    noWorkdir: 'no working directory', openBoard: 'Open the crew board', openAgent: (n: string, r: string) => `Open ${n} (${r})`,
    s: 's', m: 'm', h: 'h',
    quickNotes: ['Continue', 'Re-run the tests', 'Keep the scope smaller', 'Explain your last change'],
  },
  tr: {
    board: 'ekip', noPhase: 'Faz bilgisi yok', roadmap: 'Yol haritası', decisionWaiting: '⚑ Karar bekliyor: ',
    teamTotal: 'ekip toplam', tokens: 'token', prOpen: 'PR açık', idle: 'Boşta', open: 'Aç', noTask: 'Şu an görevi yok.',
    failedRetry: '  ✗ Hata — lead yeniden deneyecek', model: 'model?', thinking: 'düşünme', input: 'girdi', cache: 'önbellek',
    output: 'çıktı', thisTask: 'bu iş toplam', commands: 'komut', fileChanges: 'dosya değişikliği', lastActivity: 'son hareket',
    ago: 'önce', live: 'Canlı', conversation: 'Konuşma', showDiff: 'Farkı göster', hideDiff: 'Farkı gizle', askStatus: 'Durumu sor',
    stop: 'Durdur', changedFiles: 'Değişen dosyalar', reload: 'Yenile', loading: 'Yükleniyor…', noChanges: 'Değişiklik yok.', isNew: 'yeni',
    noteLabel: (n: string) => `${n}'ya not (önce lead'e gider)`, notePlaceholder: 'Örn: boş tablo durumunu da kapsa',
    send: 'Gönder', noteSent: (n: string) => `Notun lead'e iletildi → ${n}`, requestSent: "İstek lead'e iletildi",
    notFound: 'Ajan bulunamadı.', staleBoard: 'Pano güncellenemedi: ', updated: (a: string) => `güncellendi ${a} önce`,
    updating: 'güncelleniyor…', refresh: (n: number) => `${n}. yenileme`, decisionTitle: '⚑ Lead senden karar bekliyor  ',
    later: 'Sonra', wildDecision: 'Vahşi bir KARAR belirdi!', waiting: 'bekliyor…', whatWill: (n: string) => `${n} ne yapacak?`,
    run: 'KAÇ', chose: (l: string) => `${l} seçildi — süper etkili! ⚡`, noteMsg: 'Ekip notu', requestMsg: 'Ekip isteği',
    noteHint: (n: string) => `(Panelden gönderildi. Lead olarak değerlendir; uygunsa tell.sh ile ${n}'ya ilet.)`,
    statusQ: 'Bu işin durumunu ve sıradaki adımı kısaca özetler misin?', stopQ: 'Bu ajanı durdur ve nedenini panoya yaz.',
    decisionMsg: 'Karar', boardOpened: 'Ekip panosu açıldı.', paneOpened: (n: string) => `${n} paneli açıldı.`,
    notConfigured: "Bu projede ekip yok. Claude'dan crew-init skill'ini çalıştırmasını iste.", failedStep: 'hata aldı', running: 'çalışıyor',
    noWorkdir: 'çalışma klasörü yok', openBoard: 'Ekip panosunu aç', openAgent: (n: string, r: string) => `${n} (${r}) panelini aç`,
    s: 'sn', m: 'dk', h: 'sa',
    quickNotes: ['Devam et', 'Testleri yeniden çalıştır', 'Kapsamı küçült', 'Son değişikliğini açıkla'],
  },
}
type Strings = (typeof STRINGS)['en']
const strings = (c: CrewConfig): Strings => STRINGS[c.lang] ?? STRINGS.en

// ── reading the crew state (paths are relative to the session's working directory) ────────

async function readJson($: any, path: string, fallback: any) {
  return $.fs.read(path).then(JSON.parse).catch(() => fallback)
}

async function loadConfig($: any): Promise<CrewConfig> {
  const raw = await readJson($, '.crew/config.json', null)
  if (!raw) return DEFAULTS
  return { ...DEFAULTS, ...raw, isActive: true }
}

function shortCommand(raw: string): string {
  const m = /-Command '([\s\S]*)'$/.exec(raw)
  return (m ? m[1] : raw).replace(/\s+/g, ' ').trim()
}

export function parseEvents(text: string) {
  const items = new Map<string, Activity>()
  const order: string[] = []
  let commands = 0
  let edits = 0
  let tokens = 0
  const usage = { input: 0, cached: 0, output: 0, reasoning: 0 }
  const put = (id: string, act: Activity) => {
    if (!items.has(id)) order.push(id)
    items.set(id, act)
  }
  for (const raw of text.split('\n')) {
    let ev: any
    try {
      ev = JSON.parse(raw)
    } catch {
      continue
    }
    const item = ev.item
    const done = ev.type === 'item.completed'
    if (ev.type === 'turn.completed') {
      tokens += (ev.usage?.input_tokens ?? 0) + (ev.usage?.output_tokens ?? 0)
      usage.input += ev.usage?.input_tokens ?? 0
      usage.cached += ev.usage?.cached_input_tokens ?? 0
      usage.output += ev.usage?.output_tokens ?? 0
      usage.reasoning += ev.usage?.reasoning_output_tokens ?? 0
    } else if (item?.type === 'command_execution') {
      if (!done) commands += 1
      const failed = done && item.exit_code != null && item.exit_code !== 0
      put(item.id, {
        kind: failed ? 'error' : 'cmd',
        text: shortCommand(item.command ?? '') + (failed ? `  (exit ${item.exit_code})` : ''),
        isRunning: !done,
      })
    } else if (item?.type === 'file_change' && done) {
      edits += item.changes?.length ?? 0
      const files = (item.changes ?? []).map((ch: any) => String(ch.path).split(/[\\/]/).slice(-2).join('/'))
      put(item.id, { kind: 'edit', text: files.join(', '), isRunning: false })
    } else if (ev.event === 'result') {
      const resUsage = ev.result?.usage
      if (resUsage) {
        tokens += (resUsage.input_tokens ?? 0) + (resUsage.output_tokens ?? 0)
        usage.input += resUsage.input_tokens ?? 0
        usage.cached += resUsage.cache_read_tokens ?? 0
        usage.output += resUsage.output_tokens ?? 0
        usage.reasoning += resUsage.thinking_tokens ?? 0
      }
    } else if (ev.event === 'step_update' && ev.step_update?.step_type === 'tool') {
      const step = ev.step_update
      const isDone = step.state === 'DONE' || step.state === 'ERROR'
      const isError = step.state === 'ERROR'
      const toolName = step.tool_name
      const id = String(step.step_index)
      const params = step.tool_info?.parameters ?? {}
      
      if (toolName === 'run_command') {
        if (!isDone) commands += 1
        put(id, {
          kind: isError ? 'error' : 'cmd',
          text: shortCommand(params.CommandLine ?? '') + (isError ? '  (error)' : ''),
          isRunning: !isDone,
        })
      } else if (toolName === 'write_to_file' || toolName === 'replace_file_content' || toolName === 'multi_replace_file_content' || toolName === 'sed_file' || toolName === 'notebook_edit') {
        if (isDone && !isError) {
          edits += 1
          let path = params.TargetFile ?? params.AbsolutePath ?? ''
          path = path.split(/[\\/]/).slice(-2).join('/')
          put(id, { kind: 'edit', text: path, isRunning: false })
        } else if (!isDone) {
          let path = params.TargetFile ?? params.AbsolutePath ?? ''
          path = path.split(/[\\/]/).slice(-2).join('/')
          put(id, { kind: 'edit', text: path, isRunning: true })
        }
      }
    }
  }
  return { commands, edits, tokens, usage, recent: order.slice(-5).map(id => items.get(id)!) }
}

async function latestRun($: any, c: CrewConfig, wp: string) {
  const dir = `${c.stateDir}/runs/${wp}`
  if (!(await $.fs.exists(dir))) return undefined
  const names = (await $.fs.list(dir))
    .filter((r: any) => r.kind === 'dir' && /^\d{8}-\d{6}$/.test(r.name))
    .map((r: any) => r.name)
    .sort()
  const name = names.at(-1)
  if (!name) return undefined
  // Tokens over every run of this WP; review rounds resume inside the latest run dir.
  let totalTokens = 0
  for (const other of names.slice(0, -1)) {
    totalTokens += parseEvents(await $.fs.read(`${dir}/${other}/events.jsonl`).catch(() => '')).tokens
  }
  const m = /^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$/.exec(name)!
  const run = `${dir}/${name}`
  const stat = await $.fs.stat(`${run}/events.jsonl`).catch(() => undefined)
  return {
    startedAt: new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]).getTime(),
    status: (await $.fs.read(`${run}/status`).catch(() => '')).trim(),
    resumeAt: (await $.fs.read(`${run}/resume_at`).catch(() => '')).trim(),
    workdir: (await $.fs.read(`${run}/workdir`).catch(() => '')).trim(),
    modelLine: (await $.fs.read(`${run}/model`).catch(() => '')).trim(),
    totalTokens,
    updatedAt: stat?.mtimeMs ?? 0,
    ...parseEvents(stat ? await $.fs.read(`${run}/events.jsonl`).catch(() => '') : ''),
  }
}

async function readChat($: any, c: CrewConfig, wp: string): Promise<ChatEntry[]> {
  const text = await $.fs.read(`${c.stateDir}/chat/${wp}.jsonl`).catch(() => '')
  const entries: ChatEntry[] = []
  for (const line of text.split('\n')) {
    try {
      if (line.trim()) entries.push(JSON.parse(line))
    } catch {
      // a line being written right now; the next tick reads it whole
    }
  }
  return entries
}

async function scan($: any, c: CrewConfig): Promise<Snapshot> {
  const team = await readJson($, `${c.planDir}/team.json`, { agents: [], steps: [], phases: [] })
  const board = await readJson($, `${c.stateDir}/board.json`, { items: {} })
  const decision: Decision | null = await readJson($, `${c.stateDir}/decision.json`, null)
  const items: Record<string, { agent?: string; step?: string; note?: string }> = board.items ?? {}

  // A theme renames and recolors people; ids (and the files keyed by them) never change.
  const theme = team.themes?.[team.theme] ?? {}
  const skin = (m: Member, o: Partial<Member> | undefined): Member => ({ avatar: '●', ...m, ...(o ?? {}) })

  const agents: AgentView[] = []
  for (const member of ((team.agents ?? []) as Member[]).map(m => skin(m, theme.agents?.[m.id]))) {
    const own = Object.entries(items).filter(([, it]) => it.agent === member.id)
    const chats = new Map<string, ChatEntry[]>()
    for (const [wp] of own) chats.set(wp, await readChat($, c, wp))
    const lastTs = (wp: string) => chats.get(wp)?.at(-1)?.ts ?? 0
    const pick =
      own.filter(([, it]) => ACTIVE_STEPS.has(it.step ?? '')).sort((a, b) => lastTs(b[0]) - lastTs(a[0]))[0] ??
      own.sort((a, b) => lastTs(b[0]) - lastTs(a[0]))[0]
    const wp = pick?.[0] ?? ''
    const spec = wp ? await $.fs.read(`${c.planDir}/wp/${wp}.md`).catch(() => '') : ''
    const run = wp ? await latestRun($, c, wp) : undefined
    agents.push({
      member,
      wp,
      summary: /^- (?:Summary|Özet):\s*(.+)$/m.exec(spec)?.[1]?.trim() ?? '',
      step: pick?.[1].step ?? '',
      note: pick?.[1].note ?? '',
      workdir: run?.workdir ?? '',
      isRunning: !!run && (run.status === 'running' || run.status.startsWith('retry')),
      isPaused: run?.status === 'paused',
      resumeAt: run?.resumeAt ?? '',
      startedAt: run?.startedAt ?? 0,
      updatedAt: run?.updatedAt ?? 0,
      commands: run?.commands ?? 0,
      edits: run?.edits ?? 0,
      tokens: run?.tokens ?? 0,
      usage: run?.usage ?? { input: 0, cached: 0, output: 0, reasoning: 0 },
      model: run?.modelLine.split(' ')[0] ?? '',
      effort: run?.modelLine.split(' ')[1] ?? '',
      tier: run?.modelLine.split(' ')[2] ?? '',
      totalTokens: (run?.totalTokens ?? 0) + (run?.tokens ?? 0),
      recent: run?.recent ?? [],
      chat: (chats.get(wp) ?? []).slice(-12),
    })
  }

  // Phase progress: a WP id "wpNN…" belongs to phase <prefix><first digit>.
  const phaseOf = (wp: string) => `${c.phasePrefix}${/^wp(\d)/.exec(wp)?.[1] ?? '?'}`
  const phases: Phase[] = (team.phases ?? []).map((p: { id: string; label: string }) => {
    const wps = Object.entries(items).filter(([wp]) => phaseOf(wp) === p.id)
    return { ...p, total: wps.length, done: wps.filter(([, it]) => it.step === 'merged').length, isCurrent: false }
  })
  const current = phases.find(p => p.total > p.done)
  if (current) current.isCurrent = true

  return {
    phase: board.phase ?? '',
    focus: board.focus ?? '',
    lead: skin(team.lead ?? LEAD, theme.lead),
    user: skin(team.user ?? USER, theme.user),
    steps: team.steps ?? [],
    bar: theme.bar ?? 'blocks',
    themeId: team.theme ?? '',
    themeTitle: theme.title ?? '',
    teamTokens: agents.reduce((sum, a) => sum + a.totalTokens, 0),
    phases,
    agents,
    prOpen: Object.values(items).filter(it => it.step === 'pr_open').length,
    decision: decision && decision.status === 'open' ? decision : null,
    checkedAt: Date.now(),
  }
}

// ── actions ───────────────────────────────────────────────────────────────────────────────

async function openAgent($: any, a: AgentView) {
  await $.ui.open({ id: agentPane(a.member.id), title: `${a.member.name} · ${a.member.role}` })
}

async function openBoard($: any) {
  const c = await read($, config)
  await $.ui.open({ id: BOARD_PANE, title: c.project ? `${c.project} crew` : 'crew' })
}

async function appendChat($: any, wp: string, entry: ChatEntry) {
  const c = await read($, config)
  const path = `${c.stateDir}/chat/${wp}.jsonl`
  const old = await $.fs.read(path).catch(() => '')
  await $.fs.write(path, old + JSON.stringify(entry) + '\n')
}

async function sendNote($: any, a: AgentView, text: string) {
  const note = text.trim()
  if (!note || !a.wp) return
  const S = strings(await read($, config))
  await appendChat($, a.wp, { ts: Date.now(), from: 'user', kind: 'user', text: note })
  await $.prompt.submit({ text: `[${S.noteMsg} → ${a.member.name} / ${a.wp}] ${note}\n\n${S.noteHint(a.member.name)}` })
  $.ui.toast(S.noteSent(a.member.name))
}

async function askLead($: any, a: AgentView, what: string) {
  const S = strings(await read($, config))
  await $.prompt.submit({ text: `[${S.requestMsg} → ${a.member.name} / ${a.wp}] ${what}` })
  $.ui.toast(S.requestSent)
}

async function answerDecision($: any, d: Decision, label: string) {
  const c = await read($, config)
  const S = strings(c)
  await $.fs.write(`${c.stateDir}/decision.json`, JSON.stringify({ ...d, status: 'answered', answer: label }, null, 2))
  await $.prompt.submit({ text: `[${S.decisionMsg}] ${d.question} → ${label}` })
  $.ui.toast(S.chose(label))
}

async function loadDiff($: any, a: AgentView, selected: string) {
  const S = strings(await read($, config))
  let view: DiffView = { files: [], selected, patch: '', error: '' }
  try {
    if (!a.workdir) throw new Error(S.noWorkdir)
    const git = (args: string[]) => $.process.run(['git', '-C', a.workdir, ...args], { timeoutMs: 15000 })
    const numstat = await git(['diff', '--numstat'])
    const untracked = await git(['ls-files', '--others', '--exclude-standard'])
    const files: DiffFile[] = numstat.stdout
      .split('\n')
      .filter((l: string) => l.trim())
      .map((l: string) => {
        const [added, removed, path] = l.split('\t')
        return { path, added: Number(added) || 0, removed: Number(removed) || 0, isNew: false }
      })
    for (const path of untracked.stdout.split('\n').filter((l: string) => l.trim())) {
      files.push({ path, added: 0, removed: 0, isNew: true })
    }
    let patch = ''
    const chosen = files.find(f => f.path === selected)
    if (chosen?.isNew) {
      patch = (await $.fs.read(`${a.workdir}/${chosen.path}`).catch(() => '')).split('\n').slice(0, 200).join('\n')
    } else if (chosen) {
      patch = (await git(['diff', '--', chosen.path])).stdout.split('\n').slice(0, 300).join('\n')
    }
    view = { files, selected, patch, error: '' }
  } catch (error: any) {
    view.error = String(error?.message ?? error)
  }
  await update($, diffs, all => ({ ...all, [a.member.id]: view }))
}

// One refresh at a time; record how it went so a stale board is visible instead of silent.
async function refresh($: any) {
  const prev = await read($, health)
  if (prev.at < 0 && Date.now() + prev.at < 30000) return
  const started = Date.now()
  await update($, health, x => ({ ...x, at: -started }))
  let error = ''
  try {
    await refreshOnce($)
  } catch (err: any) {
    error = String(err?.stack ?? err?.message ?? err).slice(0, 800)
  }
  const next = { at: Date.now(), ms: Date.now() - started, error, count: prev.count + 1 }
  await update($, health, () => next)
}

async function refreshOnce($: any) {
  const c = await loadConfig($)
  await update($, config, () => c)
  if (!c.isActive) return
  const S = strings(c)
  const snap = await scan($, c)
  await update($, snapshot, () => snap)

  // Toast when an agent changes step, and open its pane the first time it has work.
  const before = await read($, lastSteps)
  const now: Record<string, string> = {}
  const label = (id: string) => (id === 'failed' ? S.failedStep : snap.steps.find(s => s.id === id)?.label ?? id)
  for (const a of snap.agents) {
    const key = `${a.member.id}:${a.wp}`
    now[key] = a.step
    if (key in before && before[key] !== a.step && a.step) {
      void Promise.resolve($.ui.toast(`${a.member.name} · ${a.wp}: ${label(a.step)}`)).catch(() => undefined)
    }
  }
  await update($, lastSteps, () => now)
  const seen = await read($, opened)
  for (const a of snap.agents) {
    if (ACTIVE_STEPS.has(a.step) && !seen.includes(a.member.id)) {
      await update($, opened, list => [...list, a.member.id])
      void openAgent($, a).catch(() => undefined)
    }
  }

  const parts = snap.agents.filter(a => a.isRunning).map(a => `${a.member.name} ▶ ${ago(c, snap.checkedAt - a.startedAt)}`)
  if (snap.prOpen) parts.push(`${snap.prOpen} ${S.prOpen}`)
  if (snap.decision) parts.push('⚑')
  void Promise.resolve($.ui.status(parts.length ? `${S.board} · ${parts.join(' · ')}` : undefined)).catch(() => undefined)
}

// ── drawing helpers ───────────────────────────────────────────────────────────────────────

function ago(c: CrewConfig, ms: number): string {
  const S = strings(c)
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s} ${S.s}`
  if (s < 3600) return `${Math.floor(s / 60)} ${S.m}`
  return `${Math.floor(s / 3600)} ${S.h} ${Math.floor((s % 3600) / 60)} ${S.m}`
}

const kTokens = (n: number) => (n >= 1000 ? `${Math.round(n / 1000)}k` : String(n))

function stepBar(snap: Snapshot, step: string): string {
  const ids = snap.steps.filter(s => s.id !== 'changes_requested').map(s => s.id)
  const at = step === 'changes_requested' ? ids.indexOf('reviewing') : ids.indexOf(step)
  if (snap.bar === 'pacman') return ids.map((_, i) => (i < at ? ' ' : i === at ? 'ᗧ' : '•')).join('')
  if (snap.bar === 'pokeball') return ids.map((_, i) => (i < at ? '◓' : i === at ? '⚡' : '·')).join('')
  if (snap.bar === 'mana') return ids.map((_, i) => (i <= at ? '◆' : '◇')).join('')
  return ids.map((_, i) => (i <= at ? '▰' : '▱')).join('')
}

function stepLabel(snap: Snapshot, S: Strings, id: string): string {
  return id === 'failed' ? S.failedStep : snap.steps.find(s => s.id === id)?.label ?? (id || S.idle)
}

// ── hooks ─────────────────────────────────────────────────────────────────────────────────

// ---- Quota pane (Claude / Codex / agy) ----
// Quota pane: Claude (this session's plan windows + context), Codex (rollout rate limits) and
// agy/Gemini (tokens today). Codex and agy figures come from templates/bin/usage.py.

const USAGE_PANE = 'crew-usage'
const USAGE_EMPTY: UsageView = { checkedAt: 0, claude: [], context: null, codex: null, agy: null, error: '', lang: 'en', stateDir: '.lead', isActive: false }

const usage = atom({ plugin: 'agent-crew', key: 'usage' } as const, USAGE_EMPTY)
const warned = atom({ plugin: 'agent-crew', key: 'usageWarned' } as const, [])

const USAGE_STRINGS = {
  en: {
    title: 'QUOTA',
    command: 'Show Claude, Codex and Gemini quota',
    opened: 'Quota pane opened.',
    fiveHour: '5 hours',
    weekly: 'weekly',
    context: 'context',
    resetsIn: (d: string) => `resets in ${d}`,
    full: 'FULL · new runs wait',
    tokensToday: (t: string, n: number) => `today ${t} tokens · ${n} runs`,
    limited: 'quota error on the last run',
    ok: 'no quota error',
    noData: 'no reading yet',
    noClaude: 'no reading yet (appears after the next reply)',
    updated: (s: string) => `updated ${s} ago`,
    loading: 'reading…',
    stale: 'stale',
    warn: (who: string, p: number) => `${who} quota at ${p}%`,
    legend: 'green < 75 % · yellow ≥ 75 % · red ≥ 90 %',
    s: 's',
    m: 'm',
    h: 'h',
    d: 'd',
  },
  tr: {
    title: 'KOTA',
    command: 'Claude, Codex ve Gemini kotasını göster',
    opened: 'Kota paneli açıldı.',
    fiveHour: '5 saat',
    weekly: 'haftalık',
    context: 'bağlam',
    resetsIn: (d: string) => `${d} sonra sıfırlanır`,
    full: 'DOLU · yeni işler bekler',
    tokensToday: (t: string, n: number) => `bugün ${t} token · ${n} iş`,
    limited: 'son işte kota hatası',
    ok: 'kota hatası yok',
    noData: 'henüz okuma yok',
    noClaude: 'henüz okuma yok (sonraki yanıttan sonra gelir)',
    updated: (s: string) => `${s} önce güncellendi`,
    loading: 'okunuyor…',
    stale: 'eski',
    warn: (who: string, p: number) => `${who} kotası %${p}`,
    legend: 'yeşil < %75 · sarı ≥ %75 · kırmızı ≥ %90',
    s: 'sn',
    m: 'dk',
    h: 'sa',
    d: 'g',
  },
}
type UsageStrings = (typeof USAGE_STRINGS)['en']
const usageStrings = (lang: string): UsageStrings => (USAGE_STRINGS as Record<string, UsageStrings>)[lang] ?? USAGE_STRINGS.en

const kTokensBig = (n: number) => (n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}k` : String(n))
const colorOf = (p: number) => (p >= 90 ? 'red' : p >= 75 ? 'yellow' : 'green')
const bar = (p: number) => {
  const n = Math.max(0, Math.min(10, Math.round(p / 10)))
  return '▰'.repeat(n) + '▱'.repeat(10 - n)
}

function span(S: UsageStrings, ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s} ${S.s}`
  const m = Math.round(s / 60)
  if (m < 60) return `${m} ${S.m}`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} ${S.h} ${m % 60} ${S.m}`
  return `${Math.floor(h / 24)} ${S.d} ${h % 24} ${S.h}`
}

function win(label: string, raw: any): UsageWindow | null {
  if (!raw || typeof raw.percent !== 'number') return null
  return { label, percent: Math.round(raw.percent), resetsAt: raw.resets_at ? Date.parse(raw.resets_at) : 0 }
}

async function loadUsageConfig($: any) {
  const raw = await $.fs.read('.crew/config.json').then(JSON.parse).catch(() => null)
  return { isActive: !!raw, lang: raw?.lang ?? 'en', stateDir: raw?.stateDir ?? '.crew/state' }
}

async function refreshClaude($: any) {
  const u = await $.session.usage().catch(() => null)
  if (!u) return
  const claude: UsageWindow[] = (u.rateLimits ?? [])
    .filter((r: any) => typeof r.percentUsed === 'number')
    .map((r: any) => ({ label: r.kind, percent: Math.round(r.percentUsed), resetsAt: r.resetsAt ? Date.parse(r.resetsAt) : 0 }))
  const context = u.context?.percent != null ? { percent: u.context.percent, tokens: u.context.tokens ?? 0, window: u.context.window } : null
  const prev = await read($, usage)
  await update($, usage, v => ({ ...v, claude: claude.length ? claude : v.claude, context: context ?? v.context }))
  // Scripts (run-wp failover, the lead) read the same figures from the state dir.
  if (prev.isActive && claude.length) {
    const body = { updated_at: new Date(Date.now()).toISOString(), windows: claude.map(w => ({ ...w, resetsAt: w.resetsAt ? new Date(w.resetsAt).toISOString() : null })) }
    await $.fs.write(`${prev.stateDir}/usage/claude.json`, JSON.stringify(body, null, 2)).catch(() => undefined)
  }
}

async function refreshEngines($: any) {
  const v = await read($, usage)
  if (!v.isActive) return
  const script = `${$.plugin.root}/templates/bin/usage.py`
  let error = ''
  let data: any = null
  for (const py of ['python', 'python3', 'py']) {
    const r = await $.process.run([py, script, '--state', v.stateDir], { timeoutMs: 20000 }).catch((e: any) => ({ exitCode: 1, stdout: '', stderr: String(e) }))
    if (r.exitCode === 0) {
      data = JSON.parse(r.stdout)
      error = ''
      break
    }
    error = (r.stderr || 'usage.py failed').split('\n')[0]
  }
  await update($, usage, u => ({
    ...u,
    checkedAt: Date.now(),
    error,
    codex: data?.codex?.available
      ? { plan: data.codex.plan ?? '', windows: [win('five_hour', data.codex.five_hour), win('seven_day', data.codex.weekly)].filter(Boolean) as UsageWindow[] }
      : u.codex,
    agy: data?.agy ? { tokensToday: data.agy.tokens_today, runsToday: data.agy.runs_today, isLimited: !!data.agy.limited } : u.agy,
  }))
  await warnOnce($)
}

async function warnOnce($: any) {
  const v = await read($, usage)
  const S = usageStrings(v.lang)
  const seen = await read($, warned)
  const all: [string, UsageWindow][] = [...v.claude.map(w => ['Claude', w] as [string, UsageWindow]), ...(v.codex?.windows ?? []).map(w => ['Codex', w] as [string, UsageWindow])]
  for (const [who, w] of all) {
    const key = `${who}:${w.label}:${w.resetsAt}`
    if (w.percent >= 90 && !seen.includes(key)) {
      await update($, warned, list => [...list.slice(-20), key])
      void Promise.resolve($.ui.toast(S.warn(who, w.percent))).catch(() => undefined)
    }
  }
}

/** Called from the crew's single session.start hook. */
async function startUsage($: any) {
  const c = await loadUsageConfig($)
  await update($, usage, v => ({ ...v, ...c }))
  // `usage` is a built-in command; ours are `quota` and, in Turkish, `kota`.
  for (const name of c.lang === 'tr' ? ['kota', 'quota'] : ['quota']) {
    await $.command.register({ name, description: usageStrings(c.lang).command }).catch(() => undefined)
  }
  void refreshClaude($).catch(() => undefined)
  void refreshEngines($).catch(() => undefined)
  $.clock.every(30000, () => void refreshClaude($).catch(() => undefined))
  $.clock.every(60000, () => void refreshEngines($).catch(() => undefined))
}

/** Called from the crew's single command.run hook; undefined when the command is not ours. */
async function usageCommand($: any, command: string) {
  if (command !== 'quota' && command !== 'kota') return undefined
  const v = await read($, usage)
  await $.ui.open({ id: USAGE_PANE, title: usageStrings(v.lang).title.toLowerCase() })
  void refreshEngines($).catch(() => undefined)
  return { text: usageStrings(v.lang).opened }
}


export const register: Register = on => {
  // Quota pane.
  on('session.measure', async ($, e, next) => {
    await refreshClaude($).catch(() => undefined)
    await warnOnce($).catch(() => undefined)
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: USAGE_PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const Svg = (e.surface === 'desktop' || e.surface === 'mobile' ? ($.ui.resolve(e) as any).Svg : undefined) as any
    const v = await read($, usage)
    const S = usageStrings(v.lang)
    const now = Date.now()
    const label = (l: string) => (l === 'five_hour' ? S.fiveHour : l === 'seven_day' ? S.weekly : l)
    const pick = (ws: UsageWindow[], kind: string) => ws.find(w => w.label === kind) ?? null
    const until = (w: UsageWindow | null) => (w && w.resetsAt > now ? S.resetsIn(span(S, w.resetsAt - now)) : '')
    const c5 = pick(v.claude, 'five_hour')
    const x5 = pick(v.codex?.windows ?? [], 'five_hour')
    const dials = Svg
      ? quotaDials(
          [
            { name: '✳ Claude', color: '#d97757', outer: c5?.percent ?? null, inner: pick(v.claude, 'seven_day')?.percent ?? null, caption: until(c5), note: v.context ? `${S.context} %${v.context.percent}` : '' },
            { name: '◎ Codex', color: '#10a37f', outer: x5?.percent ?? null, inner: pick(v.codex?.windows ?? [], 'seven_day')?.percent ?? null, caption: until(x5), note: (x5?.percent ?? 0) >= 100 ? `!${S.full.split(' ·')[0]}` : (v.codex?.plan ?? '') },
            { name: '✦ Gemini', color: '#4285f4', outer: null, inner: null, caption: v.agy ? `${kTokensBig(v.agy.tokensToday)} token` : S.noData, note: v.agy?.isLimited ? `!${S.limited}` : v.agy ? S.ok : '' },
          ],
          S.legend,
        )
      : ''

    const row = (w: UsageWindow) => (
      <Text>
        <Text>{'  '}{label(w.label).padEnd(9)}</Text>
        <Text color={colorOf(w.percent)}>{bar(w.percent)} {String(w.percent).padStart(3)}%</Text>
        <Text dimColor>{w.resetsAt > now ? `  · ${S.resetsIn(span(S, w.resetsAt - now))}` : ''}</Text>
        {w.percent >= 100 && <Text color="red" bold>{'  '}{S.full}</Text>}
      </Text>
    )

    return (
      <Box flexDirection="column" gap={1}>
        <Box flexDirection="row" justifyContent="space-between" borderStyle="round" borderColor="yellow" paddingX={1}>
          <Text color="yellow" bold>⚡ {S.title}</Text>
          <Text dimColor>{v.checkedAt ? S.updated(span(S, now - v.checkedAt)) : S.loading}</Text>
        </Box>

        {Svg && <Svg key="quota-dials" source={dials} alt={`${S.title}: Claude ${c5?.percent ?? '?'}%, Codex ${x5?.percent ?? '?'}%`} />}

        <Box flexDirection="column">
          <Text color="#d97757" bold>✳ Claude</Text>
          {v.claude.length === 0 ? <Text dimColor>{'  '}{S.noClaude}</Text> : v.claude.map(row)}
          {v.context && (
            <Text>
              <Text>{'  '}{S.context.padEnd(9)}</Text>
              <Text color={colorOf(v.context.percent)}>{bar(v.context.percent)} {String(v.context.percent).padStart(3)}%</Text>
              <Text dimColor>  · {kTokensBig(v.context.tokens)} / {kTokensBig(v.context.window)}</Text>
            </Text>
          )}
        </Box>

        <Box flexDirection="column">
          <Text color="#10a37f" bold>◎ Codex{v.codex?.plan ? ` · ${v.codex.plan}` : ''}</Text>
          {!v.codex || v.codex.windows.length === 0 ? <Text dimColor>{'  '}{S.noData}</Text> : v.codex.windows.map(row)}
        </Box>

        <Box flexDirection="column">
          <Text color="#4285f4" bold>✦ Gemini · agy</Text>
          {!v.agy ? (
            <Text dimColor>{'  '}{S.noData}</Text>
          ) : (
            <Text>
              <Text>{'  '}{S.tokensToday(kTokensBig(v.agy.tokensToday), v.agy.runsToday)} · </Text>
              <Text color={v.agy.isLimited ? 'red' : 'green'}>{v.agy.isLimited ? S.limited : S.ok}</Text>
            </Text>
          )}
        </Box>

        {v.error !== '' && <Text color="red" wrap="wrap">usage.py: {v.error}</Text>}
        <Text dimColor>{S.legend}</Text>
      </Box>
    )
  })

  on('session.start', async ($, e, next) => {
    const c = await loadConfig($)
    await update($, config, () => c)
    await update($, opened, () => [])
    await update($, health, () => ({ at: 0, ms: 0, error: '', count: 0 }))
    const S = strings(c)
    await $.command.register({ name: 'crew', description: S.openBoard })
    if (c.lang === 'tr') await $.command.register({ name: 'ekip', description: S.openBoard })
    if (c.isActive) {
      for (const a of (await scan($, c)).agents) {
        await $.command.register({ name: commandName(a.member), description: S.openAgent(a.member.name, a.member.role) })
      }
    }
    await refresh($).catch(() => undefined)
    $.clock.every(3000, () => void refresh($).catch(() => undefined))
    $.clock.every(300, () => void update($, tick, n => (n + 1) % 1000))
    if (c.isActive) void openBoard($).catch(() => undefined)
    await startUsage($).catch(() => undefined)
    return next(e)
  })

  on('command.run', async ($, e, next) => {
    const quota = await usageCommand($, e.command)
    if (quota) return quota
    const c = await read($, config)
    const S = strings(c)
    if (e.command === 'crew' || e.command === 'ekip') {
      if (!c.isActive) return { text: S.notConfigured }
      await openBoard($)
      return { text: S.boardOpened }
    }
    const a = (await read($, snapshot)).agents.find(x => commandName(x.member) === e.command)
    if (!a) return next(e)
    await openAgent($, a)
    return { text: S.paneOpened(a.member.name) }
  })

  // ⚑ Decision band above the prompt.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const c = await read($, config)
    const snap = await read($, snapshot)
    const d = snap.decision
    if (!c.isActive || !d || e.props.hasSurvey || (await read($, hiddenDecision)) === d.id) return next(e)
    const S = strings(c)
    const { Box, Button, Text } = $.ui.resolve(e)
    if (snap.bar === 'pokeball') {
      return (
        <Box flexDirection="column" borderStyle="double" borderColor={snap.lead.color} paddingX={1}>
          <Box flexDirection="row" justifyContent="space-between">
            <Text bold>{S.wildDecision}</Text>
            <Text color={snap.lead.color} bold>{snap.lead.avatar} {snap.lead.name.toUpperCase()} Lv.∞</Text>
          </Box>
          <Text color={snap.lead.color}>HP ▰▰▰▰▰▰▰▰▱▱  {S.waiting}</Text>
          <Box borderStyle="single" borderColor="gray" paddingX={1} marginTop={1}>
            <Text wrap="wrap">{d.question}</Text>
          </Box>
          <Box flexDirection="column" borderStyle="round" borderColor={snap.user.color} paddingX={1}>
            <Text color={snap.user.color} bold>{snap.user.avatar} {S.whatWill(snap.user.name)}</Text>
            <Box flexDirection="row" flexWrap="wrap" columnGap={2}>
              {d.options.map((o, i) => (
                <Button
                  key={`opt-${i}`}
                  label={`▶ ${o.label.toUpperCase()}`}
                  hotkey={String(i + 1)}
                  variant={i === 0 ? 'primary' : 'secondary'}
                  onPress={() => answerDecision($, d, o.label)}
                />
              ))}
              <Button key="later" label={S.run} hotkey="k" onPress={() => update($, hiddenDecision, () => d.id)} />
            </Box>
            {d.options.map((o, i) =>
              o.detail !== '' ? (
                <Text dimColor wrap="wrap">
                  {i + 1}. {o.detail}
                </Text>
              ) : null,
            )}
          </Box>
        </Box>
      )
    }
    return (
      <Box flexDirection="column" borderStyle="round" borderColor={snap.lead.color} paddingX={1}>
        <Text>
          <Text color={snap.lead.color} bold>{S.decisionTitle}</Text>
          <Text bold>{d.question}</Text>
        </Text>
        {d.options.map((o, i) => (
          <Box key={`opt-${i}`} flexDirection="row" gap={1}>
            <Button
              key={`opt-${i}`}
              label={o.label}
              hotkey={String(i + 1)}
              variant={i === 0 ? 'primary' : 'secondary'}
              onPress={() => answerDecision($, d, o.label)}
            />
            {o.detail !== '' && <Text dimColor>{o.detail}</Text>}
          </Box>
        ))}
        <Box flexDirection="row">
          <Button key="later" label={S.later} plain onPress={() => update($, hiddenDecision, () => d.id)} />
        </Box>
      </Box>
    )
  })

  // Crew board.
  on('ui.render', { component: 'Pane', requestId: BOARD_PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const c = await read($, config)
    const S = strings(c)
    const snap = await read($, snapshot)
    const t = await read($, tick)
    const hp = await read($, health)
    if (!c.isActive) return <Text dimColor>{S.notConfigured}</Text>
    const BoardSvg = (e.surface === 'desktop' || e.surface === 'mobile' ? ($.ui.resolve(e) as any).Svg : undefined) as any
    return (
      <Box flexDirection="column" gap={1}>
        {BoardSvg && (
          <BoardSvg
            key="crew-banner"
            source={banner(`◆ ${(c.project || 'crew').toUpperCase()}${snap.themeTitle ? ` · ${snap.themeTitle}` : ''}`, snap.phase || S.noPhase, snap.agents.map(x => x.member.color), snap.lead.color)}
            alt={`${c.project} · ${snap.phase}`}
          />
        )}
        <Box flexDirection="column" borderStyle="round" borderColor={snap.lead.color} paddingX={1}>
          <Text>
            <Text color={snap.lead.color} bold>
              ◆ {(c.project || 'crew').toUpperCase()} {snap.themeTitle ? `· ${snap.themeTitle} ` : ''}
            </Text>
            <Text bold>{snap.phase || S.noPhase}</Text>
          </Text>
          {snap.focus !== '' && <Text dimColor>{snap.focus}</Text>}
        </Box>

        {snap.phases.length > 0 && (
          <Box flexDirection="column">
            <Text bold>{S.roadmap}</Text>
            <Text wrap="wrap">
              {snap.phases.map(p => (
                <Text
                  color={p.isCurrent ? snap.lead.color : undefined}
                  dimColor={!p.isCurrent && !(p.total > 0 && p.done === p.total)}
                  bold={p.isCurrent}
                >
                  {p.total > 0 && p.done === p.total ? '✓' : p.isCurrent ? '▶' : '·'} {p.id} {p.label}
                  {p.total > 0 ? ` ${p.done}/${p.total}` : ''}
                  {'   '}
                </Text>
              ))}
            </Text>
          </Box>
        )}

        {snap.decision && (
          <Box borderStyle="round" borderColor={snap.lead.color} paddingX={1}>
            <Text color={snap.lead.color} bold>{S.decisionWaiting}</Text>
            <Text>{snap.decision.question}</Text>
          </Box>
        )}

        <Text>
          <Text color={snap.lead.color} bold>{snap.lead.avatar} {snap.lead.name}</Text>
          <Text dimColor>
            {' '}· {snap.lead.role}{snap.prOpen ? ` · ${snap.prOpen} ${S.prOpen}` : ''} · {S.teamTotal} {kTokens(snap.teamTokens)} {S.tokens}
          </Text>
        </Text>

        {snap.agents.map(a => (
          <Box
            key={`card-${a.member.id}`}
            flexDirection="column"
            borderStyle="round"
            borderColor={a.wp ? a.member.color : undefined}
            borderDimColor={!a.wp}
            paddingX={1}
          >
            <Box flexDirection="row" justifyContent="space-between">
              <Text>
                <Text color={a.member.color} bold>
                  {a.member.avatar} {a.member.name} {a.isRunning ? SPINNER[t % SPINNER.length] : ''}
                </Text>
                <Text dimColor> · {a.member.role}</Text>
              </Text>
              {a.wp !== '' && <Button key={`open-${a.member.id}`} label={S.open} plain onPress={() => openAgent($, a)} />}
            </Box>
            {a.wp === '' ? (
              <Text dimColor>{S.idle}</Text>
            ) : (
              <>
                <Text>
                  <Text color={a.member.color}>{stepBar(snap, a.step)} </Text>
                  <Text bold>{stepLabel(snap, S, a.step)}</Text>
                  <Text dimColor>
                    {'  '}
                    {a.wp}
                    {a.isRunning ? ` · ${ago(c, snap.checkedAt - a.startedAt)}` : ''}
                    {a.isPaused ? ` · paused · resumes ${a.resumeAt}` : ''}
                    {a.model ? ` · ${a.model}/${a.effort} · ${kTokens(a.totalTokens)} ${S.tokens}` : ''}
                  </Text>
                </Text>
                <Text dimColor wrap="truncate-end">{a.summary}</Text>
              </>
            )}
          </Box>
        ))}
        <Text dimColor>
          /{S.board} · {snap.agents.map(a => `/${commandName(a.member)}`).join(' ')}
        </Text>
        {hp.error !== '' ? (
          <Text color="red" wrap="wrap">{S.staleBoard}{hp.error.split('\n')[0]}</Text>
        ) : (
          <Text dimColor>
            {hp.at > 0 ? S.updated(ago(c, Date.now() - hp.at)) : S.updating} · {S.refresh(hp.count)} · {hp.ms} ms
          </Text>
        )}
      </Box>
    )
  })

  // One agent.
  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    const id = String(e.requestId ?? '')
    if (!id.startsWith('crew-agent-')) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const c = await read($, config)
    const S = strings(c)
    const snap = await read($, snapshot)
    const t = await read($, tick)
    const a = snap.agents.find(x => agentPane(x.member.id) === id)
    if (!a) return <Text dimColor>{S.notFound}</Text>
    const isDiffOpen = (await read($, diffOpen)).includes(a.member.id)
    const diff = (await read($, diffs))[a.member.id]
    const names: Record<string, Member> = { [snap.lead.id]: snap.lead, [a.member.id]: a.member, [snap.user.id]: snap.user }
    const shown = snap.steps.filter(s => s.id !== 'changes_requested' || a.step === 'changes_requested')
    const at = shown.findIndex(s => s.id === a.step)
    const mark = (x: Activity) => (x.isRunning ? SPINNER[t % SPINNER.length] : x.kind === 'edit' ? '✎' : x.kind === 'error' ? '✗' : '✓')
    const Input = (e.surface !== 'mobile' ? ($.ui.resolve(e) as any).Input : undefined) as any
    const Svg = (e.surface === 'desktop' || e.surface === 'mobile' ? ($.ui.resolve(e) as any).Svg : undefined) as any

    return (
      <Box flexDirection="column" gap={1}>
        <Box flexDirection="column" borderStyle="round" borderColor={a.member.color} paddingX={1}>
          <Text>
            <Text color={a.member.color} bold>
              {a.member.avatar} {a.member.name.toUpperCase()} {a.isRunning ? SPINNER[t % SPINNER.length] : ''}
            </Text>
            <Text dimColor>  {a.member.role}</Text>
          </Text>
          {a.wp === '' ? (
            <Text dimColor>{S.noTask}</Text>
          ) : (
            <>
              <Text bold>{a.wp}</Text>
              <Text wrap="wrap">{a.summary}</Text>
            </>
          )}
        </Box>

        {a.wp !== '' && Svg && (
          <Svg key={`track-${a.member.id}`} source={stepTrack(shown.map(x => x.label), at, a.member.color, a.step === 'failed')} alt={stepLabel(snap, S, a.step)} />
        )}

        {a.wp !== '' && !Svg && (
          <Box flexDirection="column">
            {shown.map((s, i) => (
              <Text color={i === at ? a.member.color : undefined} bold={i === at} dimColor={i > at}>
                {i < at ? '  ✓ ' : i === at ? (a.isRunning ? `  ${SPINNER[t % SPINNER.length]} ` : '  ▶ ') : '  ○ '}
                {s.label}
                {i === at && a.isRunning ? `  · ${ago(c, snap.checkedAt - a.startedAt)}` : ''}
                {i === at && a.isPaused ? `  · paused · resumes ${a.resumeAt}` : ''}
              </Text>
            ))}
            {a.step === 'failed' && <Text color="red" bold>{S.failedRetry}</Text>}
          </Box>
        )}

        {a.startedAt > 0 && (
          <Box flexDirection="column">
            <Text>
              <Text color={a.member.color} bold>{a.model || S.model}</Text>
              <Text dimColor> · {S.thinking} {a.effort || '?'}{a.tier ? ` · ${a.tier}` : ''}</Text>
            </Text>
            <Text dimColor>
              {S.input} {kTokens(a.usage.input)} ({S.cache} %{a.usage.input ? Math.round((100 * a.usage.cached) / a.usage.input) : 0})
              {' · '}{S.output} {kTokens(a.usage.output)} ({S.thinking} {kTokens(a.usage.reasoning)}) · {S.thisTask} {kTokens(a.totalTokens)}
            </Text>
            <Text dimColor>
              {a.commands} {S.commands} · {a.edits} {S.fileChanges} · {S.lastActivity} {ago(c, snap.checkedAt - a.updatedAt)} {S.ago}
            </Text>
          </Box>
        )}

        {a.isRunning && a.recent.length > 0 && (
          <Box flexDirection="column" borderStyle="single" borderDimColor paddingX={1}>
            <Text bold>{S.live}</Text>
            {a.recent.map(x => (
              <Text
                dimColor={!x.isRunning && x.kind !== 'error'}
                color={x.isRunning ? a.member.color : x.kind === 'error' ? 'red' : undefined}
                wrap="truncate-end"
              >
                {mark(x)} {x.text}
              </Text>
            ))}
          </Box>
        )}

        {a.chat.length > 0 && (
          <Box flexDirection="column">
            <Text bold>{S.conversation}</Text>
            {a.chat.map(ch => {
              const who: Partial<Member> = names[ch.from] ?? { name: ch.from, color: 'gray' }
              const text = ch.text.length > 480 ? ch.text.slice(0, 480) + '…' : ch.text
              return (
                <Box flexDirection="column" marginTop={1}>
                  <Text color={who.color} bold>
                    {who.avatar ?? ''} {ch.kind === 'report' ? '📋 ' : ch.kind === 'note' ? '🔎 ' : ch.kind === 'assign' ? '📌 ' : ''}
                    {who.name}
                  </Text>
                  <Text color={ch.kind === 'error' ? 'red' : undefined} wrap="wrap">
                    {text}
                  </Text>
                </Box>
              )
            })}
          </Box>
        )}

        {a.wp !== '' && (
          <Box flexDirection="row" gap={1} flexWrap="wrap">
            <Button
              key={`diff-${a.member.id}`}
              label={isDiffOpen ? S.hideDiff : S.showDiff}
              hotkey="d"
              onPress={async () => {
                await update($, diffOpen, list => (list.includes(a.member.id) ? list.filter(x => x !== a.member.id) : [...list, a.member.id]))
                await loadDiff($, a, '')
              }}
            />
            <Button key={`status-${a.member.id}`} label={S.askStatus} hotkey="s" onPress={() => askLead($, a, S.statusQ)} />
            {a.isRunning && <Button key={`stop-${a.member.id}`} label={S.stop} hotkey="x" onPress={() => askLead($, a, S.stopQ)} />}
          </Box>
        )}

        {isDiffOpen && (
          <Box flexDirection="column" borderStyle="single" borderColor={a.member.color} paddingX={1}>
            <Box flexDirection="row" justifyContent="space-between">
              <Text bold>{S.changedFiles}</Text>
              <Button key={`reload-${a.member.id}`} label={S.reload} plain onPress={() => loadDiff($, a, diff?.selected ?? '')} />
            </Box>
            {!diff && <Text dimColor>{S.loading}</Text>}
            {diff?.error && <Text color="red">{diff.error}</Text>}
            {diff && !diff.error && diff.files.length === 0 && <Text dimColor>{S.noChanges}</Text>}
            {diff?.files.map(f => (
              <Box flexDirection="row" gap={1}>
                <Button
                  key={`file-${a.member.id}-${f.path}`}
                  label={f.path}
                  plain
                  onPress={() => loadDiff($, a, diff.selected === f.path ? '' : f.path)}
                />
                <Text color="green">{f.isNew ? S.isNew : `+${f.added}`}</Text>
                {!f.isNew && <Text color="red">-{f.removed}</Text>}
              </Box>
            ))}
            {diff?.patch && (
              <Box flexDirection="column" marginTop={1}>
                {diff.patch.split('\n').map(line => (
                  <Text
                    color={
                      line.startsWith('+') && !line.startsWith('+++')
                        ? 'green'
                        : line.startsWith('-') && !line.startsWith('---')
                          ? 'red'
                          : line.startsWith('@@')
                            ? 'cyan'
                            : undefined
                    }
                    dimColor={line.startsWith('diff ') || line.startsWith('index ')}
                    wrap="truncate-end"
                  >
                    {line || ' '}
                  </Text>
                ))}
              </Box>
            )}
          </Box>
        )}

        {a.wp !== '' && !Input && (
          <Box flexDirection="row" gap={1} flexWrap="wrap">
            {S.quickNotes.map((q, i) => (
              <Button key={`quick-${a.member.id}-${i}`} label={q} onPress={() => sendNote($, a, q)} />
            ))}
          </Box>
        )}

        {a.wp !== '' && Input && (
          <Input
            key={`note-${a.member.id}`}
            label={S.noteLabel(a.member.name)}
            placeholder={S.notePlaceholder}
            submitLabel={S.send}
            onSubmit={(value: string) => sendNote($, a, value)}
          />
        )}
      </Box>
    )
  })
}
