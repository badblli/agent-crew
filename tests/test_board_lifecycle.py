"""WP lifecycle views and archives using synthetic board state (no Git writes)."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_run_wp import BASH

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def board(tmp_path, monkeypatch):
    root = tmp_path / "project"
    bin_dir = root / ".crew/bin"
    plan = root / "custom-plan"
    bin_dir.mkdir(parents=True)
    (plan / "wp").mkdir(parents=True)
    (root / ".crew/config.json").write_text(json.dumps({
        "planDir": "custom-plan", "stateDir": "custom-state", "engines": ["codex", "claude", "agy"]}),
        encoding="utf-8")
    for name in ("team.json", "models.json"):
        shutil.copy(REPO / "templates/plan" / name, plan / name)
    path = bin_dir / "board.py"
    shutil.copy(REPO / "templates/bin/board.py", path)
    spec = importlib.util.spec_from_file_location("lifecycle_board", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("CREW_ENGINE", "CREW_ENGINE_FORCE"):
        monkeypatch.delenv(name, raising=False)
    return module


def add_wp(board, wp, step="working", engine="codex", **extra):
    (board.PLAN / "wp" / f"{wp}.md").write_text(
        f"# {wp}\n- Summary: Summary {wp}\n- Engine: {engine}\n- Model: standard\n- Depends on: prerequisite\n",
        encoding="utf-8")
    state = board._load()
    state["items"][wp] = {"agent": "builder", "step": step, **extra}
    board._save(state)


def entries(path):
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("- ")]


def test_active_views_and_merge_history(board):
    add_wp(board, "first")
    add_wp(board, "second", engine="agy")
    add_wp(board, "last")
    board.step("last", "merged", "Shipped https://github.com/example/repo/pull/7")
    plan = (board.PLAN / "plan.md").read_text(encoding="utf-8")
    assert plan.startswith(board.GENERATED)
    rows = [line for line in plan.splitlines() if line.startswith("| ")][2:]
    assert len(rows) == 2
    assert rows[0] == "| [`first`](wp/first.md) | Summary first | Builder | working | codex/standard | prerequisite |"
    assert "| [`second`](wp/second.md) |" in rows[1] and "agy/standard" in rows[1]
    history = board.PLAN / "history.md"
    assert history.read_text(encoding="utf-8").startswith(board.GENERATED)
    assert "[`last`](wp/last.md) | Summary last | https://github.com/example/repo/pull/7" in entries(history)[0]
    board.step("last", "merged")
    board.views()
    assert len(entries(history)) == 1


def test_rolling_history_and_archive_are_idempotent(board):
    for n in range(31):
        wp = f"wp{n:02}"
        add_wp(board, wp, merged_at=f"2025-12-{n + 1:02}T12:00:00")
        board.step(wp, "merged")
    history = board.PLAN / "history.md"
    older = board.PLAN / "history/2025.md"
    assert len(entries(history)) == 30
    assert "`wp30`" in entries(history)[0]
    assert "`wp01`" in entries(history)[-1]
    assert len(entries(older)) == 1 and "`wp00`" in entries(older)[0]
    before = history.read_bytes(), older.read_bytes()
    board.views()
    assert (history.read_bytes(), older.read_bytes()) == before
    add_wp(board, "new-year", merged_at="2026-01-01T12:00:00")
    board.step("new-year", "merged")
    assert len(entries(history)) == 30 and len(entries(older)) == 2
    assert "`new-year`" in entries(history)[0]
    # Retain history even if the transient board state is removed.
    board.BOARD.unlink()
    board.views()
    assert len(entries(history)) == 30 and len(entries(older)) == 2


@pytest.mark.parametrize("engine", ["codex", "claude", "agy"])
def test_untracked_archive_and_cli_model(board, engine, monkeypatch):
    add_wp(board, "wp1", engine=engine)
    # No Git writes, including in fixture setup.
    with monkeypatch.context() as patch:
        patch.setattr(board.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
        board.archive("wp1")
    path = board.PLAN / "wp/done" / datetime.now().strftime("%Y-%m") / "wp1.md"
    assert path.is_file() and not (board.PLAN / "wp/wp1.md").exists()
    assert board.spec_path("wp1") == path
    board.archive("wp1")
    proc = subprocess.run([sys.executable, str(board.ROOT / ".crew/bin/board.py"), "model", "wp1"],
                          capture_output=True, text=True, encoding="utf-8", check=True)
    assert proc.stdout.split()[-2:] == ["standard", engine]
    board.main(["board.py", "assign", "wp1", "builder"])
    assert board._load()["items"]["wp1"]["step"] == "assigned"


def test_tracked_archive_uses_git_mv(board, monkeypatch):
    add_wp(board, "tracked")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if "mv" in command:
            Path(command[-2]).rename(command[-1])
            assert kwargs["check"] is True
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(board.subprocess, "run", fake_run)
    board.archive("tracked")
    assert calls[0][3:5] == ["ls-files", "--error-unmatch"]
    assert calls[1][3:5] == ["mv", "--"]
    assert board.spec_path("tracked").is_file()


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("main_tracked", [False, True])
def test_archive_delivers_main_spec_to_worktree(board, monkeypatch, tmp_path, explicit, main_tracked):
    add_wp(board, "wp1")
    source = board.spec_path("wp1")
    content = source.read_bytes()
    worktree = tmp_path / "agent tree"
    worktree.mkdir()
    older = board.LEAD / "runs/wp1/20260101-000000"
    latest = older.with_name("20260102-000000")
    older.mkdir(parents=True)
    latest.mkdir()
    (older / "workdir").write_text(str(tmp_path / "wrong-tree"), encoding="utf-8")
    (latest / "workdir").write_text(str(tmp_path / "ignored-tree" if explicit else worktree) + "\r\n",
                                    encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        assert command[3] == "ls-files"  # Untracked worktree spec must never invoke git mv.
        return SimpleNamespace(returncode=0 if main_tracked and command[2] == str(board.ROOT) else 1)

    monkeypatch.setattr(board.subprocess, "run", fake_run)
    argv = ["board.py", "archive", "wp1"]
    if explicit:
        argv.extend(["--worktree", str(worktree)])
    board.main(argv)
    dest = worktree / "custom-plan/wp/done" / datetime.now().strftime("%Y-%m") / "wp1.md"
    assert dest.read_bytes() == content
    assert source.exists() == main_tracked
    if main_tracked:
        assert source.read_bytes() == content
    assert len(calls) == 2
    assert not (board.PLAN / "wp/done").exists()
    # The lead records merged before sync brings the committed archive back to main.
    board.step("wp1", "merged")
    assert "[`wp1`](wp/wp1.md) | Summary wp1 |" in entries(board.PLAN / "history.md")[0]


def test_worktree_tracked_spec_is_moved_in_worktree(board, monkeypatch, tmp_path):
    add_wp(board, "wp1")
    main_source = board.spec_path("wp1")
    worktree = tmp_path / "agent-tree"
    active = worktree / "custom-plan/wp/wp1.md"
    active.parent.mkdir(parents=True)
    active.write_text("Tracked worktree version", encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[3] == "mv":
            assert command[2] == str(worktree.resolve()) and kwargs["check"]
            assert Path(command[-2]) == active
            active.rename(command[-1])
        return SimpleNamespace(returncode=0 if command[2] == str(worktree.resolve()) else 1)

    monkeypatch.setattr(board.subprocess, "run", fake_run)
    board.archive("wp1", worktree)
    dest = worktree / "custom-plan/wp/done" / datetime.now().strftime("%Y-%m") / "wp1.md"
    assert dest.read_text(encoding="utf-8") == "Tracked worktree version"
    assert not active.exists() and not main_source.exists()
    assert len(calls) == 3


def test_worktree_destination_collision_changes_neither_checkout(board, monkeypatch, tmp_path):
    add_wp(board, "wp1")
    source = board.spec_path("wp1")
    original = source.read_bytes()
    worktree = tmp_path / "agent-tree"
    dest = worktree / "custom-plan/wp/done" / datetime.now().strftime("%Y-%m") / "wp1.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("Existing archive", encoding="utf-8")
    active = worktree / "custom-plan/wp/wp1.md"
    active.write_text("Existing active", encoding="utf-8")
    monkeypatch.setattr(board.subprocess, "run", lambda *a, **kw: pytest.fail("Git called on collision"))
    with pytest.raises(SystemExit, match="destination exists"):
        board.main(["board.py", "archive", "wp1", "--worktree", str(worktree)])
    assert source.read_bytes() == original
    assert dest.read_text(encoding="utf-8") == "Existing archive"
    assert active.read_text(encoding="utf-8") == "Existing active"


def test_empty_board_backfills_archived_specs_newest_first(board):
    for month, wp in [("2025-12", "older"), ("2026-02", "newer")]:
        path = board.PLAN / "wp/done" / month / f"{wp}.md"
        path.parent.mkdir(parents=True)
        path.write_text(f"- Summary: Archived {wp}\n- PR: https://example.com/pull/1\n", encoding="utf-8")
    board.views()
    history = board.PLAN / "history.md"
    assert entries(history) == ["- 2026-02-01 | [`newer`](wp/done/2026-02/newer.md) | Archived newer | ",
                                "- 2025-12-01 | [`older`](wp/done/2025-12/older.md) | Archived older | "]
    before = history.read_bytes()
    board.views()
    assert history.read_bytes() == before
    assert len((board.PLAN / "plan.md").read_text(encoding="utf-8").splitlines()) == 4


def test_archive_backfill_preserves_newer_local_history(board):
    add_wp(board, "current", merged_at="2026-06-15T12:00:00")
    board.step("current", "merged")
    for n in range(31):
        path = board.PLAN / "wp/done/2025-01" / f"old{n:02}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"- Summary: Old {n}\n", encoding="utf-8")
    board.views()
    history = board.PLAN / "history.md"
    older = board.PLAN / "history/2025.md"
    assert len(entries(history)) == 30 and "`current`" in entries(history)[0]
    assert len(entries(older)) == 2
    before = history.read_bytes(), older.read_bytes()
    board.views()
    assert (history.read_bytes(), older.read_bytes()) == before


def test_active_spec_wins_and_archive_collision_is_preserved(board):
    add_wp(board, "wp1")
    archive = board.PLAN / "wp/done" / datetime.now().strftime("%Y-%m") / "wp1.md"
    archive.parent.mkdir(parents=True)
    archive.write_text("old archive", encoding="utf-8")
    assert board.spec_path("wp1") == board.PLAN / "wp/wp1.md"
    with pytest.raises(SystemExit, match="destination exists"):
        board.archive("wp1")
    assert archive.read_text(encoding="utf-8") == "old archive"


@pytest.mark.parametrize("count", [10, 50])
def test_handoff_is_short_overwritten_and_includes_decision(board, count):
    for n in range(count):
        add_wp(board, f"wp{n}")
    add_wp(board, "finished", step="merged")
    board.main(["board.py", "phase", "Build", "Finish lifecycle"])
    board.main(["board.py", "decide", "Which scope?\nChoose one", "Small|detail", "Large|detail"])
    board.main(["board.py", "handoff"])
    path = board.PLAN / "handoff.md"
    text = path.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 40
    assert "Phase: Build" in text and "Which scope? Choose one" in text and "## Next" in text
    assert "finished" not in text
    if count == 10:
        assert all(f"- wp{n}: working" in text for n in range(count))
    path.write_text(text + "Lead's old next action\n", encoding="utf-8")
    board.main(["board.py", "decide", "--clear"])
    board.handoff()
    assert "Lead's old next action" not in path.read_text(encoding="utf-8")
    assert "## Open decision\nnone" in path.read_text(encoding="utf-8")


def test_missing_or_invalid_archive_id_fails_without_mutation(board):
    for wp in ("missing", "../escape"):
        with pytest.raises(SystemExit):
            board.archive(wp)
    assert not (board.PLAN / "wp/done").exists()


@pytest.mark.skipif(not BASH, reason="needs bash (Git Bash on Windows)")
def test_sync_removes_identical_archived_local_copy(board, monkeypatch, tmp_path):
    add_wp(board, "wp1")
    with monkeypatch.context() as patch:
        patch.setattr(board.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
        board.archive("wp1")
    archived = board.spec_path("wp1")
    incoming = tmp_path / "incoming.md"
    incoming.write_bytes(archived.read_bytes().replace(b"\r\n", b"\n"))
    archived.write_bytes(incoming.read_bytes().replace(b"\n", b"\r\n"))
    stubs = tmp_path / "sync-stubs"
    stubs.mkdir()
    git = stubs / "git"
    git.write_text('''#!/usr/bin/env bash
# Synthetic upstream; this test never writes Git state.
[[ "$1" != -C ]] || shift 2
case "$1" in
  rev-parse) printf '%s\\n' "$SYNC_ROOT" ;;
  ls-files) printf '%s\\n' "$SYNC_REL" ;;
  show) cat "$SYNC_INCOMING" ;;
  fetch|cat-file|diff|merge|log) exit 0 ;;
  *) exit 99 ;;
esac
''', encoding="utf-8", newline="\n")
    git.chmod(0o755)
    env = {**os.environ, "SYNC_GIT": git.as_posix(),
           "SYNC_SCRIPT": (REPO / "templates/bin/sync.sh").as_posix(),
           "SYNC_ROOT": board.ROOT.as_posix(), "SYNC_REL": archived.relative_to(board.ROOT).as_posix(),
           "SYNC_INCOMING": incoming.as_posix()}
    # A shell function guarantees Git Bash's startup PATH cannot select the real Git.
    result = subprocess.run([BASH, "-c", 'git() { bash "$SYNC_GIT" "$@"; }; source "$SYNC_SCRIPT" main'],
                            cwd=board.ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "removed local copy (identical upstream)" in result.stdout
    assert not archived.exists()
