import { expect, test } from 'claude-code/testing'

// A small crew served through fs hooks, so the board and the agents pane draw real agents.
const TEAM = {
  lead: { id: 'claude', name: 'Claude', color: '#d97757', role: 'Tech lead' },
  user: { id: 'user', name: 'Sen', color: '#60a5fa', role: 'Ürün sahibi' },
  agents: [
    { id: 'ada', name: 'Ada', color: '#22d3ee', role: 'backend' },
    { id: 'duru', name: 'Duru', color: '#f472b6', role: 'arayüz' },
  ],
  steps: [
    { id: 'assigned', label: 'Atandı' }, { id: 'working', label: 'Çalışıyor' },
    { id: 'reviewing', label: 'İnceleniyor' }, { id: 'merged', label: 'Birleşti' },
  ],
  phases: [{ id: 'D4', label: 'Bilgi' }],
  theme: 'tamer',
  themes: { tamer: { title: 'Creature Tamer', bar: 'orb', agents: { ada: { name: 'Blazeback', avatar: '🔥' }, duru: { name: 'Melodee', avatar: '🎤' } } } },
}
const NL = String.fromCharCode(10)
const filesFor = (team: object): Record<string, string> => ({
  '.crew/config.json': JSON.stringify({ project: 'demo', lang: 'tr', planDir: 'plan', stateDir: 'state', phasePrefix: 'D' }),
  'plan/team.json': JSON.stringify(team),
  'state/board.json': JSON.stringify({ phase: 'D4', focus: 'demo', items: { 'wp51-demo': { agent: 'ada', step: 'working' }, 'wp54-demo': { agent: 'duru', step: 'reviewing' } } }),
  'plan/wp/wp51-demo.md': ['# wp51-demo', '', '- Özet: Koleksiyonları keşfet.'].join(NL),
  'plan/wp/wp54-demo.md': ['# wp54-demo', '', '- Özet: Bilgi ekranı.'].join(NL),
})
const PANE = { title: 'x', isFocused: true, bodyColumns: 80, placement: 'dock', scroll: {}, view: {} } as any

async function serve($: any, on: any, team: object) {
  const FILES = filesFor(team)
  const find = (p: string) => Object.keys(FILES).find(k => p.split(String.fromCharCode(92)).join('/').endsWith(k))
  on('fs.read', async (_$: any, e: any) => {
    const k = find(e.path)
    if (!k) return { deny: 'ENOENT' }
    return { value: FILES[k] }
  })
  on('fs.exists', async (_$: any, e: any) => ({ value: !!find(e.path) }))
  on('fs.list', async () => ({ value: [] }))
  on('fs.stat', async () => ({ deny: 'ENOENT' }))
  on('fs.write', async () => ({ value: undefined }))
  on('command.register', async (_$: any, e: any) => ({ value: { command: e.name } }))
  on('process.run', async () => ({ value: { exitCode: 1, stdout: '', stderr: 'no', isStdoutTruncated: false, isStderrTruncated: false } }))
  await $.session.start({ source: 'startup', cwd: 'C:/demo', session_id: 's', transcript_path: 't' }).catch((err: unknown) => console.log('start:', String(err)))
}

test('agents pane and board draw a real crew', async ($, on) => {
  await serve($, on, TEAM)
  for (const surface of ['terminal', 'desktop'] as const) {
    const board = await $.ui.mount({ plugin: 'agent-crew', surface, component: 'Pane', requestId: 'crew-board', props: PANE })
    expect(await board.find({ type: 'Text', text: /Blazeback/ })).toBeDefined()
    await board.unmount()
    const ui = await $.ui.mount({ plugin: 'agent-crew', surface, component: 'Pane', requestId: 'crew-agents', props: PANE })
    expect(await ui.find({ type: 'Text', text: /BLAZEBACK|MELODEE/ })).toBeDefined()
    await ui.unmount()
  }
})

// Projects set up before 0.5.3 may name a theme key that a newer team.json only has under its new name.
test('a legacy theme key resolves to its renamed theme', async ($, on) => {
  await serve($, on, { ...TEAM, theme: 'pacman', themes: { arcade: { title: 'Arcade Maze', bar: 'maze', agents: { ada: { name: 'Rumble', avatar: 'ᗣ' } } } } })
  const board = await $.ui.mount({ plugin: 'agent-crew', surface: 'terminal', component: 'Pane', requestId: 'crew-board', props: PANE })
  expect(await board.find({ type: 'Text', text: /Rumble/ })).toBeDefined()
  await board.unmount()
})
