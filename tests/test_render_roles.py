"""Native role output, safe re-renders and the shared instruction size budget."""
import importlib.util
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_roles", REPO / "tools/render_roles.py")
roles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(roles)
ROSTER = ("builder", "analyst", "api", "ui", "qa", "scribe", "reviewer")  # template agents + lead helper


@pytest.fixture
def project(tmp_path):
    plan = tmp_path / ".crew/plan"
    plan.mkdir(parents=True)
    (tmp_path / ".crew/config.json").write_text('{"engines": ["codex"]}', encoding="utf-8")
    (plan / "models.json").write_bytes((REPO / "templates/plan/models.json").read_bytes())
    return tmp_path


def test_both_native_role_formats(project):
    proc = subprocess.run([sys.executable, str(REPO / "tools/render_roles.py"), "--project", str(project),
                           "--engines", "claude,codex"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    claude = sorted((project / ".claude/agents").glob("*.md"))
    codex = sorted((project / ".codex/agents").glob("*.toml"))
    # AC-01: one file per roster agent, named by agent id, plus the lead's reviewer helper.
    assert {p.stem for p in claude} == {p.stem for p in codex} == {f"crew-{name}" for name in ROSTER}
    for path in codex:
        agent = tomllib.loads(path.read_text(encoding="utf-8"))
        assert all(agent.get(key) for key in ("name", "description", "developer_instructions"))
        assert 15 <= len(agent["developer_instructions"].strip().splitlines()) <= 35
        assert agent["model"].startswith("gpt-")
        assert agent["model_reasoning_effort"] in ("low", "medium", "high")
        assert "sandbox_mode" not in agent and "approval_policy" not in agent
    for path in claude:
        header = path.read_text(encoding="utf-8").split("---")[1]
        assert "name:" in header and "description:" in header and "disallowedTools: Agent" in header
        assert 'model: "opus"' in header if path.stem in ("crew-analyst", "crew-reviewer") else 'model: "sonnet"' in header
        assert ("tools: Read, Glob, Grep" in header) == (path.stem in ("crew-analyst", "crew-reviewer"))
        body = path.read_text(encoding="utf-8").split("---", 2)[2].strip()
        assert 15 <= len(body.splitlines()) <= 35
    builder = tomllib.loads((project / ".codex/agents/crew-builder.toml").read_text(encoding="utf-8"))
    developer = (REPO / "templates/roles/developer.md").read_text(encoding="utf-8").split("---\n", 2)[2]
    assert builder["description"].startswith("Builder (backend / core): Implement scoped")
    assert builder["developer_instructions"] == developer.strip() + "\n"
    reviewer = (project / ".claude/agents/crew-reviewer.md").read_text(encoding="utf-8")
    assert 'description: "Lead helper: Review a diff' in reviewer


def test_config_selects_codex_only(project):
    roles.sync(project)
    assert len(list((project / ".codex/agents").glob("*.toml"))) == len(ROSTER)
    assert not (project / ".claude/agents").exists()


def test_local_edits_preserved_and_reported(project):
    roles.sync(project, ["claude", "codex"])
    edited = project / ".codex/agents/crew-builder.toml"
    edited.write_text('# local instructions\n', encoding="utf-8")
    proc = subprocess.run([sys.executable, str(REPO / "tools/render_roles.py"), "--project", str(project),
                           "--engines", "claude,codex"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "left as is: .codex/agents/crew-builder.toml" in proc.stdout
    assert edited.read_text(encoding="utf-8") == '# local instructions\n'
    # A model update replaces untouched output but still preserves the edit and its old hash.
    models = project / ".crew/plan/models.json"
    routing = json.loads(models.read_text(encoding="utf-8"))
    routing["tiers"]["standard"]["model"] = "gpt-test-model"
    models.write_text(json.dumps(routing), encoding="utf-8")
    result = roles.sync(project, ["claude", "codex"])
    assert result["kept"] == [".codex/agents/crew-builder.toml"]
    assert ".codex/agents/crew-ui.toml" in result["updated"]
    assert roles.sync(project, ["claude", "codex"])["kept"] == result["kept"]


def test_unknown_existing_role_is_preserved(project):
    dest = project / ".claude/agents/crew-qa.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("User role\n", encoding="utf-8")
    assert roles.sync(project, ["claude"])["kept"] == [".claude/agents/crew-qa.md"]
    assert dest.read_text() == "User role\n"


def test_old_role_names_are_reported_once_and_kept(project):
    # A project set up before ac11: its own team.json has no roleFile, and crew-developer files
    # are recorded in the manifest. Session-start rendering must keep working.
    team = json.loads((REPO / "templates/plan/team.json").read_text(encoding="utf-8"))
    for agent in team["agents"]:
        del agent["roleFile"]
    (project / ".crew/plan/team.json").write_text(json.dumps(team), encoding="utf-8")
    old ={".claude/agents/crew-developer.md": b"old developer\n", ".codex/agents/crew-developer.toml": b"x = 1\n"}
    for rel, data in old.items():
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_bytes(data)
    manifest = project / ".crew/roles-rendered.json"
    manifest.write_text(json.dumps({rel: roles.digest(data) for rel, data in old.items()}), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(REPO / "tools/render_roles.py"), "--project", str(project),
                           "--engines", "claude,codex"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert ("No longer rendered (old role names), left in place; delete when unused: "
            ".claude/agents/crew-developer.md, .codex/agents/crew-developer.toml") in proc.stdout
    assert all((project / rel).read_bytes() == data for rel, data in old.items())
    assert {p.stem for p in (project / ".codex/agents").glob("*.toml")} == {
        "crew-developer", *(f"crew-{name}" for name in ROSTER)}
    builder = tomllib.loads((project / ".codex/agents/crew-builder.toml").read_text(encoding="utf-8"))
    assert builder["description"].startswith("Builder (backend / core): Implement scoped")
    assert roles.sync(project, ["claude", "codex"])["legacy"] == []
    assert roles.sync(project, ["claude", "codex"]) == {"added": [], "updated": [], "kept": [], "legacy": []}


def test_project_roster_and_role_files(project):
    team = {"agents": [{"id": "db", "name": "Keeper", "role": "database", "roleFile": "analyst"},
                       {"id": "qa", "name": "Tester"}, {"id": "infra"}]}
    (project / ".crew/plan/team.json").write_text(json.dumps(team), encoding="utf-8")
    roles.sync(project, ["claude"])
    names = {p.stem for p in (project / ".claude/agents").glob("*.md")}
    assert names == {"crew-db", "crew-qa", "crew-infra", "crew-reviewer"}
    assert 'description: "Keeper (database): Investigate' in (project / ".claude/agents/crew-db.md").read_text()
    assert 'description: "Tester: Verify' in (project / ".claude/agents/crew-qa.md").read_text()
    # No roleFile and no role file named after the id: the general implementer role.
    assert 'description: "infra: Implement scoped' in (project / ".claude/agents/crew-infra.md").read_text()


@pytest.mark.parametrize("agent, message", [
    ({"id": "db", "roleFile": "dba"}, "agent 'db' has roleFile 'dba', but templates/roles/dba.md does not exist; "
                                      "set roleFile to one of: analyst, developer, qa, reviewer, scribe, ui"),
    ({"id": "qa", "roleFile": "../qa"}, "roleFile '../qa'"),
    ({"id": "Bad Id"}, "agent id 'Bad Id' must use lowercase"),
])
def test_missing_role_file_fails_clearly(project, agent, message):
    # AC-02: a roster agent whose role file is missing stops the render before any file is written.
    (project / ".crew/plan/team.json").write_text(json.dumps({"agents": [agent]}), encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape(message)):
        roles.sync(project, ["claude"])
    assert not (project / ".claude").exists()
    proc = subprocess.run([sys.executable, str(REPO / "tools/render_roles.py"), "--project", str(project),
                           "--engines", "claude"], capture_output=True, text=True)
    assert proc.returncode == 1 and message in proc.stderr


def test_shared_core_budget_and_import():
    core = (REPO / "templates/AGENTS.md").read_text(encoding="utf-8")
    for key, value in {"planDir": ".crew/plan", "projectSummary": "A sample application.",
                       "language": "English", "privacyRule": "Keep customer data private."}.items():
        core = core.replace("{{" + key + "}}", value)
    assert "{{" not in core
    assert len(core.encode("utf-8")) <= 8192
    assert "unless your WP links them" in core
    claude = (REPO / "templates/CLAUDE.md").read_text(encoding="utf-8").splitlines()
    assert claude[0] == "@AGENTS.md" and len(claude) <= 30
    assert len((REPO / "templates/docs/adr/README.md").read_text().splitlines()) == 10
