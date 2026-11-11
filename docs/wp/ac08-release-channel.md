# ac08-release-channel — Every shipped change reaches users, on both clients, on purpose

- Summary: Changes to shipped files always come with a version bump and a changelog line, so Claude Code users actually receive them, and Codex users (who update from `main` automatically) only ever get released work.
- Model: standard
- Engine: codex
- Depends on: none

## Why
The two clients update differently, and today neither matches how the repo ships:
- PR #15 changed `templates/bin/board.py` after v0.5.5 was released, without a version bump. Claude Code
  users who installed 0.5.5 before the merge never get the fix (Claude Code only updates on a version
  change), while users who installed after got it under the same version number.
- Codex users get every merge to `main` at their next session start, version or not. `main` is their
  release channel.

## Facts (checked 2026-11-11)
- Claude Code: an update happens only when the plugin `version` changes; "If you set `"version": "1.0.0"`
  and push new commits without changing it, users don't receive them."
  (https://code.claude.com/docs/en/plugins/host-marketplace, "Release a new version"). Third-party
  marketplaces have auto-update off by default (https://code.claude.com/docs/en/discover-plugins,
  "Keep plugins updated"); `marketplace.json` has no field to turn it on.
- Codex 0.162.1: at startup, Codex upgrades every configured Git marketplace in the background
  (`codex-rs/core-plugins/src/manager.rs`, `maybe_start_plugin_startup_tasks_for_config`) and
  force-reinstalls installed plugins from the new snapshot. Experiment with a local Git marketplace:
  1.0.0 → 1.1.0 by `codex plugin marketplace upgrade`; same version with changed skill text was also
  reinstalled; 1.1.0 → 1.2.0 happened just by starting `codex exec`. Users can pin with
  `codex plugin marketplace add badblli/agent-crew --ref v0.5.5` (or `owner/repo@ref`).
- `claude plugin tag` creates a `{name}--v{version}` tag after checking plugin.json and the marketplace
  entry agree.

## Tasks
1. **CI version gate.** A CI step fails a PR when it changes shipped paths (`skills/`, `templates/`,
   `hooks/`, `tools/`, `types/`, `.codex-plugin/`, `.claude-plugin/plugin.json`) and
   `.claude-plugin/plugin.json` `version` is not greater than on `main`. Docs-, tests- and CI-only PRs
   pass without a bump.
2. **CHANGELOG.md** (Keep a Changelog style, newest first) with entries back to 0.5.0, built from the
   GitHub release notes and `git log`. CI checks that the current version has a heading.
3. **Release 0.5.6** for #15 (board lock) once this lands — the lead asks the user before tagging or
   publishing the release.
4. **Release checklist** in `docs/RELEASING.md`: bump both manifests, changelog, `python
   tools/sync_bin.py --record`, merge, `gh release create vX.Y.Z`, check the update toast.
5. Decide (ask the user) whether the README tells Codex users to pin a tag; default: no pin, and `main`
   stays releasable because of task 1.

## Files (you own only these)
`.github/workflows/ci.yml`, new `tools/check_version_bump.py`, new `tests/test_version_bump.py`,
new `CHANGELOG.md`, new `docs/RELEASING.md`. The version bump itself is the lead's.

## Acceptance criteria
- AC-01: on a fixture diff touching `templates/bin/board.py` with an unchanged version, the check exits
  non-zero with a one-line reason; with a bumped version, or a docs-only diff, it exits 0.
- AC-02: CHANGELOG.md has a heading for the current version; CI fails when it is missing.
- AC-03: `python -m pytest -q tests`, `claude plugin validate .` pass; shellcheck-clean shell.
- Report: changed files, commands with results, open questions.
