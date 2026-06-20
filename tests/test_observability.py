"""Unit tests for the Phoenix observability bootstrap."""
from __future__ import annotations

from unittest.mock import MagicMock

import observability


def _reset_state() -> None:
    observability._STATE["provider"] = None
    observability._STATE["configured"] = False


def test_disabled_is_noop(monkeypatch):
    monkeypatch.delenv("PHOENIX_ENABLED", raising=False)
    _reset_state()

    observability.setup_observability()  # should do nothing

    tracer = observability.get_tracer()
    assert isinstance(tracer, observability._NoOpTracer)
    # pipeline_span must be a usable, transparent context manager when disabled
    with observability.pipeline_span("electronics"):
        pass


def test_enabled_calls_register_once(monkeypatch):
    monkeypatch.setenv("PHOENIX_ENABLED", "true")
    _reset_state()

    mock_register = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(observability, "_register", mock_register)

    observability.setup_observability()
    observability.setup_observability()  # idempotent — must not register twice

    assert mock_register.call_count == 1
    _, kwargs = mock_register.call_args
    assert kwargs.get("auto_instrument") is True

    _reset_state()


def test_enabled_without_package_is_safe(monkeypatch):
    monkeypatch.setenv("PHOENIX_ENABLED", "true")
    _reset_state()
    monkeypatch.setattr(observability, "_register", None)

    observability.setup_observability()  # must not raise

    assert isinstance(observability.get_tracer(), observability._NoOpTracer)
    _reset_state()
