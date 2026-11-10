"""Codex fallback skills, board leadership and handoff contracts; no Git writes."""
import json
import subprocess
import sys
from datetime import datetime

import pytest

from test_board_lifecycle import add_wp, board  # noqa: F401 (shared fixture)
from test_render_roles import REPO, project, roles  # noqa: F401 (shared fixture)


SKILL = ".agents/skills/crew-lead/SKILL.md"


def cli(board, *args):
    return subprocess.run([sys.executable, str(board.ROOT / ".crew/bin/board.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


@pytest.mark.parametrize("engines", [["claude"], ["claude", "codex"], ["codex"]])
def test_fallback_skill_selected_by_config(project, engines):
    (project / ".crew/config.json").write_text(json.dumps({"engines": engines}), encoding="utf-8")
    result = roles.sync(project)
    path = project / SKILL
    assert path.exists() == ("codex" in engines)
    if not path.exists():
        # Explicit role selection cannot enable a fallback lead against project policy.
        roles.sync(project, ["codex"])
        assert not path.exists()
        return
    text = path.read_text(encoding="utf-8")
    header, body = text[4:].split("\n---\n", 1)
    assert "name: crew-lead" in header and "description:" in header
    assert body.lstrip().startswith("# Fallback lead (Codex)")
    assert body.endswith((REPO / "skills/crew-lead/SKILL.md").read_text(encoding="utf-8").split("\n---\n", 1)[1].lstrip())
    assert SKILL in result["added"]
    manifest = json.loads((project / ".crew/roles-rendered.json").read_text())
    assert manifest[SKILL] == roles.digest(path.read_bytes())
    assert not any(roles.sync(project).values())


@pytest.mark.parametrize("previous_render", [False, True])
def test_edited_fallback_skill_kept_and_named(project, previous_render):
    if previous_render:
        roles.sync(project)
    path = project / SKILL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Local lead rules\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(REPO / "tools/render_roles.py"),
                             "--project", str(project)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "left as is: " + SKILL in result.stdout
    assert path.read_text() == "Local lead rules\n"


def test_role_selection_does_not_disable_configured_fallback(project):
    result = roles.sync(project, ["claude"])
    assert SKILL in result["added"]
    assert (project / SKILL).is_file()


def test_untouched_fallback_skill_updates_with_source(project, tmp_path, monkeypatch):
    roles.sync(project)
    plugin = tmp_path / "plugin"
    source = plugin / "skills/crew-lead/SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text((REPO / "skills/crew-lead/SKILL.md").read_text(encoding="utf-8")
                      + "\nNew lead guidance.\n", encoding="utf-8")
    monkeypatch.setattr(roles, "PLUGIN", plugin)
    result = roles.sync(project)
    assert result["updated"] == [SKILL]
    assert (project / SKILL).read_text(encoding="utf-8").endswith("New lead guidance.\n")


def test_lead_cli_default_and_persistent_state(board):
    assert cli(board, "lead").stdout.strip() == "claude"
    assert not board.BOARD.exists()
    add_wp(board, "active")
    assert cli(board, "lead", "codex").stdout.strip() == "codex"
    state = board._load()
    assert state["lead"]["id"] == "codex"
    assert datetime.fromisoformat(state["lead"]["since"]).tzinfo is not None
    assert state["items"]["active"]["step"] == "working"
    assert cli(board, "lead").stdout.strip() == "codex"
    cli(board, "lead", "codex")
    assert board._load()["lead"] == state["lead"]  # Repeated syncs retain the start time.
    assert cli(board, "lead", "claude").stdout.strip() == "claude"
    assert board._load()["items"] == state["items"]


@pytest.mark.parametrize("tier", ["light", "standard", "deep", "peak"])
def test_claude_model_routes_to_codex_and_back(board, tier):
    add_wp(board, "active", engine="claude")
    board.spec_path("active").write_text(f"- Engine: claude\n- Model: {tier}\n", encoding="utf-8")
    models = json.loads((board.PLAN / "models.json").read_text())
    assert cli(board, "lead", "codex").returncode == 0
    result = cli(board, "model", "active")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [models["tiers"][tier]["model"], models["tiers"][tier]["effort"], tier, "codex"]
    assert len(result.stderr.splitlines()) == 1 and "shared Claude quota" in result.stderr
    cli(board, "lead", "claude")
    result = cli(board, "model", "active")
    assert result.stdout.split()[-1] == "claude" and result.stdout.split()[0] == models["claude_tiers"][tier]["model"]
    assert not result.stderr


@pytest.mark.parametrize("engine", ["codex", "claude", "agy"])
def test_engine_force_wins_during_fallback(board, monkeypatch, engine):
    add_wp(board, "active", engine="claude")
    cli(board, "lead", "codex")
    monkeypatch.setenv("CREW_ENGINE_FORCE", engine)
    result = cli(board, "model", "active")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split()[-1] == engine
    assert not result.stderr


@pytest.mark.parametrize("engine", ["codex", "agy"])
def test_fallback_leaves_other_workers_alone(board, engine):
    add_wp(board, "active", engine=engine)
    cli(board, "lead", "codex")
    result = cli(board, "model", "active")
    assert result.returncode == 0 and result.stdout.split()[-1] == engine
    assert not result.stderr


def test_fallback_covers_default_engine_and_archived_wp(board, monkeypatch):
    add_wp(board, "active")
    board.spec_path("active").write_text("- Model: standard\n", encoding="utf-8")
    cli(board, "lead", "codex")
    monkeypatch.setenv("CREW_ENGINE", "claude")
    assert cli(board, "model", "active").stdout.split()[-1] == "codex"
    archived = board.PLAN / "wp/done/2026-11/active.md"
    archived.parent.mkdir(parents=True)
    board.spec_path("active").rename(archived)
    assert cli(board, "model", "active").stdout.split()[-1] == "codex"


@pytest.mark.parametrize("count", [0, 10, 50])
@pytest.mark.parametrize("target", ["codex", "claude"])
def test_target_handoff_cli_is_short_and_sets_lead(board, count, target):
    for n in range(count):
        add_wp(board, f"wp{n}")
    board.main(["board.py", "decide", "Scope?\nChoose", "Small|detail"])
    result = cli(board, "handoff", "--to", target)
    assert result.returncode == 0, result.stderr
    assert result.stdout == (board.PLAN / "handoff.md").read_text(encoding="utf-8")
    assert len(result.stdout.splitlines()) <= 40
    assert f"## Lead\n{target}\n" in result.stdout
    assert "## Next" in result.stdout and "Scope? Choose" in result.stdout
    command = 'codex "Use the crew-lead skill as fallback lead: read .crew/plan/handoff.md and continue."'
    assert (command in result.stdout) == (target == "codex")
    if target == "codex":
        assert "Configured handoff: custom-plan/handoff.md" in result.stdout
    assert cli(board, "lead").stdout.strip() == target
    if count > 20:
        assert "30 more open WPs" in result.stdout
    # A normal end-of-session card retains the fallback lead and its paste command.
    assert cli(board, "handoff").stdout == result.stdout


@pytest.mark.parametrize("args", [("lead", "agy"), ("lead", "codex", "extra"),
                                  ("handoff", "--to", "agy"), ("handoff", "--to")])
def test_bad_lead_commands_leave_state_unchanged(board, args):
    result = cli(board, *args)
    assert result.returncode != 0 and "usage:" in result.stderr
    assert not board.BOARD.exists() and not (board.PLAN / "handoff.md").exists()


@pytest.mark.parametrize("args", [("lead", "codex"), ("handoff", "--to", "codex")])
def test_claude_only_cannot_handover(board, args):
    config = board.ROOT / ".crew/config.json"
    config.write_text(json.dumps({**board.CONFIG, "engines": ["claude"]}), encoding="utf-8")
    result = cli(board, *args)
    assert result.returncode != 0 and "requires codex in config.engines" in result.stderr
    assert not board.BOARD.exists() and not (board.PLAN / "handoff.md").exists()
