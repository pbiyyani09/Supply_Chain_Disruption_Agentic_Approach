"""Unit tests for RAG-Fusion (RRF pure logic + query expansion mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock

import rag.fusion as fusion


def test_rrf_ranks_consensus_first():
    # 'b' appears high in both lists → should win; 'a' top of one list only.
    lists = [
        ["a", "b", "c"],
        ["b", "d", "a"],
    ]
    fused = fusion.reciprocal_rank_fusion(lists, k=60)
    ids = [doc for doc, _ in fused]
    assert ids[0] == "b"
    assert set(ids) == {"a", "b", "c", "d"}


def test_rrf_empty():
    assert fusion.reciprocal_rank_fusion([]) == []


def test_expand_queries_includes_original(monkeypatch):
    fake = MagicMock()
    resp = MagicMock()
    resp.parsed = ["Suez blockage impact", "Red Sea shipping halt"]
    resp.text = '["Suez blockage impact", "Red Sea shipping halt"]'
    fake.models.generate_content.return_value = resp
    monkeypatch.setattr(fusion, "get_gemini_client", lambda: fake)

    out = fusion.expand_queries("Red Sea disruption", n=2)
    assert out[0] == "Red Sea disruption"  # original always first
    assert "Suez blockage impact" in out
    assert len(out) <= 3


def test_expand_queries_failure_falls_back(monkeypatch):
    fake = MagicMock()
    fake.models.generate_content.side_effect = Exception("api down")
    monkeypatch.setattr(fusion, "get_gemini_client", lambda: fake)
    assert fusion.expand_queries("query", n=3) == ["query"]


def test_multi_query_search_disabled(monkeypatch):
    monkeypatch.delenv("RAG_ENABLED", raising=False)
    assert fusion.multi_query_search("q") == []
