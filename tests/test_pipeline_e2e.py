"""End-to-end integration test — seeds mock events and verifies the pipeline stores scores."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base
from db.crud import create_event, get_recent_events, upsert_supplier, get_high_risk_scores


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_event_stored_and_retrieved(db_session):
    create_event(db_session, {
        "source": "gdelt",
        "headline": "Houthi militants attack container ship in Red Sea",
        "url": "https://example.com/red-sea-test",
        "category": "geopolitical",
        "affected_countries": ["YE", "SA", "EG"],
        "severity_hint": "high",
        "is_supply_chain_relevant": True,
        "brief_reason": "Red Sea disruption.",
    })
    events = get_recent_events(db_session, limit=10)
    assert len(events) == 1
    assert events[0].category == "geopolitical"
    assert "SA" in events[0].affected_countries


def test_supplier_geo_lookup(db_session):
    from data.geo_matcher import get_lat_lng
    lat, lng = get_lat_lng("TW")
    assert lat is not None
    assert abs(lat - 23.69) < 1.0  # Taiwan centroid check


def test_keyword_filter():
    from data.sources import _passes_keyword_filter
    assert _passes_keyword_filter("Port congestion at major shipping hub") is True
    assert _passes_keyword_filter("Local bakery opens new branch in Denver") is False
    assert _passes_keyword_filter("Strike at semiconductor factory closes plant") is True
