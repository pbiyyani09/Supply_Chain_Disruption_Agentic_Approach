"""The ChainWatch pipeline as a LangGraph ``StateGraph``.

Flow::

    START → signal → econ_weather → score ─┬─(HIGH)→ impact_dispatch → forecast → END
                                           └─(none)───────────────────→ forecast → END

Each node wraps existing agent logic (which already retries Gemini calls
internally); the graph adds a conditional HIGH-risk branch, node-level retries
for transient infra errors, and one nested trace per run. Both the scheduled
tick and the manual ``POST /scan`` call :func:`run_pipeline`, removing the
previous duplicated orchestration in two places (DRY).
"""
from __future__ import annotations

import logging
import os
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from observability import pipeline_span

logger = logging.getLogger(__name__)

_NETWORK_RETRY = RetryPolicy(max_attempts=2)


class PipelineState(TypedDict, total=False):
    """Shared state threaded through the pipeline graph."""

    industry: str
    new_events: int
    econ_updated: int
    weather_checked: int
    scores_created: int
    high_scores: list
    dispatched: int
    forecasts_saved: int


def _signal_node(state: PipelineState) -> dict:
    """Fetch + classify + store new events (Signal Monitor)."""
    from agents.signal_monitor import run_signal_monitor

    return {"new_events": run_signal_monitor(industry=state["industry"])}


def _econ_weather_node(state: PipelineState) -> dict:
    """Refresh economic indicators and inject weather events."""
    from agents.signal_monitor import _classify_event
    from data.economic_signals import fetch_economic_signals
    from data.weather import fetch_weather_for_suppliers
    from db.crud import create_event, event_exists, get_suppliers, upsert_economic_signal
    from db.database import SessionLocal

    industry = state["industry"]

    econ_rows = fetch_economic_signals(industry=industry)
    if econ_rows:
        db = SessionLocal()
        try:
            for row in econ_rows:
                upsert_economic_signal(db, row)
        finally:
            db.close()

    db = SessionLocal()
    try:
        supplier_dicts = [
            {"name": s.name, "country_code": s.country_code, "lat": s.lat, "lng": s.lng}
            for s in get_suppliers(db)
        ]
    finally:
        db.close()

    if supplier_dicts:
        weather_events = fetch_weather_for_suppliers(supplier_dicts)
        db = SessionLocal()
        try:
            for we in weather_events:
                if we.get("url") and not event_exists(db, we["url"]):
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

    return {"econ_updated": len(econ_rows), "weather_checked": len(supplier_dicts)}


def _score_node(state: PipelineState) -> dict:
    """Score events against suppliers and select HIGH-risk scores (Risk Scorer)."""
    from agents.risk_scorer import run_risk_scorer

    scores = run_risk_scorer(industry=state["industry"])
    threshold = int(os.getenv("HIGH_RISK_THRESHOLD", "7"))
    high = [s for s in scores if s.score >= threshold]
    return {"scores_created": len(scores), "high_scores": high}


def _route_after_score(state: PipelineState) -> str:
    """Conditional edge: branch to impact analysis only when HIGH scores exist."""
    return "impact_dispatch" if state.get("high_scores") else "forecast"


def _impact_dispatch_node(state: PipelineState) -> dict:
    """Write briefs and dispatch alerts for HIGH-risk scores.

    The scores in ``state['high_scores']`` were detached from their session by
    the scorer (``expunge_all``), so each is re-loaded by id into this node's own
    session before its lazy ``event``/``supplier`` relationships are accessed —
    otherwise a ``DetachedInstanceError`` would crash the whole HIGH-risk path.
    A per-score try/except keeps one supplier's failure from dropping the rest.
    """
    from agents.alert_dispatcher import dispatch_alert
    from agents.impact_analyst import write_brief_for_score
    from db.database import SessionLocal
    from db.models import RiskScore

    dispatched = 0
    db = SessionLocal()
    try:
        for detached in state.get("high_scores", []):
            try:
                rs = db.get(RiskScore, detached.id)  # re-attach to this session
                if rs is None:
                    continue
                brief, alternatives = write_brief_for_score(db, rs)
                if dispatch_alert(db, rs, brief, alternatives):
                    dispatched += 1
            except Exception as exc:
                logger.warning("[Pipeline] impact/dispatch failed for a score: %s", exc)
    finally:
        db.close()
    return {"dispatched": dispatched}


def _forecast_node(state: PipelineState) -> dict:
    """Generate 6-horizon forecasts for all suppliers (Forecaster)."""
    from agents.forecaster import run_forecaster

    return {"forecasts_saved": run_forecaster(industry=state["industry"])}


def build_graph():
    """Construct and compile the pipeline StateGraph.

    Returns:
        A compiled LangGraph runnable.
    """
    builder = StateGraph(PipelineState)
    builder.add_node("signal", _signal_node, retry_policy=_NETWORK_RETRY)
    builder.add_node("econ_weather", _econ_weather_node, retry_policy=_NETWORK_RETRY)
    builder.add_node("score", _score_node, retry_policy=_NETWORK_RETRY)
    builder.add_node("impact_dispatch", _impact_dispatch_node, retry_policy=_NETWORK_RETRY)
    builder.add_node("forecast", _forecast_node, retry_policy=_NETWORK_RETRY)

    builder.add_edge(START, "signal")
    builder.add_edge("signal", "econ_weather")
    builder.add_edge("econ_weather", "score")
    builder.add_conditional_edges(
        "score",
        _route_after_score,
        {"impact_dispatch": "impact_dispatch", "forecast": "forecast"},
    )
    builder.add_edge("impact_dispatch", "forecast")
    builder.add_edge("forecast", END)
    return builder.compile()


_graph = None


def get_graph():
    """Return the compiled pipeline graph (built once and cached)."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_pipeline(industry: str = "electronics") -> dict:
    """Run the full pipeline graph under one trace and return summary counts.

    Args:
        industry: The industry to run the scan for.

    Returns:
        The same summary dict shape the ``POST /scan`` endpoint returns.
    """
    logger.info("[Pipeline] Starting graph run (industry=%s)...", industry)
    initial: PipelineState = {"industry": industry, "high_scores": []}
    final: dict = {}
    try:
        with pipeline_span(industry):
            final = get_graph().invoke(initial)
    except Exception as exc:
        # Never let an orchestration error crash the caller — return partial counts.
        logger.error("[Pipeline] graph run failed: %s", exc)
    logger.info(
        "[Pipeline] Complete — %d scores, %d HIGH alerts dispatched",
        final.get("scores_created", 0),
        final.get("dispatched", 0),
    )
    return {
        "new_events": final.get("new_events", 0),
        "economic_signals_updated": final.get("econ_updated", 0),
        "weather_events_checked": final.get("weather_checked", 0),
        "scores_created": final.get("scores_created", 0),
        "high_alerts_dispatched": final.get("dispatched", 0),
        "forecasts_saved": final.get("forecasts_saved", 0),
    }
