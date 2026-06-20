"""Agent 2 — Risk Scorer.

For each new event, geo-matches it against the supplier network and uses
Gemini to produce a calibrated 1–10 risk score per supplier.
Batches up to 5 suppliers per Gemini call to control API costs.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from google.genai import types
from sqlalchemy.orm import Session

from data.geo_matcher import match_suppliers_to_event
from data.industry_profiles import get_risk_context
from data.tavily_research import confirm_medium_event, supplier_deep_search
from data.tavily_research import is_enabled as tavily_enabled
from db.crud import (
    create_risk_score,
    get_recent_events,
    risk_score_exists,
)
from db.database import SessionLocal
from db.models import Event, Supplier
from guardrails.injection import guard_scraped_text
from providers import get_gemini_client, get_model_name
from rag.retrieval import format_context, retrieve_best
from schemas import SupplierRiskScore, parse_list

logger = logging.getLogger(__name__)

_SCORE_PROMPT = (Path(__file__).parent.parent / "prompts" / "score_risk.txt").read_text()

_client = get_gemini_client()
_MODEL = get_model_name()
HIGH_RISK_THRESHOLD = int(os.getenv("HIGH_RISK_THRESHOLD", "7"))
BATCH_SIZE = 5  # max suppliers per Gemini call


def _live_supplier_context(suppliers: list[Supplier]) -> str:
    """Build a `LIVE CONTEXT` prompt block from per-supplier Tavily searches.

    The heaviest Tavily placement (up to one search per supplier), so it is
    gated by both ``TAVILY_ENABLED`` and an explicit ``TAVILY_RISK_SEARCH`` flag
    (default off). Snippets pass the injection guardrail before inclusion.

    Args:
        suppliers: Suppliers in the current scoring batch.

    Returns:
        A prompt-ready block (leading blank lines), or ``""`` when disabled or no
        usable signal is found.
    """
    if not (tavily_enabled() and os.getenv("TAVILY_RISK_SEARCH", "false").lower() in {"1", "true", "yes"}):
        return ""

    # Cost cap: only the first N suppliers in the batch get a (credit-costing) search.
    max_suppliers = int(os.getenv("TAVILY_RISK_SEARCH_MAX_SUPPLIERS", "3"))
    blocks = []
    for s in suppliers[:max_suppliers]:
        hits = supplier_deep_search(s.name, s.country_code, s.region or "", s.product_category)
        snippets = [guard_scraped_text(h.get("content", ""))[:200] for h in hits]
        snippets = [x for x in snippets if x]
        if snippets:
            blocks.append(f"{s.name}: " + " | ".join(snippets[:2]))

    if not blocks:
        return ""
    return (
        "\n\nLIVE CONTEXT (recent web signals per supplier — let this inform, "
        "not override, your score):\n" + "\n".join(blocks)
    )


def _score_batch(
    event: Event,
    suppliers: list[Supplier],
    industry: str = "electronics",
    extra_context: str = "",
) -> list[dict]:
    """Score a batch of suppliers against one event in a single Gemini call.

    Args:
        event: The disruption event being scored.
        suppliers: Up to ``BATCH_SIZE`` suppliers to score in this call.
        industry: Industry whose risk context is injected into the prompt.
        extra_context: Optional retrieved "similar past events" block (RAG) to
            prepend supplier-level priors; empty when RAG is off.

    Returns:
        A list of dicts (one per supplier, schema
        :class:`schemas.SupplierRiskScore`) in the input order, or ``[]`` on
        repeated Gemini failure.
    """
    supplier_profiles = [
        {
            "name": s.name,
            "country_code": s.country_code,
            "region": s.region or "",
            "product_category": s.product_category,
            "tier": s.tier,
        }
        for s in suppliers
    ]

    event_context = {
        "headline": event.headline,
        "category": event.category,
        "affected_countries": event.affected_countries,
        "severity_hint": event.severity_hint,
        "brief_reason": event.brief_reason or "",
    }

    industry_context = get_risk_context(industry)
    prompt = (
        f"{_SCORE_PROMPT}\n\n"
        f"INDUSTRY CONTEXT:\n{industry_context}\n\n"
        f"EVENT:\n{json.dumps(event_context, indent=2)}\n\n"
        f"SUPPLIERS TO SCORE (in order):\n{json.dumps(supplier_profiles, indent=2)}"
        f"{extra_context}"
        f"{_live_supplier_context(suppliers)}"
    )

    for attempt in range(3):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[SupplierRiskScore],
                    temperature=0.1,
                    max_output_tokens=4096,
                ),
            )
            return [r.model_dump() for r in parse_list(response, SupplierRiskScore)]
        except Exception as exc:
            wait = 2 ** attempt * 3
            logger.warning("[RiskScorer] attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
            if attempt < 2:
                time.sleep(wait)
    return []


def score_event(db: Session, event: Event, industry: str = "electronics") -> list[dict]:
    """Score all matching suppliers for a single event. Returns list of score records."""
    matched = match_suppliers_to_event(db, event.affected_countries or [])
    if not matched:
        return []

    # Filter out already-scored pairs
    to_score = [s for s in matched if not risk_score_exists(db, event.id, s.id)]
    if not to_score:
        return []

    created_scores = []
    # Placement 4 budget: bound the number of corroboration searches per event.
    medium_low = int(os.getenv("TAVILY_MEDIUM_LOW", "4"))
    checks_left = int(os.getenv("TAVILY_MEDIUM_MAX_CHECKS", "5"))

    # RAG prior: similar past events/briefs (retrieved once per event, no-op if RAG off).
    prior = format_context(retrieve_best(event.headline, kinds=("events", "briefs"), top_k=3))
    extra_context = f"\n\nSIMILAR PAST EVENTS (institutional memory):\n{prior}" if prior else ""

    for i in range(0, len(to_score), BATCH_SIZE):
        batch = to_score[i : i + BATCH_SIZE]
        results = _score_batch(event, batch, industry=industry, extra_context=extra_context)

        for supplier, result in zip(batch, results, strict=False):
            score_val = int(result.get("score", 1))
            reasoning = result.get("reasoning", "")

            # Placement 4: corroborate borderline-MEDIUM scores; elevate +1 when
            # multiple recent sources confirm the event.
            if tavily_enabled() and checks_left > 0 and medium_low <= score_val < HIGH_RISK_THRESHOLD:
                checks_left -= 1
                verdict = confirm_medium_event(event.headline, event.affected_countries or [])
                if verdict.get("elevate"):
                    score_val = min(score_val + 1, HIGH_RISK_THRESHOLD)
                    reasoning += f" [Tavily: {verdict['signal_count']} corroborating recent sources → elevated]"

            data = {
                "event_id": event.id,
                "supplier_id": supplier.id,
                "score": score_val,
                "impact_window": result.get("impact_window", "unknown"),
                "affected_tiers": result.get("affected_tiers", [supplier.tier]),
                "reasoning": reasoning,
            }
            rs = create_risk_score(db, data)
            created_scores.append(rs)
            logger.info(
                "[RiskScorer] %s → %s score=%d (%s)",
                supplier.name,
                event.headline[:50],
                score_val,
                result.get("impact_window", "?"),
            )

    return created_scores


def run_risk_scorer(industry: str = "electronics") -> list:
    """Score all recent unscored events. Called after signal monitor completes."""
    db: Session = SessionLocal()
    all_scores = []
    try:
        events = get_recent_events(db, limit=50)
        for event in events:
            scores = score_event(db, event, industry=industry)
            all_scores.extend(scores)
        # Expunge before close so callers can read scalar attributes
        db.expunge_all()
    finally:
        db.close()
    return all_scores


if __name__ == "__main__":
    from observability import setup_observability

    setup_observability()
    logging.basicConfig(level=logging.INFO)
    run_risk_scorer()
