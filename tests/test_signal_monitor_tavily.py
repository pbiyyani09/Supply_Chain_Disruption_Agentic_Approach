"""Tests for Signal Monitor full-text (Tavily) integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

MOCK_RESPONSE = """{
    "category": "logistics",
    "affected_countries": ["TW"],
    "severity_hint": "high",
    "is_supply_chain_relevant": true,
    "brief_reason": "Port strike disrupts electronics exports."
}"""


@patch("agents.signal_monitor._client")
def test_classify_includes_body_excerpt(mock_client):
    resp = MagicMock()
    resp.text = MOCK_RESPONSE
    mock_client.models.generate_content.return_value = resp

    from agents.signal_monitor import _classify_event

    _classify_event("Port strike", body="FULL ARTICLE: workers walk out at Kaohsiung terminal")

    _, kwargs = mock_client.models.generate_content.call_args
    prompt = kwargs["contents"]
    assert "Article excerpt:\n" in prompt  # the dynamically appended section
    assert "FULL ARTICLE" in prompt


@patch("agents.signal_monitor._client")
def test_classify_without_body_unchanged(mock_client):
    resp = MagicMock()
    resp.text = MOCK_RESPONSE
    mock_client.models.generate_content.return_value = resp

    from agents.signal_monitor import _classify_event

    # Extraction-failure / disabled path: no body → still classifies fine.
    result = _classify_event("Port strike")

    _, kwargs = mock_client.models.generate_content.call_args
    assert "Article excerpt:\n" not in kwargs["contents"]  # no appended body section
    assert result["is_supply_chain_relevant"] is True
