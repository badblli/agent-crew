# agent-crew

[![CI](https://github.com/badblli/agent-crew/actions/workflows/ci.yml/badge.svg)](https://github.com/badblli/agent-crew/actions/workflows/ci.yml)

**Make Claude Code the tech lead of a named crew of coding agents — and watch them work.**

Claude Code plans the work, splits it into work packages, hands each one to a coding agent (Codex or Gemini via the Antigravity CLI) in its
own git worktree, reviews the diff, re-runs the tests itself, commits, opens the PR and merges when
CI is green. You stay the product owner: critical decisions come to you in a decision band; everything
else shows up live on a crew board inside Claude Code.

> Status: early, used daily on one real project. Windows + Git Bash tested; macOS/Linux should work
> (bash, git, python, gh) but are not tested yet.

## What you get

- **Three panes**, opened when the session starts:
  - **Crew board** (`/crew`): phase, roadmap progress, every agent with its work package, step, model,
    token use and a live "now" line (the command it runs or the file it edits).
  - **Agents** (`/crew-agents`): one pane to browse every agent with tabs (keys 1–9, `p`/`n`): step
    track, live commands and edits, a colored diff viewer, and the conversation between the lead, the
    agent and you. Send a note to an agent — it goes through the lead first.
  - **Quota** (`/quota`): Claude plan windows and context, Codex 5-hour and weekly limits, Gemini tokens
    today; a toast when an engine passes 90 %.
  On desktop and mobile the panes draw SVG dials, a Poké-ball step track and a team banner; the
  terminal gets colored text bars.
- **Decision band** above the prompt when the lead needs you; pick an option with a key.
- **Model routing**: each work package declares a tier (light / standard / deep / peak); review rounds
  resume the same agent thread on the same model so the cached prompt is reused.
- **Two engines**: `- Engine: codex|agy` per work package (or `CREW_ENGINE`). When an engine hits its
  usage limit the run is marked *paused* with its reset time; with `CREW_FAILOVER=agy|codex` the work
  continues on the other engine in the same worktree.
- **Second opinion (optional)**: `jev_route.py` asks TypeSafe's Jev for engine, tier, risk and whether
  the user must decide — one request per work package, only when explicitly enabled. It sends the
  work package title, summary, goal, tasks and acceptance criteria to TypeSafe.
- **Themes**: Classic (default), Pokémon-style (with a battle-dialog decision band), Pac-Man, Fantasy.
  Agent ids never change, so switching themes is one line.
- **Two skills**: `crew-init` sets a project up; `crew-lead` is the lead's playbook (write WP →
  run agent → review for real → feedback → ship → merge on green).

## How it works

```text
you ──► Claude Code (lead) ──► work package (.crew/plan/wp/*.md)
                │                    │
                │        .crew/bin/run-wp.sh ──► Codex agent in ../<repo>-wt/<wp> (sandboxed, no git writes)
                │                    │                     │ events, messages, report
                ▼                    ▼                     ▼
          review + re-test ◄── .crew/state (board, chat, runs) ──► crew board / agent panes
                │
                └──► commit · PR · merge on green CI
```

## Install

```text
/plugin marketplace add badblli/agent-crew
/plugin install agent-crew@agent-crew
```

Then, in a project: *"set up the crew in this project"* (runs `crew-init`). The board, agents and quota
panes open on the next session start (Turkish projects also get `/ekip`, `/ajanlar`, `/kota`).

Requirements: Claude Code with plugin hooks, the Codex CLI (logged in), git, GitHub CLI (`gh`),
Python 3, bash. Optional: the Antigravity CLI `agy` (signed in; set sandbox permissions in
`~/.gemini/antigravity-cli/settings.json`), `TYPESAFE_API_KEY` for Jev.

## Updating

`/plugin update agent-crew@agent-crew`, then start a new session. On session start the plugin brings
each crew project's `.crew/bin/` up to the installed version (`tools/sync_bin.py`) and says which
files changed; commit them. A script you edited in the project is left as is and named in a toast.
Nothing is replaced while an agent run is active. Opt out per project with `"autoUpdate": false` in
`.crew/config.json`, or run it by hand: `python <plugin root>/tools/sync_bin.py --project .`.

Changing a script in `templates/bin/`? Run `python tools/sync_bin.py --record` so installed
projects recognise the old version as safe to replace (CI checks this).

Worktrees do not link the main checkout's `node_modules` by default. Linking them with
`CREW_LINK_NODE_MODULES=1` allows an agent to modify that shared directory; use it only if you
accept that access. The lead can run dependency-based checks in the main checkout after review.

## Project layout it creates

```text
.crew/config.json        project, lang (en|tr), planDir, stateDir
.crew/plan/              team.json (roster, steps, phases, themes), models.json, wp/*.md
.crew/bin/               board.py, run-wp.sh, tell.sh, lib.sh, sync.sh, usage.py, jev_route.py
.crew/state/             board, conversations, runs (git-ignored)
AGENTS.md                rules every agent reads
```

The installed crew creates project-specific WPs and local run logs in the destination project.
Review WPs before committing them; keep `.crew/state/` and `.env*` out of Git. Test fixtures in
the plugin should use synthetic events rather than captured agent conversations.

## License

MIT
