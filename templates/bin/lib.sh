# Shared helpers for the team scripts (sourced, not executed).
# shellcheck shell=bash

root="$(git rev-parse --show-toplevel)"
board() { PYTHONUTF8=1 python -u "$root/.crew/bin/board.py" "$@"; }
read -r plan_dir state_dir < <(board paths)
plan_dir="${plan_dir%$'\r'}"; state_dir="${state_dir%$'\r'}"  # board.py prints CRLF on Windows

# The global npm `codex` may be too old for the account's models; prefer the desktop app's binary.
codex_bin="${CODEX_BIN:-}"
if [[ -z "$codex_bin" ]]; then
  if [[ -n "${LOCALAPPDATA:-}" ]]; then
    # shellcheck disable=SC2012  # newest install first; the paths have no odd characters
    codex_bin="$(ls -t "$LOCALAPPDATA"/OpenAI/Codex/bin/*/codex.exe 2>/dev/null | head -1 || true)"
  fi
  codex_bin="${codex_bin:-codex}"
fi

# run_codex <wp> <run-dir> <workdir> <codex exec args...>
# Streams events into <run-dir>/events.jsonl and the agent's messages into the WP conversation.
run_codex() {
  local wp="$1" run="$2" workdir="$3"
  shift 3
  local rc
  set +e
  (cd "$workdir" && "$codex_bin" exec "$@" </dev/null) 2>>"$run/stderr.log" \
    | board ingest "$wp" >>"$run/events.jsonl"
  rc=${PIPESTATUS[0]}
  set -e
  return "$rc"
}

# run_agy <wp> <run-dir> <workdir> <prompt>
# Streams NDJSON into <run-dir>/events.jsonl, writes the final result.response to report.md, conversation id to thread
run_agy() {
  local wp="$1" run="$2" workdir="$3" prompt="$4"
  local agy_bin="${AGY_BIN:-agy}"
  [[ -n "${AGY_BIN:-}" || -z "${LOCALAPPDATA:-}" ]] || agy_bin="$LOCALAPPDATA/agy/bin/agy.exe"
  local rc
  
  read -r model effort _ < "$run/model"
  
  set +e
  (cd "$workdir" && "$agy_bin" -p "$prompt" --output-format stream-json --sandbox --mode accept-edits --print-timeout "${AGY_TIMEOUT:-55m}" --model "$model" --effort "$effort" </dev/null) 2>>"$run/stderr.log" \
    | board ingest "$wp" >>"$run/events.jsonl"
  rc=${PIPESTATUS[0]}
  set -e
  
  # Extract thread ID and report from events.jsonl
  # Find the init event or result event for conversation_id
  grep '"conversation_id"' "$run/events.jsonl" | head -1 | grep -o '"conversation_id":"[^"]*"' | cut -d'"' -f4 > "$run/thread" || true
  
  # Extract final response from result event
  grep '"event":"result"' "$run/events.jsonl" | tail -1 | python -c '
import sys, json
try:
    res = json.loads(sys.stdin.read()).get("result", {})
    if "response" in res:
        print(res["response"])
except:
    pass
' > "$run/report.md" || true

  return "$rc"
}

# Resume the run's Codex thread with a message; retries transient provider errors.
# resume_codex <wp> <run-dir> <workdir> <message>
resume_codex() {
  local wp="$1" run="$2" workdir="$3" message="$4" thread
  thread="$(grep -o '"thread_id":"[^"]*"' "$run/events.jsonl" | head -1 | cut -d'"' -f4)"
  [[ -n "$thread" ]] || { echo "no thread id in $run/events.jsonl" >&2; return 1; }
  run_codex "$wp" "$run" "$workdir" resume "$thread" -c 'sandbox_mode="workspace-write"' --json \
    -o "$run/report.md" "$message"
}

# resume_agy <wp> <run-dir> <workdir> <message>
resume_agy() {
  local wp="$1" run="$2" workdir="$3" message="$4" thread
  thread="$(cat "$run/thread" 2>/dev/null || true)"
  [[ -n "$thread" ]] || { echo "no thread id in $run/thread" >&2; return 1; }
  
  local agy_bin="${AGY_BIN:-agy}"
  [[ -n "${AGY_BIN:-}" || -z "${LOCALAPPDATA:-}" ]] || agy_bin="$LOCALAPPDATA/agy/bin/agy.exe"
  local rc
  
  read -r model effort _ < "$run/model"
  
  set +e
  (cd "$workdir" && "$agy_bin" -p "$message" --conversation "$thread" --output-format stream-json --sandbox --mode accept-edits --print-timeout "${AGY_TIMEOUT:-55m}" --model "$model" --effort "$effort" </dev/null) 2>>"$run/stderr.log" \
    | board ingest "$wp" >>"$run/events.jsonl"
  rc=${PIPESTATUS[0]}
  set -e
  
  grep '"event":"result"' "$run/events.jsonl" | tail -1 | python -c '
import sys, json
try:
    res = json.loads(sys.stdin.read()).get("result", {})
    if "response" in res:
        print(res["response"])
except:
    pass
' > "$run/report.md" || true

  return "$rc"
}

# run_claude <wp> <run-dir> <workdir> <prompt> [session-id]
# A headless worker is a separately named session; --bg is launch-only, without -p.
run_claude() {
  local wp="$1" run="$2" workdir="$3" prompt="$4" thread="${5:-}"
  local model effort rc ingest_rc name
  local -a args
  read -r model effort _ < "$run/model"
  name="$(board name "$(board agent "$wp" | tr -d '\r')" | tr -d '\r') · $wp"
  printf '%s\n' "$name" >"$run/session_name"
  args=(--name "$name" --model "$model" --permission-mode "${CREW_CLAUDE_PERMISSION_MODE:-auto}")
  [[ -z "$effort" ]] || args+=(--effort "$effort")
  [[ -z "$thread" ]] || args=(--resume "$thread" "${args[@]}")
  if [[ "${CREW_CLAUDE_BG:-0}" == "1" && -z "$thread" ]]; then
    (cd "$workdir" && "${CLAUDE_BIN:-claude}" --bg "${args[@]}" "$prompt" </dev/null) \
      >>"$run/background.log" 2>>"$run/stderr.log" || return $?
    echo background >"$run/mode"
    board session "$wp" "claude attach \"$name\""
    return 0
  fi
  echo stream >"$run/mode"
  rm -f "$run/result_status"
  set +e
  (cd "$workdir" && "${CLAUDE_BIN:-claude}" -p "${args[@]}" --output-format stream-json --verbose "$prompt" </dev/null) \
    2>>"$run/stderr.log" | board ingest "$wp" "$run" >>"$run/events.jsonl"
  local -a pipeline=("${PIPESTATUS[@]}")
  rc=${pipeline[0]}; ingest_rc=${pipeline[1]}
  set -e
  [[ $rc -eq 0 ]] || return "$rc"
  [[ $ingest_rc -eq 0 ]] || return "$ingest_rc"
  # A CLI can exit zero while reporting an error result. Missing results are failures too.
  [[ "$(cat "$run/result_status" 2>/dev/null)" == success ]]
}

resume_claude() {
  local thread
  thread="$(cat "$2/thread" 2>/dev/null || true)"
  [[ -n "$thread" ]] || { echo "no session id in $2/thread" >&2; return 1; }
  run_claude "$1" "$2" "$3" "$4" "$thread"
}

# Dispatch both initial runs and feedback through the same engine/model routing.
run_worker() {
  local engine="$1" wp="$2" run="$3" workdir="$4" prompt="$5" model effort
  printf '%s\n' "$engine" >"$run/engine"
  case "$engine" in
    claude) run_claude "$wp" "$run" "$workdir" "$prompt" ;;
    agy) run_agy "$wp" "$run" "$workdir" "$prompt" ;;
    codex)
      read -r model effort _ < "$run/model"
      run_codex "$wp" "$run" "$workdir" -s workspace-write -m "$model" \
        -c "model_reasoning_effort=\"$effort\"" --json -o "$run/report.md" "$prompt" ;;
    *) echo "unknown engine: $engine" >&2; return 1 ;;
  esac
}

resume_worker() {
  local engine="$1"
  shift
  case "$engine" in
    claude) resume_claude "$@" ;;
    agy) resume_agy "$@" ;;
    codex) resume_codex "$@" ;;
    *) echo "unknown engine: $engine" >&2; return 1 ;;
  esac
}

is_transient_failure() {
  { last_failure "$1" "${2:-codex}" || true; } \
    | grep -qiE 'capacity|disconnect|timed out|overloaded|rate limit'
}

# last_failure <run-dir> <engine>: the engine's latest failure event (Codex turn.failed, or an agy
# result that did not succeed). Engine-specific, so a run that failed over does not re-read the
# previous engine's failure.
last_failure() {
  if [[ "$2" == "agy" ]]; then
    grep '"event":"result"' "$1/events.jsonl" | tail -1 | grep -v '"status":"SUCCESS"'
  elif [[ "$2" == "claude" ]]; then
    grep '"type":"result"' "$1/events.jsonl" | tail -1 \
      | grep -E '"subtype":"error[^\"]*"|"is_error":true'
  else
    grep '"type":"turn.failed"' "$1/events.jsonl" | tail -1
  fi
}

# is_quota_failure <run-dir> <engine>: the engine hit its usage limit; retrying before the reset
# time cannot help, so the run is paused (or fails over) instead.
is_quota_failure() {
  if [[ "$2" == "agy" || "$2" == "claude" ]]; then
    last_failure "$1" "$2" | grep -qEi 'usage limit|try again at|quota|exhausted|(^|[^[:alnum:]])429([^[:alnum:]]|$)'
  else
    last_failure "$1" "$2" | grep -qEi 'usage limit|try again at'
  fi
}

# finish_run <wp> <run-dir> <status>
finish_run() {
  local wp="$1" run="$2" status="$3"
  if [[ $status -eq 0 && "$(cat "$run/mode" 2>/dev/null)" == background ]]; then
    # --bg returns when the worker launches, not when the WP finishes. The lead records stop
    # with `board step` after observing it in `claude agents` / `claude attach`.
    echo background >"$run/status"
    board step "$wp" working
  elif [[ $status -eq 0 ]]; then
    echo "done" >"$run/status"
    board report "$wp" "$run/report.md"
    board step "$wp" reported
  else
    echo "failed exit=$status" >"$run/status"
    board step "$wp" failed
  fi
}
