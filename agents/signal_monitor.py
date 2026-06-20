"""Agent 1 — Signal Monitor.

Fetches raw events from GDELT, NewsAPI, and NOAA, deduplicates them,
then uses Gemini to classify each one as supply-chain-relevant or not.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from google.genai import types
from sqlalchemy.orm import Session

from data.industry_profiles import get_keywords
from data.sources import fetch_all_events, set_industry_keywords
from data.tavily_research import extract_article_bodies
from data.tavily_research import is_enabled as tavily_enabled
from db.crud import create_event, event_exists
from db.database import SessionLocal
from guardrails.injection import guard_scraped_text
from providers import get_gemini_client, get_model_name
from rag.retrieval import index_text
from schemas import EventClassification, parse_object

logger = logging.getLogger(__name__)

_CLASSIFY_PROMPT = (Path(__file__).parent.parent / "prompts" / "classify_event.txt").read_text()

_client = get_gemini_client()
_MODEL = get_model_name()


def _classify_event(headline: str, body: str = "") -> dict:
    """Classify a single news item as supply-chain-relevant or not.

    Args:
        headline: The raw news headline text.
        body: Optional full-article excerpt (from Tavily). When present it is
            appended to the prompt so classification is not headline-blind; when
            absent (extraction disabled/failed), behaviour is unchanged.

    Returns:
        A dict matching :class:`schemas.EventClassification` (category,
        affected_countries, severity_hint, is_supply_chain_relevant,
        brief_reason). On repeated Gemini failure, returns a safe
        not-relevant default rather than raising.
    """
    prompt = f"{_CLASSIFY_PROMPT}\n\nHeadline: {headline}"
    if body:
        prompt += f"\n\nArticle excerpt:\n{body}"
    for attempt in range(3):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=EventClassification,
                    temperature=0.1,
                    max_output_tokens=512,
                ),
            )
            return parse_object(response, EventClassification).model_dump()
        except Exception as exc:
            wait = 2 ** attempt * 3
            logger.warning("Gemini classify attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
            if attempt < 2:
                time.sleep(wait)
    return {
        "category": "logistics",
        "affected_countries": [],
        "severity_hint": "medium",
        "is_supply_chain_relevant": False,
        "brief_reason": "",
    }


def run_signal_monitor(industry: str = "electronics") -> int:
    """Main entry point called by the scheduler. Returns count of new events stored."""
    logger.info("[SignalMonitor] Starting scan (industry=%s)...", industry)
    set_industry_keywords(get_keywords(industry))
    raw_events = fetch_all_events()
    logger.info("[SignalMonitor] Fetched %d candidate events", len(raw_events))

    db: Session = SessionLocal()
    stored = 0
    try:
        # Only consider URLs not already stored, then batch-extract full text
        # once (cost-aware) when Tavily is enabled.
        candidates = [r for r in raw_events if r.get("url") and not event_exists(db, r["url"])]
        bodies: dict[str, str] = {}
        if tavily_enabled() and candidates:
            bodies = extract_article_bodies([r["url"] for r in candidates])
            logger.info("[SignalMonitor] Tavily extracted %d article bodies", len(bodies))

        for raw in candidates:
            url = raw["url"]
            body = guard_scraped_text(bodies.get(url, ""))
            classification = _classify_event(raw["headline"], body)

            if not classification.get("is_supply_chain_relevant", False):
                continue

            event_data = {
                "source": raw["source"],
                "headline": raw["headline"],
                "url": url,
                "category": classification.get("category", "logistics"),
                "affected_countries": classification.get("affected_countries", []),
                "severity_hint": classification.get("severity_hint", "medium"),
                "is_supply_chain_relevant": True,
                "brief_reason": classification.get("brief_reason", ""),
                "published_at": raw.get("published_at"),
            }
            ev = create_event(db, event_data)
            # Index into institutional memory for later RAG (no-op when RAG off).
            index_text("events", ev.id, f"{raw['headline']} {classification.get('brief_reason', '')}".strip())
            stored += 1
            logger.info(
                "[SignalMonitor] Stored: [%s] %s",
                classification.get("category", "?"),
                raw["headline"][:80],
            )
    finally:
        db.close()

    logger.info("[SignalMonitor] Done — %d new events stored", stored)
    return stored


if __name__ == "__main__":
    from observability import setup_observability

    setup_observability()
    logging.basicConfig(level=logging.INFO)
    run_signal_monitor()
