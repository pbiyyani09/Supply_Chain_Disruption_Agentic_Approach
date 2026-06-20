"""Typed output contracts for every Gemini agent (output guardrail layer).

Design rationale (Phase 0):
  * **Single Responsibility** — this module owns *only* the data contracts that
    cross the LLM boundary, decoupling prompt shape from agent logic.
  * **Fail-safe coercion** — Gemini structured output (`response_schema=`) returns
    a validated object on `response.parsed`; when that is unavailable (older SDK
    paths, mocked tests, or grounding responses) we fall back to parsing
    `response.text`. Either way the value is validated by Pydantic *before* it
    reaches downstream code, so numeric bounds (probability ∈ [0, 1], risk
    score ∈ [1, 10]) and category enums can never silently leak a bad value.
  * **Resilience over strictness** — categorical/numeric fields are *coerced*
    (lower-cased, clamped, defaulted) rather than rejected, honouring the
    project's "never crash the pipeline" convention while still guaranteeing a
    well-formed shape.

These models intentionally mirror the JSON described in ``prompts/*.txt``.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ── Allowed categorical values (kept in sync with prompts/classify_event.txt) ──
EventCategory = Literal["weather", "geopolitical", "logistics", "labor", "cyber"]
SeverityHint = Literal["low", "medium", "high"]
Confidence = Literal["high", "medium", "low"]
Horizon = Literal["15d", "30d", "3m", "6m", "1y", "2y"]
OverallTrend = Literal["escalating", "stable", "improving"]
ImpactSeverity = Literal["critical", "high", "medium", "low"]

_VALID_CATEGORIES = {"weather", "geopolitical", "logistics", "labor", "cyber"}
_VALID_SEVERITIES = {"low", "medium", "high"}


# ── Agent 1: Signal Monitor ───────────────────────────────────────────────────
class EventClassification(BaseModel):
    """Classification verdict for a single news headline.

    Mirrors the JSON schema in ``prompts/classify_event.txt``.
    """

    category: str = "logistics"
    affected_countries: list[str] = Field(default_factory=list)
    severity_hint: str = "medium"
    is_supply_chain_relevant: bool = False
    brief_reason: str = ""

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category(cls, v: Any) -> str:
        """Lower-case and default unknown categories to ``logistics``."""
        s = str(v).lower().strip() if v is not None else "logistics"
        return s if s in _VALID_CATEGORIES else "logistics"

    @field_validator("severity_hint", mode="before")
    @classmethod
    def _coerce_severity(cls, v: Any) -> str:
        """Lower-case and default unknown severities to ``medium``."""
        s = str(v).lower().strip() if v is not None else "medium"
        return s if s in _VALID_SEVERITIES else "medium"


# ── Agent 2: Risk Scorer ──────────────────────────────────────────────────────
class SupplierRiskScore(BaseModel):
    """One supplier's risk verdict for a given event.

    Mirrors a single array element in ``prompts/score_risk.txt``.
    """

    supplier_name: str = ""
    score: int = Field(default=1, ge=1, le=10)
    impact_window: str = "unknown"
    affected_tiers: list[int] = Field(default_factory=list)
    reasoning: str = ""

    @field_validator("score", mode="before")
    @classmethod
    def _clamp_score(cls, v: Any) -> int:
        """Clamp the score into the valid 1–10 band instead of rejecting it."""
        try:
            return max(1, min(10, int(round(float(v)))))
        except (TypeError, ValueError):
            return 1


# ── Agent 5: Forecaster ───────────────────────────────────────────────────────
class ForecastHorizon(BaseModel):
    """Disruption probability for a single forecast horizon."""

    horizon: Horizon
    disruption_probability: float = Field(default=0.1, ge=0.0, le=1.0)
    confidence: str = "low"
    primary_drivers: list[str] = Field(default_factory=list)
    scenario: str = ""

    @field_validator("disruption_probability", mode="before")
    @classmethod
    def _clamp_probability(cls, v: Any) -> float:
        """Clamp probability into [0, 1] rather than rejecting an outlier."""
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.1

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v: Any) -> str:
        s = str(v).lower().strip() if v is not None else "low"
        return s if s in {"high", "medium", "low"} else "low"


class ForecastOutput(BaseModel):
    """Full multi-horizon forecast for one supplier.

    Mirrors the JSON schema in ``prompts/forecast.txt``.
    """

    supplier_name: str = ""
    forecasts: list[ForecastHorizon] = Field(default_factory=list)
    overall_trend: str = "stable"
    key_watchpoints: list[str] = Field(default_factory=list)

    @field_validator("overall_trend", mode="before")
    @classmethod
    def _coerce_trend(cls, v: Any) -> str:
        s = str(v).lower().strip() if v is not None else "stable"
        return s if s in {"escalating", "stable", "improving"} else "stable"


# ── What-if Scenario analysis ─────────────────────────────────────────────────
class AffectedSupplier(BaseModel):
    """Impact detail for one supplier under a hypothetical scenario."""

    supplier_name: str = ""
    country_code: str = ""
    impact_severity: str = "low"
    estimated_duration: str = ""
    revenue_at_risk: str = ""
    score_uplift: int = 0
    mitigation_actions: list[str] = Field(default_factory=list)


class ScenarioOutput(BaseModel):
    """Structured impact report for a user-described disruption scenario.

    Mirrors the JSON schema in ``prompts/scenario.txt``.
    """

    scenario_summary: str = ""
    affected_suppliers: list[AffectedSupplier] = Field(default_factory=list)
    unaffected_suppliers: list[str] = Field(default_factory=list)
    total_supply_chain_impact: str = ""
    recommended_immediate_actions: list[str] = Field(default_factory=list)
    time_to_recovery: str = "unknown"
    secondary_risks: list[str] = Field(default_factory=list)


# ── Coercion helpers (used by every agent's retry loop) ───────────────────────
def parse_object[T: BaseModel](response: Any, model: type[T]) -> T:
    """Validate a Gemini response into a single ``model`` instance.

    Prefers the SDK's server-validated ``response.parsed``; falls back to
    parsing ``response.text`` as JSON. Raises if neither yields valid data
    (the caller's retry/fallback loop handles that).

    Args:
        response: A ``google.genai`` ``GenerateContentResponse`` (or test double
            exposing ``.parsed`` / ``.text``).
        model: The Pydantic model class to validate into.

    Returns:
        A validated instance of ``model``.

    Raises:
        ValueError | pydantic.ValidationError | json.JSONDecodeError: when the
            response cannot be coerced into ``model``.
    """
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, model):
        return parsed
    text = getattr(response, "text", None)
    if not text:
        raise ValueError(f"Empty response text for {model.__name__}")
    data = json.loads(text)
    if isinstance(data, dict):
        return model.model_validate(data)
    raise ValueError(f"Expected a JSON object for {model.__name__}, got {type(data).__name__}")


def parse_list[T: BaseModel](response: Any, model: type[T]) -> list[T]:
    """Validate a Gemini response into a list of ``model`` instances.

    Handles three shapes: a server-validated ``list`` on ``response.parsed``, a
    raw JSON array in ``response.text``, or a JSON object wrapping a single array
    value (a shape Gemini occasionally returns).

    Args:
        response: A ``google.genai`` response (or test double).
        model: The Pydantic model class for each element.

    Returns:
        A list of validated ``model`` instances (possibly empty).
    """
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, list) and all(isinstance(p, model) for p in parsed):
        return parsed
    text = getattr(response, "text", None)
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])
    if not isinstance(data, list):
        return []
    return [model.model_validate(item) for item in data]
