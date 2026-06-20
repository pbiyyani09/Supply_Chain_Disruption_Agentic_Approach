"""Unit tests for the Gemma faithfulness judge (Ollama mocked)."""
from __future__ import annotations

import json

from guardrails import judge


def _ollama_reply(payload: dict):
    return {"message": {"content": json.dumps(payload)}}


def test_disabled_returns_pass(monkeypatch):
    monkeypatch.delenv("JUDGE_ENABLED", raising=False)
    out = judge.check_faithfulness("brief", ["ctx"])
    assert out["verdict"] == "PASS"


def test_flag_when_unsupported(monkeypatch):
    monkeypatch.setenv("JUDGE_ENABLED", "true")
    monkeypatch.setattr(
        "ollama.chat",
        lambda **k: _ollama_reply(
            {"verdict": "FLAG", "reason": "invented 80% figure", "unsupported_claims": ["80%"]}
        ),
    )
    out = judge.check_faithfulness("A fire destroyed 80% of capacity.", ["A minor fire, no impact."])
    assert out["verdict"] == "FLAG"
    assert "80%" in out["unsupported_claims"]


def test_pass_when_grounded(monkeypatch):
    monkeypatch.setenv("JUDGE_ENABLED", "true")
    monkeypatch.setattr(
        "ollama.chat",
        lambda **k: _ollama_reply({"verdict": "PASS", "reason": "ok", "unsupported_claims": []}),
    )
    out = judge.check_faithfulness("Grounded brief.", ["supporting context"])
    assert out["verdict"] == "PASS"


def test_error_fails_open(monkeypatch):
    monkeypatch.setenv("JUDGE_ENABLED", "true")

    def boom(**_k):
        raise RuntimeError("no ollama")

    monkeypatch.setattr("ollama.chat", boom)
    out = judge.check_faithfulness("brief", ["ctx"])
    assert out["verdict"] == "PASS"  # fail-open, never blocks
