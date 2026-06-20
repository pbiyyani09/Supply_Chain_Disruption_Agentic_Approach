"""Indexing and semantic retrieval over events, briefs, and the knowledge base.

This is the public face of the RAG layer used by agents and the dashboard chat.
All functions are gated by ``RAG_ENABLED`` and degrade to a no-op / empty result
when retrieval is disabled or embeddings are unavailable.
"""
from __future__ import annotations

import logging

from guardrails.injection import guard_scraped_text
from rag import fusion, rerank, vectorstore
from rag.config import fusion_enabled, rag_enabled, rerank_enabled
from rag.embeddings import embed_one

logger = logging.getLogger(__name__)


def index_text(kind: str, doc_id: str, content: str) -> bool:
    """Embed and store one document for later retrieval.

    Args:
        kind: One of :data:`rag.vectorstore.KINDS` (``events``/``briefs``/``kb``).
        doc_id: Stable unique id for the document.
        content: The text to embed and store.

    Returns:
        True if the document was indexed, else False (disabled / empty / error).
    """
    if not rag_enabled() or not content or not doc_id:
        return False
    vec = embed_one(content, task_type="RETRIEVAL_DOCUMENT")
    if not vec:
        return False
    return vectorstore.upsert(kind, doc_id, content, vec)


def search(
    query_text: str,
    kinds: tuple[str, ...] = vectorstore.KINDS,
    top_k: int = 5,
) -> list[dict]:
    """Semantic search across one or more document kinds.

    Embeds the query once, queries each kind, then merges by ascending distance.

    Args:
        query_text: The natural-language query.
        kinds: Which document kinds to search.
        top_k: Max results to return overall.

    Returns:
        A list of ``{"kind", "doc_id", "content", "distance"}`` dicts, best first;
        ``[]`` when RAG is disabled or nothing is found.
    """
    if not rag_enabled() or not query_text:
        return []
    vec = embed_one(query_text, task_type="RETRIEVAL_QUERY")
    if not vec:
        return []
    results: list[dict] = []
    for kind in kinds:
        results.extend(vectorstore.query(kind, vec, k=top_k))
    results.sort(key=lambda r: r["distance"])
    return results[:top_k]


def retrieve_best(
    query: str,
    kinds: tuple[str, ...] = vectorstore.KINDS,
    top_k: int = 5,
) -> list[dict]:
    """High-level retrieval: optional RAG-Fusion, then optional reranking.

    Composes the Phase-2 vector search with the Phase-3 fusion and rerank stages.
    With both flags off this is equivalent to :func:`search`, so agents can call
    it unconditionally and behaviour only changes when fusion/rerank are enabled.

    Args:
        query: The natural-language query.
        kinds: Document kinds to search.
        top_k: Final number of results to return.

    Returns:
        The best ``top_k`` candidate dicts, or ``[]`` when RAG is disabled.
    """
    if not rag_enabled() or not query:
        return []
    # Retrieve a wider pool first so the reranker has something to work with.
    pool = max(top_k * 4, 20)
    if fusion_enabled():
        candidates = fusion.multi_query_search(query, kinds=kinds, top_k=pool)
    else:
        candidates = search(query, kinds=kinds, top_k=pool)
    if rerank_enabled():
        return rerank.rerank(query, candidates, top_k=top_k)
    return candidates[:top_k]


def format_context(results: list[dict], max_chars: int = 400) -> str:
    """Render retrieval results into a compact prompt block.

    Args:
        results: Output of :func:`search`.
        max_chars: Truncation per snippet.

    Returns:
        A newline-joined block, or ``""`` when there are no results. Each snippet
        is re-screened through the injection guardrail (defense-in-depth) so any
        scraped-derived indexed content cannot smuggle instructions back into a
        prompt on the retrieval round-trip.
    """
    if not results:
        return ""
    lines = []
    for r in results:
        safe = guard_scraped_text(r.get("content") or "")
        if safe:
            lines.append(f"- [{r['kind']}] {safe[:max_chars]}")
    return "\n".join(lines)
