"""Unit tests for the risk scoring agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

MOCK_SCORE_RESPONSE = json.dumps([
    {
        "supplier_name": "TaiwanSemi Corp",
        "score": 9,
        "impact_window": "72h",
        "affected_tiers": [1, 2],
        "reasoning": (
            "TaiwanSemi is directly in the affected region. "
            "A semiconductor supply stoppage would cascade to Tier 2 assembly partners within 72 hours."
        ),
    }
])


@patch("agents.risk_scorer._client")
def test_score_batch_returns_scores(mock_client):
    mock_response = MagicMock()
    mock_response.text = MOCK_SCORE_RESPONSE
    mock_client.models.generate_content.return_value = mock_response

    from agents.risk_scorer import _score_batch

    mock_event = MagicMock()
    mock_event.headline = "China exports face 14-day delay as Asia-Europe routes rerouted"
    mock_event.category = "logistics"
    mock_event.affected_countries = ["CN", "TW", "KR"]
    mock_event.severity_hint = "high"
    mock_event.brief_reason = "14-day shipping delay expected."

    mock_supplier = MagicMock()
    mock_supplier.name = "TaiwanSemi Corp"
    mock_supplier.country_code = "TW"
    mock_supplier.region = "Hsinchu"
    mock_supplier.product_category = "semiconductors"
    mock_supplier.tier = 1

    results = _score_batch(mock_event, [mock_supplier])

    assert len(results) == 1
    assert results[0]["score"] == 9
    assert results[0]["impact_window"] == "72h"
    assert 1 in results[0]["affected_tiers"]


@patch("agents.risk_scorer._client")
def test_score_batch_handles_error(mock_client):
    mock_client.models.generate_content.side_effect = Exception("timeout")

    from agents.risk_scorer import _score_batch

    mock_event = MagicMock()
    mock_event.headline = "Test event"
    mock_event.category = "logistics"
    mock_event.affected_countries = ["CN"]
    mock_event.severity_hint = "medium"
    mock_event.brief_reason = ""

    mock_supplier = MagicMock()
    mock_supplier.name = "Test Supplier"
    mock_supplier.country_code = "CN"
    mock_supplier.region = None
    mock_supplier.product_category = "electronics"
    mock_supplier.tier = 1

    results = _score_batch(mock_event, [mock_supplier])
    assert results == []
