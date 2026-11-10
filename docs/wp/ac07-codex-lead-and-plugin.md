# ac07-codex-lead-and-plugin — Codex as a full lead, shipped as a Codex plugin

- Summary: The crew can be led by Codex from the start (not only as a fallback), and the same repository installs as a Codex plugin next to the Claude Code plugin.
- Model: deep
- Engine: codex
- Depends on: ac06 (merged in 0.5.4)

## Why
Some users have only Codex, or run out of Claude for days. The crew scripts are plain bash/Python and
ac06 already renders the crew-lead skill for Codex as a fallback. This WP makes Codex a first-class lead
and lets Codex users install agent-crew as a plugin.

## Facts (checked 2026-11-10; re-verify field names before relying on them)
- Codex plugins bundle skills, MCP servers, apps and lifecycle hooks. Manifest: a root `plugin.json`
  (portable fields: name, version, description, author, homepage, repository, license, keywords; OpenAI
  settings under `extensions.com.openai`). The legacy `.codex-plugin/plugin.json` is still accepted.
  Docs: https://learn.chatgpt.com/docs/plugins (redirect from developers.openai.com/codex/plugins).
- obra/superpowers ships `.claude-plugin/` and `.codex-plugin/` side by side; its
  `.codex-plugin/plugin.json` sets `"skills": "./skills/"`, `"hooks": {}` and an `interface` block.
  Use it as the reference for exact field names: https://github.com/obra/superpowers
- Codex marketplaces: `.agents/plugins/marketplace.json`; `codex plugin marketplace add owner/repo`.
  Users install with `/plugins` in the CLI or the Plugins tab in the app.
- Codex hooks: SessionStart, SessionEnd, PreToolUse, PostToolUse, UserPromptSubmit, Stop, PreCompact …;
  non-managed and plugin hooks must be reviewed/trusted by the user (`/hooks`).
- Codex has no panes, status line or decision band. Claude Code's panes keep reading `board.json`.
- Codex plugin auto-update is not documented.

## Tasks
1. **Lead choice.** `.crew/config.json` gains `"lead": "claude" | "codex"` (default `claude`). crew-init asks it
   in its single question when Codex is enabled. `board.py lead` (ac06) uses `config.lead` as its default.
2. **Codex lead skill.** `tools/render_roles.py` renders `.agents/skills/crew-lead/SKILL.md` with a
   preamble chosen by `config.lead`:
   - `codex` (full lead): same loop as the Claude lead. Questions go in chat as numbered options (no
     AskUserQuestion, no decision band). Merging a PR requires the user's explicit "merge" in chat for that
     PR, after CI is green; never push to the default branch directly.
   - `claude`: keep ac06's fallback preamble unchanged.
   Workers under a Codex lead: `codex` and `agy`; `claude` workers only if `claude` is in `engines`.
3. **Engine-neutral skills.** In `skills/crew-init/SKILL.md` and `skills/crew-lead/SKILL.md`, mark the few
   Claude-only steps (AskUserQuestion, `/rename`, panes, decision band, `/crew`) with a one-line Codex
   equivalent (ask in chat; `codex --name`-style naming only if documented, else skip; `board.py status`).
4. **`board.py status`.** Prints a compact text board for chat: phase/focus, lead, each open WP with agent
   name, step, engine/tier, and the open decision. ≤ 30 lines.
5. **Codex plugin package.** Add the Codex manifest next to `.claude-plugin/` (format per the facts above;
   match superpowers' working layout), pointing at `./skills/`. Add a SessionStart hook that runs
   `python <plugin root>/tools/sync_bin.py --project .` only when `.crew/config.json` exists (same behavior
   as the Claude hook; silent otherwise). Add `.agents/plugins/marketplace.json` listing this plugin.
   Keep the version in sync with `.claude-plugin/plugin.json` (a test asserts equality).
6. **README.md / README.tr.md.** Add a short "Use with Codex" section: install via `/plugins`
   (marketplace `badblli/agent-crew`), trust the hook in `/hooks`, choose `lead: codex` in crew-init, what
   is not available in Codex (panes, decision band, toasts), and how to update.

## Files (you own only these)
`tools/render_roles.py`, `templates/bin/board.py`, `templates/bin-history.json` (via
`python tools/sync_bin.py --record`), `templates/config.json`, `skills/crew-init/SKILL.md`,
`skills/crew-lead/SKILL.md`, new Codex manifest/hook/marketplace files, `README.md`, `README.tr.md`,
new tests under `tests/`. Do not change `.claude-plugin/*` except the version bump the lead does.

## Acceptance criteria
- AC-01: with `lead: codex` the rendered skill starts with the full-lead preamble (merge only on explicit
  user approval); with `lead: claude` it keeps the ac06 fallback preamble; edited copies are preserved.
- AC-02: `board.py lead` with no stored lead prints `config.lead`; `board.py status` on a fixture board
  prints ≤ 30 lines with lead, open WPs (name, step, engine/tier) and the open decision.
- AC-03: the Codex manifest and marketplace JSON parse, every path they reference exists, and the Codex
  manifest version equals `.claude-plugin/plugin.json`'s version.
- AC-04: the SessionStart hook script exits 0 and does nothing in a directory without `.crew/config.json`,
  and syncs `.crew/bin` in a temp crew project (reuse `tools/sync_bin.py` tests' fixtures).
- AC-05: `python -m pytest -q tests`, `bash -n templates/bin/*.sh`, `claude plugin validate .`,
  `claude plugin test .` pass; shellcheck-clean shell.
- Report: changed files, commands with results, open questions.
