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
import time
from pathlib import Path

from google.genai import types
from sqlalchemy.orm import Session

from data.tavily_research import event_context_search
from data.tavily_research import is_enabled as tavily_enabled
from db.models import Event, RiskScore, Supplier
from guardrails.injection import guard_scraped_text
from guardrails.judge import check_faithfulness, judge_enabled
from providers import get_gemini_client, get_model_name
from rag.retrieval import format_context, index_text, retrieve_best

logger = logging.getLogger(__name__)

_BRIEF_PROMPT = (Path(__file__).parent.parent / "prompts" / "write_brief.txt").read_text()

_client = get_gemini_client()
_MODEL = get_model_name()


def _research_and_write_brief(
    event: Event, supplier: Supplier, risk_score: RiskScore
) -> tuple[str, list[str]]:
    """Research the event with Gemini + Google Search grounding and write the brief.

    Args:
        event: The HIGH-severity event to brief on.
        supplier: The affected supplier.
        risk_score: The risk score record (score, impact window, reasoning).

    Returns:
        A ``(brief_text, alternatives_list)`` tuple. Falls back to a plain,
        non-researched brief if Gemini fails after retries.
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

    # Ground in institutional memory: similar past briefs/events (no-op if RAG off).
    prior_block = format_context(
        retrieve_best(f"{event.headline} {event.category}", kinds=("briefs", "events"), top_k=3)
    )
    if prior_block:
        user_prompt += f"\n\nSIMILAR PAST DISRUPTIONS (institutional memory — for context):\n{prior_block}"

    # Augment grounding with Tavily snippets (guarded against prompt injection),
    # alongside the native Google Search grounding configured below.
    if tavily_enabled():
        lines = []
        for hit in event_context_search(event.headline):
            safe = guard_scraped_text(hit.get("content", ""))
            if safe:
                lines.append(f"- {safe[:300]} ({hit.get('url', '')})")
        if lines:
            user_prompt += (
                "\n\nSUPPLEMENTARY WEB CONTEXT (Tavily — you may cite these; never invent statistics):\n"
                + "\n".join(lines)
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
    brief, alternatives = _research_and_write_brief(event, supplier, risk_score)

    # Second-opinion faithfulness check (local Gemma). Regenerate once if the
    # brief is judged to contain claims unsupported by the known context.
    if judge_enabled():
        contexts = [event.headline, event.brief_reason or "", risk_score.reasoning or ""]
        verdict = check_faithfulness(brief, contexts)
        if verdict.get("verdict") == "FLAG":
            logger.warning(
                "[ImpactAnalyst] brief flagged unfaithful (%s) — regenerating once",
                verdict.get("reason", ""),
            )
            brief, alternatives = _research_and_write_brief(event, supplier, risk_score)

    # Persist the brief into institutional memory for future retrieval.
    index_text("briefs", risk_score.id, brief)
    return brief, alternatives
