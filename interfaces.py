"""Shared structural interfaces (Protocols) for swappable strategy components.

Introduced in Phase 3 once there is genuinely more than one implementation to
abstract over (cross-encoder vs Gemma reranking) — avoiding premature
abstraction. Agents/retrieval depend on these Protocols, not concrete classes
(Dependency Inversion), which keeps strategies interchangeable (Open/Closed) and
trivially mockable in tests.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Reranker(Protocol):
    """Re-orders retrieved candidates by relevance to a query."""

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        """Return ``candidates`` re-ordered best-first, truncated to ``top_k``.

        Args:
            query: The user/search query.
            candidates: Retrieval results, each a dict with at least ``content``.
            top_k: Maximum number of results to return.

        Returns:
            A re-ordered, truncated list of the same dicts.
        """
        ...
