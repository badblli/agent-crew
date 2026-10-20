"""Tests for templates/bin/run-wp.sh retry, quota pause and failover (stub engines, no network).

Each test builds a throwaway crew project, points CODEX_BIN / AGY_BIN at a stub that replays a
recorded event stream from tests/fixtures/run-wp/ per call, and checks the run's status files.
"""
import os
import pathlib
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).parent.parent
FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "run-wp"

STUB = """#!/usr/bin/env bash
# Replays $STUB_DIR/<name>-<call>.jsonl on stdout and exits with <name>-<call>.rc.
name="$(basename "$0")"
n=$(( $(cat "$STUB_DIR/$name.calls" 2>/dev/null || echo 0) + 1 ))
echo "$n" >"$STUB_DIR/$name.calls"
printf '%s\\n' "$*" >"$STUB_DIR/$name-$n.args"
cat "$STUB_DIR/$name-$n.jsonl" 2>/dev/null
exit "$(cat "$STUB_DIR/$name-$n.rc" 2>/dev/null || echo 1)"
"""


def find_bash():
    if os.environ.get("CREW_TEST_BASH"):
        return os.environ["CREW_TEST_BASH"]
    if os.name != "nt":
        return shutil.which("bash")
    # On Windows `bash` may be WSL; use Git Bash next to git.
    git = shutil.which("git")
    for parent in pathlib.Path(git).resolve().parents if git else []:
        for cand in (parent / "bin" / "bash.exe", parent / "usr" / "bin" / "bash.exe"):
            if cand.exists():
                return str(cand)
    return None


BASH = find_bash()
pytestmark = pytest.mark.skipif(not BASH, reason="needs bash (Git Bash on Windows)")


class Crew:
    def __init__(self, root: pathlib.Path, engine: str):
        self.root = root
        self.stubs = root.parent / "stubs"
        self.stubs.mkdir()
        bin_dir = root / ".crew" / "bin"
        plan = root / ".crew" / "plan"
        (plan / "wp").mkdir(parents=True)
        bin_dir.mkdir(parents=True, exist_ok=True)
        for f in ("board.py", "lib.sh", "run-wp.sh"):
            shutil.copy(REPO / "templates" / "bin" / f, bin_dir / f)
        for f in ("team.json", "models.json"):
            shutil.copy(REPO / "templates" / "plan" / f, plan / f)
        (root / ".crew" / "config.json").write_text("{}", encoding="utf-8")
        (plan / "wp" / "wp1.md").write_text(
            f"# wp1 Demo\n\n- Summary: demo\n- Model: standard\n- Engine: {engine}\n\n## Goal\nDo it.\n",
            encoding="utf-8")
        for name in ("codex", "agy", "sleep"):
            stub = self.stubs / name
            stub.write_text(STUB if name != "sleep" else "#!/usr/bin/env bash\n", encoding="utf-8", newline="\n")
            stub.chmod(0o755)
        subprocess.run(["git", "init", "-q", str(root)], check=True)

    def plays(self, engine: str, *calls: tuple[str, int]):
        """Queue the event streams (fixture name, exit code) the stub engine returns per call."""
        for i, (fixture, rc) in enumerate(calls, 1):
            shutil.copy(FIXTURES / f"{fixture}.jsonl", self.stubs / f"{engine}-{i}.jsonl")
            (self.stubs / f"{engine}-{i}.rc").write_text(str(rc), encoding="utf-8")

    def calls(self, engine: str) -> list[str]:
        counter = self.stubs / f"{engine}.calls"
        n = int(counter.read_text()) if counter.exists() else 0
        return [(self.stubs / f"{engine}-{i}.args").read_text(encoding="utf-8") for i in range(1, n + 1)]

    def run(self, **env_extra):
        env = {k: v for k, v in os.environ.items()
               if k not in ("TEAM_SCRIPT_DIR", "CREW_FAILOVER", "CREW_ENGINE", "CREW_ENGINE_FORCE", "WP_RESUME_RUN")}
        env.update(STUB_DIR=self.stubs.as_posix(), CODEX_BIN=(self.stubs / "codex").as_posix(),
                   AGY_BIN=(self.stubs / "agy").as_posix(), WP_IN_PLACE="1",
                   PATH=str(self.stubs) + os.pathsep + env.get("PATH", ""), **env_extra)
        proc = subprocess.run([BASH, ".crew/bin/run-wp.sh", "wp1"], cwd=self.root, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.out = proc.stdout + proc.stderr
        runs = sorted((self.root / ".crew" / "state" / "runs" / "wp1").iterdir())
        self.run_dir = runs[-1]
        return proc.returncode

    def file(self, name: str) -> str:
        return (self.run_dir / name).read_text(encoding="utf-8").strip()


@pytest.fixture
def crew(tmp_path):
    return lambda engine="codex": Crew(tmp_path / "project", engine)


def test_codex_usage_limit_pauses(crew):
    c = crew("codex")
    c.plays("codex", ("codex-usage-limit", 1))
    assert c.run() != 0, c.out
    assert c.file("status") == "paused", c.out
    assert c.file("resume_at").startswith("try again at Oct 20th, 2026 3:05 PM")
    assert len(c.calls("codex")) == 1 and c.calls("agy") == []


def test_codex_usage_limit_fails_over_to_agy(crew):
    c = crew("codex")
    c.plays("codex", ("codex-usage-limit", 1))
    c.plays("agy", ("agy-success", 0))
    assert c.run(CREW_FAILOVER="agy") == 0, c.out
    assert "failover to agy" in c.out
    assert c.file("status") == "done"
    [agy] = c.calls("agy")
    assert "previous engine hit a quota limit" in agy
    assert c.file("model").startswith("gemini-")
    assert len(c.calls("codex")) == 1


def test_agy_quota_429_pauses(crew):
    c = crew("agy")
    c.plays("agy", ("agy-quota-429", 1))
    assert c.run() != 0, c.out
    assert c.file("status") == "paused", c.out
    assert c.file("resume_at") == "later"
    assert len(c.calls("agy")) == 1


def test_agy_quota_429_fails_over_to_codex(crew):
    c = crew("agy")
    c.plays("agy", ("agy-quota-429", 1))
    c.plays("codex", ("codex-success", 0))
    assert c.run(CREW_FAILOVER="codex") == 0, c.out
    assert "failover to codex" in c.out
    assert c.file("status") == "done"
    [codex] = c.calls("codex")
    assert "previous engine hit a quota limit" in codex
    assert c.file("model").startswith("gpt-")


def test_codex_rate_limit_retries(crew):
    c = crew("codex")
    c.plays("codex", ("codex-rate-limit", 1), ("codex-success", 0))
    assert c.run(CREW_FAILOVER="agy") == 0, c.out
    assert "retry 2/4 after transient failure" in c.out
    assert c.file("status") == "done"
    first, second = c.calls("codex")
    assert second.startswith("exec resume 0199f3a2-5c1e-7d40-9b8a-3e2f1c0d4b6a")
    assert c.calls("agy") == []


@pytest.mark.parametrize("engine", ["codex", "agy"])
def test_normal_failure_fails_without_retry(crew, engine):
    c = crew(engine)
    c.plays(engine, (f"{engine}-failed", 1))
    other = "agy" if engine == "codex" else "codex"
    assert c.run(CREW_FAILOVER=other) == 1, c.out
    assert c.file("status") == "failed exit=1"
    assert len(c.calls(engine)) == 1 and c.calls(other) == []


def test_resume_of_paused_run_continues_the_thread(crew):
    c = crew("codex")
    c.plays("codex", ("codex-usage-limit", 1), ("codex-success", 0))
    assert c.run() != 0 and c.file("status") == "paused", c.out
    assert c.run(WP_RESUME_RUN=c.run_dir.as_posix()) == 0, c.out
    assert c.file("status") == "done"
    assert c.calls("codex")[1].startswith("exec resume 0199f3a2-5c1e-7d40-9b8a-3e2f1c0d4b6a")
