from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.crud import get_high_risk_scores, get_risk_scores_for_supplier
from db.database import get_db
from db.models import RiskScore

router = APIRouter(prefix="/risk-scores", tags=["risk-scores"])


class RiskScoreOut(BaseModel):
    id: str
    event_id: str
    supplier_id: str
    supplier_name: str | None = None
    score: int
    impact_window: str
    affected_tiers: list
    reasoning: str
    scored_at: datetime | None

    model_config = {"from_attributes": True}


def _enrich(rs: RiskScore) -> dict:
    return {
        "id": rs.id,
        "event_id": rs.event_id,
        "supplier_id": rs.supplier_id,
        "supplier_name": rs.supplier.name if rs.supplier else None,
        "score": rs.score,
        "impact_window": rs.impact_window,
        "affected_tiers": rs.affected_tiers or [],
        "reasoning": rs.reasoning,
        "scored_at": rs.scored_at,
    }


@router.get("/", response_model=list[RiskScoreOut])
def list_risk_scores(
    threshold: int = Query(0, ge=0, le=10),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Return risk scores, optionally filtered by minimum score threshold."""
    scores = get_high_risk_scores(db, threshold=threshold, limit=limit)
    return [_enrich(rs) for rs in scores]


@router.get("/supplier/{supplier_id}", response_model=list[RiskScoreOut])
def scores_for_supplier(
    supplier_id: str,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    scores = get_risk_scores_for_supplier(db, supplier_id=supplier_id, days=days)
    return [_enrich(rs) for rs in scores]
