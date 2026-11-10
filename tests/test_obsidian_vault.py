"""Obsidian setup and health checks; fixtures never write Git state."""
import json
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

import pytest

from test_board_lifecycle import REPO, add_wp, board  # noqa: F401 (shared pytest fixture)


TEMPLATES = REPO / "templates/plan"


def configure(board, **changes):
    board.CONFIG.update(changes)
    (board.ROOT / ".crew/config.json").write_text(json.dumps(board.CONFIG), encoding="utf-8")


def cli(board, *args):
    return subprocess.run([sys.executable, str(board.ROOT / ".crew/bin/board.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def git_result(monkeypatch, board, tracked=""):
    def run(command, **kwargs):
        assert command == ["git", "-C", str(board.ROOT), "ls-files", "-z"]
        return SimpleNamespace(returncode=0, stdout=tracked.encode("utf-8"))
    monkeypatch.setattr(board.subprocess, "run", run)


@pytest.mark.parametrize("notes", ["none", "notion", "obsidian"])
@pytest.mark.parametrize("plan_dir", [".crew/plan", "custom plan", "deep/custom/plan"])
def test_init_notes_cli(board, notes, plan_dir):
    dest = board.ROOT / plan_dir
    dest.parent.mkdir(parents=True, exist_ok=True)
    board.PLAN.rename(dest)
    board.PLAN = dest
    configure(board, notes=notes, planDir=plan_dir)
    result = cli(board, "init-notes", str(TEMPLATES))
    assert result.returncode == 0, result.stderr
    for name in ("index.md", "notes/README.md", ".obsidian/app.json"):
        assert (dest / name).exists() == (notes == "obsidian")
    ignore = board.ROOT / ".gitignore"
    if notes != "obsidian":
        assert not ignore.exists() and not result.stdout
        return
    assert json.loads((dest / ".obsidian/app.json").read_text()) == {"userIgnoreFilters": []}
    assert f"/{plan_dir}/.obsidian/workspace*.json" in ignore.read_text().splitlines()
    assert unquote(result.stdout.strip().split("path=", 1)[1]) == str(dest.resolve())
    (board.ROOT / "rule.md").touch()
    (board.ROOT / "feature.md").touch()
    (board.ROOT / "docs/adr").mkdir(parents=True)
    add_wp(board, "active")
    add_wp(board, "finished", step="merged", merged_at="2026-01-01")
    archived = dest / "wp/done/2026-01/finished.md"
    archived.parent.mkdir(parents=True)
    (dest / "wp/finished.md").rename(archived)
    board.handoff()
    board.views()  # Local views must exist before walking index links.
    for path in (dest / "index.md", dest / "plan.md", dest / "history.md"):
        targets = re.findall(r"\[[^\]\n]*\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
        assert targets
        for target in targets:
            assert (path.parent / unquote(urlsplit(target).path)).exists(), (path, target)
    assert "wp/done/2026-01/finished.md" in (dest / "history.md").read_text()
    # Rerunning initialization preserves user edits and does not duplicate ignore rules.
    (dest / "notes/README.md").write_text("Local research", encoding="utf-8")
    again = cli(board, "init-notes", str(TEMPLATES))
    assert again.returncode == 0
    assert (dest / "notes/README.md").read_text() == "Local research"
    assert ignore.read_text().count("workspace*.json") == 1


def test_history_migrates_old_entries_and_relinks_archive(board):
    add_wp(board, "old", step="merged", merged_at="2024-01-01")
    history = board.PLAN / "history/2024.md"
    history.parent.mkdir()
    history.write_text(board.GENERATED + "\n\n- 2024-01-01 | `old` | Summary old | \n", encoding="utf-8")
    board.views()
    assert "[`old`](../wp/old.md)" in history.read_text()
    dest = board.PLAN / "wp/done/2024-01/old.md"
    dest.parent.mkdir(parents=True)
    board.spec_path("old").rename(dest)
    board.views()
    assert "[`old`](../wp/done/2024-01/old.md)" in history.read_text()
    before = history.read_bytes()
    board.views()
    assert history.read_bytes() == before


def test_doctor_reports_all_findings_without_git_writes(board, monkeypatch, capsys):
    add_wp(board, "missing")
    board.spec_path("missing").unlink()
    (board.PLAN / "index.md").write_text("[broken](missing.md)\n", encoding="utf-8")
    (board.PLAN / "plan.md").write_text("[broken plan](lost.md)\n", encoding="utf-8")
    (board.PLAN / "wp/stray.md").write_text("- Summary missing colon\n", encoding="utf-8")
    tracked = "custom-plan/.obsidian/workspace-mobile.json\0"
    git_result(monkeypatch, board, tracked)
    with pytest.raises(SystemExit) as exc:
        board.main(["board.py", "doctor"])
    assert exc.value.code == 1
    out = capsys.readouterr().out
    for finding in ("missing WP file: missing", "broken link in index.md", "tracked workspace file:",
                    "WARN: stray WP file: wp/stray.md", "WP headers: missing Summary", "broken link in plan.md"):
        assert finding in out


def test_doctor_clean_fresh_clone_and_archived_specs(board, monkeypatch, capsys):
    archive = board.PLAN / "wp/done/2025-01/old.md"
    archive.parent.mkdir(parents=True)
    archive.write_text("- Summary: Committed archive\n", encoding="utf-8")
    shutil.copy(TEMPLATES / "wp/TEMPLATE.md", board.PLAN / "wp/TEMPLATE.md")
    git_result(monkeypatch, board)
    board.doctor()
    assert "OK:" in capsys.readouterr().out


@pytest.mark.parametrize("change", ["bad-json", "bad-path", "missing-plan", "bad-notes", "bad-engines"])
def test_doctor_config_errors_cli(board, change):
    config = board.ROOT / ".crew/config.json"
    if change == "bad-json":
        config.write_text("{", encoding="utf-8")
    elif change == "bad-path":
        configure(board, planDir=None)
    elif change == "missing-plan":
        configure(board, planDir="absent")
    elif change == "bad-notes":
        configure(board, notes="unknown")
    else:
        configure(board, engines=[])
    result = cli(board, "doctor")
    assert result.returncode == 1
    assert "ERROR:" in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_rolling_history_links_resolve_without_board_state(board):
    for n in range(32):
        path = board.PLAN / "wp/done/2024-01" / f"old{n:02}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"- Summary: Archived {n}\n", encoding="utf-8")
    board.views()
    paths = [board.PLAN / "history.md", board.PLAN / "history/2024.md"]
    for path in paths:
        targets = re.findall(r"\[[^\]\n]*\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
        assert len(targets) == (30 if path.name == "history.md" else 2)
        assert all((path.parent / unquote(target)).is_file() for target in targets)
    before = [path.read_bytes() for path in paths]
    board.views()
    assert [path.read_bytes() for path in paths] == before


@pytest.mark.parametrize("planning", [False, True])
def test_doctor_fresh_clone_or_planning_warns_for_unassigned_wps(board, monkeypatch, capsys, planning):
    configure(board, notes="obsidian")
    board.init_notes(TEMPLATES)
    for name in ("rule.md", "feature.md"):
        (board.ROOT / name).touch()
    (board.ROOT / "docs/adr").mkdir(parents=True)
    for wp in ("unassigned", "another"):
        (board.PLAN / "wp" / f"{wp}.md").write_text(f"- Summary: Planned {wp}\n", encoding="utf-8")
    if planning:
        add_wp(board, "assigned")
    else:
        assert not board.BOARD.exists()
    for name in ("plan.md", "history.md", "history", "handoff.md"):
        assert not (board.PLAN / name).exists()
    git_result(monkeypatch, board)
    assert board.main(["board.py", "doctor"]) is None
    out = capsys.readouterr().out
    for wp in ("unassigned", "another"):
        assert f"WARN: stray WP file: wp/{wp}.md" in out
    assert "ERROR:" not in out and "OK:" in out


@pytest.mark.parametrize("source", ["index.md", "plan.md"])
@pytest.mark.parametrize("target", ["./plan.md", "history.md", "history/", "./handoff.md#next"])
def test_doctor_skips_missing_local_generated_targets(board, monkeypatch, capsys, source, target):
    (board.PLAN / source).write_text(f"[local]({target})\n", encoding="utf-8")
    git_result(monkeypatch, board)
    board.doctor()
    assert "ERROR:" not in capsys.readouterr().out


@pytest.mark.parametrize("source", ["index.md", "plan.md"])
@pytest.mark.parametrize("target", ["notes/missing.md", "notes/plan.md"])
def test_doctor_real_broken_links_still_fail(board, monkeypatch, capsys, source, target):
    (board.PLAN / source).write_text(f"[broken]({target})\n", encoding="utf-8")
    git_result(monkeypatch, board)
    with pytest.raises(SystemExit) as exc:
        board.main(["board.py", "doctor"])
    assert exc.value.code == 1
    assert f"ERROR: broken link in {source}: {target}" in capsys.readouterr().out
