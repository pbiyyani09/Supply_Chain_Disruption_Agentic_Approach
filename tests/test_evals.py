"""Unit tests for the Ragas harness (build_samples only — no heavy ragas import)."""
from __future__ import annotations

import json

import pytest

from evals.run_ragas import build_samples


def test_golden_set_loads_and_validates():
    samples = build_samples()
    assert len(samples) >= 4
    for s in samples:
        assert set(s.keys()) == {"user_input", "retrieved_contexts", "response", "reference"}
        assert isinstance(s["retrieved_contexts"], list)


def test_missing_field_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"user_input": "q", "response": "r"}]))  # missing fields
    with pytest.raises(ValueError, match="missing fields"):
        build_samples(bad)
