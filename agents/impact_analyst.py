"""Agent 3 — Impact Analyst.

Triggered only for HIGH risk scores (≥ threshold). Uses Gemini with
Google Search grounding (replaces Tavily) to deep-research the event
and write a structured 3-paragraph procurement brief.

Google Search grounding is a native Gemini capability — no separate
search API key required. It's available via Google AI Studio at no
extra cost up to generous limits.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from db.models import Event, RiskScore, Supplier

load_dotenv()
logger = logging.getLogger(__name__)

_BRIEF_PROMPT = (Path(__file__).parent.parent / "prompts" / "write_brief.txt").read_text()

_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def _research_and_write_brief(
    event: Event, supplier: Supplier, risk_score: RiskScore
) -> tuple[str, list[str]]:
    """
    Uses Gemini with Google Search grounding to research the event
    and write the 3-paragraph brief.

    Returns (brief_text, alternatives_list).
    """
    user_prompt = (
        f"Write a supply chain risk brief about the following HIGH-severity event "
        f"(risk score: {risk_score.score}/10).\n\n"
        f"EVENT:\n"
        f"  Headline: {event.headline}\n"
        f"  Category: {event.category}\n"
        f"  Affected countries: {', '.join(event.affected_countries or [])}\n"
        f"  Severity: {event.severity_hint}\n\n"
        f"AFFECTED SUPPLIER:\n"
        f"  Name: {supplier.name}\n"
        f"  Country: {supplier.country_code} ({supplier.region or 'N/A'})\n"
        f"  Product: {supplier.product_category}\n"
        f"  Tier: {supplier.tier}\n"
        f"  Impact window: {risk_score.impact_window}\n\n"
        f"Scoring reasoning: {risk_score.reasoning}\n\n"
        f"Search the web for the latest developments on this event, then write the brief."
    )

    for attempt in range(3):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_BRIEF_PROMPT,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )
            brief_text = response.text.strip()
            alternatives = _extract_alternatives(brief_text)
            return brief_text, alternatives
        except Exception as exc:
            wait = 2 ** attempt * 3
            logger.warning("[ImpactAnalyst] attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
            if attempt < 2:
                time.sleep(wait)

    fallback = (
        f"{event.headline} — Risk score {risk_score.score}/10 for {supplier.name}. "
        f"Impact window: {risk_score.impact_window}. {risk_score.reasoning}"
    )
    return fallback, []


def _extract_alternatives(brief_text: str) -> list[str]:
    """Pull alternative region names from the brief's third paragraph."""
    lower = brief_text.lower()
    marker = "alternatives:"
    idx = lower.find(marker)
    if idx == -1:
        return []
    after = brief_text[idx + len(marker):].strip()
    # Take everything up to the next period or end of paragraph
    segment = after.split(".")[0]
    parts = [p.strip().strip(",") for p in segment.split(",") if p.strip()]
    return parts[:2]


def write_brief_for_score(
    db: Session, risk_score: RiskScore
) -> tuple[str, list[str]]:
    """Public entry point called by the pipeline."""
    event: Event = risk_score.event
    supplier: Supplier = risk_score.supplier
    logger.info(
        "[ImpactAnalyst] Writing brief for %s / %s (score=%d)",
        supplier.name,
        event.headline[:60],
        risk_score.score,
    )
    return _research_and_write_brief(event, supplier, risk_score)
