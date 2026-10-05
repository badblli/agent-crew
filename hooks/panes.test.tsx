import { expect, test } from 'claude-code/testing'
import { parseEvents } from './register'

// The test host has no file system, so the crew is unconfigured and the panes render their quiet
// state; this still validates every tree against each surface's element table.
const PANE = { title: 'crew', isFocused: true, bodyColumns: 70, placement: 'dock', scroll: {}, view: {} } as any

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
  const text = [
    { event: 'step_update', step_update: { step_index: 1, state: 'DONE', step_type: 'tool', tool_name: 'run_command', tool_info: { parameters: { CommandLine: 'pwd' } } } },
    { event: 'step_update', step_update: { step_index: 2, state: 'DONE', step_type: 'tool', tool_name: 'run_command', tool_info: { parameters: { CommandLine: 'git status --short' } } } },
    { event: 'step_update', step_update: { step_index: 3, state: 'ERROR', step_type: 'tool', tool_name: 'run_command', tool_info: { parameters: { CommandLine: 'false' } } } },
    { event: 'result', result: { usage: { input_tokens: 40, output_tokens: 2, thinking_tokens: 1 } } },
  ].map(JSON.stringify).join(NL)
  const parsed = parseEvents(text)
  expect(parsed.commands).toBe(3)
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
