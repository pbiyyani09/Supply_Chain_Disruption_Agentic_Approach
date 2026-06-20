"""Embedding generation via Google ``gemini-embedding-001``.

Uses the same ``providers.get_gemini_client()`` the agents use. Fail-safe: any
error returns an empty result so callers (indexing/retrieval) degrade to no-op
rather than crashing the pipeline.
"""
from __future__ import annotations

import logging

from google.genai import types

from providers import get_gemini_client
from rag.config import embedding_dim, embedding_model

logger = logging.getLogger(__name__)


def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed a batch of texts with the configured Gemini embedding model.

    Args:
        texts: Texts to embed.
        task_type: Gemini embedding task type, e.g. ``"RETRIEVAL_DOCUMENT"`` for
            stored documents or ``"RETRIEVAL_QUERY"`` for search queries.

    Returns:
        A list of float vectors aligned with ``texts``; ``[]`` on any failure.
    """
    if not texts:
        return []
    try:
        client = get_gemini_client()
        resp = client.models.embed_content(
            model=embedding_model(),
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=embedding_dim(),
            ),
        )
        return [list(e.values) for e in resp.embeddings]
    except Exception as exc:
        logger.warning("[Embeddings] embed failed (%s) — returning no vectors", exc)
        return []


def embed_one(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Embed a single text. Convenience wrapper over :func:`embed`.

    Args:
        text: The text to embed.
        task_type: Gemini embedding task type.

    Returns:
        A single float vector, or ``[]`` on failure.
    """
    if not text:
        return []
    vectors = embed([text], task_type=task_type)
    return vectors[0] if vectors else []
