---
name: crew-init
description: Set up an agent crew in the current project (Claude Code as tech lead, Claude or Codex workers or both, live crew board). Use when the user asks to set up / initialize / add the crew, the team, the agents or the Pokémon team in a project, or when the crew board says no crew is configured.
---

# Set up an agent crew in this project

Goal: after this, the user can say "give X to the crew" and you (the lead) write work packages,
run named Claude or Codex worker sessions in their own git worktrees, review, commit and track everything on the live
crew board (`/crew`). Follow the `crew-lead` skill for the day-to-day loop.

The plugin's files are in this plugin's root (the directory that contains `.claude-plugin/` and
`templates/`). Find it from this skill's own path: `<plugin root>/skills/crew-init/SKILL.md`.

## Steps

1. **Check the project.** Git repo root, default branch (`gh repo view --json defaultBranchRef` or
   `git symbolic-ref refs/remotes/origin/HEAD`), whether it is public, how tests/lint/build run (CI
   workflow, Makefile, package.json, pyproject). Check the Codex CLI: prefer the newest
   `%LOCALAPPDATA%/OpenAI/Codex/bin/*/codex.exe` on Windows, else `codex` on PATH; run
   `codex exec -s read-only "Reply OK"` once to confirm the account model works. A missing CLI or
   failed check permits a Claude-only setup; do not block initialization on Codex. Check Claude
   availability with `claude --version`. Verify that `plan/models.json` names models available to
   the selected accounts; adapt unavailable model IDs before starting an agent.
2. **Ask in one AskUserQuestion:** worker engines (Claude / Codex / both), crew language (en/tr),
   theme (classic default, pokemon, pacman, fantasy), and categories of private information that
   must never be committed. Default engines to both if the Codex CLI check passed, otherwise Claude.
   Infer known answers, but include engine choice in this single question. Do not ask the user to
   paste secrets or private examples.
3. **Copy templates** from `<plugin root>/templates/` into the project:
   - `config.json` → `.crew/config.json` (set `project`, `lang`, `engines`; keep `planDir: .crew/plan`,
     `stateDir: .crew/state` unless the project already has a plan dir).
   - `plan/` → `<planDir>/` (`team.json`, `models.json`, `wp/TEMPLATE.md`). Set `team.json.theme`.
     If `lang` is `tr`, translate step labels, roles and phase labels. Set each roster member's
     `engine` to an enabled engine: all Claude in a Claude-only setup, all Codex in a Codex-only
     setup, or choose per role for both. Keep role labels independent of the engine.
   - `bin/` → `.crew/bin/`: run `python <plugin root>/tools/sync_bin.py --project .` (copies
     `board.py`, `jev_route.py`, `lib.sh`, `run-wp.sh`, `sync.sh`, `tell.sh`, `usage.py` with LF
     line endings). The plugin re-runs it on every session start, so later plugin updates reach
     the project; `"autoUpdate": false` in `.crew/config.json` turns that off.
   - `AGENTS.md`, `CLAUDE.md`, `rule.md`, `feature.md`, `docs/adr/` → project root (merge carefully
     if they exist; preserve project content). Fill `{{…}}` in AGENTS.md: `planDir`, project summary
     from README, language and privacy rule. Keep rendered AGENTS.md at most 8 KB; keep CLAUDE.md
     at most 30 lines with line 1 exactly `@AGENTS.md`, outside a code fence. Codex reads AGENTS.md
     natively; Claude imports it through CLAUDE.md.
   - Fill `rule.md` with the observed stack/versions and install/run/test/lint/build commands
     you verified by running them (AGENTS.md no longer has a `{{testCommands}}` block),
     module boundaries, coding standard, shared contracts and only proven recurring lessons.
     Unverified values stay `unknown`; keep process instructions in AGENTS.md. Fill the single
     feature.md table from the README and code: capability, limits, entry-file paths and test paths.
     Read decision records only when relevant. Do not add plan/history/handoff archives to the
     always-loaded instructions.
   - Templates ship in English. For `lang: tr`, translate document headings, table labels and role
     prose to Turkish while preserving paths, CLI commands, config/frontmatter keys, `unknown`,
     the exact first CLAUDE.md line and the literal final-report headings required by AGENTS.md.
   - Render roles from the plugin's single source:
     `python <plugin root>/tools/render_roles.py --project . --engines <comma-separated engines>`.
     Claude-only writes `.claude/agents/crew-*.md`; Codex-only writes `.codex/agents/crew-*.toml`;
     both writes both sets. The renderer uses the project's models.json and records hashes in
     `.crew/roles-rendered.json`; keep that manifest so future renders preserve edited files.
     Review any files reported as locally changed rather than overwriting them. For Turkish,
     translate role prose deliberately after rendering; later renders will preserve those edits.
     Codex repository skills belong in `.agents/skills/<name>/SKILL.md`. Custom agent definitions
     do not launch workers automatically; use run-wp.sh for WP sessions. Codex agent files do not
     override parent sandbox/approval settings.
4. **Git hygiene:** add `<stateDir>/`, `.env`, and `.env.*` (except `.env.example`) to `.gitignore`;
   check `git ls-files` for any already tracked private files, since ignore rules do not untrack them.
   Add `*.sh text eol=lf` to `.gitattributes`.
   Commit on a branch and open a PR (`chore(crew): set up agent crew`) — never push to a protected
   branch directly.
5. **Verify:** `python .crew/bin/board.py paths`, `python .crew/bin/board.py phase "D0 Setup" "Crew ready"`.
   Tell the user to type `/crew` to see the board (the plugin opens it automatically on the next
   session start).
6. **Explain sessions:** ask the user once to run `/rename <project> lead`; the model cannot invoke
   that built-in slash command itself. Each Claude worker gets `<agent display name> · <wp>` and
   can be reopened with `claude --resume <session_id>` from `<run>/thread`. See crew-lead for
   optional `CREW_CLAUDE_BG=1` sessions and `claude attach <name>`.
