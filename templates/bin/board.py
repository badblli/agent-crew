"""Crew board and lead↔agent conversation log (agent-crew).

Paths come from .crew/config.json (planDir, stateDir); state is shown by the agent-crew plugin:
  <stateDir>/board.json        phase, focus and per-WP {agent, step, note}
  <stateDir>/chat/<wp>.jsonl   conversation: {ts, from, kind, text}; from = "claude" or an agent id

Usage:
  board.py phase "<phase>" "<focus>"
  board.py assign <wp> <agent-id>             lead assigns a WP (logs the assignment)
  board.py step <wp> <step> ["<note>"]        move a WP to a step; a note is logged as a lead message
  board.py say <wp> <from> "<text>"           log one message
  board.py agent <wp>                         print the assigned agent id
  board.py name <agent-id>                    print the agent\'s name in the active theme
  board.py paths                              print "<planDir> <stateDir>" (absolute)
  board.py model <wp>                         print "<model> <effort> <tier>" from the WP's "- Model:" line
  board.py ingest <wp> [run-dir]              read engine JSON events, log messages and session metadata
  board.py session <wp> "<open command>"      publish a worker's interactive session command
  board.py report <wp> <report.md>            log the agent's final report summary
  board.py decide "<question>" "<label>|<detail>" ...   ask the user (band above the prompt)
  board.py decide --clear                     remove the pending decision
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = {"planDir": ".crew/plan", "stateDir": ".crew/state",
          **json.loads((ROOT / ".crew/config.json").read_text(encoding="utf-8"))}
PLAN = ROOT / CONFIG["planDir"]
LEAD = ROOT / CONFIG["stateDir"]
BOARD = LEAD / "board.json"
TEAM = json.loads((PLAN / "team.json").read_text(encoding="utf-8"))
STEPS = [s["id"] for s in TEAM["steps"]]
AGENTS = {a["id"] for a in TEAM["agents"]}


def _load() -> dict:
    try:
        return json.loads(BOARD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"phase": "", "focus": "", "items": {}}


def _save(board: dict) -> None:
    LEAD.mkdir(exist_ok=True)
    tmp = BOARD.with_suffix(".tmp")
    tmp.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(BOARD)


def say(wp: str, sender: str, text: str, kind: str = "message") -> None:
    text = text.strip()
    if not text:
        return
    chat = LEAD / "chat"
    chat.mkdir(parents=True, exist_ok=True)
    entry = {"ts": int(time.time() * 1000), "from": sender, "kind": kind, "text": text}
    with (chat / f"{wp}.jsonl").open("a", encoding="utf-8") as out:
        out.write(json.dumps(entry, ensure_ascii=False) + "\n")


def display_name(agent_id: str) -> str:
    """The agent's name in the active theme (team.json "theme"), else its plain name, else the id."""
    theme = TEAM.get("themes", {}).get(TEAM.get("theme", ""), {})
    themed = theme.get("agents", {}).get(agent_id, {}).get("name")
    plain = next((a.get("name") for a in TEAM.get("agents", []) if a.get("id") == agent_id), None)
    return themed or plain or agent_id


def agent_of(wp: str) -> str:
    return _load()["items"].get(wp, {}).get("agent", "")


def step(wp: str, step_id: str, note: str = "") -> None:
    if step_id not in STEPS and step_id != "failed":
        raise SystemExit(f"unknown step {step_id}; one of {STEPS + ['failed']}")
    board = _load()
    item = board["items"].setdefault(wp, {})
    item["step"] = step_id
    if note:
        item["note"] = note
        say(wp, "claude", note, "note")
    _save(board)


def session(wp: str, command: str) -> None:
    board = _load()
    item = board["items"].setdefault(wp, {})
    if item.get("session") == command:
        return
    item["session"] = command
    item["note"] = "open: " + command
    _save(board)
    say(wp, "claude", "open: " + command, "note")


def ingest(wp: str, run: Path | None) -> None:
    sender = agent_of(wp) or "agent"
    quota_notified = bool(run and (run / "quota_notified").exists())
    for line in sys.stdin:
        try:
            event = json.loads(line)
        except ValueError:
            continue  # Hook stdout can contain non-JSON text.
        if not isinstance(event, dict):
            continue
        # Stable compact JSON also supports the existing shell failure/thread extractors.
        print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)
        kind = event.get("type")
        if run and event.get("session_id"):
            thread = str(event["session_id"])
            (run / "thread").write_text(thread + "\n", encoding="utf-8")
            session(wp, f"claude --resume {thread}")
        item = event.get("item") or {}
        if kind == "assistant":
            for content in (event.get("message") or {}).get("content", []):
                if content.get("type") == "text":
                    say(wp, sender, content.get("text", ""))
        elif kind == "result":
            success = event.get("subtype") == "success" and not event.get("is_error", False)
            text = event.get("result") or "\n".join(event.get("errors") or [])
            if run:
                (run / "report.md").write_text(text, encoding="utf-8")
                (run / "result_status").write_text("success" if success else "error", encoding="utf-8")
            if not success:
                say(wp, sender, text or str(event.get("subtype", "error")), "error")
        elif kind == "rate_limit_event":
            hint = event.get("rate_limit_info") or {}
            if run:
                (run / "rate_limit.json").write_text(json.dumps(hint), encoding="utf-8")
            usage = LEAD / "usage"
            usage.mkdir(parents=True, exist_ok=True)
            (usage / "claude-workers.json").write_text(
                json.dumps({"wp": wp, "updated_at": int(time.time()), "rate_limit_info": hint}),
                encoding="utf-8")
            utilization = hint.get("utilization")
            limited = (hint.get("status", "allowed") != "allowed"
                       or isinstance(utilization, (int, float)) and utilization >= 1)
            if limited and not quota_notified:
                say(wp, sender, "Claude quota: " + json.dumps(hint), "note")
                quota_notified = True
                if run:
                    (run / "quota_notified").write_text("notified\n", encoding="utf-8")
        elif kind == "item.completed" and item.get("type") == "agent_message":
            say(wp, sender, item.get("text", ""))
        elif kind == "turn.failed":
            say(wp, sender, "Hata: " + str((event.get("error") or {}).get("message", "")), "error")
        elif event.get("event") == "result":
            res = event.get("result") or {}
            if res.get("status") == "SUCCESS":
                say(wp, sender, res.get("response", ""))
            else:
                say(wp, sender, "Hata: " + str(res.get("status", "")), "error")


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd, args = argv[1], argv[2:]
    if cmd == "phase":
        board = _load()
        board["phase"], board["focus"] = args[0], args[1] if len(args) > 1 else ""
        _save(board)
    elif cmd == "assign":
        wp, agent = args
        if agent not in AGENTS:
            raise SystemExit(f"unknown agent {agent}; one of {sorted(AGENTS)}")
        board = _load()
        board["items"].setdefault(wp, {})["agent"] = agent
        _save(board)
        spec = (PLAN / "wp" / f"{wp}.md").read_text(encoding="utf-8")
        summary = next((ln.split(":", 1)[1].strip() for ln in spec.splitlines()
                        if ln.startswith(("- Summary:", "- Özet:"))), wp)
        say(wp, "claude", ("Görev: " if CONFIG.get("lang") == "tr" else "Task: ") + summary, "assign")
        step(wp, "assigned")
    elif cmd == "step":
        step(args[0], args[1], args[2] if len(args) > 2 else "")
    elif cmd == "paths":
        print(PLAN.as_posix(), LEAD.as_posix())
    elif cmd == "model":
        routing = json.loads((PLAN / "models.json").read_text(encoding="utf-8"))
        spec = (PLAN / "wp" / f"{args[0]}.md").read_text(encoding="utf-8")
        tier = next((ln.split(":", 1)[1].strip().split()[0].lower() for ln in spec.splitlines()
                     if ln.startswith("- Model:")), routing["default"])
        engine = next((ln.split(":", 1)[1].strip().split()[0].lower() for ln in spec.splitlines()
                       if ln.startswith("- Engine:")), None)
        
        # Explicit WP/env choices win; otherwise use the roster's enabled engine, then config.
        import os
        enabled = CONFIG.get("engines", ["codex"])
        roster_engine = next((a.get("engine") for a in TEAM["agents"] if a["id"] == agent_of(args[0])), None)
        default_engine = roster_engine if roster_engine in enabled else enabled[0]
        engine = (os.environ.get("CREW_ENGINE_FORCE", "").lower() or engine
                  or os.environ.get("CREW_ENGINE", "").lower() or default_engine)
            
        tiers_key = f"{engine}_tiers" if engine != "codex" else "tiers"
        if tiers_key not in routing or tier not in routing[tiers_key]:
            raise SystemExit(f"unknown engine/tier {engine}/{tier}; check models.json")

        print(routing[tiers_key][tier]["model"], routing[tiers_key][tier].get("effort", "medium"), tier, engine)
    elif cmd == "agent":
        print(agent_of(args[0]))
    elif cmd == "name":
        print(display_name(args[0]))
    elif cmd == "say":
        say(args[0], args[1], args[2])
    elif cmd == "session":
        session(args[0], args[1])
    elif cmd == "ingest":
        ingest(args[0], Path(args[1]) if len(args) > 1 else None)
    elif cmd == "decide":
        path = LEAD / "decision.json"
        if args == ["--clear"]:
            path.unlink(missing_ok=True)
            return
        options = []
        for raw in args[1:]:
            label, _, detail = raw.partition("|")
            options.append({"label": label.strip(), "detail": detail.strip()})
        decision = {"id": str(int(time.time() * 1000)), "question": args[0], "options": options, "status": "open"}
        LEAD.mkdir(exist_ok=True)
        path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    elif cmd == "report":
        wp, path = args
        text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
        summary = text.split("## Summary", 1)[-1].split("\n## ", 1)[0].strip() if "## Summary" in text else text[:600]
        say(wp, agent_of(wp) or "codex", "Rapor: " + summary, "report")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    main(sys.argv)
