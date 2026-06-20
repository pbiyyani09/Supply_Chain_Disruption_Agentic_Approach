"""Client factories for external model providers (Gemini, and later Gemma/Tavily).

Design rationale (Phase 0):
  * **Factory pattern** — five agent modules previously each called
    ``genai.Client(api_key=...)`` at import time. Centralising construction here
    removes that duplication (DRY) and gives a *single* place to configure,
    cache, or instrument the client (Dependency Inversion: agents depend on this
    small factory, not on the SDK constructor directly).
  * **Cached singleton** — ``functools.lru_cache`` returns one client per
    process, matching the previous module-level behaviour while remaining
    trivially overridable in tests.

Agents keep a module-level ``_client = get_gemini_client()`` so existing tests
that patch ``agents.<name>._client`` continue to work unchanged.
"""
from __future__ import annotations

import functools
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


@functools.lru_cache(maxsize=1)
def get_gemini_client() -> genai.Client:
    """Return a process-wide cached Google AI Studio (Gemini) client.

    Reads ``GOOGLE_API_KEY`` from the environment. The result is cached so every
    agent shares one client (and one set of OpenInference instrumentation hooks).

    Returns:
        A configured ``google.genai.Client`` instance.
    """
    return genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def get_model_name() -> str:
    """Return the configured Gemini model id, defaulting to ``gemini-2.0-flash``.

    Returns:
        The value of ``GEMINI_MODEL`` or the default fallback.
    """
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
