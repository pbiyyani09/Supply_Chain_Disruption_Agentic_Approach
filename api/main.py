"""FastAPI application — REST backend for ChainWatch dashboard and integrations."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import alerts, economic_signals, events, forecasts, maritime, risk_scores, seasonal, suppliers
from api.scheduler import create_scheduler
from db.database import init_db
from observability import setup_observability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ChainWatch API", version="3.0.0")

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
    """Initialise observability + database and start the APScheduler pipeline."""
    global _scheduler
    setup_observability()
    init_db()
    logger.info("[API] Database initialized")
    _scheduler = create_scheduler()
    _scheduler.start()
    logger.info("[API] Scheduler started — pipeline runs every 30 min")


@app.on_event("shutdown")
def shutdown() -> None:
    """Gracefully stop the background scheduler on app shutdown."""
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
    from orchestration.graph import run_pipeline

    return run_pipeline(industry=industry)


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
    """Liveness probe returning service status and version."""
    return {"status": "ok", "version": "3.0.0"}
