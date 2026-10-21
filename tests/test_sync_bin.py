"""Tests for tools/sync_bin.py (keeps .crew/bin of an installed project current)."""
import importlib.util
import json
import os
import pathlib
import time

import pytest

REPO = pathlib.Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location("sync_bin", REPO / "tools" / "sync_bin.py")
sync_bin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_bin)

TEMPLATES = REPO / "templates" / "bin"


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".crew" / "bin").mkdir(parents=True)
    (tmp_path / ".crew" / "config.json").write_text(json.dumps({"stateDir": ".crew/state"}))
    return tmp_path


def fake_history(monkeypatch, name, *contents):
    monkeypatch.setattr(sync_bin, "load_history",
                        lambda: {name: [sync_bin.digest(c) for c in contents]})


def test_history_covers_every_current_template():
    # Fails when a template changed without `python tools/sync_bin.py --record`.
    history = sync_bin.load_history()
    for name, path in sync_bin.templates().items():
        assert sync_bin.digest(path.read_bytes()) in history.get(name, []), name


def test_adds_missing_files_with_lf(project):
    r = sync_bin.sync(project, auto=True)
    assert r["status"] == "ok" and sorted(r["added"]) == sorted(sync_bin.templates())
    assert b"\r\n" not in (project / ".crew" / "bin" / "lib.sh").read_bytes()
    assert sync_bin.sync(project, auto=True)["added"] == []


def test_updates_released_version_keeps_local_edit(project, monkeypatch):
    old = b"# released lib.sh\r\n"
    fake_history(monkeypatch, "lib.sh", old)
    bin_dir = project / ".crew" / "bin"
    (bin_dir / "lib.sh").write_bytes(old)
    (bin_dir / "run-wp.sh").write_bytes(b"# edited in this project\n")
    r = sync_bin.sync(project, auto=True)
    assert r["updated"] == ["lib.sh"] and "run-wp.sh" in r["kept"]
    assert sync_bin.digest((bin_dir / "lib.sh").read_bytes()) == sync_bin.digest((TEMPLATES / "lib.sh").read_bytes())
    assert (bin_dir / "run-wp.sh").read_bytes() == b"# edited in this project\n"


def test_waits_while_an_agent_runs(project):
    run = project / ".crew" / "state" / "runs" / "wp1" / "20261021-100000"
    run.mkdir(parents=True)
    (run / "status").write_text("running\n")
    r = sync_bin.sync(project, auto=True)
    assert r["status"] == "busy" and r["busy"] == ["wp1"]
    assert not (project / ".crew" / "bin" / "lib.sh").exists()
    # A "running" status nobody touched for hours is a dead run, not an active one.
    old = time.time() - sync_bin.ACTIVE_RUN_SECONDS - 60
    os.utime(run / "status", (old, old))
    assert sync_bin.sync(project, auto=True)["status"] == "ok"


def test_auto_update_opt_out(project):
    (project / ".crew" / "config.json").write_text(json.dumps({"autoUpdate": False}))
    assert sync_bin.sync(project, auto=True)["status"] == "disabled"
    assert sync_bin.sync(project, auto=False)["status"] == "ok"


def test_no_crew(tmp_path):
    assert sync_bin.sync(tmp_path, auto=True)["status"] == "no-crew"
