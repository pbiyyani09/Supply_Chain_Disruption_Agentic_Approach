"""Arize Phoenix observability bootstrap (self-hosted, OpenTelemetry-based).

Design rationale (Phase 0):
  * **Opt-in & fail-safe** — everything is gated by ``PHOENIX_ENABLED``. When the
    flag is off (or the optional packages are missing), every function degrades
    to a zero-cost no-op so the pipeline never crashes for an observability
    reason — consistent with the project's "never crash" convention.
  * **Single bootstrap** — ``setup_observability()`` is idempotent and must run
    *before* the agent modules build their Gemini clients, so it is called at the
    very top of each entry point (``api/main.py``, ``dashboard/app.py``, and each
    agent's ``__main__``). With ``auto_instrument=True`` Phoenix discovers the
    installed ``openinference-instrumentation-*`` packages (google-genai now,
    langchain in Phase 5) and captures prompts, responses, latency, and the
    token counts that the agents previously discarded.
  * **Parent span** — ``pipeline_span()`` groups a whole scan run so every agent
    LLM call nests under one trace.
"""
from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Iterator

logger = logging.getLogger(__name__)

# Resolve the optional Phoenix dependency once. Absent package → tracing simply
# stays off (and tests can patch this symbol without Phoenix installed).
try:  # pragma: no cover - import availability depends on the environment
    from phoenix.otel import register as _register
except Exception:  # pragma: no cover
    _register = None

_STATE: dict[str, object] = {"provider": None, "configured": False}


def _enabled() -> bool:
    """Return True when Phoenix tracing is switched on via ``PHOENIX_ENABLED``."""
    return os.getenv("PHOENIX_ENABLED", "false").lower() in {"1", "true", "yes"}


class _NoOpTracer:
    """Stand-in tracer used when Phoenix is disabled or unavailable."""

    def start_as_current_span(self, *_args: object, **_kwargs: object):
        """Return a context manager that does nothing."""
        return contextlib.nullcontext()


def setup_observability() -> None:
    """Initialise Phoenix tracing once, if enabled. Safe to call repeatedly.

    No-ops when ``PHOENIX_ENABLED`` is unset/false or when the optional
    ``arize-phoenix-otel`` / OpenInference packages are not installed. Any error
    during setup is logged and swallowed so application start is never blocked.
    """
    if _STATE["configured"] or not _enabled():
        return
    _STATE["configured"] = True  # set first so a failed import never retries in a hot loop
    if _register is None:
        logger.warning("[Observability] arize-phoenix-otel not installed — continuing without tracing")
        return
    try:
        endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT") or None
        provider = _register(
            project_name=os.getenv("PHOENIX_PROJECT_NAME", "chainwatch"),
            endpoint=endpoint,
            auto_instrument=True,
            batch=True,
        )
        _STATE["provider"] = provider
        logger.info("[Observability] Phoenix tracing enabled (endpoint=%s)", endpoint or "default")
    except Exception as exc:  # pragma: no cover - depends on network/collector
        logger.warning("[Observability] Phoenix setup failed (%s) — continuing without tracing", exc)


def get_tracer():
    """Return an OpenTelemetry tracer, or a no-op tracer when disabled.

    Returns:
        A real tracer from the registered provider when Phoenix is active,
        otherwise a :class:`_NoOpTracer`.
    """
    provider = _STATE["provider"]
    if provider is not None:
        return provider.get_tracer("chainwatch")
    return _NoOpTracer()


@contextlib.contextmanager
def pipeline_span(industry: str) -> Iterator[None]:
    """Group a full pipeline scan under one parent span.

    Args:
        industry: The industry the scan is running for (recorded as a span
            attribute for filtering in the Phoenix UI).

    Yields:
        None. Acts as a transparent passthrough when tracing is disabled or if
        starting the span fails — tracing must never break the run.
    """
    try:
        span_cm = get_tracer().start_as_current_span(
            "pipeline.run",
            attributes={"openinference.span.kind": "CHAIN", "industry": industry},
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[Observability] could not start pipeline span (%s)", exc)
        yield
        return
    with span_cm:
        yield
