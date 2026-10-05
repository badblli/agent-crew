# ac02-usage-and-live-view — quota strip for Claude, Codex and agy + "what is happening now"

- Summary: The crew panel shows at a glance what every agent is doing right now and how much quota each engine has left.
- Model: standard
- Engine: agy
- Depends on: ac01 (same files; start after ac01 is merged)

## Why
The user supervises from the desktop app and the phone. Today they cannot see how close Claude, Codex or
Gemini (agy) are to their limits, and agent panes show raw event streams rather than "what it is doing now".

## Facts (verified by the lead)
- Codex: every `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` carries `"rate_limits"` objects:
  `primary {used_percent, window_minutes:300, resets_at:<unix>}` (5-hour window) and
  `secondary {used_percent, window_minutes:10080, resets_at}` (weekly); `primary` may be null. The latest
  non-null values in the newest rollout file are the current state.
- Claude: plan windows (5-hour %, weekly %, reset times) are visible to the lead session, not to scripts.
  The lead writes them to `<stateDir>/usage/claude.json`
  (`{"updated_at": iso, "windows":[{"label","percent","resets_at"}]}`); the panel only reads that file. First check
  whether the mod API in `types/index.d.ts` / the plugin runtime exposes plan usage directly; prefer it if so.
- agy: no quota endpoint. Token usage per step is in `step_update.usage`; sum per day from
  `<stateDir>/runs/*/*/events.jsonl` whose `model` file starts with `gemini`. A failed result whose text mentions
  quota/exhausted/429 marks agy as limited.

## Tasks
1. `templates/bin/board.py usage`: collects Codex (rollout files) and agy (run events) into
   `<stateDir>/usage/{codex,agy}.json` with `updated_at`; `run-wp.sh` calls it at start and end of every run.
2. Panel: a quota strip at the top of the team pane: one bar per engine (Claude 5h + weekly, Codex 5h + weekly,
   agy tokens today / limited flag), percent and "resets HH:MM" in local time; amber ≥75 %, red ≥90 %;
   stale (> 30 min) values shown dimmed with their age.
3. Panel: a "now" line per agent: current step (thinking / running `<command>` / editing `<file>` / tests),
   elapsed time, files touched so far, last test result (pass/fail count when visible). Paused runs show
   `paused · resumes HH:MM`.
4. Strings in en + tr; keeps mobile layout readable (390 px).
5. `skills/crew-lead/SKILL.md`: the lead refreshes `usage/claude.json` at each loop step and must pause new
   launches when an engine is ≥90 %.

## Files (you own only these)
`templates/bin/board.py`, `templates/bin/run-wp.sh`, `hooks/register.tsx`, `hooks/panes.test.tsx`,
`skills/crew-lead/SKILL.md`, new tests under `tests/` (fixtures under `tests/fixtures/`).

## Acceptance
- Tests: rollout fixture → expected codex.json; agy events fixture → token totals; panel test renders the strip
  with stale/amber/red states and a paused run.
- `bash -n` on scripts, `python -m pytest tests`, `claude plugin validate .`, `claude plugin test .` pass.
- Report: changed files, commands with results, open questions. Never use Git writes.
