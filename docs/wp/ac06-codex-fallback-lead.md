# ac06-codex-fallback-lead — Codex keeps the crew going when Claude's limit runs out

- Summary: When the Claude lead nears its usage limit it hands over to Codex, which can plan, run and review work packages and open PRs (but not merge) until Claude is back.
- Model: deep
- Engine: codex
- Depends on: ac05 (same skill files and board.py)

## Why
The lead is Claude Code. When Claude's 5-hour or weekly window is used up, the crew stops even though
Codex (a separate subscription) still has quota. The crew scripts are plain bash/Python, so Codex can drive
them; it only needs the lead playbook, the current state and clear limits on what it may do alone.

## Facts (verified by the lead, 2026-11-10)
- Codex loads repo skills from `.agents/skills/<name>/SKILL.md` (`name`, `description` frontmatter) and
  reads `AGENTS.md` natively. Custom agents live in `.codex/agents/*.toml` (ac03 renders them).
- The board panes, decision band and `/crew` are Claude Code plugin hooks; Codex cannot show them, but
  `board.py` keeps writing `<stateDir>/board.json`, so the panes show everything when Claude returns.
- The lead already writes `<stateDir>/usage/claude.json` (plan windows) and the quota pane warns at 90 %.
- `board.py handoff` (ac04) writes a ≤40-line `handoff.md` the next lead reads at session start.

## Tasks
1. Lead playbook for Codex: `tools/render_roles.py` (or a small sibling `tools/render_lead.py`) renders
   `skills/crew-lead/SKILL.md` plus a short "Fallback lead (Codex)" preamble into
   `.agents/skills/crew-lead/SKILL.md` when `codex` is in `config.engines`. Same edit protection as roles
   (hash manifest; an edited file is kept and named). crew-init runs it; the session-start sync re-runs it.
   Preamble rules:
   - You are the fallback lead. Read `.crew/config.json` and `<planDir>/handoff.md` first.
   - Allowed: write/assign WPs, `run-wp.sh` (Codex/agy workers), `tell.sh`, review diffs, re-run tests,
     commit in the agent worktree, push the branch, open a PR, `board.py step … pr_open`.
   - Not allowed: merging PRs, pushing to the default branch, history rewrites, sending data to new external
     services, changing `.crew/config.json` or permissions. Leave those for the user or the Claude lead.
   - Questions for the user go in your own chat (no decision band in Codex); record the answer in the WP.
   - Before stopping: `board.py handoff`, fill `## Next`, and list the PRs you opened.
2. `board.py lead [claude|codex]`: prints or sets `board.json` `lead` = `{id, since}`. `board.py model`:
   while the lead is `codex`, a WP with `- Engine: claude` resolves to `codex` (Claude workers share the
   exhausted quota) unless `CREW_ENGINE_FORCE` says otherwise; print a one-line note to stderr.
3. `board.py handoff --to codex|claude`: same card plus a `## Lead` section naming the next lead and, for
   codex, the exact command for the user to paste:
   `codex "Use the crew-lead skill as fallback lead: read .crew/plan/handoff.md and continue."`
   (it also sets `lead` accordingly).
4. `skills/crew-lead/SKILL.md`:
   - Claude lead: when `usage/claude.json` shows a window ≥ 90 % (or a worker/lead call fails with a usage
     limit), stop launching new work, run `board.py handoff --to codex`, fill `## Next`, and tell the user
     the paste command and the reset time. Do not hand over if `codex` is not in `config.engines`.
   - Claude lead returning: if `board.py lead` says `codex`, read `handoff.md`, review every PR the fallback
     lead opened as if it were an agent's work (diff + re-run tests) before merging, then `board.py lead claude`.
5. Panel (`hooks/register.tsx`): when `board.json.lead.id == "codex"`, the crew board header shows
   "Lead: Codex (fallback) since HH:MM" / "Lider: Codex (yedek) HH:MM'den beri". Strings in en + tr.

## Files (you own only these)
`tools/render_roles.py` (or new `tools/render_lead.py`), `templates/bin/board.py`,
`templates/bin-history.json` (via `python tools/sync_bin.py --record`), `skills/crew-lead/SKILL.md`,
`skills/crew-init/SKILL.md`, `hooks/register.tsx`, `hooks/panes.test.tsx`, new tests and fixtures under
`tests/`. Do not touch README.md (another session owns it).

## Acceptance criteria
- AC-01: with `engines: ["claude","codex"]` the renderer writes `.agents/skills/crew-lead/SKILL.md` whose
  frontmatter has `name` and `description` and whose body starts with the fallback preamble; with
  `engines: ["claude"]` it writes nothing there; an edited copy is kept and reported.
- AC-02: `board.py lead codex` then `board.py model <wp>` for a `- Engine: claude` WP prints a codex model;
  after `board.py lead claude` it prints the claude model again.
- AC-03: `board.py handoff --to codex` output ≤ 40 lines, contains `## Lead` and the paste command, and
  `board.py lead` prints `codex`.
- AC-04: panel test renders the fallback badge in en and tr when `lead.id` is `codex`, and no badge otherwise.
- AC-05: `python -m pytest -q tests`, `bash -n templates/bin/*.sh`, the hook tests and
  `claude plugin validate .` pass; shellcheck-clean shell.
- Report: changed files, commands with results, open questions. Never use Git writes.
