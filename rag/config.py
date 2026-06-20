"""RAG configuration — feature flag and tunables read from the environment.

Centralised here (Single Responsibility) so the embeddings, vector store, and
retrieval modules share one source of truth and stay independently testable.
"""
from __future__ import annotations

import os

DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_EMBEDDING_DIM = 768
DEFAULT_VECTOR_DB_PATH = "./chainwatch_vectors.db"


def rag_enabled() -> bool:
    """Return True when the RAG retrieval layer is switched on.

    Gated by ``RAG_ENABLED`` so retrieval/indexing are a no-op by default and the
    pipeline behaves exactly as before when RAG is off.
    """
    return os.getenv("RAG_ENABLED", "false").lower() in {"1", "true", "yes"}


def embedding_model() -> str:
    """Return the embedding model id (``gemini-embedding-001`` by default)."""
    return os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def embedding_dim() -> int:
    """Return the embedding output dimensionality (768 by default)."""
    try:
        return int(os.getenv("EMBEDDING_DIM", str(DEFAULT_EMBEDDING_DIM)))
    except (TypeError, ValueError):
        return DEFAULT_EMBEDDING_DIM


def vector_db_path() -> str:
    """Return the path to the dedicated sqlite-vec database file.

    Kept separate from the ORM ``DATABASE_URL`` so retrieval works even when the
    main database is PostgreSQL (the documented prod configuration).
    """
    return os.getenv("VECTOR_DB_PATH", DEFAULT_VECTOR_DB_PATH)


# ── Phase 3: fusion + reranking ───────────────────────────────────────────────
def fusion_enabled() -> bool:
    """Return True to enable RAG-Fusion (multi-query expansion + RRF)."""
    return os.getenv("FUSION_ENABLED", "false").lower() in {"1", "true", "yes"}


def fusion_subqueries() -> int:
    """Return the number of extra sub-queries to generate for fusion (default 3)."""
    try:
        return max(1, int(os.getenv("FUSION_SUBQUERIES", "3")))
    except (TypeError, ValueError):
        return 3


def rerank_enabled() -> bool:
    """Return True to re-rank retrieved candidates before use."""
    return os.getenv("RERANK_ENABLED", "false").lower() in {"1", "true", "yes"}


def rerank_strategy() -> str:
    """Return the reranker strategy: ``crossencoder`` (default), ``gemma``, or ``none``."""
    return os.getenv("RERANK_STRATEGY", "crossencoder").lower()


def crossencoder_model() -> str:
    """Return the sentence-transformers cross-encoder model name."""
    return os.getenv("CROSSENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")


def gemma_model() -> str:
    """Return the local Ollama Gemma model id (default ``gemma3:4b``)."""
    return os.getenv("GEMMA_MODEL", "gemma3:4b")
