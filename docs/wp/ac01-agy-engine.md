# ac01-agy-engine — Antigravity (agy / Gemini) as a second crew engine

- Summary: Add `agy` as a second implementation/review engine next to Codex, with quota-aware failover.
- Model: standard

## Facts (verified by the lead)
- Binary: `%LOCALAPPDATA%\agy\bin\agy.exe` (1.2.17), signed in. Models include gemini-3.8-flash-{low,medium,high},
  gemini-3.1-pro-{low,high}.
- Headless: `agy -p "<prompt>" --output-format stream-json --sandbox --model <m> [--effort ...] [--mode accept-edits]`,
  run with cwd = the worktree. Events (NDJSON): `{"event":"init","init":{model,cwd,tools,permission_mode}}`,
  `{"event":"step_update","step_update":{conversation_id,step_index,state,step_type,text_delta?,usage?,duration_seconds?}}`,
  `{"event":"result","result":{conversation_id,status,response,duration_seconds,num_turns,usage}}`.
  Resume: `--conversation <id>` (or `-c`).
- Tool steps: `step_update` with `step_type:"tool"`, `tool_name` (e.g. `run_command`, `write_to_file`,
  `replace_file_content`, `view_file`), `tool_info.parameters` (`CommandLine` for commands) and, when
  `state:"DONE"`, `tool_info.output`. Denied commands show up in the agent text and `result.denied_actions`.
- Permissions live in `~/.gemini/antigravity-cli/settings.json` (already configured by the lead:
  sandbox on, `toolPermission: proceed-in-sandbox`, prefix-matched allow/deny rules). Headless mode
  auto-denies anything not allowed. On Windows commands run in PowerShell.
- Allowed for you: read commands, `git status|diff|log|show`, `python -m pytest`, `bash -n`,
  `claude plugin validate|test`, `npm test`. Denied: any Git write, `gh`, deletes, installs, network.

## Files (you own only these)
`templates/bin/lib.sh`, `templates/bin/run-wp.sh`, `templates/bin/tell.sh`, `templates/bin/board.py`,
`templates/plan/models.json`, `hooks/register.tsx`, `hooks/panes.test.tsx`, `skills/crew-lead/SKILL.md`,
new tests under `tests/`.

## Tasks
1. `templates/bin/lib.sh`: `run_agy <wp> <run-dir> <workdir> <prompt>` mirroring `run_codex`: streams NDJSON into
   `events.jsonl`, writes the final `result.response` to `report.md`, conversation id to `thread`, usage totals.
   `board.py ingest` must also understand agy events (agent text → chat message; failed result → error).
2. Engine selection: WP line `- Engine: codex|agy` (default codex) or env `CREW_ENGINE`; models.json gets an
   `agy` tier map (light→gemini-3.8-flash-low, standard→gemini-3.8-flash-medium, deep→gemini-3.1-pro-high,
   peak→gemini-3.1-pro-high). `templates/bin/tell.sh` resumes with `--conversation`.
3. Quota-aware failover: when the last Codex `turn.failed` says "usage limit" / "try again at <time>", write
   `status=paused` + `resume_at` into the run dir; if `CREW_FAILOVER=agy` is set, continue the WP on agy in the
   same worktree with a handover prompt (WP spec + `git status`/diff summary). Same in the other direction.
4. Plugin panel (`hooks/register.tsx`): parse agy events in `parseEvents` (tool steps as commands, usage), show
   `paused · resumes HH:MM` for paused runs. Keep `claude plugin validate` and `claude plugin test` green.
5. `skills/crew-lead/SKILL.md`: document engines, cross-review (`agy` reviews a Codex diff read-only:
   `--mode plan`), and failover.

## Acceptance
- `bash -n` on scripts; python tests for ingest of both event formats; plugin validate + test pass.
- A fixture-based test feeds a recorded agy NDJSON stream (put one under `tests/fixtures/agy-events.jsonl`)
  through ingest and the panel parser. The lead does the real smoke run (you cannot create worktrees).
- Finish with a report: changed files, commands run with results, open questions. Do not commit.
