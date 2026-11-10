"""Codex full-lead workflow and plugin package contracts."""

import json
import os
import subprocess

import pytest

from test_fallback_lead import SKILL, add_wp, board, cli  # noqa: F401 (shared fixture)
from test_render_roles import REPO, project as role_project, roles  # noqa: F401 (shared fixture)
from test_sync_bin import project as sync_project, sync_bin  # noqa: F401 (shared fixture)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_full_lead_rerender_preserves_local_edits(role_project):
    config = role_project / ".crew/config.json"
    dest = role_project / SKILL
    roles.sync(role_project)
    fallback = dest.read_text(encoding="utf-8")
    assert "# Fallback lead (Codex)" in fallback

    config.write_text('{"lead": "codex", "engines": ["codex"]}', encoding="utf-8")
    assert roles.sync(role_project)["updated"] == [SKILL]
    _, _, body = dest.read_text(encoding="utf-8").split("---", 2)
    preamble = body.lstrip().split("# Leading the crew", 1)[0]
    assert preamble.startswith("# Crew lead (Codex)")
    assert 'merge only after the user explicitly says "merge" in chat for that specific PR' in preamble
    assert "CI is\ngreen" in preamble

    dest.write_text("Local lead rules\n", encoding="utf-8")
    config.write_text('{"lead": "claude", "engines": ["codex"]}', encoding="utf-8")
    assert roles.sync(role_project)["kept"] == [SKILL]
    assert dest.read_text(encoding="utf-8") == "Local lead rules\n"


def test_lead_status_and_handoff(board):
    config = board.ROOT / ".crew/config.json"
    config.write_text(json.dumps({**board.CONFIG, "lead": "codex"}), encoding="utf-8")
    assert cli(board, "lead").stdout.strip() == "codex"
    assert not board.BOARD.exists()
    card = cli(board, "handoff").stdout
    assert "## Lead\ncodex" in card and "fallback lead" not in card

    board.main(["board.py", "phase", "Build", "Finish\nrelease"])
    add_wp(board, "first", engine="claude")
    add_wp(board, "second", step="reviewing", engine="agy")
    add_wp(board, "shipped", step="merged")
    board.main(["board.py", "decide", "Ready?\nChoose", "Yes|Proceed"])
    result = cli(board, "status")
    assert result.returncode == 0, result.stderr
    assert "Phase: Build | Focus: Finish release" in result.stdout
    assert "Lead: codex" in result.stdout
    assert "Open decision: Ready? Choose" in result.stdout
    assert "- first | Builder | working | claude/standard" in result.stdout
    assert "- second | Builder | reviewing | agy/standard" in result.stdout
    assert "shipped" not in result.stdout

    for index in range(30):
        add_wp(board, f"wp{index}")
    assert cli(board, "lead", "claude").returncode == 0
    result = cli(board, "status")
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) == 30
    assert "7 more open WPs" in result.stdout
    assert "Lead: claude" in result.stdout


@pytest.mark.parametrize("engines,expected", [
    (["codex", "claude"], "claude"),
    (["codex"], "codex"),
])
def test_full_lead_routes_claude_only_if_enabled(board, engines, expected):
    config = board.ROOT / ".crew/config.json"
    config.write_text(json.dumps({**board.CONFIG, "lead": "codex", "engines": engines}), encoding="utf-8")
    add_wp(board, "first", engine="claude")
    result = cli(board, "model", "first")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split()[-1] == expected


def test_manifests_match_and_resolve():
    claude = read_json(REPO / ".claude-plugin/plugin.json")
    codex = read_json(REPO / ".codex-plugin/plugin.json")
    marketplace = read_json(REPO / ".agents/plugins/marketplace.json")
    [entry] = marketplace["plugins"]
    assert codex["version"] == claude["version"]
    assert entry["name"] == codex["name"] == claude["name"]
    assert (REPO / codex["skills"] / "crew-init/SKILL.md").is_file()
    assert (REPO / codex["skills"] / "crew-lead/SKILL.md").is_file()
    assert (REPO / entry["source"]["path"] / ".codex-plugin/plugin.json").is_file()
    assert hook_command()["type"] == "command"


def hook_command():
    manifest = read_json(REPO / ".codex-plugin/plugin.json")
    hooks = read_json(REPO / manifest["hooks"])
    [group] = hooks["hooks"]["SessionStart"]
    [handler] = group["hooks"]
    return handler


def run_session_start(cwd):
    hook = hook_command()
    command = (["powershell.exe", "-NoProfile", "-Command", hook["commandWindows"]]
               if os.name == "nt" else ["sh", "-c", hook["command"]])
    return subprocess.run(command, cwd=cwd, env={**os.environ, "PLUGIN_ROOT": str(REPO)},
                          input='{"hook_event_name":"SessionStart"}', capture_output=True, text=True)


def test_session_start_is_silent_without_crew(tmp_path):
    result = run_session_start(tmp_path)
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
    assert not list(tmp_path.iterdir())


def test_session_start_syncs_crew_project(sync_project):
    config = sync_project / ".crew/config.json"
    config.write_text('{"lead": "codex", "engines": ["codex"]}', encoding="utf-8")
    plan = sync_project / ".crew/plan"
    plan.mkdir()
    (plan / "models.json").write_bytes((REPO / "templates/plan/models.json").read_bytes())
    result = run_session_start(sync_project)
    assert result.returncode == 0, result.stderr
    for name, template in sync_bin.templates().items():
        assert (sync_project / ".crew/bin" / name).read_bytes() == template.read_bytes().replace(b"\r\n", b"\n")
    assert "# Crew lead (Codex)" in (sync_project / SKILL).read_text(encoding="utf-8")
    assert run_session_start(sync_project).stdout == ""
