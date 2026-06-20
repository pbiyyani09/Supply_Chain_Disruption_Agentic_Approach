"""Unit tests for the structured-output guardrail (schemas.py)."""
from __future__ import annotations

import json

from schemas import (
    EventClassification,
    ForecastHorizon,
    SupplierRiskScore,
    parse_list,
    parse_object,
)


class _Resp:
    """Minimal stand-in for a google-genai response."""

    def __init__(self, text: str = "", parsed: object = None):
        self.text = text
        self.parsed = parsed


def test_event_classification_coerces_bad_enums():
    ev = EventClassification(category="ASIA", severity_hint="catastrophic")
    assert ev.category == "logistics"      # unknown category → default
    assert ev.severity_hint == "medium"    # unknown severity → default


def test_risk_score_clamped_into_range():
    assert SupplierRiskScore(score=12).score == 10
    assert SupplierRiskScore(score=0).score == 1
    assert SupplierRiskScore(score="8").score == 8


def test_forecast_probability_clamped():
    assert ForecastHorizon(horizon="15d", disruption_probability=1.5).disruption_probability == 1.0
    assert ForecastHorizon(horizon="30d", disruption_probability=-0.2).disruption_probability == 0.0


def test_parse_object_prefers_real_parsed_instance():
    instance = EventClassification(is_supply_chain_relevant=True)
    out = parse_object(_Resp(parsed=instance), EventClassification)
    assert out is instance


def test_parse_object_falls_back_to_text():
    payload = {
        "category": "geopolitical",
        "affected_countries": ["EG"],
        "severity_hint": "high",
        "is_supply_chain_relevant": True,
        "brief_reason": "Suez disruption",
    }
    out = parse_object(_Resp(text=json.dumps(payload), parsed=object()), EventClassification)
    assert out.category == "geopolitical"
    assert out.affected_countries == ["EG"]


def test_parse_list_from_text_array():
    payload = [{"supplier_name": "A", "score": 9, "impact_window": "72h", "affected_tiers": [1]}]
    out = parse_list(_Resp(text=json.dumps(payload)), SupplierRiskScore)
    assert len(out) == 1
    assert out[0].score == 9


def test_parse_list_unwraps_object_with_array():
    payload = {"results": [{"supplier_name": "B", "score": 5}]}
    out = parse_list(_Resp(text=json.dumps(payload)), SupplierRiskScore)
    assert len(out) == 1
    assert out[0].supplier_name == "B"
