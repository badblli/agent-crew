"""Native role output, safe re-renders and the shared instruction size budget."""
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_roles", REPO / "tools/render_roles.py")
roles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(roles)


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
    assert len(claude) == len(codex) == 5
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


def test_config_selects_codex_only(project):
    roles.sync(project)
    assert len(list((project / ".codex/agents").glob("*.toml"))) == 5
    assert not (project / ".claude/agents").exists()


def test_local_edits_preserved_and_reported(project):
    roles.sync(project, ["claude", "codex"])
    edited = project / ".codex/agents/crew-developer.toml"
    edited.write_text('# local instructions\n', encoding="utf-8")
    proc = subprocess.run([sys.executable, str(REPO / "tools/render_roles.py"), "--project", str(project),
                           "--engines", "claude,codex"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "left as is: .codex/agents/crew-developer.toml" in proc.stdout
    assert edited.read_text(encoding="utf-8") == '# local instructions\n'
    # A model update replaces untouched output but still preserves the edit and its old hash.
    models = project / ".crew/plan/models.json"
    routing = json.loads(models.read_text(encoding="utf-8"))
    routing["tiers"]["standard"]["model"] = "gpt-test-model"
    models.write_text(json.dumps(routing), encoding="utf-8")
    result = roles.sync(project, ["claude", "codex"])
    assert result["kept"] == [".codex/agents/crew-developer.toml"]
    assert ".codex/agents/crew-ui.toml" in result["updated"]
    assert roles.sync(project, ["claude", "codex"])["kept"] == result["kept"]


def test_unknown_existing_role_is_preserved(project):
    dest = project / ".claude/agents/crew-qa.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("User role\n", encoding="utf-8")
    assert roles.sync(project, ["claude"])["kept"] == [".claude/agents/crew-qa.md"]
    assert dest.read_text() == "User role\n"


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
