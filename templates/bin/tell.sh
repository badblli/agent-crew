#!/usr/bin/env bash
# Lead → agent: send review feedback or a question to the agent of a WP and let it continue.
#
#   .crew/bin/tell.sh <wp-id> "<message>"
#
# Resumes the agent's session from the latest run (same worktree), logs both
# sides in <stateDir>/chat/<wp-id>.jsonl and moves the WP to "working", then "reported".
set -euo pipefail
# Bash reads a script while running it; run from a private copy so the lead can edit the team
# scripts while agents are working.
if [[ -z "${TEAM_SCRIPT_DIR:-}" ]]; then
  TEAM_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  export TEAM_SCRIPT_DIR
  copy="$(mktemp)"
  cp "$0" "$copy"
  exec bash "$copy" "$@"
fi
# shellcheck source=lib.sh
source "$TEAM_SCRIPT_DIR/lib.sh"

wp="${1:?usage: tell.sh <wp-id> \"<message>\"}"
message="${2:?message required}"
# shellcheck disable=SC2012  # run dirs are timestamps; ls sorts them oldest first
run="$(ls -d "$state_dir/runs/$wp"/2*/ 2>/dev/null | tail -1 || true)"
run="${run%/}"
[[ -n "$run" ]] || { echo "no run for $wp; start it with run-wp.sh" >&2; exit 1; }

# One writer per agent thread: a message sent while the agent still runs is rejected by the engine and
# would mark the run failed. Wait until the current turn ends (status is not "running").
if [[ "$(cat "$run/status" 2>/dev/null)" == running* ]]; then
  echo "$wp is still running; send the message after it finishes." >&2
  exit 2
fi
if [[ "$(cat "$run/status" 2>/dev/null)" == background ]]; then
  echo "$wp is a background session; use claude attach \"$(cat "$run/session_name")\" for feedback." >&2
  exit 2
fi
workdir="$(cat "$run/workdir")"

board say "$wp" claude "$message"
board step "$wp" working
echo running >"$run/status"

status=0
read -r _ _ _ engine < <(board model "$wp" | tr -d '\r')
[[ ! -f "$run/engine" ]] || engine="$(tr -d '\r\n' < "$run/engine")"
resume_worker "$engine" "$wp" "$run" "$workdir" "Message from the tech lead (Claude): $message

Act on it inside this work package, do not commit, then finish with the report format from AGENTS.md." \
  || status=$?
if [[ $status -ne 0 ]] && is_transient_failure "$run" "$engine"; then
  sleep 60
  status=0
  resume_worker "$engine" "$wp" "$run" "$workdir" "Continue acting on the lead's last message; check git status first." || status=$?
fi
finish_run "$wp" "$run" "$status"
exit $status
