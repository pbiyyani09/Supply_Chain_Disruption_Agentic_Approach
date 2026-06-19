"""Agent 1 — Signal Monitor.

Fetches raw events from GDELT, NewsAPI, and NOAA, deduplicates them,
then uses Gemini to classify each one as supply-chain-relevant or not.
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

from data.industry_profiles import get_keywords
from data.sources import fetch_all_events, set_industry_keywords
from db.crud import create_event, event_exists
from db.database import SessionLocal

load_dotenv()
logger = logging.getLogger(__name__)

_CLASSIFY_PROMPT = (Path(__file__).parent.parent / "prompts" / "classify_event.txt").read_text()

_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def _classify_event(headline: str) -> dict:
    """Send a single headline to Gemini for classification."""
    prompt = f"{_CLASSIFY_PROMPT}\n\nHeadline: {headline}"
    for attempt in range(3):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=512,
                ),
            )
            return json.loads(response.text)
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
        for raw in raw_events:
            url = raw.get("url", "")
            if not url or event_exists(db, url):
                continue

            classification = _classify_event(raw["headline"])

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
            create_event(db, event_data)
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
    logging.basicConfig(level=logging.INFO)
    run_signal_monitor()
