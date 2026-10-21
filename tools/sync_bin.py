#!/usr/bin/env python3
"""Bring a project's .crew/bin up to this plugin's templates/bin.

Usage:
  python <plugin>/tools/sync_bin.py [--project DIR] [--auto] [--json]
  python <plugin>/tools/sync_bin.py --record      # in the plugin repo, after changing templates/bin

A project file is replaced only when it is a released template version (its hash is in
templates/bin-history.json); a file changed in the project is kept and reported. Missing files
are added. Nothing is written while an agent run is active. --auto (the session-start hook)
also honours `"autoUpdate": false` in .crew/config.json. Stdlib only.
"""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

PLUGIN = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN / "templates" / "bin"
HISTORY = PLUGIN / "templates" / "bin-history.json"
ACTIVE_RUN_SECONDS = 2 * 60 * 60  # a "running" status older than this is a run that died


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def templates() -> dict:
    return {p.name: p for p in sorted(TEMPLATES.iterdir()) if p.is_file() and p.name != "__pycache__"}


def load_history() -> dict:
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def plugin_version() -> str:
    try:
        return json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return "?"


def active_runs(state_dir: pathlib.Path) -> list:
    busy = []
    now = time.time()
    for status in state_dir.glob("runs/*/*/status"):
        try:
            text = status.read_text(encoding="utf-8").strip()
            age = now - max(p.stat().st_mtime for p in status.parent.iterdir())
        except OSError:
            continue
        if (text == "running" or text.startswith("retry")) and age < ACTIVE_RUN_SECONDS:
            busy.append(status.parent.parent.name)
    return sorted(set(busy))


def sync(project: pathlib.Path, auto: bool) -> dict:
    out = {"version": plugin_version(), "added": [], "updated": [], "kept": [], "busy": []}
    config_path = project / ".crew" / "config.json"
    if not config_path.is_file():
        return {**out, "status": "no-crew"}
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if auto and config.get("autoUpdate") is False:
        return {**out, "status": "disabled"}
    out["busy"] = active_runs(project / config.get("stateDir", ".crew/state"))
    if out["busy"]:
        return {**out, "status": "busy"}

    history = load_history()
    bin_dir = project / ".crew" / "bin"
    for name, src in templates().items():
        data = src.read_bytes().replace(b"\r\n", b"\n")
        dest = bin_dir / name
        if not dest.exists():
            out["added"].append(name)
        else:
            current = digest(dest.read_bytes())
            if current == digest(data):
                continue
            if current not in history.get(name, []):
                out["kept"].append(name)
                continue
            out["updated"].append(name)
        bin_dir.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)  # LF, as crew-init copies them; an existing file keeps its mode
        if name.endswith(".sh") and os.name != "nt":
            dest.chmod(dest.stat().st_mode | 0o111)
    return {**out, "status": "ok"}


def record() -> dict:
    """Add every committed and current version of each template to bin-history.json."""
    history = {k: set(v) for k, v in load_history().items()}
    for name, src in templates().items():
        seen = history.setdefault(name, set())
        seen.add(digest(src.read_bytes()))
        revs = subprocess.run(["git", "-C", str(PLUGIN), "log", "--all", "--format=%H", "--",
                               f"templates/bin/{name}"], capture_output=True, text=True).stdout.split()
        for rev in revs:
            blob = subprocess.run(["git", "-C", str(PLUGIN), "show", f"{rev}:templates/bin/{name}"],
                                  capture_output=True).stdout
            if blob:
                seen.add(digest(blob))
    body = {k: sorted(v) for k, v in sorted(history.items())}
    HISTORY.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8", newline="\n")
    return {"status": "recorded", "files": len(body), "hashes": sum(len(v) for v in body.values())}


def describe(r: dict) -> str:
    if r["status"] == "no-crew":
        return "No .crew/config.json here; nothing to update."
    if r["status"] == "disabled":
        return "autoUpdate is false in .crew/config.json; run without --auto to update."
    if r["status"] == "busy":
        return f"Agents are running ({', '.join(r['busy'])}); try again when they finish."
    lines = []
    if r["added"] or r["updated"]:
        lines.append(f"Updated .crew/bin to agent-crew {r['version']}: "
                     + ", ".join(r["updated"] + [f"{n} (new)" for n in r["added"]]) + ". Commit .crew/bin.")
    if r["kept"]:
        lines.append("Changed in this project, left as is: " + ", ".join(r["kept"])
                     + f". Compare with {TEMPLATES}.")
    return "\n".join(lines) or f".crew/bin is up to date (agent-crew {r['version']})."


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", default=".", help="project root (default: the current directory)")
    ap.add_argument("--auto", action="store_true", help="called from the session-start hook")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--record", action="store_true", help="update templates/bin-history.json (plugin repo)")
    args = ap.parse_args(argv)
    result = record() if args.record else sync(pathlib.Path(args.project).resolve(), args.auto)
    print(json.dumps(result) if args.json or args.record else describe(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
