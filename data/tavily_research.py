"""Tavily web-research client (full-article extraction + deep live search).

Design rationale (Phase 1):
  * **Opt-in & fail-safe** — gated by ``TAVILY_ENABLED`` and the presence of
    ``TAVILY_API_KEY``. Every public function early-returns an empty value when
    disabled, when the key is missing, when the SDK is absent, or on any API
    error — matching the project's "never crash the pipeline" convention.
  * **Cost-aware** — Tavily bills per call/credit. Extraction is *batched*
    (≤ ``TAVILY_MAX_EXTRACT_URLS`` per run) and bodies are truncated; searches
    use ``search_depth="basic"`` with a small ``max_results``. The heaviest
    placement (per-supplier search) is gated by an extra ``TAVILY_RISK_SEARCH``
    flag in the risk scorer.
  * **Adapter** — wraps the Tavily SDK behind a stable, project-shaped surface so
    callers never touch the raw client (and it is trivially mockable in tests).

Complements (does not replace) Gemini Google Search grounding, which remains the
in-brief web tool of the Impact Analyst.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_client: object | None = None
_client_init_attempted = False


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to ``default``."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def is_enabled() -> bool:
    """Return True when Tavily is switched on and usable.

    Requires ``TAVILY_ENABLED`` truthy and ``TAVILY_API_KEY`` present.
    """
    enabled = os.getenv("TAVILY_ENABLED", "false").lower() in {"1", "true", "yes"}
    return enabled and bool(os.getenv("TAVILY_API_KEY"))


def _get_client():
    """Lazily construct and cache the Tavily client, or return None.

    Returns None (and logs once) if Tavily is disabled, the key is missing, or
    the ``tavily-python`` package is not installed — so import of this module and
    its callers never fails for a missing optional dependency.
    """
    global _client, _client_init_attempted
    if not is_enabled():
        return None
    if _client is not None:
        return _client
    if _client_init_attempted:
        return _client
    _client_init_attempted = True
    try:
        from tavily import TavilyClient

        _client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    except Exception as exc:  # pragma: no cover - depends on optional dep/network
        logger.warning("[Tavily] client init failed (%s) — Tavily disabled this run", exc)
        _client = None
    return _client


def extract_article_bodies(urls: list[str]) -> dict[str, str]:
    """Extract truncated article bodies for a batch of URLs.

    Batched into a single Tavily ``extract`` call (capped at
    ``TAVILY_MAX_EXTRACT_URLS``, default 10) to bound credit spend. Failed URLs
    simply map to ``""``.

    Args:
        urls: Candidate article URLs to fetch full text for.

    Returns:
        A mapping ``{url: body_text}``. Empty dict when Tavily is disabled,
        ``urls`` is empty, or the call fails.
    """
    client = _get_client()
    if client is None or not urls:
        return {}

    max_urls = _env_int("TAVILY_MAX_EXTRACT_URLS", 10)
    char_cap = _env_int("TAVILY_EXTRACT_CHARS", 1500)
    target = urls[:max_urls]

    try:
        resp = client.extract(urls=target, extract_depth="basic")
    except Exception as exc:
        logger.warning("[Tavily] extract failed (%s) — returning no bodies", exc)
        return {}

    bodies: dict[str, str] = {}
    for item in resp.get("results", []) if isinstance(resp, dict) else []:
        url = item.get("url", "")
        raw = (item.get("raw_content") or "").strip()
        if url:
            bodies[url] = raw[:char_cap]
    return bodies


def extract_article_body(url: str) -> str:
    """Extract a single article body. Convenience wrapper over the batch call.

    Args:
        url: The article URL.

    Returns:
        Truncated body text, or ``""`` on failure / when disabled.
    """
    if not url:
        return ""
    return extract_article_bodies([url]).get(url, "")


def supplier_deep_search(
    supplier_name: str,
    country_code: str,
    region: str = "",
    category: str = "",
) -> list[dict]:
    """Search for live supply-chain context about a specific supplier.

    Args:
        supplier_name: Supplier company name.
        country_code: ISO-3166 alpha-2 country code.
        region: Optional region/city for a sharper query.
        category: Optional product category for a sharper query.

    Returns:
        A list of ``{"title", "url", "content"}`` dicts (possibly empty).
    """
    client = _get_client()
    if client is None or not supplier_name:
        return []

    locality = " ".join(p for p in (region, country_code) if p)
    query = (
        f"{supplier_name} {locality} {category} supply chain disruption "
        f"production status OR factory OR shipment news"
    ).strip()
    return _search(client, query, topic="news")


def event_context_search(headline: str, max_results: int | None = None) -> list[dict]:
    """Search the web for context to augment a HIGH-risk impact brief.

    Args:
        headline: The event headline to research.
        max_results: Override for result count (defaults to
            ``TAVILY_SEARCH_MAX_RESULTS``).

    Returns:
        A list of ``{"title", "url", "content"}`` dicts (possibly empty).
    """
    client = _get_client()
    if client is None or not headline:
        return []
    n = max_results if max_results is not None else _env_int("TAVILY_SEARCH_MAX_RESULTS", 3)
    return _search(client, headline, topic="news", max_results=n)


def confirm_medium_event(headline: str, affected_countries: list[str] | None = None) -> dict:
    """Check whether a borderline-MEDIUM event has corroborating recent sources.

    Used by the Risk Scorer to optionally elevate a 4–6 score when multiple
    independent recent sources corroborate the event.

    Args:
        headline: The event headline.
        affected_countries: Optional ISO codes to focus the query.

    Returns:
        ``{"signal_count": int, "snippets": list[str], "elevate": bool}``.
        ``elevate`` is True when ``signal_count >= TAVILY_MEDIUM_ELEVATE_MIN``.
    """
    client = _get_client()
    if client is None or not headline:
        return {"signal_count": 0, "snippets": [], "elevate": False}

    countries = " ".join(affected_countries or [])
    query = f"{headline} {countries}".strip()
    hits = _search(client, query, topic="news", max_results=5, time_range="week")
    snippets = [h["content"][:200] for h in hits if h.get("content")]
    min_signals = _env_int("TAVILY_MEDIUM_ELEVATE_MIN", 2)
    return {
        "signal_count": len(hits),
        "snippets": snippets,
        "elevate": len(hits) >= min_signals,
    }


def _search(
    client,
    query: str,
    topic: str = "general",
    max_results: int = 3,
    time_range: str | None = None,
) -> list[dict]:
    """Run a Tavily search and normalise results to the project shape.

    Args:
        client: An initialised Tavily client.
        query: The search query.
        topic: Tavily topic (``"general"`` | ``"news"`` | ``"finance"``).
        max_results: Number of results to request.
        time_range: Optional recency window (``"day"`` | ``"week"`` | ...).

    Returns:
        A list of ``{"title", "url", "content"}`` dicts (possibly empty).
    """
    kwargs = {"search_depth": "basic", "topic": topic, "max_results": max_results}
    if time_range:
        kwargs["time_range"] = time_range
    try:
        resp = client.search(query=query, **kwargs)
    except Exception as exc:
        logger.warning("[Tavily] search failed (%s) — returning no results", exc)
        return []

    results = resp.get("results", []) if isinstance(resp, dict) else []
    return [
        {
            # Strip newlines + cap length on title/url so an injection payload
            # cannot hide in those fields (content is guarded at the call sites).
            "title": (r.get("title") or "").replace("\n", " ").replace("\r", " ").strip()[:200],
            "url": (r.get("url") or "").replace("\n", " ").replace("\r", " ").strip()[:300],
            "content": (r.get("content") or "").strip(),
        }
        for r in results
    ]
