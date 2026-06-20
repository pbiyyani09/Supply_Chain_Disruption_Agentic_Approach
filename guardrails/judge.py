"""Second-opinion faithfulness judge (self-hosted Gemma via Ollama).

Design rationale (Phase 4):
  * **Cross-model check** — a *different*, cheaper model (Gemma, local) audits the
    Gemini-written brief for claims unsupported by the provided context. Using a
    different family avoids the self-preference bias of same-model judging.
  * **Cost-gated** — gated by ``JUDGE_ENABLED`` and intended to run only on
    HIGH-value outputs (the impact brief), never on every classification.
  * **Fail-open** — on any error (no Ollama, parse failure) the verdict defaults
    to ``PASS`` so the guardrail never blocks the pipeline; it only *adds* a check
    when available.
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def judge_enabled() -> bool:
    """Return True when the Gemma faithfulness judge is switched on."""
    return os.getenv("JUDGE_ENABLED", "false").lower() in {"1", "true", "yes"}


def check_faithfulness(text: str, contexts: list[str]) -> dict:
    """Judge whether ``text`` is grounded in ``contexts`` using local Gemma.

    Args:
        text: The generated output to audit (e.g. an impact brief).
        contexts: Supporting context strings the output should be grounded in.

    Returns:
        ``{"verdict": "PASS"|"FLAG", "reason": str, "unsupported_claims": [...]}``.
        Defaults to PASS when disabled or on any error (fail-open).
    """
    if not judge_enabled() or not text or not contexts:
        return {"verdict": "PASS", "reason": "judge disabled or no context", "unsupported_claims": []}

    context_block = "\n---\n".join(c for c in contexts if c)
    try:
        from ollama import chat

        resp = chat(
            model=os.getenv("GEMMA_MODEL", "gemma3:4b"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a faithfulness auditor. Decide whether every factual claim in "
                        "BRIEF is supported by CONTEXT. Reply ONLY with JSON: "
                        '{"verdict": "PASS"|"FLAG", "reason": "...", "unsupported_claims": ["..."]}. '
                        "Use FLAG only for clearly unsupported or invented facts."
                    ),
                },
                {"role": "user", "content": f"CONTEXT:\n{context_block}\n\nBRIEF:\n{text}"},
            ],
            options={"temperature": 0},
        )
        verdict = json.loads(resp["message"]["content"])
        if verdict.get("verdict") not in {"PASS", "FLAG"}:
            verdict["verdict"] = "PASS"
        verdict.setdefault("reason", "")
        verdict.setdefault("unsupported_claims", [])
        return verdict
    except Exception as exc:  # pragma: no cover - needs a running Ollama
        logger.warning("[Judge] faithfulness check failed (%s) — defaulting to PASS", exc)
        return {"verdict": "PASS", "reason": f"judge error: {exc}", "unsupported_claims": []}
