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
  theme: 'pokemon',
  themes: { pokemon: { title: 'Pokémon', bar: 'pokeball', agents: { ada: { name: 'Charizard', avatar: '🔥' }, duru: { name: 'Jigglypuff', avatar: '🎤' } } } },
}
const NL = String.fromCharCode(10)
const FILES: Record<string, string> = {
  '.crew/config.json': JSON.stringify({ project: 'demo', lang: 'tr', planDir: 'plan', stateDir: 'state', phasePrefix: 'D' }),
  'plan/team.json': JSON.stringify(TEAM),
  'state/board.json': JSON.stringify({ phase: 'D4', focus: 'demo', items: { 'wp51-demo': { agent: 'ada', step: 'working' }, 'wp54-demo': { agent: 'duru', step: 'reviewing' } } }),
  'plan/wp/wp51-demo.md': ['# wp51-demo', '', '- Özet: Koleksiyonları keşfet.'].join(NL),
  'plan/wp/wp54-demo.md': ['# wp54-demo', '', '- Özet: Bilgi ekranı.'].join(NL),
}
const PANE = { title: 'x', isFocused: true, bodyColumns: 80, placement: 'dock', scroll: {}, view: {} } as any
const find = (p: string) => Object.keys(FILES).find(k => p.split(String.fromCharCode(92)).join('/').endsWith(k))

test('agents pane and board draw a real crew', async ($, on) => {
  on('fs.read', async (_$, e: any) => {
    const k = find(e.path)
    if (!k) return { deny: 'ENOENT' }
    return { value: FILES[k] }
  })
  on('fs.exists', async (_$, e: any) => ({ value: !!find(e.path) }))
  on('fs.list', async () => ({ value: [] }))
  on('fs.stat', async () => ({ deny: 'ENOENT' }))
  on('fs.write', async () => ({ value: undefined }))
  on('command.register', async (_$, e: any) => ({ value: { command: e.name } }))
  on('process.run', async () => ({ value: { exitCode: 1, stdout: '', stderr: 'no', isStdoutTruncated: false, isStderrTruncated: false } }))
  await ($ as any).session.start({ source: 'startup', cwd: 'C:/demo', session_id: 's', transcript_path: 't' }).catch((err: unknown) => console.log('start:', String(err)))
  for (const surface of ['terminal', 'desktop'] as const) {
    const board = await $.ui.mount({ plugin: 'agent-crew', surface, component: 'Pane', requestId: 'crew-board', props: PANE })
    expect(await board.find({ type: 'Text', text: /Charizard/ })).toBeDefined()
    await board.unmount()
    const ui = await $.ui.mount({ plugin: 'agent-crew', surface, component: 'Pane', requestId: 'crew-agents', props: PANE })
    expect(await ui.find({ type: 'Text', text: /CHARIZARD|JIGGLYPUFF/ })).toBeDefined()
    await ui.unmount()
  }
})
