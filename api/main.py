"""FastAPI application — REST backend for ChainWatch dashboard and integrations."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import alerts, events, risk_scores, suppliers
from api.scheduler import create_scheduler
from db.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ChainWatch API", version="1.0.0")

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
def trigger_manual_scan():
    """Manually trigger a pipeline run without waiting for the cron."""
    from agents.alert_dispatcher import dispatch_alert
    from agents.impact_analyst import write_brief_for_score
    from agents.risk_scorer import run_risk_scorer
    from agents.signal_monitor import run_signal_monitor
    from db.database import SessionLocal
    import os

    run_signal_monitor()
    scores = run_risk_scorer()
    threshold = int(os.getenv("HIGH_RISK_THRESHOLD", "7"))
    high_scores = [s for s in scores if s.score >= threshold]

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

    return {
        "new_events": "check /events",
        "scores_created": len(scores),
        "high_alerts_dispatched": dispatched,
    }


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
