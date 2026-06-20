"""RAG-Fusion: multi-query expansion + Reciprocal Rank Fusion (RRF).

A single query phrasing misses synonyms common in supply-chain jargon ("Suez
blockage" vs "Red Sea disruption"). We expand the query into several sub-queries
(via Gemini), retrieve candidates for each, and merge the ranked lists with RRF —
a rank-based fusion that needs no score calibration across sources.

All functions are fail-safe: any failure falls back to single-query behaviour or
an empty result rather than raising.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict

from google.genai import types

from providers import get_gemini_client, get_model_name
from rag import vectorstore
from rag.config import fusion_subqueries, rag_enabled
from rag.embeddings import embed

logger = logging.getLogger(__name__)


def expand_queries(query: str, n: int | None = None) -> list[str]:
    """Expand a query into the original plus ``n`` paraphrase sub-queries.

    Args:
        query: The original search query.
        n: Number of extra sub-queries (defaults to ``FUSION_SUBQUERIES``).

    Returns:
        ``[query, *paraphrases]`` (always includes the original). Returns
        ``[query]`` on any failure.
    """
    n = n if n is not None else fusion_subqueries()
    if n <= 0 or not query:
        return [query] if query else []
    try:
        client = get_gemini_client()
        prompt = (
            f"Generate {n} alternative search queries (paraphrases, synonyms, related "
            f"supply-chain phrasings) for this query. Return ONLY a JSON array of strings.\n\n"
            f"Query: {query}"
        )
        resp = client.models.generate_content(
            model=get_model_name(),
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[str],
                temperature=0.3,
                max_output_tokens=512,
            ),
        )
        parsed = getattr(resp, "parsed", None)
        extra = parsed if isinstance(parsed, list) else json.loads(resp.text)
        extra = [q for q in extra if isinstance(q, str) and q.strip() and q != query]
        return [query, *extra][: n + 1]
    except Exception as exc:
        logger.warning("[Fusion] query expansion failed (%s) — using original query only", exc)
        return [query]


def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Merge ranked id-lists with RRF: ``score(d) = Σ 1/(k + rank_i(d))``.

    Args:
        ranked_lists: Each inner list is doc ids ordered best-first.
        k: RRF damping constant (canonical 60).

    Returns:
        ``[(doc_id, score), ...]`` sorted by descending fused score.
    """
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def multi_query_search(
    query: str,
    kinds: tuple[str, ...] = vectorstore.KINDS,
    top_k: int = 20,
) -> list[dict]:
    """Fused vector retrieval: expand → per-sub-query search → RRF merge.

    Args:
        query: The original query.
        kinds: Document kinds to search.
        top_k: Max merged results to return.

    Returns:
        Merged candidate dicts (each with an added ``rrf_score``), best-first;
        ``[]`` when RAG is disabled or nothing is found.
    """
    if not rag_enabled() or not query:
        return []
    subqueries = expand_queries(query)
    vectors = embed(subqueries, task_type="RETRIEVAL_QUERY")
    if not vectors:
        return []

    ranked_lists: list[list[str]] = []
    by_key: dict[str, dict] = {}
    for vec in vectors:
        for kind in kinds:
            ids = []
            for hit in vectorstore.query(kind, vec, k=top_k):
                key = f"{hit['kind']}:{hit['doc_id']}"
                by_key[key] = hit
                ids.append(key)
            if ids:
                ranked_lists.append(ids)

    fused = reciprocal_rank_fusion(ranked_lists)
    out = []
    for key, score in fused[:top_k]:
        item = dict(by_key[key])
        item["rrf_score"] = score
        out.append(item)
    return out
