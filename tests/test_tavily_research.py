"""Unit tests for the Tavily web-research module (client mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock

import data.tavily_research as tv


def test_disabled_is_noop(monkeypatch):
    monkeypatch.delenv("TAVILY_ENABLED", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    assert tv.is_enabled() is False
    assert tv.extract_article_bodies(["http://x"]) == {}
    assert tv.supplier_deep_search("Acme", "CN") == []
    assert tv.event_context_search("headline") == []
    assert tv.confirm_medium_event("headline", ["CN"]) == {
        "signal_count": 0,
        "snippets": [],
        "elevate": False,
    }


def test_extract_truncates_body(monkeypatch):
    monkeypatch.setenv("TAVILY_EXTRACT_CHARS", "50")
    fake = MagicMock()
    fake.extract.return_value = {
        "results": [{"url": "http://a", "raw_content": "x" * 5000}],
        "failed_results": [],
    }
    monkeypatch.setattr(tv, "_get_client", lambda: fake)

    bodies = tv.extract_article_bodies(["http://a"])
    assert len(bodies["http://a"]) == 50


def test_extract_caps_url_count(monkeypatch):
    monkeypatch.setenv("TAVILY_MAX_EXTRACT_URLS", "2")
    fake = MagicMock()
    fake.extract.return_value = {"results": [], "failed_results": []}
    monkeypatch.setattr(tv, "_get_client", lambda: fake)

    tv.extract_article_bodies(["u1", "u2", "u3", "u4"])
    _, kwargs = fake.extract.call_args
    assert kwargs["urls"] == ["u1", "u2"]


def test_extract_failure_returns_empty(monkeypatch):
    fake = MagicMock()
    fake.extract.side_effect = Exception("network down")
    monkeypatch.setattr(tv, "_get_client", lambda: fake)

    assert tv.extract_article_bodies(["http://a"]) == {}


def test_search_normalises_shape(monkeypatch):
    fake = MagicMock()
    fake.search.return_value = {
        "results": [
            {"title": "T1", "url": "http://1", "content": "  body one  "},
            {"title": "T2", "url": "http://2", "content": "body two"},
        ]
    }
    monkeypatch.setattr(tv, "_get_client", lambda: fake)

    out = tv.event_context_search("Suez closure")
    assert out == [
        {"title": "T1", "url": "http://1", "content": "body one"},
        {"title": "T2", "url": "http://2", "content": "body two"},
    ]


def test_confirm_medium_event_elevates(monkeypatch):
    monkeypatch.setenv("TAVILY_MEDIUM_ELEVATE_MIN", "2")
    fake = MagicMock()
    fake.search.return_value = {
        "results": [
            {"title": "a", "url": "u1", "content": "c1"},
            {"title": "b", "url": "u2", "content": "c2"},
        ]
    }
    monkeypatch.setattr(tv, "_get_client", lambda: fake)

    verdict = tv.confirm_medium_event("Port strike", ["CN"])
    assert verdict["signal_count"] == 2
    assert verdict["elevate"] is True
    assert len(verdict["snippets"]) == 2
