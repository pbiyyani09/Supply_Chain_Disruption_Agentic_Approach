"""Tests for the LangGraph pipeline routing (node functions stubbed)."""
from __future__ import annotations

import orchestration.graph as g


def _stub_nodes(monkeypatch, *, high: bool):
    monkeypatch.setattr(g, "_signal_node", lambda s: {"new_events": 1})
    monkeypatch.setattr(g, "_econ_weather_node", lambda s: {"econ_updated": 2, "weather_checked": 3})
    monkeypatch.setattr(
        g, "_score_node",
        lambda s: {"scores_created": 5, "high_scores": [object()] if high else []},
    )
    monkeypatch.setattr(g, "_forecast_node", lambda s: {"forecasts_saved": 6})
    flag = {"impact_called": False}

    def _impact(_s):
        flag["impact_called"] = True
        return {"dispatched": 4}

    monkeypatch.setattr(g, "_impact_dispatch_node", _impact)
    return flag


def test_high_risk_routes_through_impact(monkeypatch):
    flag = _stub_nodes(monkeypatch, high=True)
    out = g.build_graph().invoke({"industry": "electronics", "high_scores": []})
    assert flag["impact_called"] is True
    assert out["dispatched"] == 4
    assert out["forecasts_saved"] == 6


def test_no_high_risk_skips_impact(monkeypatch):
    flag = _stub_nodes(monkeypatch, high=False)
    out = g.build_graph().invoke({"industry": "electronics", "high_scores": []})
    assert flag["impact_called"] is False
    assert out.get("dispatched", 0) == 0
    assert out["forecasts_saved"] == 6


def test_run_pipeline_returns_summary_shape(monkeypatch):
    _stub_nodes(monkeypatch, high=True)
    g._graph = None  # force rebuild with stubbed nodes
    result = g.run_pipeline(industry="electronics")
    g._graph = None  # reset cache for other tests
    assert set(result.keys()) == {
        "new_events",
        "economic_signals_updated",
        "weather_events_checked",
        "scores_created",
        "high_alerts_dispatched",
        "forecasts_saved",
    }
    assert result["high_alerts_dispatched"] == 4
    assert result["economic_signals_updated"] == 2
