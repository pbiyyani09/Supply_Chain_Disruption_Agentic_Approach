"""Unit tests for the Gemini event classifier."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

MOCK_HIGH_RESPONSE = """{
    "category": "logistics",
    "affected_countries": ["TW", "CN"],
    "severity_hint": "high",
    "is_supply_chain_relevant": true,
    "brief_reason": "Taiwan semiconductor production disrupted."
}"""

MOCK_IRRELEVANT_RESPONSE = """{
    "category": "logistics",
    "affected_countries": [],
    "severity_hint": "low",
    "is_supply_chain_relevant": false,
    "brief_reason": ""
}"""


@patch("agents.signal_monitor._client")
def test_classify_supply_chain_event(mock_client):
    mock_response = MagicMock()
    mock_response.text = MOCK_HIGH_RESPONSE
    mock_client.models.generate_content.return_value = mock_response

    from agents.signal_monitor import _classify_event
    result = _classify_event("Taiwan semiconductor factory reports power outage")

    assert result["is_supply_chain_relevant"] is True
    assert result["category"] == "logistics"
    assert "TW" in result["affected_countries"]
    assert result["severity_hint"] == "high"


@patch("agents.signal_monitor._client")
def test_classify_irrelevant_event(mock_client):
    mock_response = MagicMock()
    mock_response.text = MOCK_IRRELEVANT_RESPONSE
    mock_client.models.generate_content.return_value = mock_response

    from agents.signal_monitor import _classify_event
    result = _classify_event("Local city council approves new park in Denver")

    assert result["is_supply_chain_relevant"] is False
    assert result["affected_countries"] == []


@patch("agents.signal_monitor._client")
def test_classify_handles_gemini_error(mock_client):
    mock_client.models.generate_content.side_effect = Exception("API quota exceeded")

    from agents.signal_monitor import _classify_event
    result = _classify_event("Some headline")

    # Should return safe defaults, not raise
    assert result["is_supply_chain_relevant"] is False
    assert isinstance(result["affected_countries"], list)
