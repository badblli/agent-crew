# ac09-preflight-doctor — One command tells a new user what is missing before crew-init

- Summary: A preflight check lists every missing or misconfigured prerequisite (Git, Bash, Python, gh, Claude/Codex CLIs and sign-in) with the exact fix for the user's OS, and crew-init runs it first.
- Model: standard
- Engine: codex
- Depends on: none

## Why
The README lists prerequisites in one sentence. A stranger finds out what is missing only when a
script fails half-way. The 2026-11-11 fresh-install test on Windows hit several things the README does
not mention:
- `python3` on Windows can be the Microsoft Store stub (`WindowsApps\python3.exe`), which opens the Store
  instead of running Python. The Codex hook uses `python` on Windows, but shell scripts and docs mix both.
- Two Codex CLIs can be installed (npm `codex` 0.162.1 on PATH, a newer one under `%LOCALAPPDATA%`).
  crew-init picked the newest; `run-wp.sh` runs whatever `codex` is first on PATH.
- `%LOCALAPPDATA%\OpenAI\Codex\bin\*\` can hold a folder with only `rg.exe`, so the glob must skip it.
- Bash on Windows means Git Bash; WSL bash is not tested.
- `gh` must be signed in for the setup PR; without a remote crew-init silently skips the PR.

## Tasks
1. `tools/doctor.py` (stdlib only, no network except the CLIs' own version/auth commands): checks
   `git --version`, `bash --version` (on Windows: Git Bash, not WSL), Python ≥ 3.10 and the
   `python`/`python3` stub case, `gh auth status`, `claude --version`, the Codex CLI the scripts will
   actually run (and any newer one it would ignore), `codex login status`, optional `agy`. Prints one
   line per check: ok / missing / warn, with a one-line fix for the detected OS.
2. Exit code 0 when the chosen lead and at least one worker engine work; 1 otherwise. `--json` for the
   skills.
3. `skills/crew-init/SKILL.md` step 1 runs `python <plugin root>/tools/doctor.py` and shows its output
   instead of probing by hand. `board.py doctor` (project health) stays as is and links to it.
4. `run-wp.sh` / `lib.sh` resolve the Codex binary the same way crew-init does (one function), and log
   the path and version in the run dir.
5. README "Install": a short prerequisites table (Windows / macOS / Linux) and "run the doctor first".

## Files (you own only these)
New `tools/doctor.py`, new `tests/test_doctor.py`, `skills/crew-init/SKILL.md` (step 1 only),
`templates/bin/lib.sh` (Codex binary resolution), `templates/bin-history.json` (via
`python tools/sync_bin.py --record`), `README.md`, `README.tr.md` (Install section only).

## Acceptance criteria
- AC-01: with stub PATHs (tests) the doctor reports missing gh, missing Codex, the Store `python3` stub
  and a second, newer Codex binary, each with a fix line; exit codes match task 2.
- AC-02: `run-wp.sh` and crew-init pick the same Codex binary in a fixture with two installs.
- AC-03: `python -m pytest -q tests`, `bash -n templates/bin/*.sh`, `claude plugin validate .` pass;
  shellcheck-clean shell.
- Report: changed files, commands with results, open questions.
