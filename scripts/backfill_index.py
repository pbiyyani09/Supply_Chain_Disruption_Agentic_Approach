"""Backfill the RAG vector store from existing DB rows + the static knowledge base.

Run once (or after enabling RAG) to populate institutional memory:

    RAG_ENABLED=true python -m scripts.backfill_index

Indexes:
  * events  — existing supply-chain events (headline + reason)
  * briefs  — existing alert briefs
  * kb      — industry profiles, response playbooks, seasonal risk windows

No-op (with a clear message) unless ``RAG_ENABLED`` is set, so it never embeds
or spends credits by accident.
"""
from __future__ import annotations

import logging

from data.industry_profiles import INDUSTRY_PROFILES
from data.playbooks import PLAYBOOKS
from data.seasonal_calendar import SEASONAL_WINDOWS
from db.crud import get_recent_alerts, get_recent_events
from db.database import SessionLocal
from rag.config import rag_enabled
from rag.retrieval import index_text

logger = logging.getLogger(__name__)


def _kb_chunks() -> list[tuple[str, str]]:
    """Build (doc_id, text) chunks from the static knowledge base."""
    chunks: list[tuple[str, str]] = []

    for key, prof in INDUSTRY_PROFILES.items():
        text = (
            f"Industry {prof.get('label', key)}: {prof.get('description', '')}. "
            f"Key countries: {', '.join(prof.get('key_countries', []))}. "
            f"Risk context: {prof.get('risk_context', '')}"
        )
        chunks.append((f"industry:{key}", text))

    for industry, by_risk in PLAYBOOKS.items():
        for risk_type, actions in by_risk.items():
            text = f"Playbook — {industry} / {risk_type}: " + " ".join(actions)
            chunks.append((f"playbook:{industry}:{risk_type}", text))

    for w in SEASONAL_WINDOWS:
        text = (
            f"Seasonal risk '{w.get('title', '')}' ({w.get('risk_type', '')}, "
            f"{w.get('severity', '')}): {w.get('description', '')} "
            f"Regions: {', '.join(w.get('region_codes', []))}."
        )
        chunks.append((f"seasonal:{w.get('title', '')}", text))

    return chunks


def backfill() -> dict[str, int]:
    """Index events, briefs, and KB chunks into the vector store.

    Returns:
        Counts indexed per kind, e.g. ``{"events": 12, "briefs": 4, "kb": 60}``.
    """
    counts = {"events": 0, "briefs": 0, "kb": 0}

    db = SessionLocal()
    try:
        for ev in get_recent_events(db, limit=1000):
            text = f"{ev.headline} {ev.brief_reason or ''}".strip()
            if index_text("events", ev.id, text):
                counts["events"] += 1
        for alert in get_recent_alerts(db, limit=1000):
            if alert.brief and index_text("briefs", alert.risk_score_id, alert.brief):
                counts["briefs"] += 1
    finally:
        db.close()

    for doc_id, text in _kb_chunks():
        if index_text("kb", doc_id, text):
            counts["kb"] += 1

    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not rag_enabled():
        logger.warning("RAG_ENABLED is not set — nothing to backfill. Set RAG_ENABLED=true and retry.")
    else:
        result = backfill()
        logger.info("[Backfill] Indexed: %s", result)
