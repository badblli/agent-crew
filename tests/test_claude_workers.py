"""Claude sessions through the real runner/board/feedback pipeline, using synthetic CLI output."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from test_run_wp import BASH, REPO, STUB, Crew

pytestmark = pytest.mark.skipif(not BASH, reason="needs bash (Git Bash on Windows)")


class ClaudeCrew(Crew):
    def __init__(self, root, engine="claude"):
        super().__init__(root, engine)
        shutil.copy(REPO / "templates/bin/tell.sh", root / ".crew/bin/tell.sh")
        stub = self.stubs / "claude"
        stub.write_text(STUB, encoding="utf-8", newline="\n")
        stub.chmod(0o755)
        self.board("assign", "wp1", "builder")

    def board(self, *args, **kwargs):
        return subprocess.run([sys.executable, str(self.root / ".crew/bin/board.py"), *args],
                              capture_output=True, text=True, encoding="utf-8", check=True, **kwargs)

    def run(self, **kwargs):
        return super().run(**{"CREW_CLAUDE_BG": "0", "CLAUDE_BIN": "claude",
                              "CREW_CLAUDE_PERMISSION_MODE": "", **kwargs})

    def tell(self):
        env = {k: v for k, v in os.environ.items() if k != "TEAM_SCRIPT_DIR"}
        env.update(STUB_DIR=self.stubs.as_posix(), CLAUDE_BIN="claude", CREW_CLAUDE_BG="0",
                   CREW_CLAUDE_PERMISSION_MODE="",
                   PATH=str(self.stubs) + os.pathsep + env.get("PATH", ""))
        return subprocess.run([BASH, ".crew/bin/tell.sh", "wp1", "Verify the change"],
                              cwd=self.root, env=env, capture_output=True, text=True,
                              encoding="utf-8", timeout=120)

    def chats(self):
        return [json.loads(line) for line in (self.root / ".crew/state/chat/wp1.jsonl")
                .read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def crew(tmp_path):
    return ClaudeCrew(tmp_path / "project")


@pytest.mark.parametrize("tier,model", [("light", "haiku"), ("standard", "sonnet"),
                                        ("deep", "opus"), ("peak", "opus")])
def test_model_each_claude_tier(crew, tier, model):
    spec = crew.root / ".crew/plan/wp/wp1.md"
    spec.write_text(f"- Engine: claude\n- Model: {tier}\n", encoding="utf-8")
    assert crew.board("model", "wp1").stdout.split() == [model, "low" if tier == "light" else
                                                        "medium" if tier == "standard" else "high", tier, "claude"]


def test_claude_session_report_chat_and_resume(crew):
    crew.plays("claude", ("claude-success", 0), ("claude-success", 0))
    assert crew.run() == 0, crew.out
    assert crew.file("status") == "done"
    assert crew.file("thread") == "synthetic-claude-session"
    assert crew.file("report.md").startswith("## Summary\nSynthetic Claude report.")
    assert "--name Builder · wp1" in crew.calls("claude")[0]
    assert "--model sonnet" in crew.calls("claude")[0]
    assert "--output-format stream-json --verbose" in crew.calls("claude")[0]
    assert "--permission-mode auto" in crew.calls("claude")[0]
    assert not any(c["text"].startswith("Claude quota:") for c in crew.chats())
    assert any(c["text"].startswith("Synthetic Claude progress") for c in crew.chats())
    assert any(c["text"] == "open: claude --resume synthetic-claude-session" for c in crew.chats())
    assert "hidden reasoning" not in json.dumps(crew.chats())
    assert "hook:" not in crew.file("events.jsonl")
    assert json.loads(crew.file("rate_limit.json"))["utilization"] == 0.25
    hint = json.loads((crew.root / ".crew/state/usage/claude-workers.json").read_text())
    assert hint["rate_limit_info"]["status"] == "allowed"
    proc = crew.tell()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert crew.calls("claude")[1].startswith("-p --resume synthetic-claude-session ")
    assert "--permission-mode auto" in crew.calls("claude")[1]
    assert not any(c["text"].startswith("Claude quota:") for c in crew.chats())
    assert crew.file("status") == "done"


def test_claude_permission_mode_can_be_overridden(crew):
    crew.plays("claude", ("claude-success", 0))
    assert crew.run(CREW_CLAUDE_PERMISSION_MODE="acceptEdits") == 0, crew.out
    assert "--permission-mode acceptEdits" in crew.calls("claude")[0]


@pytest.mark.parametrize("warning", [{"status": "rejected"}, {"status": "allowed_warning"},
                                     {"status": "allowed", "utilization": 1}])
def test_quota_warning_once_per_run_and_hints_always_updated(crew, warning):
    run = crew.root / ".crew/state/runs/wp1/synthetic"
    run.mkdir(parents=True)

    def ingest(*hints):
        crew.board("ingest", "wp1", str(run), input="".join(json.dumps({
            "type": "rate_limit_event", "rate_limit_info": hint}) + "\n" for hint in hints))

    def notes():
        return [c for c in crew.chats() if c["text"].startswith("Claude quota:")]

    allowed = {"status": "allowed", "utilization": 0.25}
    ingest(allowed, allowed)
    assert notes() == []
    assert json.loads((run / "rate_limit.json").read_text()) == allowed
    ingest(warning, warning)
    assert len(notes()) == 1
    # A fresh ingest process (as on resume) must not repeat the run's warning.
    ingest(warning, allowed)
    assert len(notes()) == 1
    assert json.loads((run / "rate_limit.json").read_text()) == allowed
    hint_path = crew.root / ".crew/state/usage/claude-workers.json"
    assert json.loads(hint_path.read_text())["rate_limit_info"] == allowed
    # Another run of this WP gets its own warning.
    next_run = run.with_name("synthetic-next")
    next_run.mkdir()
    crew.board("ingest", "wp1", str(next_run), input=json.dumps({
        "type": "rate_limit_event", "rate_limit_info": warning}) + "\n")
    assert len(notes()) == 2


@pytest.mark.parametrize("exit_code", [0, 1])
def test_error_result_marks_failed_even_on_zero_exit(crew, exit_code):
    crew.plays("claude", ("claude-failed", exit_code))
    assert crew.run() == 1, crew.out
    assert crew.file("status") == "failed exit=1"
    assert crew.file("report.md") == "Synthetic execution failure"
    assert len(crew.calls("claude")) == 1


def test_claude_quota_pauses(crew):
    crew.plays("claude", ("claude-quota", 1))
    assert crew.run() == 1, crew.out
    assert crew.file("status") == "paused"
    assert crew.file("resume_at").startswith("try again at Nov 11th")


def test_claude_transient_resumes_session(crew):
    crew.plays("claude", ("claude-transient", 1), ("claude-success", 0))
    assert crew.run() == 0, crew.out
    assert crew.file("status") == "done"
    assert crew.calls("claude")[1].startswith("-p --resume synthetic-claude-session ")


@pytest.mark.parametrize("target", ["codex", "agy"])
def test_claude_quota_can_fail_over(crew, target):
    crew.plays("claude", ("claude-quota", 1))
    crew.plays(target, (f"{target}-success", 0))
    assert crew.run(CREW_FAILOVER=target) == 0, crew.out
    assert crew.file("status") == "done"
    assert crew.file("engine") == target
    assert "previous engine hit a quota limit" in crew.calls(target)[0]


@pytest.mark.parametrize("source,fixture", [("codex", "codex-usage-limit"), ("agy", "agy-quota-429")])
def test_failover_to_claude_then_tell_uses_effective_engine(tmp_path, source, fixture):
    crew = ClaudeCrew(tmp_path / "project", source)
    crew.plays(source, (fixture, 1))
    crew.plays("claude", ("claude-success", 0), ("claude-success", 0))
    assert crew.run(CREW_FAILOVER="claude") == 0, crew.out
    assert crew.file("engine") == "claude" and crew.file("model").startswith("sonnet")
    proc = crew.tell()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert crew.calls("claude")[1].startswith("-p --resume synthetic-claude-session ")


def test_claude_background_launch_is_not_a_completed_wp(crew):
    crew.plays("claude", ("claude-success", 0))
    assert crew.run(CREW_CLAUDE_BG="1") == 0, crew.out
    args = crew.calls("claude")[0]
    assert args.startswith("--bg --name Builder · wp1")
    assert "--permission-mode auto" in args
    assert "-p " not in args and "--output-format" not in args
    assert crew.file("status") == "background"
    assert not (crew.run_dir / "report.md").exists()
    assert any(c["text"] == 'open: claude attach "Builder · wp1"' for c in crew.chats())
    proc = crew.tell()
    assert proc.returncode == 2 and "claude attach" in proc.stderr


def test_session_id_is_saved_without_init(crew):
    run = crew.root / ".crew/state/runs/wp1/synthetic"
    run.mkdir(parents=True)
    crew.board("ingest", "wp1", str(run), input=json.dumps({
        "type": "assistant", "session_id": "synthetic-no-init", "message": {
            "content": [{"type": "text", "text": "Synthetic message"}]}}) + "\n")
    assert (run / "thread").read_text().strip() == "synthetic-no-init"
