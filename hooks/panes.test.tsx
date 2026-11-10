import { expect, test } from 'claude-code/testing'
import { parseEvents } from './register'

// The test host has no file system, so the crew is unconfigured and the panes render their quiet
// state; this still validates every tree against each surface's element table.
const PANE = { title: 'crew', isFocused: true, bodyColumns: 70, placement: 'dock', scroll: {}, view: {} } as any
const NL = String.fromCharCode(10)

test('crew board draws on terminal and desktop', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'agent-crew', surface, component: 'Pane', requestId: 'crew-board', props: PANE })
    expect(await ui.find({ type: 'Text', text: /crew/ })).toBeDefined()
    await ui.unmount()
  }
})

test('agent pane draws on terminal and desktop', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'agent-crew', surface, component: 'Pane', requestId: 'crew-agent-ada', props: PANE })
    await ui.unmount()
  }
})

test('quota pane draws on terminal and desktop', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'agent-crew', surface, component: 'Pane', requestId: 'crew-usage', props: PANE })
    expect(await ui.find({ type: 'Text', text: /QUOTA|KOTA/ })).toBeDefined()
    await ui.unmount()
  }
})

test('agy events fixture parses correctly', async $ => {
  // agy sends each tool step as ACTIVE, then DONE or ERROR; commands are counted when they start.
  const step = (step_index: number, state: string, CommandLine: string) =>
    ({ event: 'step_update', step_update: { step_index, state, step_type: 'tool', tool_name: 'run_command', tool_info: { parameters: { CommandLine } } } })
  const text = [
    step(1, 'ACTIVE', 'pwd'), step(1, 'DONE', 'pwd'),
    step(2, 'ACTIVE', 'git status --short'), step(2, 'DONE', 'git status --short'),
    step(3, 'ACTIVE', 'false'), step(3, 'ERROR', 'false'),
    { event: 'result', result: { usage: { input_tokens: 40, output_tokens: 2, thinking_tokens: 1 } } },
  ].map(ev => JSON.stringify(ev)).join(NL)
  const parsed = parseEvents(text)
  expect(parsed.commands).toBe(3)
  expect(parsed.recent.at(-1)?.kind).toBe('error')
  expect(parsed.tokens).toBe(42)
  expect(parsed.usage.input).toBe(40)
  expect(parsed.usage.output).toBe(2)
  expect(parsed.usage.reasoning).toBe(1)
})

test('agent browser pane draws on terminal and desktop', async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'agent-crew', surface, component: 'Pane', requestId: 'crew-agents', props: PANE })
    await ui.unmount()
  }
})

// Synthetic project state through the same fs hooks used by the agents pane tests.
async function fallbackCrew($: any, on: any, lang: string, lead: any, syncStatus = 'disabled') {
  const files: Record<string, string> = {
    '.crew/config.json': JSON.stringify({ project: 'fallback-demo', lang, planDir: 'plan', stateDir: 'state' }),
    'plan/team.json': JSON.stringify({ agents: [], steps: [], phases: [] }),
    'state/board.json': JSON.stringify({ items: {}, lead }),
  }
  const find = (path: string) => Object.keys(files).find(k => path.split(String.fromCharCode(92)).join('/').endsWith(k))
  const processes: string[][] = []
  on('session.start', async (_$: any, e: any) => ({ cwd: e.cwd }))
  on('clock.every', async () => ({ value: undefined }))
  on('ui.status', async () => ({ value: undefined }))
  on('fs.read', async (_$: any, e: any) => {
    const key = find(e.path)
    return key ? { value: files[key] } : { deny: 'ENOENT' }
  })
  on('fs.exists', async (_$: any, e: any) => ({ value: !!find(e.path) }))
  on('fs.list', async () => ({ value: [] }))
  on('fs.stat', async () => ({ deny: 'ENOENT' }))
  on('fs.write', async () => ({ value: undefined }))
  on('command.register', async (_$: any, e: any) => ({ value: { command: e.name } }))
  on('process.run', async (_$: any, e: any) => {
    processes.push(e.argv)
    const script = e.argv[1] ?? ''
    const stdout = script.endsWith('/sync_bin.py')
      ? JSON.stringify({ status: syncStatus, updated: [], added: [], kept: [] })
      : script.endsWith('/render_roles.py') ? 'Roles are up to date.' : '{}'
    return { value: { exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  await $.session.start({ source: 'startup', cwd: 'C:/demo', session_id: 's', transcript_path: 't' })
  return processes
}

for (const lang of ['en', 'tr']) {
  for (const leadId of ['codex', 'claude', undefined]) {
    test(`crew board fallback badge: ${lang}, ${leadId ?? 'legacy'}`, async ($, on) => {
      // A local timestamp makes the expected wall-clock time independent of the test timezone.
      await fallbackCrew($, on, lang, leadId ? { id: leadId, since: '2026-11-10T08:07:00' } : undefined)
      for (const surface of ['terminal', 'desktop', 'mobile'] as const) {
        const ui = await $.ui.mount({ plugin: 'agent-crew', surface, component: 'Pane', requestId: 'crew-board', props: PANE })
        const badge = await ui.find({ type: 'Text', text: /Lead: Codex \(fallback\)|Lider: Codex \(yedek\)/ })
        if (leadId === 'codex') {
          expect(badge).toBeDefined()
          expect(await ui.find({ type: 'Text', text: lang === 'en'
            ? 'Lead: Codex (fallback) since 08:07' : "Lider: Codex (yedek) 08:07'den beri" })).toBeDefined()
        } else {
          expect(badge).toBeUndefined()
        }
        await ui.unmount()
      }
    })
  }
}

for (const status of ['ok', 'busy', 'disabled']) {
  test(`session-start renders roles and fallback skill only after safe sync: ${status}`, async ($, on) => {
    const calls = await fallbackCrew($, on, 'en', undefined, status)
    const ui = await $.ui.mount({ plugin: 'agent-crew', surface: 'terminal', component: 'Pane', requestId: 'crew-board', props: PANE })
    expect(calls.some(argv => argv[1]?.endsWith('/render_roles.py'))).toBe(status === 'ok')
    await ui.unmount()
  })
}
