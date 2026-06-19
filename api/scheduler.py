"""APScheduler wiring — fires the full pipeline every N minutes.

Pipeline order (per tick):
  1. Signal Monitor  — fetch news events (GDELT, NewsAPI, NOAA, USGS, ACLED)
  2. Economic Signals — refresh FRED / World Bank indicators
  3. Weather Scan    — Open-Meteo alerts for supplier locations
  4. Risk Scorer     — Gemini score per (event, supplier) pair
  5. Impact Analyst  — Gemini brief for HIGH-risk scores
  6. Alert Dispatcher — Slack/email with cooldown dedup
  7. Forecaster      — 6-horizon probability forecasts per supplier

Economic signals and forecasts also have their own lighter-weight cron jobs
so they can run more frequently than the full news scan.
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))
ECON_INTERVAL = int(os.getenv("ECON_INTERVAL_HOURS", "6"))   # economic signals refresh
FORECAST_INTERVAL = int(os.getenv("FORECAST_INTERVAL_HOURS", "4"))  # re-forecast


def _run_pipeline() -> None:
    """Execute the full 7-agent pipeline in sequence."""
    from agents.alert_dispatcher import dispatch_alert
    from agents.forecaster import run_forecaster
    from agents.impact_analyst import write_brief_for_score
    from agents.risk_scorer import run_risk_scorer
    from agents.signal_monitor import run_signal_monitor
    from data.economic_signals import fetch_economic_signals
    from data.weather import fetch_weather_for_suppliers
    from db.crud import create_event, event_exists, get_suppliers, upsert_economic_signal
    from db.database import SessionLocal

    industry = os.getenv("DEFAULT_INDUSTRY", "electronics")
    logger.info("[Pipeline] Starting tick (industry=%s)...", industry)

    # 1. Signal Monitor
    run_signal_monitor(industry=industry)

    # 2. Economic Signals
    _refresh_economic_signals(industry)

    # 3. Weather scan for supplier locations
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

    # 5+6. Impact Analyst + Alert Dispatcher
    if high_scores:
        db = SessionLocal()
        try:
            for rs in high_scores:
                brief, alternatives = write_brief_for_score(db, rs)
                dispatch_alert(db, rs, brief, alternatives)
        finally:
            db.close()

    # 7. Forecaster
    run_forecaster(industry=industry)

    logger.info(
        "[Pipeline] Tick complete — %d scores, %d HIGH alerts",
        len(scores),
        len(high_scores),
    )


def _refresh_economic_signals(industry: str = "electronics") -> None:
    """Refresh economic indicators without running the full news scan."""
    from data.economic_signals import fetch_economic_signals
    from db.crud import upsert_economic_signal
    from db.database import SessionLocal

    try:
        rows = fetch_economic_signals(industry=industry)
        if rows:
            db = SessionLocal()
            try:
                for row in rows:
                    upsert_economic_signal(db, row)
            finally:
                db.close()
        logger.info("[EconSignals] Refreshed %d indicators", len(rows))
    except Exception as exc:
        logger.warning("[EconSignals] Refresh failed: %s", exc)


def _refresh_forecasts() -> None:
    """Re-run forecasts without re-fetching news events."""
    from agents.forecaster import run_forecaster
    industry = os.getenv("DEFAULT_INDUSTRY", "electronics")
    try:
        saved = run_forecaster(industry=industry)
        logger.info("[Forecaster] Cron refresh — %d rows saved", saved)
    except Exception as exc:
        logger.warning("[Forecaster] Refresh failed: %s", exc)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")

    # Full pipeline every SCAN_INTERVAL minutes (default 30)
    scheduler.add_job(
        _run_pipeline,
        "interval",
        minutes=SCAN_INTERVAL,
        id="pipeline",
        replace_existing=True,
    )

    # Economic signals refresh every ECON_INTERVAL hours (default 6)
    scheduler.add_job(
        _refresh_economic_signals,
        "interval",
        hours=ECON_INTERVAL,
        id="economic_signals",
        replace_existing=True,
    )

    # Forecast refresh every FORECAST_INTERVAL hours (default 4)
    scheduler.add_job(
        _refresh_forecasts,
        "interval",
        hours=FORECAST_INTERVAL,
        id="forecasts",
        replace_existing=True,
    )

    return scheduler
