"""Unit tests for reranking strategies (models mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock

import interfaces
import rag.rerank as rerank

_CANDIDATES = [
    {"kind": "events", "doc_id": "a", "content": "irrelevant filler"},
    {"kind": "events", "doc_id": "b", "content": "Red Sea shipping disruption"},
    {"kind": "events", "doc_id": "c", "content": "minor note"},
]


def test_rerank_disabled_is_passthrough(monkeypatch):
    monkeypatch.delenv("RERANK_ENABLED", raising=False)
    out = rerank.rerank("Red Sea", _CANDIDATES, top_k=2)
    assert [c["doc_id"] for c in out] == ["a", "b"]  # unchanged order, truncated


def test_noop_reranker():
    out = rerank.NoOpReranker().rerank("q", _CANDIDATES, top_k=2)
    assert len(out) == 2


def test_crossencoder_reorders_by_score(monkeypatch):
    reranker = rerank.CrossEncoderReranker()
    fake_model = MagicMock()
    # scores: a=0.1, b=0.9, c=0.2  → order b, c, a
    fake_model.predict.return_value = [0.1, 0.9, 0.2]
    monkeypatch.setattr(reranker, "_get_model", lambda: fake_model)

    out = reranker.rerank("Red Sea", _CANDIDATES, top_k=2)
    assert [c["doc_id"] for c in out] == ["b", "c"]
    assert out[0]["rerank_score"] == 0.9


def test_crossencoder_missing_model_passthrough(monkeypatch):
    reranker = rerank.CrossEncoderReranker()
    monkeypatch.setattr(reranker, "_get_model", lambda: None)
    out = reranker.rerank("q", _CANDIDATES, top_k=3)
    assert [c["doc_id"] for c in out] == ["a", "b", "c"]


def test_gemma_reranker_orders_by_score(monkeypatch):
    reranker = rerank.GemmaReranker()
    scores = {"irrelevant filler": 2, "Red Sea shipping disruption": 9, "minor note": 4}
    monkeypatch.setattr(reranker, "_score_one", lambda q, d: scores[d])

    out = reranker.rerank("Red Sea", _CANDIDATES, top_k=2)
    assert [c["doc_id"] for c in out] == ["b", "c"]


def test_get_reranker_strategy_selection(monkeypatch):
    monkeypatch.setenv("RERANK_STRATEGY", "gemma")
    assert isinstance(rerank.get_reranker(), rerank.GemmaReranker)
    monkeypatch.setenv("RERANK_STRATEGY", "none")
    assert isinstance(rerank.get_reranker(), rerank.NoOpReranker)
    monkeypatch.setenv("RERANK_STRATEGY", "crossencoder")
    assert isinstance(rerank.get_reranker(), rerank.CrossEncoderReranker)


def test_strategies_satisfy_protocol():
    assert isinstance(rerank.NoOpReranker(), interfaces.Reranker)
    assert isinstance(rerank.CrossEncoderReranker(), interfaces.Reranker)
    assert isinstance(rerank.GemmaReranker(), interfaces.Reranker)
