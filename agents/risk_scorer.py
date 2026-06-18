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

from dotenv import load_dotenv
from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from data.geo_matcher import match_suppliers_to_event
from db.crud import (
    create_risk_score,
    get_recent_events,
    risk_score_exists,
)
from db.database import SessionLocal
from db.models import Event, Supplier

load_dotenv()
logger = logging.getLogger(__name__)

_SCORE_PROMPT = (Path(__file__).parent.parent / "prompts" / "score_risk.txt").read_text()

_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
HIGH_RISK_THRESHOLD = int(os.getenv("HIGH_RISK_THRESHOLD", "7"))
BATCH_SIZE = 5  # max suppliers per Gemini call


def _score_batch(event: Event, suppliers: list[Supplier]) -> list[dict]:
    """Score a batch of suppliers against an event in one Gemini call."""
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

    prompt = (
        f"{_SCORE_PROMPT}\n\n"
        f"EVENT:\n{json.dumps(event_context, indent=2)}\n\n"
        f"SUPPLIERS TO SCORE (in order):\n{json.dumps(supplier_profiles, indent=2)}"
    )

    for attempt in range(3):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=4096,
                ),
            )
            results = json.loads(response.text)
            if isinstance(results, list):
                return results
            for v in results.values():
                if isinstance(v, list):
                    return v
            return []
        except Exception as exc:
            wait = 2 ** attempt * 3
            logger.warning("[RiskScorer] attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
            if attempt < 2:
                time.sleep(wait)
    return []


def score_event(db: Session, event: Event) -> list[dict]:
    """Score all matching suppliers for a single event. Returns list of score records."""
    matched = match_suppliers_to_event(db, event.affected_countries or [])
    if not matched:
        return []

    # Filter out already-scored pairs
    to_score = [s for s in matched if not risk_score_exists(db, event.id, s.id)]
    if not to_score:
        return []

    created_scores = []
    for i in range(0, len(to_score), BATCH_SIZE):
        batch = to_score[i : i + BATCH_SIZE]
        results = _score_batch(event, batch)

        for supplier, result in zip(batch, results):
            score_val = int(result.get("score", 1))
            data = {
                "event_id": event.id,
                "supplier_id": supplier.id,
                "score": score_val,
                "impact_window": result.get("impact_window", "unknown"),
                "affected_tiers": result.get("affected_tiers", [supplier.tier]),
                "reasoning": result.get("reasoning", ""),
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


def run_risk_scorer() -> list:
    """Score all recent unscored events. Called after signal monitor completes."""
    db: Session = SessionLocal()
    all_scores = []
    try:
        events = get_recent_events(db, limit=50)
        for event in events:
            scores = score_event(db, event)
            all_scores.extend(scores)
        # Expunge before close so callers can read scalar attributes
        db.expunge_all()
    finally:
        db.close()
    return all_scores


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_risk_scorer()
