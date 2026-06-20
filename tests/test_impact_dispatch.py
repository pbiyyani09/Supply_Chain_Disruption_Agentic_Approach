"""Regression test for the critical detached-ORM fix in the impact_dispatch node.

The risk scorer detaches RiskScore objects (expunge_all); the orchestration node
must re-attach them by id before accessing the lazy ``event``/``supplier``
relationships, or the whole HIGH-risk path raises DetachedInstanceError.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db.database as dbmod
import orchestration.graph as g
from db import crud
from db.models import Base


def test_impact_dispatch_reattaches_detached_scores(monkeypatch):
    # Shared in-memory DB (StaticPool keeps one connection across sessions).
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)
    monkeypatch.setattr(dbmod, "SessionLocal", test_session)

    # Seed a supplier, an event, and a HIGH-risk score.
    seed = test_session()
    sup = crud.upsert_supplier(
        seed,
        {"name": "TaiwanSemi", "country_code": "TW", "product_category": "semiconductors", "tier": 1},
    )
    ev = crud.create_event(
        seed,
        {
            "source": "gdelt",
            "headline": "Red Sea attack disrupts shipping",
            "url": "https://example.com/rs",
            "category": "geopolitical",
            "affected_countries": ["EG"],
            "severity_hint": "high",
            "is_supply_chain_relevant": True,
            "brief_reason": "Red Sea disruption",
        },
    )
    rs = crud.create_risk_score(
        seed,
        {
            "event_id": ev.id,
            "supplier_id": sup.id,
            "score": 9,
            "impact_window": "72h",
            "affected_tiers": [1],
            "reasoning": "direct exposure",
        },
    )
    # Simulate run_risk_scorer: detach then close the producing session.
    seed.expunge_all()
    seed.close()

    accessed = {"event": False, "supplier": False}

    def fake_brief(_db, risk_score):
        accessed["event"] = bool(risk_score.event.headline)  # raises if detached
        return ("brief text", ["Eastern Europe"])

    def fake_dispatch(_db, risk_score, _brief, _alts):
        accessed["supplier"] = bool(risk_score.supplier.name)  # raises if detached
        return object()  # truthy → counts as dispatched

    monkeypatch.setattr("agents.impact_analyst.write_brief_for_score", fake_brief)
    monkeypatch.setattr("agents.alert_dispatcher.dispatch_alert", fake_dispatch)

    out = g._impact_dispatch_node({"high_scores": [rs]})

    assert out["dispatched"] == 1
    assert accessed["event"] is True
    assert accessed["supplier"] is True
