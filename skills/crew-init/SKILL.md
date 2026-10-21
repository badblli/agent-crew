---
name: crew-init
description: Set up an agent crew in the current project (Claude Code as tech lead, named Codex agents in parallel worktrees, live crew board). Use when the user asks to set up / initialize / add the crew, the team, the agents or the Pokémon team in a project, or when the crew board says no crew is configured.
---

# Set up an agent crew in this project

Goal: after this, the user can say "give X to the crew" and you (the lead) write work packages,
run named Codex agents in their own git worktrees, review, commit and track everything on the live
crew board (`/crew`). Follow the `crew-lead` skill for the day-to-day loop.

The plugin's files are in this plugin's root (the directory that contains `.claude-plugin/` and
`templates/`). Find it from this skill's own path: `<plugin root>/skills/crew-init/SKILL.md`.

## Steps

1. **Check the project.** Git repo root, default branch (`gh repo view --json defaultBranchRef` or
   `git symbolic-ref refs/remotes/origin/HEAD`), whether it is public, how tests/lint/build run (CI
   workflow, Makefile, package.json, pyproject). Check the Codex CLI: prefer the newest
   `%LOCALAPPDATA%/OpenAI/Codex/bin/*/codex.exe` on Windows, else `codex` on PATH; run
   `codex exec -s read-only "Reply OK"` once to confirm the account model works. Verify that
   `plan/models.json` names models available to this account; adapt unavailable model IDs before
   starting an agent.
2. **Ask the user only what you cannot infer** (one AskUserQuestion): crew language (en/tr),
   theme (classic default, pokemon, pacman, fantasy), and categories of private information that
   must never be committed. Do not ask the user to paste secrets or private examples.
3. **Copy templates** from `<plugin root>/templates/` into the project:
   - `config.json` → `.crew/config.json` (set `project`, `lang`; keep `planDir: .crew/plan`,
     `stateDir: .crew/state` unless the project already has a plan dir).
   - `plan/` → `<planDir>/` (`team.json`, `models.json`, `wp/TEMPLATE.md`). Set `team.json.theme`.
     If `lang` is `tr`, translate step labels, roles and phase labels.
   - `bin/` → `.crew/bin/`: run `python <plugin root>/tools/sync_bin.py --project .` (copies
     `board.py`, `jev_route.py`, `lib.sh`, `run-wp.sh`, `sync.sh`, `tell.sh`, `usage.py` with LF
     line endings). The plugin re-runs it on every session start, so later plugin updates reach
     the project; `"autoUpdate": false` in `.crew/config.json` turns that off.
   - `AGENTS.md` → project root (merge carefully if one exists). Fill `{{…}}`: project summary from
     the README, language, test commands you verified, privacy rule.
4. **Git hygiene:** add `<stateDir>/`, `.env`, and `.env.*` (except `.env.example`) to `.gitignore`;
   check `git ls-files` for any already tracked private files, since ignore rules do not untrack them.
   Add `*.sh text eol=lf` to `.gitattributes`.
   Commit on a branch and open a PR (`chore(crew): set up agent crew`) — never push to a protected
   branch directly.
5. **Verify:** `python .crew/bin/board.py paths`, `python .crew/bin/board.py phase "D0 Setup" "Crew ready"`.
   Tell the user to type `/crew` to see the board (the plugin opens it automatically on the next
   session start).
6. **Add a CLAUDE.md note** (or create one): "This project uses agent-crew; follow the crew-lead skill."
