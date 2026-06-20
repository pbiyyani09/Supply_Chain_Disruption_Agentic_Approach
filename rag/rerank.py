"""Reranking strategies (Strategy pattern) for retrieved candidates.

Two self-hosted strategies behind the :class:`interfaces.Reranker` Protocol:
  * :class:`CrossEncoderReranker` — fast sentence-transformers cross-encoder
    (default; ~50-100 ms / 20 docs). Optional dependency: if
    ``sentence-transformers`` is not installed it degrades to a no-op.
  * :class:`GemmaReranker` — pointwise LLM reranking via a local Ollama-served
    Gemma model. Heavier; reserved for high-value reranking.

Selection is config-driven (``RERANK_STRATEGY``). Everything is fail-safe: a
missing model/package returns the candidates unranked rather than raising.
"""
from __future__ import annotations

import logging
import re

from rag.config import (
    crossencoder_model,
    gemma_model,
    rerank_enabled,
    rerank_strategy,
)

logger = logging.getLogger(__name__)


class NoOpReranker:
    """Identity reranker — returns candidates unchanged (truncated to ``top_k``)."""

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        """Return the first ``top_k`` candidates unchanged."""
        return candidates[:top_k]


class CrossEncoderReranker:
    """Cross-encoder reranker via sentence-transformers (optional dependency)."""

    def __init__(self, model_name: str | None = None):
        """Store the model name; the model itself is loaded lazily on first use."""
        self._model_name = model_name or crossencoder_model()
        self._model = None
        self._load_failed = False

    def _get_model(self):
        """Lazily load the CrossEncoder, or return None if unavailable."""
        if self._model is not None or self._load_failed:
            return self._model
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        except Exception as exc:  # pragma: no cover - depends on optional dep
            logger.warning("[Rerank] cross-encoder unavailable (%s) — passthrough", exc)
            self._load_failed = True
        return self._model

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        """Score each candidate against the query and return the top ``top_k``."""
        if not candidates:
            return []
        model = self._get_model()
        if model is None:
            return candidates[:top_k]
        try:
            pairs = [(query, c.get("content", "")) for c in candidates]
            scores = model.predict(pairs)
            order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
            return [{**candidates[i], "rerank_score": float(scores[i])} for i in order[:top_k]]
        except Exception as exc:
            logger.warning("[Rerank] cross-encoder predict failed (%s) — passthrough", exc)
            return candidates[:top_k]


class GemmaReranker:
    """Pointwise LLM reranker via a local Ollama-served Gemma model."""

    def __init__(self, model: str | None = None):
        """Store the Ollama model id (loaded/served by Ollama, not in-process)."""
        self._model = model or gemma_model()

    def _score_one(self, query: str, document: str) -> int:
        """Ask Gemma to rate one document's relevance 1-10; 0 on failure."""
        try:
            from ollama import chat

            resp = chat(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Rate how relevant the DOCUMENT is to the QUERY on a 1-10 scale. "
                            "Reply with a single integer only.\n\n"
                            f"QUERY: {query}\nDOCUMENT: {document[:1500]}"
                        ),
                    }
                ],
                options={"temperature": 0},
            )
            text = resp["message"]["content"].strip()
            match = re.search(r"\d+", text)
            return int(match.group()) if match else 0
        except Exception as exc:  # pragma: no cover - needs a running Ollama
            logger.warning("[Rerank] Gemma score failed (%s)", exc)
            return 0

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        """Score each candidate with Gemma and return the top ``top_k``."""
        if not candidates:
            return []
        scored = [(c, self._score_one(query, c.get("content", ""))) for c in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [{**c, "rerank_score": float(s)} for c, s in scored[:top_k]]


def get_reranker():
    """Return the configured reranker strategy instance (factory).

    Returns:
        A :class:`interfaces.Reranker` — ``CrossEncoderReranker`` (default),
        ``GemmaReranker``, or ``NoOpReranker`` per ``RERANK_STRATEGY``.
    """
    strategy = rerank_strategy()
    if strategy == "gemma":
        return GemmaReranker()
    if strategy in {"none", "noop", "off"}:
        return NoOpReranker()
    return CrossEncoderReranker()


def rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """Rerank candidates with the configured strategy when ``RERANK_ENABLED``.

    Args:
        query: The search query.
        candidates: Retrieved candidate dicts.
        top_k: Number of results to return.

    Returns:
        Reranked top-``top_k`` candidates, or the first ``top_k`` unchanged when
        reranking is disabled.
    """
    if not rerank_enabled() or not candidates:
        return candidates[:top_k]
    return get_reranker().rerank(query, candidates, top_k)
