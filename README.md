# agent-crew

**Make Claude Code the tech lead of a named crew of coding agents — and watch them work.**

Claude Code plans the work, splits it into work packages, hands each one to a Codex agent in its
own git worktree, reviews the diff, re-runs the tests itself, commits, opens the PR and merges when
CI is green. You stay the product owner: critical decisions come to you in a decision band; everything
else shows up live on a crew board inside Claude Code.

> Status: early, used daily on one real project. Windows + Git Bash tested; macOS/Linux should work
> (bash, git, python, gh) but are not tested yet.

## What you get

- **Crew board** (`/crew`): phase, roadmap progress, every agent with its step, model and token use.
- **One pane per agent**: task, step timeline, live commands and file edits, a colored diff viewer, and
  the conversation between the lead, the agent and you. Send a note to an agent — it goes through
  the lead first.
- **Decision band** above the prompt when the lead needs you; pick an option with a key.
- **Model routing**: each work package declares a tier (light / standard / deep / peak); review rounds
  resume the same agent thread on the same model so the cached prompt is reused.
- **Themes**: Pokémon-style (default, with a battle-dialog decision band), Pac-Man, Fantasy, Classic.
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

Then, in a project: *"set up the crew in this project"* (runs `crew-init`), and `/crew` to open the board.

Requirements: Claude Code with plugin hooks, the Codex CLI (logged in), git, GitHub CLI (`gh`),
Python 3, bash.

## Project layout it creates

```text
.crew/config.json        project, lang (en|tr), planDir, stateDir
.crew/plan/              team.json (roster, steps, phases, themes), models.json, wp/*.md
.crew/bin/               board.py, run-wp.sh, tell.sh, lib.sh
.crew/state/             board, conversations, runs (git-ignored)
AGENTS.md                rules every agent reads
```

## License

MIT
