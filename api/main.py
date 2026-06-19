"""FastAPI application — REST backend for ChainWatch dashboard and integrations."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import alerts, economic_signals, events, forecasts, maritime, risk_scores, seasonal, suppliers
from api.scheduler import create_scheduler
from db.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ChainWatch API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(suppliers.router)
app.include_router(events.router)
app.include_router(alerts.router)
app.include_router(risk_scores.router)
app.include_router(economic_signals.router)
app.include_router(forecasts.router)
app.include_router(maritime.router)
app.include_router(seasonal.router)

_scheduler = None


@app.on_event("startup")
def startup() -> None:
    global _scheduler
    init_db()
    logger.info("[API] Database initialized")
    _scheduler = create_scheduler()
    _scheduler.start()
    logger.info("[API] Scheduler started — pipeline runs every 30 min")


@app.on_event("shutdown")
def shutdown() -> None:
    if _scheduler:
        _scheduler.shutdown()


@app.post("/scan", tags=["pipeline"])
def trigger_manual_scan(industry: str = "electronics"):
    """Manually trigger a full pipeline run.

    Pipeline:
      1. Signal Monitor  — fetch events (GDELT + NewsAPI + NOAA + USGS + ACLED)
      2. Economic Signals — fetch FRED / World Bank indicators
      3. Weather Scan     — check Open-Meteo for supplier location extremes
      4. Risk Scorer      — geo-match and Gemini-score events per supplier
      5. Impact Analyst   — write Gemini brief for HIGH-risk scores
      6. Alert Dispatcher — send Slack/email alerts with cooldown dedup
      7. Forecaster       — generate 6-horizon probability forecasts per supplier
    """
    import os
    from agents.alert_dispatcher import dispatch_alert
    from agents.forecaster import run_forecaster
    from agents.impact_analyst import write_brief_for_score
    from agents.risk_scorer import run_risk_scorer
    from agents.signal_monitor import run_signal_monitor
    from data.economic_signals import fetch_economic_signals
    from data.weather import fetch_weather_for_suppliers
    from db.crud import create_event, event_exists, get_suppliers, upsert_economic_signal
    from db.database import SessionLocal

    # 1. Signal Monitor (GDELT + NewsAPI + NOAA + USGS + ACLED)
    new_events = run_signal_monitor(industry=industry)

    # 2. Economic signals (FRED / World Bank)
    econ_rows = fetch_economic_signals(industry=industry)
    if econ_rows:
        db = SessionLocal()
        try:
            for row in econ_rows:
                upsert_economic_signal(db, row)
        finally:
            db.close()

    # 3. Weather scan for all supplier locations → inject as events
    db = SessionLocal()
    try:
        supplier_list = get_suppliers(db)
        supplier_dicts = [
            {"name": s.name, "country_code": s.country_code, "lat": s.lat, "lng": s.lng}
            for s in supplier_list
        ]
    finally:
        db.close()

    if supplier_dicts:
        weather_events = fetch_weather_for_suppliers(supplier_dicts)
        db = SessionLocal()
        try:
            for we in weather_events:
                if we.get("url") and not event_exists(db, we["url"]):
                    from agents.signal_monitor import _classify_event
                    cls = _classify_event(we["headline"])
                    if cls.get("is_supply_chain_relevant", True):
                        create_event(db, {
                            "source": we["source"],
                            "headline": we["headline"],
                            "url": we["url"],
                            "category": cls.get("category", "weather"),
                            "affected_countries": cls.get("affected_countries", []),
                            "severity_hint": cls.get("severity_hint", "medium"),
                            "is_supply_chain_relevant": True,
                            "brief_reason": cls.get("brief_reason", ""),
                            "published_at": we.get("published_at"),
                        })
        finally:
            db.close()

    # 4. Risk Scorer
    scores = run_risk_scorer(industry=industry)
    threshold = int(os.getenv("HIGH_RISK_THRESHOLD", "7"))
    high_scores = [s for s in scores if s.score >= threshold]

    # 5+6. Impact Analyst + Alert Dispatcher for HIGH scores
    dispatched = 0
    if high_scores:
        db = SessionLocal()
        try:
            for rs in high_scores:
                brief, alternatives = write_brief_for_score(db, rs)
                alert = dispatch_alert(db, rs, brief, alternatives)
                if alert:
                    dispatched += 1
        finally:
            db.close()

    # 7. Forecaster — generate 6-horizon forecasts for all suppliers
    forecasts_saved = run_forecaster(industry=industry)

    return {
        "new_events": new_events,
        "economic_signals_updated": len(econ_rows),
        "weather_events_checked": len(supplier_dicts),
        "scores_created": len(scores),
        "high_alerts_dispatched": dispatched,
        "forecasts_saved": forecasts_saved,
    }


@app.post("/scan/economics", tags=["pipeline"])
def refresh_economic_signals(industry: str = "electronics"):
    """Refresh only economic indicator signals (FRED / World Bank). Runs fast, no LLM calls."""
    from data.economic_signals import fetch_economic_signals
    from db.crud import upsert_economic_signal
    from db.database import SessionLocal

    rows = fetch_economic_signals(industry=industry)
    if rows:
        db = SessionLocal()
        try:
            for row in rows:
                upsert_economic_signal(db, row)
        finally:
            db.close()
    return {"updated": len(rows)}


@app.post("/scan/forecast", tags=["pipeline"])
def refresh_forecasts(industry: str = "electronics"):
    """Regenerate 6-horizon forecasts for all suppliers without re-fetching events."""
    from agents.forecaster import run_forecaster
    saved = run_forecaster(industry=industry)
    return {"forecasts_saved": saved}


@app.post("/scenario", tags=["analysis"])
def run_scenario(scenario: str, industry: str = "electronics"):
    """Run a what-if scenario analysis. scenario = free text disruption description."""
    from agents.forecaster import run_scenario_analysis
    from db.crud import get_suppliers
    from db.database import SessionLocal

    db = SessionLocal()
    try:
        supplier_list = get_suppliers(db)
        supplier_dicts = [
            {
                "name": s.name,
                "country_code": s.country_code,
                "product_category": s.product_category,
                "tier": s.tier,
            }
            for s in supplier_list
        ]
    finally:
        db.close()

    return run_scenario_analysis(scenario, supplier_dicts)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "version": "2.0.0"}
