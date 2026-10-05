#!/usr/bin/env python3
"""Route a work package with Jev (TypeSafe System One): engine, tier, escalation, risk.

Usage: python .crew/bin/jev_route.py <wp-spec.md> [--json]

One request, four independent questions over the same state. Stdlib only.
The API key comes from TYPESAFE_API_KEY or the project root .env and is never printed.
On any failure it prints a fallback notice and exits 0 so the lead can decide manually.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
RISK_LEVELS = ["none", "low", "medium", "high"]
# Section heading prefixes (English and Turkish) mapped to state fields.
SECTIONS = {"goal": ("goal", "hedef"), "tasks": ("tasks", "görevler"),
            "acceptance": ("acceptance", "kabul")}

QUESTIONS = {
    "engine": {
        "type": "choice",
        "instructions": "Which agent engine should implement this work package?",
        "criteria": {
            "codex": "Repo coding: implementing code changes, writing and running tests in the repository.",
            "agy": "Gemini via the Antigravity CLI: long-context reading, cross-review of large diffs, documentation.",
            "claude-subagent": "Notion or document writing and small scripted tasks that need no repo test cycle.",
        },
    },
    "tier": {
        "type": "choice",
        "instructions": "Which model tier does this work package need?",
        "criteria": {
            "light": "Mechanical edits, renames, docs.",
            "standard": "Typical implementation.",
            "deep": "Correctness-critical parsing, data handling or multi-file changes.",
            "peak": "Architecture work, or a task that already failed twice.",
        },
    },
    "needs_user_decision": {
        "type": "noul",
        "instructions": "Does this work package contain a decision that must go to the product owner "
                        "(privacy, sending data to external services, destructive git history changes, "
                        "or product direction)?",
        "criteria": {
            "true": "Needs a privacy, external-data, destructive-history or product-direction decision.",
            "false": "Purely technical; the lead can decide alone.",
        },
    },
    "risk": {
        "type": "score",
        "instructions": "How risky is this change for existing behavior?",
        "criteria": [
            "None: new isolated file or docs only; nothing existing is touched.",
            "Low: small additive change; existing behavior is untouched and easy to revert.",
            "Medium: modifies existing logic or shared code; regressions are possible but covered by tests.",
            "High: changes core data, public interfaces or many modules; regressions would be hard to detect.",
        ],
    },
}


def parse_wp(text):
    """Extract title, summary and Goal/Tasks/Acceptance sections from WP markdown."""
    state = {"title": "", "summary": "", "goal": "", "tasks": "", "acceptance": ""}
    m = re.search(r"^#\s+(.+)$", text, re.M)
    state["title"] = m.group(1).strip() if m else ""
    # Prefer the English summary line, fall back to the Turkish "Özet" line.
    for label in ("Summary", "Özet"):
        m = re.search(rf"^\s*[-*]?\s*{label}\s*:\s*(.+)$", text, re.M | re.I)
        if m:
            state["summary"] = m.group(1).strip()
            break
    # Split on level 2+ headings; keep the bodies of the sections we know.
    parts = re.split(r"^#{2,}\s+(.+)$", text, flags=re.M)
    for head, body in zip(parts[1::2], parts[2::2]):
        for key, names in SECTIONS.items():
            if head.strip().lower().startswith(names) and not state[key]:
                state[key] = body.strip()
    return state


def find_root():
    """Project root = git top-level of the cwd, else the cwd itself."""
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, check=True).stdout.strip()
        return out or os.getcwd()
    except (OSError, subprocess.CalledProcessError):
        return os.getcwd()


def load_key(root):
    """TYPESAFE_API_KEY from the environment, else from <root>/.env (KEY=VALUE lines)."""
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    try:
        with open(os.path.join(root, ".env"), encoding="utf-8") as fh:
            for line in fh:
                k, sep, v = line.strip().partition("=")
                if sep and k.strip().removeprefix("export ").strip() == "TYPESAFE_API_KEY":
                    return v.strip().strip("'\"")
    except OSError:
        pass
    return ""


def post(payload, key):
    """POST to the API; retry once on 429/5xx (docs advise backoff). Returns parsed JSON."""
    body = json.dumps(payload).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
               "User-Agent": "agent-crew-jev-route/1"}
    for attempt in (0, 1):
        req = urllib.request.Request(URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if attempt == 0 and err.code in (429, 500, 502, 503, 529):
                time.sleep(1.5)
                continue
            raise


def summarize(answers):
    """Flatten the raw API answers into one record per question."""
    out = {}
    for name, ans in answers.items():
        rec = {k: ans[k] for k in ("choice", "noul", "score", "probabilities", "confidence") if k in ans}
        if name == "risk" and "score" in ans:
            idx = min(len(RISK_LEVELS) - 1, max(0, round(ans["score"])))
            rec["level"] = RISK_LEVELS[idx]
        out[name] = rec
    return out


def render(res):
    """Human-readable lines for the lead."""
    a = res["answers"]
    lines = []
    for name in ("engine", "tier"):
        r = a[name]
        p = r["probabilities"][r["choice"]]
        lines.append(f"{name}: {r['choice']} (p={p:.2f}, confidence={r.get('confidence', 0):.2f})")
    lines.append(f"needs_user_decision: {a['needs_user_decision']['noul']:.2f} probability of yes")
    r = a["risk"]
    lines.append(f"risk: {r['level']} (score={r['score']:.2f}/3, confidence={r.get('confidence', 0):.2f})")
    lines.append(f"latency: {res['latency_ms']} ms")
    return "\n".join(lines)


def route(state, key):
    """Ask Jev all four questions in one request; return the result record."""
    payload = {"state": state, "model": MODEL, "questions": QUESTIONS}
    start = time.perf_counter()
    raw = post(payload, key)
    latency = round((time.perf_counter() - start) * 1000)
    return {"fallback": False, "model": raw.get("model", MODEL), "latency_ms": latency,
            "answers": summarize(raw["answers"])}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("wp", help="work package markdown file")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    def fallback(reason):
        if args.json:
            print(json.dumps({"fallback": True, "reason": reason}))
        else:
            print(f"Jev routing unavailable ({reason}); decide engine and tier manually.")
        return 0

    with open(args.wp, encoding="utf-8") as fh:
        state = parse_wp(fh.read())
    key = load_key(find_root())
    if not key:
        return fallback("TYPESAFE_API_KEY not set in the environment or project .env")
    try:
        res = route(state, key)
    except urllib.error.HTTPError as err:
        return fallback(f"API error HTTP {err.code}")
    except (urllib.error.URLError, OSError, ValueError, KeyError) as err:
        return fallback(f"{type(err).__name__} while calling the API")
    print(json.dumps(res, indent=2) if args.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
