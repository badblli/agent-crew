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
