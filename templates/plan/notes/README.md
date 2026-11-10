# Project notes

Keep research, meeting notes and ideas here — never secrets or private customer data.
The lead writes these notes and links relevant ones from the work package. Workers never
write here. Move accepted decisions into the project's docs/adr/ decision records.

Open the plan folder as an Obsidian vault, not the repository root, so code is not indexed.
Markdown links also work outside Obsidian. Settings in .obsidian/app.json use an empty
ignore-filter list; state lives outside this vault. Per-device workspace*.json files are ignored by Git. No account, API or sync service is needed.
Use index.md to navigate handoff, active work and history. Run `board.py views` to regenerate
local plan/history views after cloning; use `board.py doctor` to check vault health.
