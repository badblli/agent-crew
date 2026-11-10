# ac03-engines-and-lean-core — engine choice in crew-init + a lean shared instruction core

- Summary: crew-init asks whether the workers are Claude, Codex or both, and installs one short rule set that both tools read natively.
- Model: deep
- Engine: codex
- Depends on: none

## Why
Projects should work the same whether the crew runs Codex workers, Claude subagents or both, and opening the
project directly in Codex or Claude Code should give the same rules. Heavy rule packages (100–250 KB of
Markdown) cost tokens on every task; the crew keeps the always-loaded part small and moves everything else to
files that are read only when a task needs them.

## Facts (verified by the lead, 2026-11-10)
- Codex reads `AGENTS.md` from the repo root down to the working directory, at most one file per directory
  (`AGENTS.override.md` first), and stops at `project_doc_max_bytes` (32 KiB by default).
- Codex custom agents: one TOML file per agent in `.codex/agents/`. Required `name`, `description`,
  `developer_instructions`; optional `model`, `model_reasoning_effort`. `sandbox_mode` and `approval_policy`
  in an agent file do not override the parent config. Codex does not spawn custom agents on its own.
- Codex repo skills live in `.agents/skills/<name>/SKILL.md`.
- Claude Code reads `CLAUDE.md`, not `AGENTS.md`. The documented pattern is a `CLAUDE.md` whose first line is
  `@AGENTS.md` (not inside a code fence; fenced imports are skipped), followed by Claude-only notes. Target
  under 200 lines per CLAUDE.md.
- Claude Code 2.1.289, checked locally: `claude -p --name <n> --output-format stream-json --verbose` works and
  emits JSON lines: `system/init` (`session_id`, `model`, `cwd`), `assistant` (`message.content[]` with
  `type: text|thinking|tool_use`), `rate_limit_event` (`rate_limit_info`), `result` (`subtype: success`,
  `result`, `session_id`, `usage`, `total_cost_usd`). Every event has `session_id`. Hook lines may appear on
  stdout as non-JSON text; ignore them.
- Docs (code.claude.com/docs/en/cli-reference, sessions, agent-view): `--name`/`-n` sets the session display
  name; `claude --resume <id|name>` reopens a session (headless sessions by id); `claude --bg` starts a
  background session listed by `claude agents` and attachable with `claude attach`; `--bg` and `-p` cannot
  be combined. `/rename` is a user command; no documented way for the model to run it.
- Claude subagents: Markdown with YAML frontmatter in `.claude/agents/`; `name`, `description` required;
  `tools`, `disallowedTools`, `model` (`haiku|sonnet|opus|inherit`), `effort`, `isolation: worktree` optional.

## Tasks
1. `.crew/config.json` gains `"engines": ["codex"] | ["claude"] | ["claude","codex"]`. `crew-init` asks it in
   its single AskUserQuestion (default: both if the Codex CLI check passes, else claude).
2. Lean templates (each shipped in en; crew-init translates headings when `lang` is `tr`):
   - `templates/AGENTS.md`: keep the current hard rules and report format; add a short "Where to look" table
     (commands and architecture → `rule.md`, feature → code map → `feature.md`, past decisions →
     `docs/adr/`) and one rule: "Do not read `<planDir>/plan.md`, `history.md`, `handoff.md`, `notes/` or
     `wp/done/` unless your WP links them." Rendered size ≤ 8 KB.
   - `templates/rule.md`: stack and versions, verified commands (install / run / test / lint / build),
     architecture and module boundaries, coding standard, shared contracts, lessons learned (only proven,
     recurring ones). Unknown values stay `unknown`; no meta-process rules.
   - `templates/feature.md`: one table — id, capability, limits, entry files, tests.
   - `templates/docs/adr/_template.md` (context, options, decision, consequences) and a 10-line README.
   - `templates/CLAUDE.md`: line 1 `@AGENTS.md`, then "This project uses agent-crew; the lead follows the
     crew-lead skill." ≤ 30 lines.
3. Roles from one source: `templates/roles/{analyst,ui,developer,reviewer,qa}.md` (frontmatter `name`,
   `description`, `tier`, `readonly: true|false`; body ≤ 50 lines). New `tools/render_roles.py --project .
   --engines claude,codex` writes:
   - claude → `.claude/agents/crew-<role>.md` (`name`, `description`, `model` from `claude_tiers[tier]`,
     `tools: Read, Glob, Grep` for read-only roles, `disallowedTools: Agent` for all).
   - codex → `.codex/agents/crew-<role>.toml` (`name`, `description`, `developer_instructions` = body,
     `model` and `model_reasoning_effort` from `tiers[tier]`).
   Files the user edited (hash differs from the last render) are left alone and named, like `sync_bin.py`.
4. Claude workers run as their own named, visible Claude Code sessions through the same pipeline as Codex:
   `run-wp.sh` gets `run_claude`, used when the WP says `- Engine: claude`:
   `claude -p --name "<agent display name> · <wp>" --model <claude_tiers model> --output-format stream-json
   --verbose --permission-mode acceptEdits "<prompt>"` in the WP worktree (same prompt as Codex).
   - `board.py ingest` learns the Claude events: `assistant` messages with `text` content → chat lines;
     `result` (`subtype` success / error) → report text and status; `system/init` and every event carry
     `session_id` → saved to `<run>/thread`; `rate_limit_event` → usage hint for the quota pane.
   - `tell.sh` resumes the same session: `claude -p --resume <session_id> ...` (cache reuse, like Codex).
   - The board/agent pane shows "open: `claude --resume <session_id>`" so the user can open any worker
     session interactively, next to the lead session. With `CREW_CLAUDE_BG=1` the run uses
     `claude --bg --name "<…>"` instead, so it is listed in `claude agents` and can be attached live
     (`claude attach <name>`); in that mode the board only tracks start/stop.
   - `models.json` `claude_tiers` gets `deep` (`opus`) and `peak` (`opus`, effort high); `board.py model`
     already resolves `claude_tiers`. `team.json` agents get an `engine` field; role labels lose the
     hard-coded "Codex ·" prefix.
   - Quota failover: `CREW_FAILOVER` accepts `claude` as a target and source, like codex/agy.
5. `skills/crew-init/SKILL.md` and `skills/crew-lead/SKILL.md` describe the three engine setups. crew-lead also
   covers sessions: name the lead session at start (tell the user once: `/rename <project> lead`, since the
   model cannot run built-in slash commands itself); every worker session is named `<agent> · <wp>`; the
   Agent tool (in-session subagents, not separately visible) is only for tiny read-only helpers; when the
   user asks to watch a worker, give the `claude --resume <session_id>` / `claude attach <name>` line.

## Files (you own only these)
`templates/AGENTS.md`, `templates/CLAUDE.md`, `templates/rule.md`, `templates/feature.md`,
`templates/docs/adr/*`, `templates/roles/*`, `templates/config.json`, `templates/plan/models.json`,
`templates/plan/team.json`, `templates/bin/run-wp.sh`, `templates/bin/tell.sh`, `templates/bin/board.py`,
`templates/bin/lib.sh`, `templates/bin-history.json` (via `python tools/sync_bin.py --record`), `tools/render_roles.py`, `skills/crew-init/SKILL.md`,
`skills/crew-lead/SKILL.md`, `README.md`, new tests and synthetic fixtures under `tests/`.

## Acceptance criteria
- AC-01: `render_roles.py` on a temp project with `--engines claude,codex` writes 5 `.md` + 5 `.toml`; every
  TOML parses with `tomllib` and has `name`, `description`, `developer_instructions`; every `.md` has
  `name` and `description` frontmatter. With `--engines codex` no `.claude/agents/` file is written.
- AC-02: an edited rendered role is not overwritten and is reported.
- AC-03: rendered `AGENTS.md` ≤ 8 KB; `CLAUDE.md` line 1 is exactly `@AGENTS.md`.
- AC-04: `board.py model` returns a claude model for `- Engine: claude` with each tier.
- AC-06: with a stub `claude` on PATH replaying `tests/fixtures/run-wp/claude-success.jsonl` (synthetic, shape
  as in Facts), `run-wp.sh` writes `report.md` from the `result` text, `thread` = the session id, passes
  `--name "<agent> · <wp>"`, and the board chat gets the assistant text; `claude-failed.jsonl` marks the run
  failed; `tell.sh` on that WP calls `claude -p --resume <session id>`.
- AC-05: `python -m pytest tests`, `bash -n templates/bin/*.sh`, `claude plugin validate .` pass.
- Report: changed files, commands with results, open questions. Never use Git writes.
