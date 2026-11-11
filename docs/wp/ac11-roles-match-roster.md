# ac11-roles-match-roster — Rendered role files match the crew roster

- Summary: Every agent on the board has a role definition with its own name, so a new user is not left wondering why Builder, Connector and Scribe have no role file.
- Model: standard
- Engine: codex
- Depends on: none

## Why
In the 2026-11-11 fresh-install test, crew-init rendered `.claude/agents/crew-{analyst,developer,qa,
reviewer,ui}.md` (and the Codex `.toml` twins) from `templates/roles/`, while `team.json` lists
`builder, analyst, api, ui, qa, scribe`. The lead itself reported this as confusing: nothing says which
role file Builder, Connector or Scribe use, and `reviewer` has no agent.

## Tasks
1. Add an optional `role` field to each `team.json` agent (`developer` for builder and api, `analyst`,
   `ui`, `qa`, and a new `scribe` role), defaulting to the agent id when it matches a role file.
2. `tools/render_roles.py` renders one file per roster agent as `crew-<agent id>` from its role source
   (keep the hash-manifest edit protection; files from the old names are reported, never deleted).
   `reviewer` stays a lead helper and is documented as such.
3. `templates/roles/scribe.md` for docs/notes WPs (`Role: scribe` already exists in the WP template).
4. crew-init and crew-lead skills: one line on how roster agents map to role files.

## Files (you own only these)
`tools/render_roles.py`, `templates/roles/*`, `templates/plan/team.json`, `skills/crew-init/SKILL.md`
(roles step only), `skills/crew-lead/SKILL.md` (one line), `tests/test_render_roles.py`.

## Acceptance criteria
- AC-01: rendering the template roster produces one Claude and one Codex role file per roster agent,
  named by agent id; an existing project with the old file names keeps them and lists them as legacy.
- AC-02: an agent whose `role` names a missing role file fails with a clear message.
- AC-03: `python -m pytest -q tests`, `claude plugin validate .` pass.
- Report: changed files, commands with results, open questions.
