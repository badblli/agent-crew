# ac05-obsidian-vault — the crew plan folder as an Obsidian vault

- Summary: crew-init can turn the plan folder into an Obsidian vault, so the user reads and edits WPs, handoff, history and notes in Obsidian instead of Notion.
- Model: standard
- Engine: codex
- Depends on: ac04 (handoff.md, generated plan.md/history.md, wp/done/)

## Why
Everything the crew plans is already plain Markdown. An Obsidian vault over it needs no API, no account and
no sync service, and the files stay in Git next to the code. Avenox's open "Avenox Beyin" setup
(github.com/avenoxai/avenoxbeyin) shows the pattern: a Markdown vault that agents write directly, a per-session
handoff card, and a health-check command. We take the pattern, not the package.

## Facts
- Any folder opens as an Obsidian vault; settings live in `<vault>/.obsidian/` (created by the app if missing).
  `workspace.json` / `workspace-mobile.json` hold per-device UI state and should not be committed.
- Obsidian resolves `[[wikilinks]]` and standard Markdown links; Bases (`.base` YAML files) can show
  table views from note properties — out of scope for this WP (status lives on the board, not in WP files).

## Tasks
1. `crew-init` asks (in the same AskUserQuestion) "Notes: none / Obsidian vault / Notion". With Obsidian:
   - vault root = `<planDir>` (default `.crew/plan`), so code folders are not indexed;
   - write `<planDir>/.obsidian/app.json` with `"userIgnoreFilters": ["state/"]` and nothing else;
   - create `<planDir>/notes/README.md` (what belongs here: research, meeting notes, ideas — never secrets);
   - add `<planDir>/.obsidian/workspace*.json` to `.gitignore`;
   - write `<planDir>/index.md`: links to `handoff.md`, `plan.md`, `history.md`, `wp/`, `notes/`, and to
     `../../rule.md`, `../../feature.md`, `../../docs/adr/` (relative links so they work in Git too);
   - set `.crew/config.json` `"notes": "obsidian"`; print the `obsidian://open?path=<absolute planDir>` link.
2. `board.py views` (from ac04) writes WP ids in `plan.md` / `history.md` as relative Markdown links to the WP
   file (`wp/<id>.md` or its `wp/done/...` path) so they are clickable in Obsidian and on GitHub.
3. `board.py doctor`: checks config, plan dir, WP headers parse, broken links in `index.md`/`plan.md`,
   stray files in `wp/` that the board does not know, `.obsidian/workspace*.json` tracked by Git. Prints
   findings; exit 1 on errors.
4. `skills/crew-lead/SKILL.md`: replace the Notion-specific wording with "the project's notes
   (`config.notes`)": with `obsidian`, the lead writes research and decisions-in-progress under `notes/`
   and links them from the WP; workers never write there.

## Files (you own only these)
`skills/crew-init/SKILL.md`, `skills/crew-lead/SKILL.md`, `templates/bin/board.py`,
`templates/config.json`, new `templates/plan/index.md`, `templates/plan/notes/README.md`,
`templates/plan/.obsidian/app.json`, `templates/bin-history.json` (via `--record`), new tests under `tests/`.

## Acceptance criteria
- AC-01: init on a temp project with notes=obsidian creates the files above; `.gitignore` gains the workspace
  rule; without obsidian none of them exist.
- AC-02: links in `plan.md`, `history.md` and `index.md` resolve to existing files (test walks them).
- AC-03: `board.py doctor` reports a missing WP file, a broken link and a tracked workspace file in a fixture.
- AC-04: `python -m pytest tests`, `bash -n templates/bin/*.sh` pass.
- Report: changed files, commands with results, open questions. Never use Git writes.
