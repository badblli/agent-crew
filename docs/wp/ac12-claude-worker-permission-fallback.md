# ac12-claude-worker-permission-fallback — A blocked Claude worker is never reported as done

- Summary: Light-tier Claude workers (Haiku) silently start in `default` permission mode, edit nothing, and the run is still marked successful; the runner must catch this and pick a mode that works.
- Model: standard
- Engine: codex
- Depends on: none

## Why
In the 2026-11-11 fresh-install test (Windows, Claude Code 2.1.289) a `light` WP with `Engine: claude`
ran on `claude-haiku-4-5`. `lib.sh` passes `--permission-mode auto`, but the session's init event said
`"permissionMode":"default"`. Every Edit was denied ("requested permissions to write … but you haven't
granted it yet"), the worker's report said it was waiting for permission, and still `status` was
`done`, `result_status` success, and the board step `reported`. Only reading the diff caught it.
Re-run check: `claude -p --model haiku --permission-mode auto` → init `default`;
`--model sonnet` → init `auto`. The lead's workaround (`CREW_CLAUDE_PERMISSION_MODE=acceptEdits`) lets
the worker edit but blocks Bash, so it cannot run tests.

## Tasks
1. `run-wp.sh` / `lib.sh`: read `permissionMode` from the Claude init event. If it differs from the
   requested mode, record it in the run dir (`mode`), warn in chat once, and treat the run as
   `failed` with reason `permission-mode-fallback` when the run produced permission denials and no diff.
2. Any run whose events contain `permission_denied` for Edit/Write/Bash and whose worktree has no diff
   ends as `blocked` (new board step or `failed` with that reason), never `done`/`reported`.
3. Choose a working default: for Claude models where `auto` is not available (today: Haiku), either map
   the `light` Claude tier to a model that supports `auto`, or pass `acceptEdits` plus an
   `--allowedTools` list for the project's verified test command from `rule.md`. Document the choice in
   `templates/plan/models.json` and README.
4. Fixture `tests/fixtures/run-wp/claude-permission-fallback.jsonl` (synthetic events) and a test.

## Files (you own only these)
`templates/bin/run-wp.sh`, `templates/bin/lib.sh`, `templates/bin/board.py` (status/reason only),
`templates/bin-history.json` (via `python tools/sync_bin.py --record`), `templates/plan/models.json`,
`tests/test_claude_workers.py`, `tests/test_run_wp.py`, new fixture, `README.md`/`README.tr.md`
(one paragraph on Claude worker permission modes).

## Acceptance criteria
- AC-01: with the fallback fixture, the run ends `failed`/`blocked` with reason
  `permission-mode-fallback`, the run dir records the effective mode, and the board is not `reported`.
- AC-02: a normal `auto` run fixture still ends `done`.
- AC-03: a real light-tier Claude WP in a scratch repo edits files and runs the test command (lead checks
  once by hand and pastes the init line).
- AC-04: `python -m pytest -q tests`, `bash -n templates/bin/*.sh`, `claude plugin validate .` pass;
  shellcheck-clean shell.
- Report: changed files, commands with results, open questions.
