"""Tests for templates/bin/jev_route.py (no network)."""
import importlib.util
import json
import pathlib
import urllib.error

import pytest

SPEC = importlib.util.spec_from_file_location(
    "jev_route", pathlib.Path(__file__).parent.parent / "templates" / "bin" / "jev_route.py")
jev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jev)

WP = """# WP9 Parser fix

- Özet: Ayrıştırıcı hatasını düzelt.

## Goal
Make the CSV parser handle quoted newlines.

## Tasks
- edit parser.py
- add tests

## Acceptance
pytest -q passes
"""
SECRET = "sk-test-SECRET-123"
RAW = {"model": "jev-1.13.0", "usage": {}, "answers": {
    "engine": {"type": "choice", "choice": "codex", "confidence": 0.9,
               "probabilities": {"codex": 0.9, "agy": 0.08, "claude-subagent": 0.02}},
    "tier": {"type": "choice", "choice": "deep", "confidence": 0.6,
             "probabilities": {"light": 0.0, "standard": 0.3, "deep": 0.6, "peak": 0.1}},
    "needs_user_decision": {"type": "noul", "noul": 0.04},
    "risk": {"type": "score", "score": 1.8, "confidence": 0.5,
             "probabilities": {"0": 0.0, "1": 0.3, "2": 0.6, "3": 0.1}}}}


@pytest.fixture
def wp_file(tmp_path, monkeypatch):
    f = tmp_path / "wp.md"
    f.write_text(WP, encoding="utf-8")
    monkeypatch.setattr(jev, "find_root", lambda: str(tmp_path))
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    return f


def test_parse_wp_builds_state():
    s = jev.parse_wp(WP)
    assert s["title"] == "WP9 Parser fix"
    assert s["summary"].startswith("Ayrıştırıcı")
    assert "quoted newlines" in s["goal"]
    assert "add tests" in s["tasks"]
    assert s["acceptance"] == "pytest -q passes"


def test_questions_shape():
    q = jev.QUESTIONS
    assert [q[k]["type"] for k in ("engine", "tier", "needs_user_decision", "risk")] == \
        ["choice", "choice", "noul", "score"]
    assert set(q["engine"]["criteria"]) == {"codex", "agy", "claude-subagent"}
    assert set(q["tier"]["criteria"]) == {"light", "standard", "deep", "peak"}
    assert 2 <= len(q["risk"]["criteria"]) <= 10


def test_key_from_env_file_without_quotes(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    (tmp_path / ".env").write_text(f'OTHER=1\nTYPESAFE_API_KEY="{SECRET}"\n')
    assert jev.load_key(str(tmp_path)) == SECRET
    monkeypatch.setenv("TYPESAFE_API_KEY", "from-env")
    assert jev.load_key(str(tmp_path)) == "from-env"


def test_success_json_and_key_not_leaked(wp_file, monkeypatch, capsys):
    (wp_file.parent / ".env").write_text(f"TYPESAFE_API_KEY={SECRET}\n")
    seen = {}

    def fake_post(payload, key):
        seen.update(payload=payload, key=key)
        return RAW

    monkeypatch.setattr(jev, "post", fake_post)
    assert jev.main([str(wp_file), "--json", "--allow-external"]) == 0
    out = capsys.readouterr().out
    assert SECRET not in out
    assert seen["key"] == SECRET and seen["payload"]["state"]["title"] == "WP9 Parser fix"
    res = json.loads(out)
    assert res["fallback"] is False and isinstance(res["latency_ms"], int)
    assert res["answers"]["engine"]["choice"] == "codex"
    assert res["answers"]["tier"]["probabilities"]["deep"] == 0.6
    assert res["answers"]["needs_user_decision"]["noul"] == 0.04
    assert res["answers"]["risk"]["level"] == "medium"


def test_human_output(wp_file, monkeypatch, capsys):
    monkeypatch.setenv("TYPESAFE_API_KEY", SECRET)
    monkeypatch.setattr(jev, "post", lambda p, k: RAW)
    assert jev.main([str(wp_file), "--allow-external"]) == 0
    out = capsys.readouterr().out
    assert "engine: codex" in out and "tier: deep" in out and "risk: medium" in out
    assert SECRET not in out


def test_fallback_without_key(wp_file, capsys):
    assert jev.main([str(wp_file), "--json", "--allow-external"]) == 0
    assert json.loads(capsys.readouterr().out)["fallback"] is True
    assert jev.main([str(wp_file), "--allow-external"]) == 0
    assert "manually" in capsys.readouterr().out


def test_no_external_call_by_default(wp_file, monkeypatch, capsys):
    monkeypatch.setenv("TYPESAFE_API_KEY", SECRET)
    monkeypatch.setattr(jev, "post", lambda *_: pytest.fail("unexpected external call"))
    assert jev.main([str(wp_file), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["fallback"] is True


def test_fallback_on_api_failure(wp_file, monkeypatch, capsys):
    monkeypatch.setenv("TYPESAFE_API_KEY", SECRET)

    def boom(payload, key):
        raise urllib.error.HTTPError(jev.URL, 401, "bad key", {}, None)

    monkeypatch.setattr(jev, "post", boom)
    assert jev.main([str(wp_file), "--json", "--allow-external"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["fallback"] is True and SECRET not in out
