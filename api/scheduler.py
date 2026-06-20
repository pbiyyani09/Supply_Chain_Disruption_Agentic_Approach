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
    """Execute the full pipeline via the LangGraph orchestration (scheduled tick)."""
    from orchestration.graph import run_pipeline

    industry = os.getenv("DEFAULT_INDUSTRY", "electronics")
    try:
        run_pipeline(industry=industry)
    except Exception as exc:
        logger.warning("[Pipeline] scheduled tick failed: %s", exc)


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
