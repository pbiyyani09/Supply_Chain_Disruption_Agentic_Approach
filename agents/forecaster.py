"""Agent 5 — Forecaster.

Generates multi-horizon disruption probability forecasts (15d / 30d / 3m / 6m / 1y / 2y)
for each supplier using:
  - Recent events from the DB (last 30 days)
  - Economic indicator signals (WTI, copper, food index, etc.)
  - Seasonal risk calendar for the supplier's country
  - Historical risk score pattern for that supplier
  - Industry-specific risk context

All inference is done by Gemini. Results are stored in the `forecasts` table.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from google.genai import types
from sqlalchemy.orm import Session

from data.seasonal_calendar import get_risk_context_for_country
from db.crud import (
    get_latest_signals,
    get_recent_events,
    get_risk_scores_for_supplier,
    get_suppliers,
    upsert_forecast,
)
from db.database import SessionLocal
from db.models import EconomicSignal, Supplier
from providers import get_gemini_client, get_model_name
from schemas import ForecastOutput, ScenarioOutput, parse_object

logger = logging.getLogger(__name__)

_FORECAST_PROMPT = (Path(__file__).parent.parent / "prompts" / "forecast.txt").read_text()
_SCENARIO_PROMPT = (Path(__file__).parent.parent / "prompts" / "scenario.txt").read_text()

_client = get_gemini_client()
_MODEL = get_model_name()

HORIZONS = ["15d", "30d", "3m", "6m", "1y", "2y"]


def _format_signals(signals: list[EconomicSignal]) -> str:
    if not signals:
        return "No economic indicator data available."
    lines = []
    for s in signals:
        chg = f"{s.change_pct_30d:+.1f}%" if s.change_pct_30d is not None else "n/a"
        trend = "RISING" if (s.change_pct_30d or 0) > 5 else ("FALLING" if (s.change_pct_30d or 0) < -5 else "stable")
        lines.append(f"  {s.indicator}: {s.value:.2f} (Δ30d: {chg} — {trend}) [{s.source}]")
    return "\n".join(lines)


def _format_events(events: list) -> str:
    if not events:
        return "No recent supply chain events on record."
    return "\n".join(
        f"  [{e.category.upper()}] {e.headline[:120]} ({e.severity_hint} severity, countries: {e.affected_countries})"
        for e in events[:15]
    )


def _format_history(scores: list) -> str:
    if not scores:
        return "No historical risk scores for this supplier."
    return "\n".join(
        f"  Score {rs.score}/10 on {str(rs.scored_at)[:10]} — {rs.reasoning[:80]}"
        for rs in scores[:5]
    )


def _forecast_supplier(
    supplier: Supplier,
    events: list,
    signals: list[EconomicSignal],
    industry: str,
) -> list[dict]:
    """Call Gemini to generate forecasts for all 6 horizons for a single supplier."""
    seasonal = get_risk_context_for_country(supplier.country_code, industry)

    db2 = SessionLocal()
    try:
        history = get_risk_scores_for_supplier(db2, supplier.id, days=30)
    finally:
        db2.close()

    # Filter events relevant to this supplier's country
    country_events = [
        e for e in events
        if not e.affected_countries or supplier.country_code in (e.affected_countries or [])
    ]
    # Include global high-severity events even if not country-specific
    global_events = [e for e in events if e.severity_hint == "high" and e not in country_events]
    relevant_events = (country_events + global_events)[:15]

    supplier_profile = {
        "name": supplier.name,
        "country": supplier.country_code,
        "region": supplier.region or "",
        "product_category": supplier.product_category,
        "tier": supplier.tier,
    }

    prompt = (
        f"{_FORECAST_PROMPT}\n\n"
        f"SUPPLIER:\n{json.dumps(supplier_profile, indent=2)}\n\n"
        f"INDUSTRY: {industry}\n\n"
        f"RECENT SUPPLY CHAIN EVENTS (last 30 days affecting supplier region):\n"
        f"{_format_events(relevant_events)}\n\n"
        f"ECONOMIC INDICATOR SIGNALS:\n{_format_signals(signals)}\n\n"
        f"SEASONAL RISK CONTEXT:\n{seasonal}\n\n"
        f"HISTORICAL RISK SCORE PATTERN:\n{_format_history(history)}"
    )

    for attempt in range(3):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ForecastOutput,
                    temperature=0.2,
                    max_output_tokens=4096,
                ),
            )
            parsed = parse_object(response, ForecastOutput)

            rows = []
            for fc in parsed.forecasts:
                if fc.horizon not in HORIZONS:
                    continue
                rows.append({
                    "supplier_id": supplier.id,
                    "industry": industry,
                    "horizon": fc.horizon,
                    "disruption_probability": fc.disruption_probability,
                    "confidence": fc.confidence,
                    "drivers": fc.primary_drivers,
                    "scenario": fc.scenario,
                    "overall_trend": parsed.overall_trend,
                })
            return rows

        except Exception as exc:
            wait = 2 ** attempt * 3
            logger.warning("[Forecaster] attempt %d failed for %s: %s — retry in %ds",
                           attempt + 1, supplier.name, exc, wait)
            if attempt < 2:
                time.sleep(wait)

    return []


def run_forecaster(industry: str = "electronics") -> int:
    """Generate forecasts for all suppliers. Called after risk_scorer in the pipeline."""
    db: Session = SessionLocal()
    saved = 0
    try:
        suppliers = get_suppliers(db)
        events = get_recent_events(db, limit=100)
        signals = get_latest_signals(db)
        db.expunge_all()
    finally:
        db.close()

    if not suppliers:
        logger.info("[Forecaster] No suppliers — skipping")
        return 0

    for supplier in suppliers:
        logger.info("[Forecaster] Generating forecasts for %s (%s)...", supplier.name, supplier.country_code)
        rows = _forecast_supplier(supplier, events, signals, industry)

        if not rows:
            continue

        db2: Session = SessionLocal()
        try:
            for row in rows:
                upsert_forecast(db2, row)
                saved += 1
                logger.info(
                    "[Forecaster] %s / %s → P=%.0f%% (%s confidence)",
                    supplier.name, row["horizon"],
                    row["disruption_probability"] * 100,
                    row["confidence"],
                )
        finally:
            db2.close()

        time.sleep(1)  # gentle pacing between suppliers

    logger.info("[Forecaster] Done — %d forecast rows saved", saved)
    return saved


def run_scenario_analysis(scenario_text: str, suppliers: list[dict]) -> dict:
    """What-if scenario builder — analyze impact of a user-described disruption on all suppliers."""
    prompt = (
        f"{_SCENARIO_PROMPT}\n\n"
        f"USER SCENARIO:\n{scenario_text}\n\n"
        f"SUPPLIER LIST:\n{json.dumps(suppliers, indent=2)}"
    )

    for attempt in range(3):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ScenarioOutput,
                    temperature=0.3,
                    max_output_tokens=8192,
                ),
            )
            return parse_object(response, ScenarioOutput).model_dump()
        except Exception as exc:
            wait = 2 ** attempt * 3
            logger.warning("[Scenario] attempt %d failed: %s — retry in %ds", attempt + 1, exc, wait)
            if attempt < 2:
                time.sleep(wait)

    return {
        "scenario_summary": "Analysis failed — please retry",
        "affected_suppliers": [],
        "unaffected_suppliers": [s.get("name", "") for s in suppliers],
        "total_supply_chain_impact": "Unable to complete analysis at this time.",
        "recommended_immediate_actions": [],
        "time_to_recovery": "unknown",
        "secondary_risks": [],
    }


if __name__ == "__main__":
    from observability import setup_observability

    setup_observability()
    logging.basicConfig(level=logging.INFO)
    run_forecaster()
