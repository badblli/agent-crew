#!/usr/bin/env python3
"""Render shared roles into native Claude and Codex agent files (stdlib only).

Usage: python <plugin>/tools/render_roles.py --project . --engines claude,codex
Local edits are preserved and named. The last rendered hashes live in
.crew/roles-rendered.json; an existing file without a matching hash is also preserved.
"""
import argparse
import hashlib
import json
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
ROLES = PLUGIN / "templates" / "roles"
ENGINES = {"claude", "codex"}
FALLBACK_PREAMBLE = """# Fallback lead (Codex)

You are the fallback lead. Read `.crew/config.json` and `<planDir>/handoff.md` first.
Act as lead only if `python .crew/bin/board.py lead` prints `codex` or the user explicitly asks you
to take over; otherwise do the user's request as a normal Codex session and leave the crew alone.
The rules in this preamble take precedence over the Claude-only instructions below.
- Allowed: write and assign WPs; run `run-wp.sh` with Codex/agy workers; use `tell.sh`;
  review diffs and re-run tests; commit in the agent worktree, push the branch, open a PR,
  and record `board.py step <wp> pr_open`. Claude workers share the exhausted quota.
- Not allowed: merging PRs, pushing to the default branch, history rewrites, sending data
  to new external services, changing `.crew/config.json` or permissions. Leave these to
  the user or the Claude lead; stop shipping at `pr_open` even when CI is green.
- Ask the user in your own chat (Codex has no decision band); record the answer in the WP.
- Before stopping: run `board.py handoff` (or `board.py handoff --to claude` when returning
  control), fill `## Next`, and list every PR you opened for the Claude lead to review.
  Keep the handoff card at most 40 lines. Board panes appear again when Claude returns.

"""


FULL_LEAD_PREAMBLE = """# Crew lead (Codex)

You are the configured tech lead. Read `.crew/config.json` and the configured `<planDir>/handoff.md`
if it exists. Check `python .crew/bin/board.py lead` for a stored handoff before acting as lead.
Follow the shared lead loop below. Ask questions in chat as numbered options and record decisions
in the WP. Use `python .crew/bin/board.py status` to show the board in chat.

Use Codex workers or explicitly configured agy workers. Use Claude workers only if
`claude` is in `config.engines`. Never push directly to the default branch. After CI is
green, merge only after the user explicitly says "merge" in chat for that specific PR.

"""


def render_lead(lead: str) -> bytes:
    text = (PLUGIN / "skills/crew-lead/SKILL.md").read_text(encoding="utf-8")
    header, body = text[4:].split("\n---\n", 1)
    # Keep the source frontmatter, which provides Codex's required name and description.
    preamble = FULL_LEAD_PREAMBLE if lead == "codex" else FALLBACK_PREAMBLE
    return ("---\n" + header + "\n---\n\n" + preamble + body.lstrip()).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def read_role(path: Path) -> tuple[dict, str]:
    """Read the deliberately small frontmatter schema without a YAML dependency."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing frontmatter")
    header, body = text[4:].split("\n---\n", 1)
    meta = dict(line.split(":", 1) for line in header.splitlines())
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    for key in ("name", "description", "tier", "readonly"):
        if not meta.get(key):
            raise ValueError(f"{path}: missing {key}")
    if meta["readonly"] not in ("true", "false"):
        raise ValueError(f"{path}: readonly must be true or false")
    if meta["name"] != path.stem or len(body.strip().splitlines()) > 50:
        raise ValueError(f"{path}: invalid name or body longer than 50 lines")
    return meta, body.strip() + "\n"


def render(meta: dict, body: str, engine: str, routing: dict) -> bytes:
    name = "crew-" + meta["name"]
    tier = routing["claude_tiers" if engine == "claude" else "tiers"][meta["tier"]]
    # JSON strings are valid YAML and TOML basic strings, including escaped multiline bodies.
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    if engine == "claude":
        lines = ["---", f"name: {quote(name)}", f"description: {quote(meta['description'])}",
                 f"model: {quote(tier['model'])}"]
        if tier.get("effort"):
            lines.append(f"effort: {quote(tier['effort'])}")
        if meta["readonly"] == "true":
            lines.append("tools: Read, Glob, Grep")
        lines += ["disallowedTools: Agent", "---", body]
        return ("\n".join(lines)).encode("utf-8")
    fields = {"name": name, "description": meta["description"], "developer_instructions": body,
              "model": tier["model"], "model_reasoning_effort": tier["effort"]}
    return ("\n".join(f"{k} = {quote(v)}" for k, v in fields.items()) + "\n").encode("utf-8")


def sync(project: Path, engines: list[str] | None = None) -> dict:
    config = json.loads((project / ".crew/config.json").read_text(encoding="utf-8"))
    engines = engines if engines is not None else config.get("engines", ["claude", "codex"])
    if not engines or any(engine not in ENGINES for engine in engines):
        raise ValueError("engines must contain claude, codex, or both")
    routing = json.loads((project / config.get("planDir", ".crew/plan") / "models.json")
                         .read_text(encoding="utf-8"))
    manifest = project / ".crew/roles-rendered.json"
    hashes = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    # Prepare everything before writing so invalid role/model data cannot leave a partial render.
    prepared = []
    for src in sorted(ROLES.glob("*.md")):
        meta, body = read_role(src)
        for engine in dict.fromkeys(engines):
            suffix = "md" if engine == "claude" else "toml"
            rel = f".{engine}/agents/crew-{meta['name']}.{suffix}"
            prepared.append((rel, render(meta, body, engine, routing)))
    if "codex" in config.get("engines", []):
        prepared.append((".agents/skills/crew-lead/SKILL.md", render_lead(config.get("lead", "claude"))))
    result = {"added": [], "updated": [], "kept": []}
    for rel, data in prepared:
        dest = project / rel
        if dest.exists():
            current = digest(dest.read_bytes())
            if current == digest(data):
                hashes[rel] = current
                continue
            if current != hashes.get(rel):
                result["kept"].append(rel)
                continue
            result["updated"].append(rel)
        else:
            result["added"].append(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        hashes[rel] = digest(data)
    manifest.write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--engines", help="claude, codex, or claude,codex; defaults to config engines")
    args = parser.parse_args()
    try:
        result = sync(args.project.resolve(), args.engines.split(",") if args.engines else None)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"render_roles: {exc}\n")
    for action, paths in result.items():
        if paths:
            label = "Changed in this project, left as is" if action == "kept" else action.capitalize()
            print(f"{label}: {', '.join(paths)}")
    if not any(result.values()):
        print("Roles are up to date.")


if __name__ == "__main__":
    main()
