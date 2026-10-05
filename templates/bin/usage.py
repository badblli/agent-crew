#!/usr/bin/env python3
"""Print engine quota and usage as one JSON object for the crew panel.

codex: the newest rate-limit reading in ~/.codex/sessions/**/rollout-*.jsonl
       (primary = 5-hour window, secondary = weekly window).
agy:   no quota endpoint; tokens used today by runs whose model starts with "gemini",
       plus a "limited" flag when the latest such run failed on a quota error.

Usage: usage.py [--state <stateDir>]
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

QUOTA_WORDS = re.compile(r"quota|exhausted|rate.?limit|429|usage limit", re.I)


def _window(raw: dict | None) -> dict | None:
    if not raw or raw.get("used_percent") is None:
        return None
    resets = raw.get("resets_at")
    return {
        "percent": float(raw["used_percent"]),
        "window_minutes": raw.get("window_minutes"),
        "resets_at": datetime.fromtimestamp(resets).astimezone().isoformat() if resets else None,
    }


def codex(home: Path) -> dict:
    root = home / ".codex" / "sessions"
    if not root.is_dir():
        return {"available": False}
    files = sorted(root.glob("*/*/*/rollout-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files[:5]:
        primary = secondary = None
        plan = None
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"rate_limits"' not in line:
                continue
            try:
                found = _find(json.loads(line), "rate_limits")
            except json.JSONDecodeError:
                continue
            if not isinstance(found, dict):
                continue
            plan = found.get("plan_type") or plan
            primary = _window(found.get("primary")) or primary
            secondary = _window(found.get("secondary")) or secondary
        if primary or secondary:
            return {
                "available": True,
                "plan": plan,
                "five_hour": primary,
                "weekly": secondary,
                "updated_at": datetime.fromtimestamp(f.stat().st_mtime).astimezone().isoformat(),
            }
    return {"available": False}


def _find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find(v, key)
            if r is not None:
                return r
    return None


def agy(state: Path) -> dict:
    runs = state / "runs"
    today = time.strftime("%Y%m%d")
    tokens = runs_today = 0
    latest: tuple[float, Path] | None = None
    for run in runs.glob("*/*") if runs.is_dir() else []:
        model = (run / "model").read_text(encoding="utf-8").strip() if (run / "model").exists() else ""
        events = run / "events.jsonl"
        if not model.startswith("gemini") or not events.exists():
            continue
        mtime = events.stat().st_mtime
        if latest is None or mtime > latest[0]:
            latest = (mtime, run)
        if not run.name.startswith(today):
            continue
        runs_today += 1
        for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            u = (e.get("step_update") or {}).get("usage")
            if u:
                tokens += int(u.get("total_tokens") or 0) + int(u.get("cache_read_tokens") or 0)
    limited = False
    if latest:
        tail = (latest[1] / "events.jsonl").read_text(encoding="utf-8", errors="replace")[-4000:]
        limited = '"event":"result"' in tail and '"SUCCESS"' not in tail and bool(QUOTA_WORDS.search(tail))
    return {"available": True, "tokens_today": tokens, "runs_today": runs_today, "limited": limited}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=".lead")
    args = ap.parse_args()
    out = {"checked_at": datetime.now().astimezone().isoformat(), "codex": codex(Path.home()), "agy": agy(Path(args.state))}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
