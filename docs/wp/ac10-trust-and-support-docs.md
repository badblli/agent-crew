# ac10-trust-and-support-docs — What it touches, what it sends, how to remove it, where to get help

- Summary: Strangers can see, before installing, which files and folders the crew writes, which network calls happen, how to uninstall it cleanly, and where to report a bug.
- Model: standard
- Engine: claude
- Depends on: ac08 (CHANGELOG link)

## Why
The README explains features well but a new user cannot answer the trust questions: Does it phone home?
Where do the worktrees go? How do I get rid of it? Is the bundled TypeSafe skill part of the product?
There is no CHANGELOG, SECURITY.md, CONTRIBUTING.md or issue template.

## Facts (checked 2026-11-11)
- Network calls: the Claude Code mod fetches
  `https://raw.githubusercontent.com/badblli/agent-crew/main/.claude-plugin/plugin.json` once a day
  (`hooks/register.tsx`, `UPDATE_URL`, off with `updateCheck`); `jev_route.py` calls TypeSafe only when
  enabled and sends the WP title, summary, goal, tasks and acceptance criteria; Codex, Claude and agy
  workers talk to their own providers; Codex itself refreshes the Git marketplace at every startup.
- Worktrees are created next to the repo as `../<repo>-wt/<wp>` on branches `codex/<wp>` (also for
  Claude workers).
- The plugin ships a third skill, `skills/typesafe-ai/` (generic "build AI features with TypeSafe"),
  loaded in every project for Claude Code and Codex users; the README says "Two skills".
- Claude worker default permission mode is `auto`; Codex workers run `workspace-write`.

## Tasks
1. README (EN + TR) **"What it changes and what it sends"** section: files written by crew-init, the
   sibling `-wt` folder and `codex/*` branches, permission modes of workers, every outbound call above
   with how to turn it off. State plainly: no telemetry.
2. README **"Uninstall"**: Claude Code (`claude plugin uninstall agent-crew@agent-crew`,
   `claude plugin marketplace remove agent-crew`), Codex (`codex plugin remove agent-crew@agent-crew`,
   `codex plugin marketplace remove agent-crew`), and the project side (remove `.crew/`, rendered roles,
   `.agents/skills/crew-lead/`, `../<repo>-wt/` worktrees via `git worktree remove`, `codex/*` branches).
3. **TypeSafe skill**: ask the user whether it stays in this plugin. If it stays, list it in "What you
   get" and the privacy section; if not, remove `skills/typesafe-ai/` (and its tests/mentions).
4. `.github/ISSUE_TEMPLATE/bug_report.yml` (OS, client + version, plugin version, `board.py doctor`
   and ac09 doctor output, steps) and `feature_request.yml`; `SECURITY.md` (private report via GitHub
   security advisories); short `CONTRIBUTING.md` (tests, `sync_bin.py --record`, WP style).
5. Add a `description` to `.claude-plugin/marketplace.json` so `claude plugin validate . --strict`
   passes, and switch CI to `--strict`.
6. A 20–40 s demo GIF or video of "set up the crew" → one WP → PR (recorded by the user; leave a
   placeholder and a shot list in `docs/assets/README.md`).

## Files (you own only these)
`README.md`, `README.tr.md`, `.claude-plugin/marketplace.json` (description only), `.github/ISSUE_TEMPLATE/*`,
new `SECURITY.md`, new `CONTRIBUTING.md`, `.github/workflows/ci.yml` (validate `--strict` only),
`docs/assets/README.md`; `skills/typesafe-ai/` only after the user decides.

## Acceptance criteria
- AC-01: README EN and TR both have "What it changes and what it sends" and "Uninstall"; every outbound
  call in Facts is listed with its off switch.
- AC-02: following the Uninstall steps in a scratch config leaves `claude plugin list` /
  `codex plugin list` without agent-crew and the demo project without crew files or worktrees.
- AC-03: `claude plugin validate . --strict` passes and CI runs it.
- Report: changed files, commands with results, open questions.
