"""APScheduler wiring — fires the full pipeline every N minutes."""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))


def _run_pipeline() -> None:
    """Execute the full 4-agent pipeline in sequence."""
    from agents.signal_monitor import run_signal_monitor
    from agents.risk_scorer import run_risk_scorer
    from agents.alert_dispatcher import dispatch_alert
    from agents.impact_analyst import write_brief_for_score
    from db.database import SessionLocal

    logger.info("[Pipeline] Starting tick...")
    run_signal_monitor()
    scores = run_risk_scorer()

    threshold = int(os.getenv("HIGH_RISK_THRESHOLD", "7"))
    high_scores = [s for s in scores if s.score >= threshold]

    if high_scores:
        db = SessionLocal()
        try:
            for rs in high_scores:
                brief, alternatives = write_brief_for_score(db, rs)
                dispatch_alert(db, rs, brief, alternatives)
        finally:
            db.close()

    logger.info(
        "[Pipeline] Tick complete — %d scores, %d HIGH alerts",
        len(scores),
        len(high_scores),
    )


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _run_pipeline,
        "interval",
        minutes=SCAN_INTERVAL,
        id="pipeline",
        replace_existing=True,
    )
    return scheduler
