# ac13-runner-paper-cuts — Small runner and board issues found in the fresh-install test

- Summary: Fix the small things a first-time user trips over after a WP runs: engine-neutral branch names, the board's engine/tier after archiving, archive output, and line-ending noise on Windows.
- Model: light
- Engine: codex
- Depends on: ac12 (same runner files; run after it)

## Why
Found on 2026-11-11 by a headless Claude lead running one Codex and one Claude WP in a scratch repo
(Windows, `core.autocrlf=true`):
1. Every WP branch is `codex/<wp>`, including Claude and agy workers.
2. After `board.py archive`, the board listed both WPs as `codex/standard`; they ran as codex/light and
   claude/light.
3. `board.py archive` prints nothing and moved the WP file out of the main checkout into the worktree;
   the WP files then existed only on the WP branches.
4. `.crew/roles-rendered.json` shows as modified in the main checkout and every worktree on Windows
   (line endings only).
5. The template roster has only Scribe on Claude, so "give this code job to a Claude worker" has no
   natural agent in a both-engines crew.

## Tasks
1. Branch prefix `crew/<wp>` (configurable `branchPrefix` in config.json; keep `codex/` for existing
   projects that have open `codex/*` branches).
2. Archive keeps the engine/tier that actually ran (from the run dir), not the WP default.
3. `board.py archive` prints what it moved and from where to where; it never removes the WP from the
   main checkout when the WP is not yet committed there (warn instead).
4. Write `.crew/roles-rendered.json` with LF and add it to the `.gitattributes` rule crew-init writes.
5. crew-init: in a both-engines crew, put at least one implementer on each engine.

## Files (you own only these)
`templates/bin/run-wp.sh`, `templates/bin/lib.sh`, `templates/bin/board.py`, `templates/bin-history.json`
(via `python tools/sync_bin.py --record`), `templates/config.json`, `tools/render_roles.py` (LF only),
`skills/crew-init/SKILL.md` (gitattributes + roster lines), tests under `tests/`.

## Acceptance criteria
- AC-01: a fixture run with `Engine: claude` creates `crew/<wp>`; a project with `"branchPrefix": "codex/"`
  keeps the old name.
- AC-02: after archive, the board entry shows the engine/tier from the run dir.
- AC-03: archive prints its moves; an uncommitted WP stays in the main checkout.
- AC-04: `python -m pytest -q tests`, `bash -n templates/bin/*.sh` pass; shellcheck-clean shell.
- Report: changed files, commands with results, open questions.
